#!/usr/bin/env python3
"""
BMW SP-Daten 0PA/0DA to .BIN Converter
========================================
Converts BMW INPA / WinKFP SP-Daten flash files (.0PA, .0DA) into flat
binary views for offline inspection and comparison.  A successful conversion
does not by itself prove controller compatibility, checksums, signatures, or a
safe programming/recovery path.

Supports:
  - Siemens MS42 (MDS42) — 512 KB full / 32 KB calibration at 0x48000
  - Siemens MS43 (MDS43) — 512 KB full / 64 KB calibration
  - Siemens MS45.0 (MDS450) — explicit MPC or external-flash views
  - Siemens MS45.1 (MDS451) — explicit MPC or external-flash views
  - Bosch ME7.2 (ME72)
  - Bosch GS8.60.x EGS (GD86xx)
  - Any BMW Austausch-Datei with Intel HEX payload

Per-OSID calibration sizes:
  MS42 factory OSIDs             → 32 KB cal at 0x48000
  MS42 0110SA                    → reject (damaged 0110CA read/copy lineage)
  MS43 430037..430070           → 64 KB cal at 0x70000
  MS45 0044560                  → 128 KB output window at 0x40000

Handles BMW/Siemens type 0x10 boundary data and empty marker records.

Still to prove before any production-grade claim:
  - WinKFP directive checks ($CHECKSUMME/$CRC16/$SIGNATUR and Modulo36)
  - Per-controller checksum/signature and programming/recovery behavior
  - Corpus-backed address profiles for every advertised ECU family

File format:
  .0PA = "Austausch-Datei Programm" (code/program flash partition)
  .0DA = "Austausch-Datei Daten"    (calibration/data flash partition)
  Both contain a text header with BMW metadata followed by Intel HEX records.

Usage:
  # Convert a single file
  python bmw_0pa_0da_to_bin.py path/to/file.0DA

  # Convert all 0PA/0DA in a folder
  python bmw_0pa_0da_to_bin.py path/to/folder/

  # Combine source-defined external bytes into an offline analysis view
  python bmw_0pa_0da_to_bin.py --combine path/to/file.0PA path/to/file.0DA \
      --source-region external

  # Scan C:\\EC-APPS for a specific ECU group and convert all
  python bmw_0pa_0da_to_bin.py --scan MDS43

  # Output to a specific directory
  python bmw_0pa_0da_to_bin.py path/to/file.0DA -o output_folder/

  # Show info only (no conversion)
  python bmw_0pa_0da_to_bin.py --info path/to/file.0DA

Adapted from:  scan_gs8604_egs.py, find_austausch_files.py parsing logic
Author:        KingAI / Copilot
"""

import os
import sys
import re
import argparse
import hashlib
import string
import platform
from pathlib import Path
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "1.1.0"

# Known output-view sizes.  These are converter layouts, not proof that a
# produced file is a complete or flash-ready image for a particular module.
ECU_FLASH_SIZES = {
    "MDS42":  512 * 1024,   # MS42 = 512 KB
    "MDS43":  512 * 1024,   # MS43 = 512 KB
    "MDS450": 1024 * 1024,  # MS45.0 = 1 MB
    "MDS451": 1024 * 1024,  # MS45.1 = 1 MB
    "ME72":   1024 * 1024,  # ME7.2 = 1 MB (varies)
    "GD8600": 256 * 1024,   # EGS GS8.60.0
    "GD8604": 512 * 1024,   # EGS GS8.60.4; program to 0x6FFFF, cal to 0x7FFFF
}

# Calibration section sizes and offsets for known ECU + OSID combos
# Key = (ecu_type, osid) or (ecu_type, None) as fallback
ECU_CAL_INFO = {
    # MS42 uses a 32 KiB calibration at 0x48000.  Factory C6/C7/CA 0DA
    # address ranges and the working full/partial XDFs agree.  The previous
    # 0x70000/64 KiB and 0x78000 entries were displaced MS43-style assumptions.
    ("MDS42", "0110AD"): {"cal_offset": 0x48000, "cal_size": 32 * 1024},
    ("MDS42", "011025"): {"cal_offset": 0x48000, "cal_size": 32 * 1024},
    ("MDS42", "0110AB"): {"cal_offset": 0x48000, "cal_size": 32 * 1024},
    ("MDS42", "0110C6"): {"cal_offset": 0x48000, "cal_size": 32 * 1024},
    ("MDS42", "0110C7"): {"cal_offset": 0x48000, "cal_size": 32 * 1024},
    ("MDS42", "0110CA"): {"cal_offset": 0x48000, "cal_size": 32 * 1024},
    ("MDS42", None):     {"cal_offset": None,    "cal_size": None},         # auto-detect from HEX
    # MS43 — OSID sets (most are 64 KB at 0x70000)
    ("MDS43", "430037"): {"cal_offset": 0x70000, "cal_size": 64 * 1024},
    ("MDS43", "430055"): {"cal_offset": 0x70000, "cal_size": 64 * 1024},
    ("MDS43", "430056"): {"cal_offset": 0x70000, "cal_size": 64 * 1024},
    ("MDS43", "430064"): {"cal_offset": 0x70000, "cal_size": 64 * 1024},
    ("MDS43", "430066"): {"cal_offset": 0x70000, "cal_size": 64 * 1024},
    ("MDS43", "430069"): {"cal_offset": 0x70000, "cal_size": 64 * 1024},
    ("MDS43", "430070"): {"cal_offset": 0x70000, "cal_size": 64 * 1024},
    ("MDS43", None):     {"cal_offset": 0x70000, "cal_size": 64 * 1024},   # default
    # MS45.0 — 128 KB at 0x40000  (CPU 0x02040000-0x0205FFFF → flash 0x40000)
    ("MDS450", None):    {"cal_offset": 0x40000, "cal_size": 128 * 1024},
    # MS45.1 — 128 KB at 0x40000
    ("MDS451", None):    {"cal_offset": 0x40000, "cal_size": 128 * 1024},
}

# CPU-to-flash address translation for each ECU.
# Each entry is a list of (hex_addr_start, hex_addr_end, flash_offset) tuples.
# When a HEX record address falls in [hex_addr_start, hex_addr_end],
# it maps to flash offset: (addr - hex_addr_start) + flash_offset.
# Checked in order; first match wins.  None = identity (no translation).
ECU_ADDR_MAP = {
    "MDS42": None,  # Flash-relative addresses, no translation needed
    "MDS43": [
        # C167 maps flash at 0x080000.  0PA uses CPU addresses (0x80000+).
        # 0DA uses flash-relative addresses (0x00000+).
        # Both patterns need to work → two ranges:
        (0x080000, 0x0FFFFF, 0x000000),  # CPU addr → flash offset 0x00000+
        (0x000000, 0x07FFFF, 0x000000),  # Flash-relative → identity
    ],
    "MDS450": [
        # Independent source domains selected explicitly by --source-region:
        #   MPC internal:   0x00000000..0x0006FFFF
        #   External flash: 0x02000000..0x020FFFFF
        # Rebasing both into one output is lossy and is rejected by default.
        (0x02000000, 0x020FFFFF, 0x000000),
        (0x00000000, 0x000FFFFF, 0x000000),
    ],
    "MDS451": [
        (0x02000000, 0x020FFFFF, 0x000000),
        (0x00000000, 0x000FFFFF, 0x000000),
    ],
}

# Austausch-Datei markers
MARKER_DATEN    = b"Austausch-Datei    Daten"
MARKER_PROGRAMM = b"Austausch-Datei    Programm"
MARKER_BROAD    = b"Austausch-Datei"

# Flash file extensions
FLASH_EXTS = {".0da", ".0pa", ".0di", ".0pi"}

# Directories to skip when scanning
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".vs", ".idea", "dist", "build", "__MACOSX",
    "System Volume Information", "$Recycle.Bin", "Recovery",
    "Windows", "ProgramData",
}

MAX_FILE_SIZE = 64 * 1024 * 1024  # 64 MB

MAPPED_OVERLAP_POLICIES = ("error", "legacy-last-wins")
SOURCE_REGIONS = ("all", "mpc", "external")
MS45_ECUS = frozenset({"MDS450", "MDS451"})
MS45_MPC_SIZE = 0x70000


def _canonical_ecu_type(value: Optional[str]) -> Optional[str]:
    """Normalize accepted ECU aliases without treating plain MS45 as specific."""
    if value is None:
        return None
    normalized = value.strip().upper()
    aliases = {
        "MS45.0": "MDS450",
        "MS450": "MDS450",
        "MS45.1": "MDS451",
        "MS451": "MDS451",
    }
    if normalized == "MS45":
        raise ValueError("MS45 is ambiguous; choose MDS450/MS45.0 or MDS451/MS45.1")
    return aliases.get(normalized, normalized)


def _normalize_mapping_options(
    ecu_type: Optional[str], mapped_overlap_policy: str, source_region: str
) -> Tuple[Optional[str], str, str]:
    ecu = _canonical_ecu_type(ecu_type)
    policy = mapped_overlap_policy.strip().lower()
    if policy not in MAPPED_OVERLAP_POLICIES:
        choices = ", ".join(MAPPED_OVERLAP_POLICIES)
        raise ValueError(
            f"Unknown mapped-overlap policy '{mapped_overlap_policy}' (expected {choices})"
        )
    region = source_region.strip().lower()
    if region not in SOURCE_REGIONS:
        choices = ", ".join(SOURCE_REGIONS)
        raise ValueError(f"Unknown source region '{source_region}' (expected {choices})")
    if region != "all" and ecu not in MS45_ECUS:
        raise ValueError(
            f"source-region '{region}' is only defined for MDS450/MDS451; "
            f"resolved ECU is {ecu or 'unknown'}"
        )
    return ecu, policy, region


def _source_region_contains(ecu_type: Optional[str], region: str, address: int) -> bool:
    if region == "all":
        return True
    if ecu_type not in MS45_ECUS:
        return False
    if region == "mpc":
        return 0 <= address < MS45_MPC_SIZE
    return 0x02000000 <= address < 0x02100000


def _ms45_source_spaces(records: List[Tuple[int, bytes, int]]) -> List[str]:
    spaces = set()
    for start, payload, _line_num in records:
        end = start + len(payload)
        if start < MS45_MPC_SIZE and end > 0:
            spaces.add("mpc")
        if start < 0x02100000 and end > 0x02000000:
            spaces.add("external")
    return sorted(spaces)


# ---------------------------------------------------------------------------
# Safe string handling
# ---------------------------------------------------------------------------
def _decode_safe(data: bytes) -> str:
    """Decode bytes to string, trying utf-8 then latin-1."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def _safe_print(s: str) -> str:
    """Strip non-ASCII chars so print() never chokes on cp1252 stdout."""
    return s.encode("ascii", errors="replace").decode("ascii")


def _extract_osid(header: Dict[str, Any]) -> Optional[str]:
    """
    Extract OSID from the header's ZL_Referenz or referenz_line.
    
    Common patterns:
      ZL_Referenz: 11101102C600       → OSID 0110C6
      ZL_Referenz: 11101100CA010000   → OSID 0110CA
      ZL_Referenz: 111430533703       → OSID 430037 (MS43)
      $REFERENZ 11101102C600 C        → same
    
    For MS42 the reference encodes the OSID reversed/embedded.  We look for
    known OSID patterns in both the reference and the file-path/filename.
    """
    known_osids = [
        # MS42 OSIDs
        "0110AD", "0110AB", "011025", "0110C6", "0110C7", "0110CA", "0110SA",
        # MS43 OSIDs  
        "430037", "430055", "430056", "430064", "430066", "430069", "430070",
        "43X001",
        # MS45 OSIDs
        "0044560",
    ]
    
    # Check referenz_line first 
    ref = header.get("referenz_line", "") or ""
    ref_val = header.get("fields", {}).get("ZL_Referenz", "") or ""
    ref_val2 = header.get("fields", {}).get("ZL_REFERENZ", "") or ""
    
    candidates = [ref, ref_val, ref_val2]
    
    for text in candidates:
        text_upper = text.upper().replace(" ", "")
        for osid in known_osids:
            if osid.upper() in text_upper:
                return osid
        # MS42 ZL_Referenz contains an extra zero between the first four OSID
        # characters and its suffix: 11101100C6010000 -> 0110C6.
        match = re.search(r"111(0110)0([A-Z0-9]{2})01", text_upper)
        if match:
            decoded = match.group(1) + match.group(2)
            if decoded in known_osids:
                return decoded
    
    # Also check the Freigabenummer field (sometimes has OSID encoded)
    freigabe = header.get("fields", {}).get("ZL_Freigabenummer", "") or ""
    if freigabe:
        freigabe_upper = freigabe.upper().replace(" ", "").replace(":", "")
        for osid in known_osids:
            if osid.upper() in freigabe_upper:
                return osid
    
    return None


def _translate_addr(addr: int, addr_map: Optional[list]) -> Optional[int]:
    """
    Translate a HEX record address to a flash offset using the ECU address map.
    Returns the flash offset, or None if the address doesn't match any range.
    If addr_map is None, returns addr unchanged (identity mapping).
    """
    if addr_map is None:
        return addr
    for hex_start, hex_end, flash_offset in addr_map:
        if hex_start <= addr <= hex_end:
            return (addr - hex_start) + flash_offset
    return None  # Address not in any mapped range


def _align_cal_region(min_addr: int, max_addr: int) -> Tuple[int, int]:
    """
    Given raw HEX min/max addresses, compute an aligned calibration region.
    Aligns base down to 0x8000 (32 KB sector) boundary, size up to 
    nearest power-of-2 that is >= 8 KB.
    """
    SECTOR = 0x8000  # 32 KB sector alignment
    base = (min_addr // SECTOR) * SECTOR
    end = max_addr + 1
    raw_size = end - base
    
    # Round up to nearest power of 2 that is >= the raw size and >= 8KB
    size = max(8 * 1024, raw_size)
    # Find next power of 2
    p2 = 1
    while p2 < size:
        p2 <<= 1
    
    return base, p2


# ---------------------------------------------------------------------------
# Austausch-Datei header parser
# ---------------------------------------------------------------------------
def parse_austausch_header(data: bytes) -> Dict[str, Any]:
    """
    Find and parse the BMW DAMOS Austausch-Datei header in binary data.
    Returns dict with:
      - file_type: "Programm" or "Daten" or "Unknown"
      - fields: OrderedDict of header key-value pairs
      - referenz_line: the $REFERENZ line if found
      - hex_data_offset: byte offset where Intel HEX data begins
      - marker_offset: where the Austausch marker was found
    """
    result = {
        "file_type": "Unknown",
        "fields": OrderedDict(),
        "referenz_line": None,
        "hex_data_offset": None,
        "marker_offset": None,
    }

    # Find marker
    marker_offset = data.find(MARKER_PROGRAMM)
    if marker_offset >= 0:
        result["file_type"] = "Programm"
    else:
        marker_offset = data.find(MARKER_DATEN)
        if marker_offset >= 0:
            result["file_type"] = "Daten"
        else:
            marker_offset = data.find(MARKER_BROAD)
            if marker_offset >= 0:
                # Determine type from context
                context = _decode_safe(data[marker_offset:marker_offset + 80])
                if "Programm" in context:
                    result["file_type"] = "Programm"
                elif "Daten" in context:
                    result["file_type"] = "Daten"

    if marker_offset < 0:
        # No Austausch header — might be raw Intel HEX or S-record
        # Look for Intel HEX start directly
        hex_start = _find_intel_hex_start(data)
        if hex_start is not None:
            result["hex_data_offset"] = hex_start
        return result

    result["marker_offset"] = marker_offset

    # Parse backwards to find header start (;=== line)
    search_start = max(0, marker_offset - 500)
    header_start = data.rfind(b";===", search_start, marker_offset)
    if header_start == -1:
        header_start = marker_offset

    # Read up to 8KB of header
    header_chunk = data[header_start : header_start + 8192]
    text = _decode_safe(header_chunk)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # Parse header fields
    for line in lines:
        stripped = line.strip()

        # ;;Key: Value format
        m = re.match(r"^;;([A-Za-z0-9_\-]+):\s*(.*)", stripped)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            if val and val != "---":
                result["fields"][key] = val

        # $REFERENZ marks end of header
        if stripped.upper().startswith("$REFERENZ"):
            result["referenz_line"] = stripped
            # HEX data starts on the next line after $REFERENZ
            ref_offset_in_text = text.index(stripped)
            # Find the newline after $REFERENZ
            after_ref = text[ref_offset_in_text + len(stripped):]
            newline_pos = 0
            for ch in after_ref:
                newline_pos += 1
                if ch == '\n':
                    break
            result["hex_data_offset"] = header_start + ref_offset_in_text + len(stripped) + newline_pos
            break

    # If no $REFERENZ found, look for first Intel HEX line after header
    if result["hex_data_offset"] is None:
        hex_start = _find_intel_hex_start(data, start_from=marker_offset)
        if hex_start is not None:
            result["hex_data_offset"] = hex_start

    return result


def _find_intel_hex_start(data: bytes, start_from: int = 0) -> Optional[int]:
    """Find the byte offset of the first Intel HEX record in data."""
    # Search for lines starting with ':' followed by hex digits
    pos = start_from
    while pos < len(data) - 11:
        # Find next ':'
        colon = data.find(b":", pos)
        if colon == -1:
            break

        # Check if this looks like a valid Intel HEX record
        # :LLAAAATT[DD...]CC format — at least 11 chars (:BBAAAATTCC)
        try:
            # Check that following bytes are hex ASCII
            after = data[colon + 1 : colon + 11]
            if len(after) == 10 and all(
                c in b"0123456789ABCDEFabcdef" for c in after
            ):
                # Verify it's at the start of a line (preceded by \n, \r, or BOF)
                if colon == 0 or data[colon - 1] in (0x0A, 0x0D):
                    return colon
        except IndexError:
            pass

        pos = colon + 1

    return None


# ---------------------------------------------------------------------------
# Intel HEX to binary converter (the core logic)
# ---------------------------------------------------------------------------
def intel_hex_to_binary(
    data: bytes,
    start_offset: int = 0,
    fill_byte: int = 0xFF,
    force_size: Optional[int] = None,
    force_base: Optional[int] = None,
    addr_map: Optional[list] = None,
    ecu_type: Optional[str] = None,
    mapped_overlap_policy: str = "error",
    source_region: str = "all",
    include_defined_bytes: bool = False,
) -> Tuple[Optional[bytearray], Dict[str, Any]]:
    """
    Parse Intel HEX records from data starting at start_offset.
    Returns (binary_data, info_dict).

    binary_data is a bytearray starting at min_addr (or force_base),
    with gaps filled with fill_byte (0xFF = erased flash).

    addr_map: optional list of (hex_start, hex_end, flash_offset) tuples
    for CPU-to-flash address translation (see ECU_ADDR_MAP).

    MDS450/MDS451 program packages contain independent MPC-internal and
    external-flash source spaces.  The default policy refuses to collapse a
    mixed package.  Select ``source_region="mpc"`` or ``"external"`` for a
    lossless view.  ``mapped_overlap_policy="legacy-last-wins"`` is an
    explicit, reported compatibility mode for the historical lossy overlay.

    info_dict contains:
      - min_addr, max_addr: address range found in HEX records (after translation)
      - data_bytes: total number of data bytes decoded
      - record_count: total HEX records processed
      - eof_found: whether an EOF record was encountered
      - base_addr: the base address (min_addr or force_base)
      - unmapped_records: records with addresses outside all mapped ranges
      - errors/warnings: validation diagnostics
      - mapping collision counts and selected source-space provenance
    """
    info = {
        "min_addr": None,
        "max_addr": None,
        "data_bytes": 0,
        "raw_data_bytes": 0,
        "record_count": 0,
        "eof_found": False,
        "base_addr": 0,
        "unmapped_records": 0,
        "unmapped_bytes": 0,
        "source_region": source_region,
        "source_spaces": [],
        "mapping_policy": mapped_overlap_policy,
        "source_unique_bytes": 0,
        "source_identical_overlap_bytes": 0,
        "source_conflicting_overlap_bytes": 0,
        "mapped_unique_bytes": 0,
        "mapped_identical_alias_bytes": 0,
        "mapped_conflicting_alias_bytes": 0,
        "discarded_conflicting_bytes": 0,
        "lossy": False,
        "first_source_conflicts": [],
        "first_mapped_conflicts": [],
        "source_defined_output_bytes": 0,
        "fill_only_output_bytes": 0,
        "errors": [],
        "warnings": [],
    }

    try:
        ecu_type, policy, region = _normalize_mapping_options(
            ecu_type, mapped_overlap_policy, source_region
        )
    except ValueError as error:
        info["errors"].append(str(error))
        return None, info
    info["source_region"] = region
    info["mapping_policy"] = policy

    if not 0 <= fill_byte <= 0xFF:
        info["errors"].append("Fill byte must be in range 0x00..0xFF")
        return None, info
    if force_size is not None and force_size <= 0:
        info["errors"].append("Output size must be greater than zero")
        return None, info

    # Preserve raw source addresses until a source space has been selected.
    # Each record also retains its input line for useful collision diagnostics.
    records: List[Tuple[int, bytes, int]] = []
    source_values: Dict[int, int] = {}
    source_owners: Dict[int, int] = {}
    source_identical = 0
    source_conflicting = 0
    source_conflict_examples: List[Dict[str, Any]] = []
    # BMW SP-Daten files use BOTH type 02 (Extended Segment Address) and
    # type 04 (Extended Linear Address) records together.  Type 04 selects
    # the flash bank (e.g. 0x00000000 = program, 0x02000000 = cal/data)
    # and type 02 selects the 64 KB sector within that bank.  The full
    # address is:  extended_linear + extended_segment + record_address.
    extended_linear  = 0   # Upper 16 bits from type 04 records
    extended_segment = 0   # Segment base from type 02 records

    text = _decode_safe(data[start_offset:])
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    for line_num, line in enumerate(lines, 1):
        line = line.strip()

        # Skip empty lines and comment/header lines
        if not line:
            continue
        if not line.startswith(":"):
            # If we've already seen records and hit non-hex, might be EOF region
            if info["record_count"] > 0:
                continue
            else:
                continue

        try:
            if info["eof_found"]:
                raise ValueError("HEX record appears after EOF")
            if len(line) < 11:
                raise ValueError(f"record too short ({len(line)} characters)")

            # Parse Intel HEX fields
            byte_count = int(line[1:3], 16)
            address    = int(line[3:7], 16)
            rec_type   = int(line[7:9], 16)

            # Reject both truncation and trailing content.  Accepting a valid
            # prefix with junk after its checksum makes corrupted inputs look
            # successful and differs from WinKFP's exact record grammar.
            expected_len = 1 + 2 + 4 + 2 + byte_count * 2 + 2  # : LL AAAA TT DD..DD CC
            if len(line) != expected_len:
                raise ValueError(
                    f"record length mismatch (expected {expected_len}, got {len(line)})"
                )
            if any(character not in string.hexdigits for character in line[1:]):
                raise ValueError("record contains non-hexadecimal characters")

            record_bytes = bytes.fromhex(line[1:])
            if sum(record_bytes) & 0xFF:
                checksum_byte = record_bytes[-1]
                calc_sum = (-sum(record_bytes[:-1])) & 0xFF
                raise ValueError(
                    f"checksum mismatch (calc=0x{calc_sum:02X}, "
                    f"file=0x{checksum_byte:02X})"
                )

            # Extract data bytes
            data_hex = line[9 : 9 + byte_count * 2]
            record_data = bytes.fromhex(data_hex)

            expected_counts = {0x01: 0, 0x02: 2, 0x03: 4, 0x04: 2, 0x05: 4}
            if rec_type in expected_counts and byte_count != expected_counts[rec_type]:
                raise ValueError(
                    f"record type 0x{rec_type:02X} requires "
                    f"{expected_counts[rec_type]} data bytes, got {byte_count}"
                )
            if rec_type in (0x01, 0x02, 0x04) and address != 0:
                raise ValueError(
                    f"record type 0x{rec_type:02X} requires address 0x0000"
                )
            if rec_type not in (0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x10):
                raise ValueError(f"unknown record type 0x{rec_type:02X}")

            info["record_count"] += 1

            if rec_type in (0x00, 0x10):
                # Standard data or BMW/Siemens boundary data.  Empty 0x10
                # records are boundary markers and contain no source bytes.
                if not record_data:
                    continue
                full_addr = extended_linear + extended_segment + address
                records.append((full_addr, record_data, line_num))
                info["raw_data_bytes"] += byte_count
                for index, value in enumerate(record_data):
                    source_addr = full_addr + index
                    if source_addr in source_values:
                        if source_values[source_addr] == value:
                            source_identical += 1
                        else:
                            source_conflicting += 1
                            if len(source_conflict_examples) < 8:
                                source_conflict_examples.append(
                                    {
                                        "source_address": source_addr,
                                        "earlier_line": source_owners[source_addr],
                                        "later_line": line_num,
                                        "earlier_value": source_values[source_addr],
                                        "later_value": value,
                                    }
                                )
                    else:
                        source_values[source_addr] = value
                        source_owners[source_addr] = line_num

            elif rec_type == 0x01:
                # End Of File
                info["eof_found"] = True

            elif rec_type == 0x02:
                # Extended Segment Address — sets sector within current bank.
                # Combined with type 04 (bank select) for full address.
                seg = int(data_hex, 16)
                extended_segment = seg << 4

            elif rec_type == 0x04:
                # Extended Linear Address — selects flash bank.
                # NOTE: In BMW SP-Daten files the type 02 record (segment)
                # appears BEFORE the type 04 record (bank), so we must NOT
                # reset extended_segment here — it was already set for the
                # upcoming data records.
                upper = int(data_hex, 16)
                extended_linear = upper << 16

            elif rec_type == 0x03:
                # Start Segment Address — skip, not needed for bin
                pass

            elif rec_type == 0x05:
                # Start Linear Address — skip, not needed for bin
                pass

        except (ValueError, IndexError) as error:
            info["errors"].append(f"Line {line_num}: {error}")
            continue

    info["source_unique_bytes"] = len(source_values)
    info["source_identical_overlap_bytes"] = source_identical
    info["source_conflicting_overlap_bytes"] = source_conflicting
    info["first_source_conflicts"] = source_conflict_examples
    if source_conflicting:
        first = source_conflict_examples[0]
        info["errors"].append(
            f"Conflicting source-address overlap: {source_conflicting} byte writes; "
            f"first at 0x{first['source_address']:08X} from lines "
            f"{first['earlier_line']} and {first['later_line']}"
        )
    if not info["eof_found"]:
        info["errors"].append("Missing Intel HEX EOF record")
    if not records:
        info["errors"].append("No valid Intel HEX data records found")

    source_spaces = _ms45_source_spaces(records) if ecu_type in MS45_ECUS else []
    info["source_spaces"] = source_spaces

    target_values: Dict[int, int] = {}
    target_sources: Dict[int, int] = {}
    mapped_identical = 0
    mapped_conflicting = 0
    mapped_conflict_examples: List[Dict[str, Any]] = []
    selected_source_bytes = 0
    unmapped_lines = set()

    # Preserve input order so explicit legacy mode reproduces the previous
    # last-record-wins materialization exactly.
    for source_start, payload, line_num in records:
        for index, value in enumerate(payload):
            source_addr = source_start + index
            if not _source_region_contains(ecu_type, region, source_addr):
                continue
            selected_source_bytes += 1
            target_addr = _translate_addr(source_addr, addr_map)
            if target_addr is None:
                info["unmapped_bytes"] += 1
                unmapped_lines.add(line_num)
                continue
            if target_addr in target_values:
                earlier_source = target_sources[target_addr]
                # Equal raw source addresses were already audited above; the
                # counts here describe aliases between distinct source bytes.
                if earlier_source != source_addr:
                    if target_values[target_addr] == value:
                        mapped_identical += 1
                    else:
                        mapped_conflicting += 1
                        if len(mapped_conflict_examples) < 8:
                            mapped_conflict_examples.append(
                                {
                                    "target_address": target_addr,
                                    "earlier_source_address": earlier_source,
                                    "later_source_address": source_addr,
                                    "earlier_value": target_values[target_addr],
                                    "later_value": value,
                                }
                            )
                if policy == "legacy-last-wins":
                    target_values[target_addr] = value
                    target_sources[target_addr] = source_addr
            else:
                target_values[target_addr] = value
                target_sources[target_addr] = source_addr

    info["data_bytes"] = selected_source_bytes - info["unmapped_bytes"]
    info["unmapped_records"] = len(unmapped_lines)
    info["mapped_unique_bytes"] = len(target_values)
    info["mapped_identical_alias_bytes"] = mapped_identical
    info["mapped_conflicting_alias_bytes"] = mapped_conflicting
    info["discarded_conflicting_bytes"] = (
        mapped_conflicting if policy == "legacy-last-wins" else 0
    )
    info["lossy"] = bool(mapped_conflicting and policy == "legacy-last-wins")
    info["first_mapped_conflicts"] = mapped_conflict_examples

    if ecu_type in MS45_ECUS and region == "all" and policy == "error" and source_spaces == ["external", "mpc"]:
        info["errors"].append(
            f"Ambiguous mixed MPC-internal and external-flash source spaces for {ecu_type}; "
            "select --source-region mpc or --source-region external"
        )
    if mapped_conflicting and policy == "error":
        first = mapped_conflict_examples[0]
        info["errors"].append(
            f"Conflicting mapped overlap: {mapped_conflicting} byte writes; first target "
            f"0x{first['target_address']:08X} maps source "
            f"0x{first['earlier_source_address']:08X}=0x{first['earlier_value']:02X} and "
            f"0x{first['later_source_address']:08X}=0x{first['later_value']:02X}"
        )
    if info["unmapped_bytes"]:
        info["errors"].append(
            f"{info['unmapped_bytes']} source bytes in {info['unmapped_records']} records "
            "fell outside the selected address map"
        )
    if region != "all" and selected_source_bytes == 0:
        info["errors"].append(f"No source bytes matched source-region '{region}'")
    if not target_values:
        info["errors"].append("No mapped Intel HEX data bytes remain")
    if info["errors"]:
        return None, info

    info["min_addr"] = min(target_values)
    info["max_addr"] = max(target_values)

    # Determine base address and total size
    base_addr = force_base if force_base is not None else info["min_addr"]
    end_addr = info["max_addr"]

    if force_size is not None:
        total_size = force_size
    else:
        total_size = end_addr - base_addr + 1

    # Sanity check
    if total_size > 16 * 1024 * 1024:
        info["errors"].append(
            f"Computed output size {total_size} bytes exceeds the 16 MiB safety limit"
        )
        return None, info
    if total_size <= 0:
        info["errors"].append(
            f"Invalid size calculation: base=0x{base_addr:X}, end=0x{end_addr:X}"
        )
        return None, info

    info["base_addr"] = base_addr

    # Build the binary buffer
    binary = bytearray([fill_byte]) * total_size

    out_of_range = [
        address
        for address in target_values
        if not base_addr <= address < base_addr + total_size
    ]
    if out_of_range:
        info["errors"].append(
            f"{len(out_of_range)} source-defined bytes fall outside the requested output "
            f"window; first is 0x{out_of_range[0]:08X}"
        )
        return None, info

    for address, value in target_values.items():
        binary[address - base_addr] = value

    info["source_defined_output_bytes"] = len(target_values)
    info["fill_only_output_bytes"] = len(binary) - len(target_values)
    if info["lossy"]:
        info["warnings"].append(
            "LOSSY legacy-last-wins mapping discarded "
            f"{mapped_conflicting} conflicting earlier byte values"
        )
    if include_defined_bytes:
        info["_defined_bytes"] = dict(target_values)

    return binary, info


# ---------------------------------------------------------------------------
# ECU type detection
# ---------------------------------------------------------------------------
def detect_ecu_type(filepath: str, header: Dict[str, Any]) -> Optional[str]:
    """
    Try to detect ECU type from file path and header fields.
    Returns ECU group string like 'MDS42', 'MDS43', 'MDS450', etc.
    """
    path_upper = filepath.upper()
    
    # Check path components
    for ecu in ["MDS451", "MDS450", "MDS43", "MDS42", "ME72", "GD8604", "GD8600"]:
        if ecu in path_upper:
            return ecu
    
    # Check alternate naming in path
    if "MS45.1" in path_upper or "MS451" in path_upper:
        return "MDS451"
    if "MS45.0" in path_upper or "MS450" in path_upper:
        return "MDS450"
    if "MS43" in path_upper:
        return "MDS43"
    if "MS42" in path_upper:
        return "MDS42"
    if "ME7" in path_upper:
        return "ME72"
    if "GS8604" in path_upper or "GD8604" in path_upper:
        return "GD8604"
    if "GS8600" in path_upper or "GD8600" in path_upper:
        return "GD8600"

    # Hardware references distinguish moved MDS450/MDS451 files whose generic
    # ZL_System field says only "MS45".
    fields = header.get("fields", {})
    joined_fields = " ".join(str(value).upper() for value in fields.values())
    joined_fields += " " + str(header.get("referenz_line") or "").upper()
    if "0044570" in joined_fields:
        return "MDS451"
    if "0044560" in joined_fields:
        return "MDS450"

    # Check remaining explicit header identities. Plain "MS45" is ambiguous.
    for val in fields.values():
        val_upper = val.upper()
        if "MDS451" in val_upper:
            return "MDS451"
        if "MDS450" in val_upper:
            return "MDS450"
        if "MDS43" in val_upper:
            return "MDS43"
        if "MDS42" in val_upper:
            return "MDS42"

    return None


# ---------------------------------------------------------------------------
# Known SP-Daten locations
# ---------------------------------------------------------------------------
def get_spdaten_paths() -> List[str]:
    """Return standard BMW Standard Tools / SP-Daten paths."""
    paths = []
    known_roots = [
        r"C:\EC-APPS",
        r"C:\NFS\data",
        r"C:\NFS-Backup",
        r"C:\EDIABAS\Ecu",
        r"A:\BMW Standard Tools",
        r"A:\bmw-advanced-tools",
        r"A:\bmw-advanced-tools-master",
        r"A:\BMW_ECU_Downloads",
    ]
    for p in known_roots:
        if os.path.isdir(p):
            paths.append(p)
    return paths


def find_flash_files(
    search_paths: List[str],
    ecu_filter: Optional[str] = None,
    max_depth: int = 6,
) -> List[str]:
    """
    Find all .0DA/.0PA files under the given paths.
    If ecu_filter is set, only return files under folders matching that ECU group.
    """
    found = []
    ecu_upper = ecu_filter.upper() if ecu_filter else None

    for root_path in search_paths:
        for dirpath, dirnames, filenames in os.walk(root_path):
            # Depth check
            depth = dirpath[len(root_path):].count(os.sep)
            if depth > max_depth:
                dirnames.clear()
                continue

            # Skip known junk dirs
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

            # ECU filter on directory name
            if ecu_upper and ecu_upper not in dirpath.upper():
                continue

            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in FLASH_EXTS:
                    fp = os.path.join(dirpath, f)
                    if os.path.getsize(fp) <= MAX_FILE_SIZE:
                        found.append(fp)

    return sorted(found)


# ---------------------------------------------------------------------------
# Single file conversion
# ---------------------------------------------------------------------------
def convert_file(
    filepath: str,
    output_dir: Optional[str] = None,
    info_only: bool = False,
    force_ecu: Optional[str] = None,
    fill_byte: int = 0xFF,
    mapped_overlap_policy: str = "error",
    source_region: str = "all",
) -> Dict[str, Any]:
    """
    Convert a single .0PA/.0DA file to .bin.

    Returns dict with conversion results and metadata.
    """
    result = {
        "input": filepath,
        "output": None,
        "success": False,
        "ecu_type": None,
        "file_type": None,
        "hex_info": {},
        "header_fields": {},
        "warnings": [],
        "error": None,
        "mapping_policy": mapped_overlap_policy,
        "source_region": source_region,
    }

    if not os.path.isfile(filepath):
        result["error"] = f"File not found: {filepath}"
        return result

    file_size = os.path.getsize(filepath)
    if file_size > MAX_FILE_SIZE:
        result["error"] = f"File too large: {file_size} bytes"
        return result

    print(f"\n{'='*70}")
    print(f"  INPUT:  {_safe_print(filepath)}")
    print(f"  SIZE:   {file_size:,} bytes")

    # Read file
    try:
        with open(filepath, "rb") as f:
            data = f.read()
    except (OSError, PermissionError) as e:
        result["error"] = str(e)
        print(f"  ERROR:  {e}")
        return result

    # Parse Austausch-Datei header
    header = parse_austausch_header(data)
    result["file_type"] = header["file_type"]
    result["header_fields"] = dict(header["fields"])

    print(f"  TYPE:   Austausch-Datei {header['file_type']}")

    if header["fields"]:
        print(f"  HEADER FIELDS:")
        for k, v in list(header["fields"].items())[:8]:
            print(f"    {k}: {_safe_print(v)}")
    
    if header["referenz_line"]:
        print(f"  REF:    {_safe_print(header['referenz_line'][:80])}")

    # Detect ECU type and reject an explicit profile that conflicts with the
    # file's own directory/header identity.
    detected_ecu = detect_ecu_type(filepath, header)
    try:
        requested_ecu = _canonical_ecu_type(force_ecu)
        if requested_ecu and detected_ecu and requested_ecu != detected_ecu:
            raise ValueError(
                f"Explicit ECU {requested_ecu} conflicts with detected {detected_ecu}"
            )
        ecu_type, mapped_overlap_policy, source_region = _normalize_mapping_options(
            requested_ecu or detected_ecu, mapped_overlap_policy, source_region
        )
    except ValueError as error:
        result["error"] = str(error)
        print(f"  ERROR:  {error}")
        return result
    result["ecu_type"] = ecu_type
    result["mapping_policy"] = mapped_overlap_policy
    result["source_region"] = source_region
    if ecu_type:
        print(f"  ECU:    {ecu_type}")

    # Find HEX data start
    hex_offset = header.get("hex_data_offset")
    if hex_offset is None:
        hex_offset = _find_intel_hex_start(data)

    if hex_offset is None:
        result["error"] = "No Intel HEX data found in file"
        result["warnings"].append("Could not locate Intel HEX records")
        print(f"  ERROR:  No Intel HEX data found")
        return result

    print(f"  HEX:    Intel HEX data starts at offset 0x{hex_offset:X}")

    # Extract OSID from header for per-OSID cal sizing
    osid = _extract_osid(header)
    if osid:
        print(f"  OSID:   {osid}")
    if ecu_type == "MDS42" and osid == "0110SA":
        result["error"] = ("0110SA is quarantined: no independent factory lineage is accepted; "
                           "treat it as damaged 0110CA read/copy data")
        result["warnings"].append("DO NOT CONVERT OR FLASH 0110SA as a stock MS42 lane")
        print(f"  ERROR:  {result['error']}")
        return result

    if ecu_type in MS45_ECUS and header["file_type"] == "Daten":
        if source_region == "mpc":
            result["error"] = (
                "MS45 calibration packages use the external-flash source space; "
                "--source-region mpc is invalid"
            )
            print(f"  ERROR:  {result['error']}")
            return result
        if source_region == "all":
            source_region = "external"
            result["source_region"] = source_region

    # Determine forced size based on ECU type and file type
    force_size = None
    force_base = None
    if ecu_type:
        total_flash = ECU_FLASH_SIZES.get(ecu_type)

        if header["file_type"] == "Daten":
            # Look up cal info by (ecu_type, osid), fall back to (ecu_type, None)
            cal_info = ECU_CAL_INFO.get((ecu_type, osid)) or ECU_CAL_INFO.get((ecu_type, None))
            if cal_info and cal_info.get("cal_offset") is not None:
                force_base = cal_info["cal_offset"]
                force_size = cal_info["cal_size"]
                print(f"  MODE:   Calibration partition  "
                      f"(0x{force_base:06X} - 0x{force_base + force_size - 1:06X}, "
                      f"{force_size // 1024} KB)")
            else:
                # Auto-detect: do a quick pre-parse to find address range,
                # then align base down and size up to sector boundaries
                print(f"  MODE:   Calibration partition  (auto-detect from HEX addresses)")
                # force_base/force_size stay None; we'll align after parsing
        elif header["file_type"] == "Programm" and total_flash:
            # Program partition — output from base 0 for the full flash range
            force_base = 0
            force_size = (
                MS45_MPC_SIZE
                if ecu_type in MS45_ECUS and source_region == "mpc"
                else total_flash
            )
            print(f"  MODE:   Program partition  "
                  f"(0x{force_base:06X} - 0x{force_base + force_size - 1:06X}, "
                  f"{force_size // 1024} KB)")

    # Look up CPU-to-flash address translation for this ECU
    addr_map = ECU_ADDR_MAP.get(ecu_type) if ecu_type else None

    # Convert Intel HEX → binary
    binary, hex_info = intel_hex_to_binary(
        data,
        start_offset=hex_offset,
        fill_byte=fill_byte,
        force_size=force_size,
        force_base=force_base,
        addr_map=addr_map,
        ecu_type=ecu_type,
        mapped_overlap_policy=mapped_overlap_policy,
        source_region=source_region,
    )
    result["hex_info"] = hex_info

    # Auto-detect alignment for Daten files when cal_offset was unknown
    if (binary is not None
        and header["file_type"] == "Daten"
        and force_base is None
        and hex_info["min_addr"] is not None):
        aligned_base, aligned_size = _align_cal_region(
            hex_info["min_addr"], hex_info["max_addr"]
        )
        # Re-parse with the aligned base/size
        binary, hex_info = intel_hex_to_binary(
            data,
            start_offset=hex_offset,
            fill_byte=fill_byte,
            force_size=aligned_size,
            force_base=aligned_base,
            addr_map=addr_map,
            ecu_type=ecu_type,
            mapped_overlap_policy=mapped_overlap_policy,
            source_region=source_region,
        )
        result["hex_info"] = hex_info
        print(f"  ALIGN:  Auto-detected cal region "
              f"0x{aligned_base:06X} - 0x{aligned_base + aligned_size - 1:06X} "
              f"({aligned_size // 1024} KB)")

    if hex_info["min_addr"] is not None:
        print(f"  ADDR:   0x{hex_info['min_addr']:08X} - 0x{hex_info['max_addr']:08X}")
        print(f"  DATA:   {hex_info['data_bytes']:,} bytes in {hex_info['record_count']} records")
        print(f"  EOF:    {'Yes' if hex_info['eof_found'] else 'No'}")
        print(f"  VIEW:   {hex_info['source_region']}")
        print(f"  MAP:    {hex_info['mapping_policy']}")
        if hex_info.get("mapped_identical_alias_bytes") or hex_info.get("mapped_conflicting_alias_bytes"):
            print(
                "  ALIAS:  "
                f"{hex_info['mapped_identical_alias_bytes']:,} identical, "
                f"{hex_info['mapped_conflicting_alias_bytes']:,} conflicting bytes"
            )

    result["warnings"].extend(hex_info.get("warnings", []))
    for w in hex_info.get("warnings", [])[:8]:
        print(f"  WARN:   {w}")

    if binary is None:
        errors = hex_info.get("errors", [])
        result["error"] = errors[0] if errors else "Failed to decode Intel HEX data"
        print(f"  ERROR:  {result['error']}")
        for error in errors[1:6]:
            print(f"          {error}")
        return result

    print(f"  BIN:    {len(binary):,} bytes ({len(binary) // 1024} KB)")
    print(
        f"  SOURCE: {hex_info['source_defined_output_bytes']:,} defined; "
        f"{hex_info['fill_only_output_bytes']:,} fill-only bytes"
    )

    # Compute hash
    sha = hashlib.sha256(binary).hexdigest()[:16]
    print(f"  SHA256: {sha}...")

    if info_only:
        result["success"] = True
        result["output"] = "(info mode — no output written)"
        print(f"  (info only — skipping write)")
        return result

    # Determine output filename and path
    basename = Path(filepath).stem
    ext = Path(filepath).suffix.lower()
    type_tag = "cal" if header["file_type"] == "Daten" else "prg"
    ecu_tag = ecu_type if ecu_type else "unknown"
    size_kb = len(binary) // 1024

    view_tag = (
        f"_{source_region}"
        if ecu_type in MS45_ECUS and source_region != "all"
        else ""
    )
    policy_tag = (
        "_legacy-lossy" if mapped_overlap_policy == "legacy-last-wins" else ""
    )
    out_name = (
        f"{basename}_{ecu_tag}_{type_tag}{view_tag}{policy_tag}_{size_kb}KB.bin"
    )
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, out_name)
    else:
        out_path = os.path.join(os.path.dirname(filepath), out_name)

    # Avoid overwriting
    if os.path.exists(out_path):
        # Append hash to make unique
        out_name = (
            f"{basename}_{ecu_tag}_{type_tag}{view_tag}{policy_tag}_"
            f"{size_kb}KB_{sha[:8]}.bin"
        )
        out_path = os.path.join(
            output_dir if output_dir else os.path.dirname(filepath), out_name
        )

    # Write
    try:
        with open(out_path, "wb") as f:
            f.write(binary)
        result["output"] = out_path
        result["success"] = True
        print(f"  OUTPUT: {_safe_print(out_path)}")
        print(f"  STATUS: OK")
    except (OSError, PermissionError) as e:
        result["error"] = str(e)
        print(f"  ERROR:  Write failed: {e}")

    return result


# ---------------------------------------------------------------------------
# Combine 0PA + 0DA into a single full flash binary
# ---------------------------------------------------------------------------
def _referenz_value(header: Dict[str, Any]) -> Optional[str]:
    line = (header.get("referenz_line") or "").strip()
    parts = line.split()
    return parts[1].upper() if len(parts) >= 2 else None


def combine_pa_da(
    pa_path: str,
    da_path: str,
    output_dir: Optional[str] = None,
    force_ecu: Optional[str] = None,
    fill_byte: int = 0xFF,
    mapped_overlap_policy: str = "error",
    source_region: str = "all",
) -> Dict[str, Any]:
    """Combine source-defined bytes from one program and calibration package.

    Synthetic fill bytes are never treated as source data.  Conflicting
    mapped writes fail before the destination path is touched unless the
    caller explicitly requests the lossy ``legacy-last-wins`` policy.
    """
    result = {
        "pa_input": pa_path,
        "da_input": da_path,
        "output": None,
        "success": False,
        "ecu_type": None,
        "error": None,
        "warnings": [],
        "mapping_policy": mapped_overlap_policy,
        "source_region": source_region,
        "combine_info": {},
    }

    print(f"\n{'='*70}")
    print("  COMBINE MODE")
    print(f"  PROG:   {_safe_print(pa_path)}")
    print(f"  DATA:   {_safe_print(da_path)}")

    for path, label in [(pa_path, "0PA"), (da_path, "0DA")]:
        if not os.path.isfile(path):
            result["error"] = f"{label} file not found: {path}"
            print(f"  ERROR:  {result['error']}")
            return result
        if os.path.getsize(path) > MAX_FILE_SIZE:
            result["error"] = f"{label} file exceeds the {MAX_FILE_SIZE}-byte safety limit"
            print(f"  ERROR:  {result['error']}")
            return result

    try:
        with open(pa_path, "rb") as file_handle:
            pa_data = file_handle.read()
        with open(da_path, "rb") as file_handle:
            da_data = file_handle.read()
    except (OSError, PermissionError) as error:
        result["error"] = str(error)
        print(f"  ERROR:  {error}")
        return result

    pa_header = parse_austausch_header(pa_data)
    da_header = parse_austausch_header(da_data)
    if pa_header["file_type"] != "Programm":
        result["error"] = "The 0PA input is not identified as Austausch-Datei Programm"
        print(f"  ERROR:  {result['error']}")
        return result
    if da_header["file_type"] != "Daten":
        result["error"] = "The 0DA input is not identified as Austausch-Datei Daten"
        print(f"  ERROR:  {result['error']}")
        return result

    detected = {
        ecu
        for ecu in (
            detect_ecu_type(pa_path, pa_header),
            detect_ecu_type(da_path, da_header),
        )
        if ecu
    }
    try:
        requested_ecu = _canonical_ecu_type(force_ecu)
        if len(detected) > 1:
            raise ValueError(
                "Cannot combine mixed ECU families: " + ", ".join(sorted(detected))
            )
        if requested_ecu and detected and requested_ecu not in detected:
            raise ValueError(
                f"Explicit ECU {requested_ecu} conflicts with detected "
                + ", ".join(sorted(detected))
            )
        ecu_type, mapped_overlap_policy, source_region = _normalize_mapping_options(
            requested_ecu or next(iter(detected), None),
            mapped_overlap_policy,
            source_region,
        )
    except ValueError as error:
        result["error"] = str(error)
        print(f"  ERROR:  {error}")
        return result

    if not ecu_type:
        result["error"] = "Cannot determine ECU type — use --ecu to specify"
        print(f"  ERROR:  {result['error']}")
        return result
    if ecu_type in MS45_ECUS and source_region == "mpc":
        result["error"] = (
            "Cannot combine an external-flash MS45 calibration package into an MPC-only view"
        )
        print(f"  ERROR:  {result['error']}")
        return result

    pa_ref = _referenz_value(pa_header)
    da_ref = _referenz_value(da_header)
    if ecu_type in MS45_ECUS and pa_ref and da_ref and not da_ref.startswith(pa_ref):
        result["error"] = (
            f"Program/calibration $REFERENZ mismatch: {pa_ref} vs {da_ref}"
        )
        print(f"  ERROR:  {result['error']}")
        return result

    result["ecu_type"] = ecu_type
    result["mapping_policy"] = mapped_overlap_policy
    result["source_region"] = source_region
    total_flash = ECU_FLASH_SIZES.get(ecu_type, 512 * 1024)
    addr_map = ECU_ADDR_MAP.get(ecu_type)
    print(f"  ECU:    {ecu_type} ({total_flash // 1024} KB analysis view)")
    print(f"  VIEW:   {source_region}")
    print(f"  MAP:    {mapped_overlap_policy}")

    member_infos = []
    for label, member_data, member_header in (
        ("0PA", pa_data, pa_header),
        ("0DA", da_data, da_header),
    ):
        hex_offset = member_header.get("hex_data_offset")
        if hex_offset is None:
            hex_offset = _find_intel_hex_start(member_data, 0)
        if hex_offset is None:
            result["error"] = f"{label}: no Intel HEX data found"
            print(f"  ERROR:  {result['error']}")
            return result
        _binary, member_info = intel_hex_to_binary(
            member_data,
            start_offset=hex_offset,
            fill_byte=fill_byte,
            addr_map=addr_map,
            ecu_type=ecu_type,
            mapped_overlap_policy=mapped_overlap_policy,
            source_region=source_region,
            include_defined_bytes=True,
        )
        if _binary is None:
            errors = member_info.get("errors", [])
            result["error"] = f"{label}: " + (
                errors[0] if errors else "failed strict Intel HEX validation"
            )
            result["warnings"].extend(
                f"{label}: {warning}" for warning in member_info.get("warnings", [])
            )
            print(f"  ERROR:  {result['error']}")
            for error in errors[1:5]:
                print(f"          {error}")
            return result
        member_infos.append((label, member_info))
        print(
            f"  {label}:    {member_info['mapped_unique_bytes']:,} source-defined "
            f"mapped bytes @ 0x{member_info['min_addr']:06X}-"
            f"0x{member_info['max_addr']:06X}"
        )
        result["warnings"].extend(
            f"{label}: {warning}" for warning in member_info.get("warnings", [])
        )

    combined_values: Dict[int, int] = {}
    combined_owners: Dict[int, str] = {}
    identical = 0
    conflicting = 0
    first_conflicts = []
    for label, member_info in member_infos:
        for address, value in sorted(member_info["_defined_bytes"].items()):
            if address in combined_values:
                if combined_values[address] == value:
                    identical += 1
                else:
                    conflicting += 1
                    if len(first_conflicts) < 8:
                        first_conflicts.append(
                            {
                                "address": address,
                                "earlier_member": combined_owners[address],
                                "later_member": label,
                                "earlier_value": combined_values[address],
                                "later_value": value,
                            }
                        )
                    if mapped_overlap_policy == "error":
                        continue
                if mapped_overlap_policy == "legacy-last-wins":
                    combined_values[address] = value
                    combined_owners[address] = label
            else:
                combined_values[address] = value
                combined_owners[address] = label

    combine_info = {
        "source_region": source_region,
        "mapping_policy": mapped_overlap_policy,
        "unique_target_bytes": len(combined_values),
        "member_identical_alias_bytes": sum(
            info.get("mapped_identical_alias_bytes", 0)
            for _label, info in member_infos
        ),
        "member_conflicting_alias_bytes": sum(
            info.get("mapped_conflicting_alias_bytes", 0)
            for _label, info in member_infos
        ),
        "identical_cross_file_overlap_bytes": identical,
        "conflicting_cross_file_overlap_bytes": conflicting,
        "discarded_conflicting_bytes": 0,
        "first_conflicts": first_conflicts,
        "lossy": bool(
            mapped_overlap_policy == "legacy-last-wins"
            and (
                conflicting
                or any(info.get("lossy") for _label, info in member_infos)
            )
        ),
    }
    result["combine_info"] = combine_info
    if conflicting and mapped_overlap_policy == "error":
        first = first_conflicts[0]
        result["error"] = (
            f"Conflicting combine overlap: {conflicting} bytes; first at "
            f"0x{first['address']:08X} ({first['earlier_member']}=0x"
            f"{first['earlier_value']:02X}, {first['later_member']}=0x"
            f"{first['later_value']:02X})"
        )
        print(f"  ERROR:  {result['error']}")
        return result
    if not combined_values:
        result["error"] = "No source-defined bytes remain to combine"
        print(f"  ERROR:  {result['error']}")
        return result

    outside = [address for address in combined_values if not 0 <= address < total_flash]
    if outside:
        result["error"] = (
            f"{len(outside)} source-defined bytes fall outside the {total_flash}-byte "
            f"output view; first is 0x{outside[0]:08X}"
        )
        print(f"  ERROR:  {result['error']}")
        return result

    combined = bytearray([fill_byte]) * total_flash
    for address, value in combined_values.items():
        combined[address] = value

    combine_info["output_size"] = len(combined)
    combine_info["source_defined_output_bytes"] = len(combined_values)
    combine_info["fill_only_output_bytes"] = len(combined) - len(combined_values)
    if combine_info["lossy"]:
        discarded = (
            combine_info["member_conflicting_alias_bytes"] + conflicting
        )
        combine_info["discarded_conflicting_bytes"] = discarded
        warning = (
            f"LOSSY legacy-last-wins combine discarded {discarded} conflicting "
            "earlier byte values; "
            "retain the original source packages and mapping report"
        )
        result["warnings"].append(warning)

    basename = Path(pa_path).stem
    size_kb = len(combined) // 1024
    view_tag = f"_{source_region}" if ecu_type in MS45_ECUS else ""
    policy_tag = (
        "_legacy-lossy" if mapped_overlap_policy == "legacy-last-wins" else ""
    )
    out_name = (
        f"{basename}_{ecu_type}_combined{view_tag}{policy_tag}_{size_kb}KB.bin"
    )
    destination_dir = output_dir if output_dir else os.path.dirname(pa_path)
    out_path = os.path.join(destination_dir, out_name)
    if os.path.exists(out_path):
        sha = hashlib.sha256(combined).hexdigest()[:8]
        out_name = (
            f"{basename}_{ecu_type}_combined{view_tag}{policy_tag}_"
            f"{size_kb}KB_{sha}.bin"
        )
        out_path = os.path.join(destination_dir, out_name)

    try:
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(out_path, "wb") as file_handle:
            file_handle.write(combined)
        result["output"] = out_path
        result["success"] = True
        print(f"  OUTPUT: {_safe_print(out_path)}")
        print(f"  SIZE:   {len(combined):,} bytes ({size_kb} KB)")
        print(f"  SOURCE: {len(combined_values):,} defined; "
              f"{len(combined) - len(combined_values):,} fill-only bytes")
        print("  STATUS: OK — offline combined analysis view")
    except (OSError, PermissionError) as error:
        result["error"] = str(error)
        print(f"  ERROR:  Write failed: {error}")

    for warning in result["warnings"]:
        print(f"  WARN:   {warning}")

    return result


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------
def process_path(
    path: str,
    output_dir: Optional[str] = None,
    info_only: bool = False,
    force_ecu: Optional[str] = None,
    recursive: bool = True,
    mapped_overlap_policy: str = "error",
    source_region: str = "all",
) -> List[Dict[str, Any]]:
    """
    Process a file or folder. If folder, recursively find all 0PA/0DA files.
    """
    results = []

    if os.path.isfile(path):
        r = convert_file(
            path,
            output_dir=output_dir,
            info_only=info_only,
            force_ecu=force_ecu,
            mapped_overlap_policy=mapped_overlap_policy,
            source_region=source_region,
        )
        results.append(r)
    elif os.path.isdir(path):
        files = find_flash_files([path], max_depth=6 if recursive else 0)
        if not files:
            print(f"No .0DA/.0PA files found in: {path}")
        for fp in files:
            r = convert_file(
                fp,
                output_dir=output_dir,
                info_only=info_only,
                force_ecu=force_ecu,
                mapped_overlap_policy=mapped_overlap_policy,
                source_region=source_region,
            )
            results.append(r)
    else:
        print(f"Path not found: {path}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="BMW SP-Daten 0PA/0DA to .BIN Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s  C:\\EC-APPS\\NFS\\data\\MDS43\\
  %(prog)s  7506537.0DA
  %(prog)s  7549387A.0PA --source-region mpc
  %(prog)s  7549387A.0PA --source-region external
  %(prog)s  --combine 7549387A.0PA P7550114.0DA --source-region external
  %(prog)s  --scan MDS43
  %(prog)s  --info 7506537.0DA
  %(prog)s  7506537.0DA -o converted_bins/
  %(prog)s  --scan MDS42 --info

Compatibility regression only (lossy and prominently reported):
  %(prog)s  7549387A.0PA --mapped-overlap-policy legacy-last-wins

Supported ECU types:
  MDS42  = Siemens MS42   (512 KB output view)
  MDS43  = Siemens MS43   (512 KB output view)
  MDS450 = Siemens MS45.0 (explicit MPC/external views)
  MDS451 = Siemens MS45.1 (explicit MPC/external views)
  ME72   = Bosch ME7.2
  GD8600 = Bosch GS8.60.0 EGS
  GD8604 = Bosch GS8.60.4 EGS

Outputs are offline analysis views. Conversion success is not flash proof.
""",
    )
    parser.add_argument("input", nargs="*", help="Input .0DA/.0PA file(s) or folder(s)")
    parser.add_argument("-o", "--output", help="Output directory for converted .bin files")
    parser.add_argument("--info", action="store_true", help="Show file info only, don't write .bin")
    parser.add_argument("--combine", action="store_true",
                        help="Combine one 0PA and one 0DA into an offline analysis view")
    parser.add_argument("--scan", metavar="ECU",
                        help="Scan standard SP-Daten paths for ECU group (e.g. MDS43, MDS42)")
    parser.add_argument(
        "--ecu",
        help="Force ECU type (MDS42, MDS43, MDS450, MDS451, ME72, GD8600, GD8604)",
    )
    parser.add_argument("--fill", type=lambda x: int(x, 0), default=0xFF,
                        help="Fill byte for gaps (default: 0xFF = erased flash)")
    parser.add_argument(
        "--source-region",
        choices=SOURCE_REGIONS,
        default="all",
        help=(
            "Source address space; MDS450/MDS451 mixed program packages require "
            "mpc or external (default: all)"
        ),
    )
    parser.add_argument(
        "--mapped-overlap-policy",
        choices=MAPPED_OVERLAP_POLICIES,
        default="error",
        help=(
            "Mapped collision policy: error is fail-closed; legacy-last-wins "
            "explicitly enables and reports the historical lossy overlay"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    args = parser.parse_args()

    print(f"BMW SP-Daten 0PA/0DA to .BIN Converter v{VERSION}")
    print(f"{'='*70}")

    all_results = []

    # --scan mode: find and convert all files for an ECU group
    if args.scan:
        sp_paths = get_spdaten_paths()
        print(f"Scanning {len(sp_paths)} SP-Daten locations for {args.scan}...")
        files = find_flash_files(sp_paths, ecu_filter=args.scan)
        print(f"Found {len(files)} flash file(s)")
        for fp in files:
            r = convert_file(
                fp,
                output_dir=args.output,
                info_only=args.info,
                force_ecu=args.ecu,
                mapped_overlap_policy=args.mapped_overlap_policy,
                source_region=args.source_region,
            )
            all_results.append(r)

    # --combine mode: merge 0PA + 0DA
    elif args.combine:
        if len(args.input) != 2:
            print("ERROR: --combine requires exactly 2 input files (0PA and 0DA)")
            sys.exit(1)
        
        # Figure out which is PA and which is DA
        pa_file = da_file = None
        for f in args.input[:2]:
            ext = os.path.splitext(f)[1].lower()
            if ext == ".0pa":
                pa_file = f
            elif ext == ".0da":
                da_file = f
            elif pa_file is None:
                pa_file = f  # First unrecognized → treat as PA
            else:
                da_file = f  # Second → treat as DA

        if pa_file and da_file:
            r = combine_pa_da(
                pa_file,
                da_file,
                output_dir=args.output,
                force_ecu=args.ecu,
                fill_byte=args.fill,
                mapped_overlap_policy=args.mapped_overlap_policy,
                source_region=args.source_region,
            )
            all_results.append(r)
        else:
            print("ERROR: Could not identify PA and DA files")
            sys.exit(1)

    # Normal mode: convert file(s) or folder(s)
    elif args.input:
        for inp in args.input:
            results = process_path(
                inp,
                output_dir=args.output,
                info_only=args.info,
                force_ecu=args.ecu,
                mapped_overlap_policy=args.mapped_overlap_policy,
                source_region=args.source_region,
            )
            all_results.extend(results)
    else:
        parser.print_help()
        sys.exit(0)

    # Summary
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    total = len(all_results)
    ok = sum(1 for r in all_results if r.get("success"))
    fail = total - ok
    print(f"  Total:     {total}")
    print(f"  Success:   {ok}")
    print(f"  Failed:    {fail}")

    if fail > 0:
        print(f"\n  Failed files:")
        for r in all_results:
            if not r.get("success"):
                inp = r.get("input") or r.get("pa_input", "?")
                err = r.get("error", "unknown error")
                print(f"    {_safe_print(inp)}: {err}")

    if ok > 0:
        print(f"\n  Converted files:")
        for r in all_results:
            if r.get("success") and r.get("output"):
                print(f"    {_safe_print(r['output'])}")

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
