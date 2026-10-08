#!/usr/bin/env python3
"""Cross-platform regression runner for the KingAI TunerPro exporter.

The suite executes the public CLI against locally maintained, known-readable
fixtures.  It verifies process success, all output formats, JSON structure,
element counts, and basic source identity.  The output directory is temporary
unless --keep-output is supplied.

This tests exporter behaviour.  It does not certify that every XDF address,
axis, equation, or table semantic is correct for the connected ECU family.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any


HERE = Path(__file__).resolve().parent
REPOS = Path(os.environ.get("KINGAI_REPOS_ROOT", HERE.parent)).resolve()
GUIDES = Path(
    os.environ.get(
        "KINGAI_BMW_GUIDES_ROOT",
        REPOS / "1bmw_ms42_tuning_guides",
    )
).resolve()
EXPORTER = HERE / "tunerpro_exporter.py"


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.is_file():
            return path
    return paths[0]


CASES = (
    {
        "name": "BMW_MS42_0110C6",
        "xdf": first_existing(
            GUIDES / "Siemens_MS42_0110C6_ENG_512K_v1.1.xdf",
            GUIDES / "xdfs" / "Siemens_MS42_0110C6_ENG_512K_v1.1.xdf",
        ),
        "bin": first_existing(
            GUIDES
            / "all_ms42_bins"
            / "Siemens_MS42_0110C6_E46_M52TUB28_EU3_RHD.bin",
            GUIDES / "all_ms42_bins" / "cfm54b30.bin",
        ),
        "expected": {"scalars": 1384, "flags": 0, "tables": 597},
        "sentinels": (
            {
                "table": "id_maf_tab__v_maf_1__v_maf_2",
                "row": 0,
                "col": 4,
                "value": 4.95,
                "lsb_first": True,
                "z_address": "0x17A6",
            },
        ),
    },
    {
        "name": "BMW_MS43_430069",
        "xdf": first_existing(
            GUIDES / "Siemens_MS43_430069_512K_1.1.3v.xdf",
            GUIDES / "xdfs" / "Siemens_MS43_430069_512K_1.1.3v.xdf",
        ),
        "bin": first_existing(
            GUIDES / "all_ms43_bins" / "cfm54b30.bin",
            GUIDES / "all_ms42_bins" / "cfm54b30.bin",
        ),
        "expected": {"scalars": 2256, "flags": 0, "tables": 1454},
    },
    {
        "name": "BMW_MS45_4560BN00_v3",
        "xdf": first_existing(
            GUIDES
            / "ms45_work"
            / "Siemens_MS450_4560BN00_ENG_1024K_v3.0.xdf",
            GUIDES
            / "ms42_ms43_ms45_ai_kingai_xdfs"
            / "ms45"
            / "Siemens_MS450_4560BN00_ENG_1024K_v3.0.xdf",
        ),
        "bin": first_existing(
            GUIDES / "all_ms45_bins" / "B039588_0044560_Flash.bin",
            GUIDES / "all_ms45_bins" / "B039588_0044560.bin",
        ),
        "expected": {"scalars": 0, "flags": 0, "tables": 1244},
    },
    {
        "name": "Holden_VY_V6_060A_Enhanced",
        "xdf": REPOS
        / "VY_V6_Assembly_Modding"
        / "VX VY_V6_$060A_Enhanced_v2.09a.xdf",
        "bin": REPOS
        / "VY_V6_Assembly_Modding"
        / "VX-VY_V6_$060A_Enhanced_v1.0a.bin",
        "expected": {"scalars": 1310, "flags": 351, "tables": 330},
    },
    {
        "name": "Synthetic_Positive_Major_Stride",
        "synthetic": "positive_major_stride",
        "expected": {"scalars": 0, "flags": 0, "tables": 1},
        "sentinels": (
            {
                "table": "Synthetic Positive Major Stride",
                "row": 0,
                "col": 0,
                "value": 10.0,
                "x_labels": [1000.0, 2000.0, 3000.0, 4000.0],
                "y_labels": [5.0, 10.0, 15.0],
            },
            {
                "table": "Synthetic Positive Major Stride",
                "row": 1,
                "col": 0,
                "value": 20.0,
            },
            {
                "table": "Synthetic Positive Major Stride",
                "row": 2,
                "col": 3,
                "value": 33.0,
            },
        ),
    },
    {
        "name": "Synthetic_Overlapping_Axis_Stride",
        "synthetic": "overlapping_axis_stride",
        "expected": {"scalars": 0, "flags": 0, "tables": 1},
        "sentinels": (
            {
                "table": "Synthetic Overlapping Axis Stride",
                "row": 0,
                "col": 3,
                "value": 13.0,
                "x_labels": [258.0, 515.0, 772.0, 1029.0],
                "y_labels": [],
            },
        ),
    },
    {
        "name": "Synthetic_Native_Text_Limit_Warning",
        "synthetic": "native_text_limit_warning",
        "expected": {"scalars": 0, "flags": 0, "tables": 1},
        "expected_log_fragment": "TunerPro native text limit exceeded",
    },
    {
        "name": "Synthetic_Native_Axis_Semantics",
        "synthetic": "native_axis_semantics",
        "expected": {"scalars": 0, "flags": 0, "tables": 4},
        "sentinels": (
            {
                "table": "Implicit Address Is Not An Embedded Axis",
                "row": 0,
                "col": 1,
                "value": 2.0,
                "x_labels": [0.0, 0.0],
                "y_labels": [],
            },
            {
                "table": "Text Labels Keep Display Metadata",
                "row": 0,
                "col": 0,
                "value": 3.0,
                "x_labels": [0.0, 0.0],
                "x_display_labels": ["Low", "High"],
                "y_labels": [],
            },
            {
                "table": "Negative Singleton Axis Is Suppressed",
                "row": 0,
                "col": 2,
                "value": 7.0,
                "x_labels": [0.0, 1.0, 2.0],
                "y_labels": [],
            },
            {
                "table": "One By One Table",
                "row": 0,
                "col": 0,
                "value": 42.0,
                "x_labels": [0.0],
                "y_labels": [0.0],
            },
        ),
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-output",
        type=Path,
        help="Keep artifacts in this directory instead of a temporary directory.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Run only a named case (repeatable).",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value is not an object")
    return data


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.reader(handle))


def build_positive_stride_fixture(root: Path) -> tuple[Path, Path]:
    """Create a tiny packed-row fixture with an embedded Y value per row."""
    root.mkdir(parents=True, exist_ok=True)
    binary = root / "positive_major_stride.bin"
    xdf = root / "positive_major_stride.xdf"

    data = bytearray(0x1000)
    struct.pack_into(">4H", data, 0x20, 1000, 2000, 3000, 4000)
    for row, (y_value, z_values) in enumerate(
        (
            (5, (10, 11, 12, 13)),
            (10, (20, 21, 22, 23)),
            (15, (30, 31, 32, 33)),
        )
    ):
        row_address = 0x30 + row * 10
        struct.pack_into(">H4H", data, row_address, y_value, *z_values)
    binary.write_bytes(data)

    xdf.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<XDFFORMAT version="1.70">
  <XDFHEADER>
    <flags>0x1</flags>
    <deftitle>Synthetic positive major-stride regression</deftitle>
    <description>Generated regression fixture.</description>
    <author>KingAI regression</author>
    <BASEOFFSET offset="0" subtract="0" />
    <DEFAULTS datasizeinbits="16" sigdigits="0" outputtype="1" signed="0" lsbfirst="0" float="0" />
    <REGION type="0xFFFFFFFF" startaddress="0x0" size="0x1000" regionflags="0x0" name="Binary" desc="Synthetic" />
    <CATEGORY index="0x1" name="Regression" />
  </XDFHEADER>
  <XDFTABLE uniqueid="0x1" flags="0x30">
    <title>Synthetic Positive Major Stride</title>
    <description>Rows contain one embedded Y word followed by four Z words.</description>
    <CATEGORYMEM index="0" category="0x1" />
    <XDFAXIS id="x" uniqueid="0x0">
      <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x20" mmedelementsizebits="16" mmedmajorstridebits="16" mmedminorstridebits="0" />
      <indexcount>4</indexcount>
      <decimalpl>0</decimalpl>
      <outputtype>1</outputtype>
      <units>raw_x</units>
      <embedinfo type="1" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="y" uniqueid="0x0">
      <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x30" mmedelementsizebits="16" mmedmajorstridebits="80" mmedminorstridebits="0" />
      <indexcount>3</indexcount>
      <decimalpl>0</decimalpl>
      <outputtype>1</outputtype>
      <units>raw_y</units>
      <embedinfo type="1" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="z" uniqueid="0x0">
      <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x32" mmedelementsizebits="16" mmedrowcount="3" mmedcolcount="4" mmedmajorstridebits="80" mmedminorstridebits="16" />
      <decimalpl>0</decimalpl>
      <outputtype>1</outputtype>
      <units>raw_z</units>
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
  </XDFTABLE>
</XDFFORMAT>
""",
        encoding="utf-8",
        newline="\n",
    )
    return xdf, binary


def build_overlapping_axis_stride_fixture(root: Path) -> tuple[Path, Path]:
    """Create a native MS42-style 16-bit axis with an 8-bit stride."""
    root.mkdir(parents=True, exist_ok=True)
    binary = root / "overlapping_axis_stride.bin"
    xdf = root / "overlapping_axis_stride.xdf"

    data = bytearray(0x100)
    data[0x20:0x25] = bytes((0x01, 0x02, 0x03, 0x04, 0x05))
    data[0x40:0x44] = bytes((10, 11, 12, 13))
    binary.write_bytes(data)

    xdf.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<XDFFORMAT version="1.70">
  <XDFHEADER>
    <flags>0x1</flags>
    <deftitle>Synthetic overlapping-axis-stride regression</deftitle>
    <description>Generated from an MS42 native TunerPro axis shape.</description>
    <author>KingAI regression</author>
    <BASEOFFSET offset="0" subtract="0" />
    <DEFAULTS datasizeinbits="8" sigdigits="0" outputtype="1" signed="0" lsbfirst="0" float="0" />
    <REGION type="0xFFFFFFFF" startaddress="0x0" size="0x100" regionflags="0x0" name="Binary" desc="Synthetic" />
    <CATEGORY index="0x1" name="Regression" />
  </XDFHEADER>
  <XDFTABLE uniqueid="0x2" flags="0x0">
    <title>Synthetic Overlapping Axis Stride</title>
    <CATEGORYMEM index="0" category="0x1" />
    <XDFAXIS id="x" uniqueid="0x0">
      <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x20" mmedelementsizebits="16" mmedmajorstridebits="8" mmedminorstridebits="0" />
      <indexcount>4</indexcount>
      <decimalpl>0</decimalpl>
      <outputtype>1</outputtype>
      <units>raw_x</units>
      <embedinfo type="1" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="y" uniqueid="0x0">
      <EMBEDDEDDATA mmedelementsizebits="8" mmedmajorstridebits="-8" mmedminorstridebits="0" />
      <indexcount>1</indexcount>
      <LABEL index="0" value="" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="z" uniqueid="0x0">
      <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x40" mmedelementsizebits="8" mmedrowcount="1" mmedcolcount="4" mmedmajorstridebits="0" mmedminorstridebits="0" />
      <decimalpl>0</decimalpl>
      <outputtype>1</outputtype>
      <units>raw_z</units>
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
  </XDFTABLE>
</XDFFORMAT>
""",
        encoding="utf-8",
        newline="\n",
    )
    return xdf, binary


def build_native_text_limit_fixture(root: Path) -> tuple[Path, Path]:
    """Reuse the valid stride fixture with one 1024-byte XML value."""
    xdf, binary = build_positive_stride_fixture(root)
    text = xdf.read_text(encoding="utf-8")
    text = text.replace(
        "<description>Generated regression fixture.</description>",
        f"<description>{'X' * 1024}</description>",
        1,
    )
    xdf.write_text(text, encoding="utf-8", newline="\n")
    return xdf, binary


def build_native_axis_semantics_fixture(root: Path) -> tuple[Path, Path]:
    """Create native-proven literal, implicit, suppressed, and 1x1 axes."""
    root.mkdir(parents=True, exist_ok=True)
    binary = root / "native_axis_semantics.bin"
    xdf = root / "native_axis_semantics.xdf"

    data = bytearray(0x1000)
    struct.pack_into(">2H", data, 0x100, 100, 200)
    struct.pack_into(">2B", data, 0x120, 1, 2)
    struct.pack_into(">2B", data, 0x130, 3, 4)
    struct.pack_into(">3B", data, 0x140, 5, 6, 7)
    struct.pack_into(">B", data, 0x150, 42)
    binary.write_bytes(data)

    xdf.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<XDFFORMAT version="1.70">
  <XDFHEADER>
    <flags>0x1</flags>
    <deftitle>Synthetic native axis semantics</deftitle>
    <description>Regression fixture derived from native TunerPro exports.</description>
    <author>KingAI regression</author>
    <BASEOFFSET offset="0" subtract="0" />
    <DEFAULTS datasizeinbits="8" sigdigits="0" outputtype="1" signed="0" lsbfirst="0" float="0" />
    <REGION type="0xFFFFFFFF" startaddress="0x0" size="0x1000" regionflags="0x0" name="Binary" desc="Synthetic" />
    <CATEGORY index="0x1" name="Regression" />
  </XDFHEADER>
  <XDFTABLE uniqueid="0x10" flags="0x0">
    <title>Implicit Address Is Not An Embedded Axis</title>
    <CATEGORYMEM index="0" category="0x1" />
    <XDFAXIS id="x" uniqueid="0x0">
      <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x100" mmedelementsizebits="16" mmedmajorstridebits="16" mmedminorstridebits="0" />
      <indexcount>2</indexcount>
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="y" uniqueid="0x0">
      <EMBEDDEDDATA mmedelementsizebits="16" mmedmajorstridebits="-32" mmedminorstridebits="0" />
      <indexcount>1</indexcount>
      <LABEL index="0" value="" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="z" uniqueid="0x0">
      <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x120" mmedelementsizebits="8" mmedrowcount="1" mmedcolcount="2" mmedmajorstridebits="0" mmedminorstridebits="0" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
  </XDFTABLE>
  <XDFTABLE uniqueid="0x11" flags="0x0">
    <title>Text Labels Keep Display Metadata</title>
    <CATEGORYMEM index="0" category="0x1" />
    <XDFAXIS id="x" uniqueid="0x0">
      <EMBEDDEDDATA mmedelementsizebits="8" mmedmajorstridebits="0" mmedminorstridebits="0" />
      <indexcount>2</indexcount>
      <LABEL index="0" value="Low" />
      <LABEL index="1" value="High" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="y" uniqueid="0x0">
      <EMBEDDEDDATA mmedelementsizebits="16" mmedmajorstridebits="-32" mmedminorstridebits="0" />
      <indexcount>1</indexcount>
      <LABEL index="0" value="" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="z" uniqueid="0x0">
      <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x130" mmedelementsizebits="8" mmedrowcount="1" mmedcolcount="2" mmedmajorstridebits="0" mmedminorstridebits="0" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
  </XDFTABLE>
  <XDFTABLE uniqueid="0x12" flags="0x0">
    <title>Negative Singleton Axis Is Suppressed</title>
    <CATEGORYMEM index="0" category="0x1" />
    <XDFAXIS id="x" uniqueid="0x0">
      <EMBEDDEDDATA mmedelementsizebits="8" mmedmajorstridebits="0" mmedminorstridebits="0" />
      <indexcount>3</indexcount>
      <LABEL index="0" value="0" />
      <LABEL index="1" value="1" />
      <LABEL index="2" value="2" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="y" uniqueid="0x0">
      <EMBEDDEDDATA mmedelementsizebits="16" mmedmajorstridebits="-32" mmedminorstridebits="0" />
      <indexcount>1</indexcount>
      <LABEL index="0" value="" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="z" uniqueid="0x0">
      <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x140" mmedelementsizebits="8" mmedrowcount="1" mmedcolcount="3" mmedmajorstridebits="0" mmedminorstridebits="0" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
  </XDFTABLE>
  <XDFTABLE uniqueid="0x13" flags="0x0">
    <title>One By One Table</title>
    <CATEGORYMEM index="0" category="0x1" />
    <XDFAXIS id="x" uniqueid="0x0">
      <EMBEDDEDDATA mmedelementsizebits="8" mmedmajorstridebits="0" mmedminorstridebits="0" />
      <indexcount>1</indexcount>
      <LABEL index="0" value="0" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="y" uniqueid="0x0">
      <EMBEDDEDDATA mmedelementsizebits="8" mmedmajorstridebits="0" mmedminorstridebits="0" />
      <indexcount>1</indexcount>
      <LABEL index="0" value="0" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="z" uniqueid="0x0">
      <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x150" mmedelementsizebits="8" mmedrowcount="1" mmedcolcount="1" mmedmajorstridebits="0" mmedminorstridebits="0" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
  </XDFTABLE>
</XDFFORMAT>
""",
        encoding="utf-8",
        newline="\n",
    )
    return xdf, binary


def check_sentinels(
    exported: dict[str, Any], sentinels: tuple[dict[str, Any], ...]
) -> list[str]:
    """Check exact decoded cells so count-only regressions cannot pass silently."""
    tables = exported.get("tables") or []
    failures: list[str] = []
    for sentinel in sentinels:
        title = sentinel["table"]
        matches = [table for table in tables if table.get("title") == title]
        if not matches:
            failures.append(f"missing sentinel table {title!r}")
            continue
        table = matches[0]
        row = int(sentinel["row"])
        col = int(sentinel["col"])
        try:
            actual = table["data"][row][col]
        except (KeyError, IndexError, TypeError) as exc:
            failures.append(f"{title!r} cell [{row}][{col}] unreadable: {exc}")
            continue
        expected = sentinel["value"]
        if actual != expected:
            failures.append(
                f"{title!r} cell [{row}][{col}] expected {expected!r}, got {actual!r}"
            )

        expected_lsb = sentinel.get("lsb_first")
        actual_lsb = (table.get("data_format") or {}).get("lsb_first")
        if expected_lsb is not None and actual_lsb is not expected_lsb:
            failures.append(
                f"{title!r} lsb_first expected {expected_lsb!r}, got {actual_lsb!r}"
            )

        expected_address = sentinel.get("z_address")
        actual_address = ((table.get("axes") or {}).get("z") or {}).get("address")
        if expected_address is not None and actual_address != expected_address:
            failures.append(
                f"{title!r} Z address expected {expected_address!r}, got {actual_address!r}"
            )

        for axis_name in ("x", "y"):
            expected_labels = sentinel.get(f"{axis_name}_labels")
            if expected_labels is None:
                expected_display_labels = sentinel.get(
                    f"{axis_name}_display_labels"
                )
            else:
                actual_labels = (
                    ((table.get("axes") or {}).get(axis_name) or {}).get("labels")
                )
                if actual_labels != expected_labels:
                    failures.append(
                        f"{title!r} {axis_name.upper()} labels expected "
                        f"{expected_labels!r}, got {actual_labels!r}"
                    )
                expected_display_labels = sentinel.get(
                    f"{axis_name}_display_labels"
                )
            if expected_display_labels is None:
                continue
            actual_display_labels = (
                ((table.get("axes") or {}).get(axis_name) or {}).get(
                    "display_labels"
                )
            )
            if actual_display_labels != expected_display_labels:
                failures.append(
                    f"{title!r} {axis_name.upper()} display labels expected "
                    f"{expected_display_labels!r}, got {actual_display_labels!r}"
                )
    return failures


def run_case(case: dict[str, Any], root: Path) -> dict[str, Any]:
    if case.get("synthetic") == "positive_major_stride":
        xdf, binary = build_positive_stride_fixture(root / "fixtures" / case["name"])
    elif case.get("synthetic") == "overlapping_axis_stride":
        xdf, binary = build_overlapping_axis_stride_fixture(
            root / "fixtures" / case["name"]
        )
    elif case.get("synthetic") == "native_text_limit_warning":
        xdf, binary = build_native_text_limit_fixture(
            root / "fixtures" / case["name"]
        )
    elif case.get("synthetic") == "native_axis_semantics":
        xdf, binary = build_native_axis_semantics_fixture(
            root / "fixtures" / case["name"]
        )
    else:
        xdf = Path(case["xdf"])
        binary = Path(case["bin"])
    missing = [str(path) for path in (xdf, binary) if not path.is_file()]
    if missing:
        return {
            "name": case["name"],
            "status": "FAIL",
            "reason": "missing fixture: " + "; ".join(missing),
        }

    output_base = root / case["name"]
    command = [
        sys.executable,
        str(EXPORTER),
        str(xdf),
        str(binary),
        str(output_base),
        "all",
    ]
    completed = subprocess.run(
        command,
        cwd=HERE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if completed.returncode != 0:
        return {
            "name": case["name"],
            "status": "FAIL",
            "reason": f"exporter rc={completed.returncode}",
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
        }

    expected_log_fragment = case.get("expected_log_fragment")
    combined_log = completed.stdout + "\n" + completed.stderr
    if expected_log_fragment and expected_log_fragment not in combined_log:
        return {
            "name": case["name"],
            "status": "FAIL",
            "reason": (
                "missing compatibility warning: "
                f"{expected_log_fragment!r}"
            ),
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
        }

    outputs = {
        "txt": output_base.with_suffix(".txt"),
        "json": output_base.with_suffix(".json"),
        "md": output_base.with_suffix(".md"),
        "csv": output_base.with_suffix(".csv"),
        "zeros": output_base.with_name(output_base.name + "_zeros.md"),
    }
    bad_outputs = [
        f"{kind}:{path}"
        for kind, path in outputs.items()
        if not path.is_file() or path.stat().st_size == 0
    ]
    if bad_outputs:
        return {
            "name": case["name"],
            "status": "FAIL",
            "reason": "missing/empty output: " + "; ".join(bad_outputs),
        }

    try:
        exported = load_json(outputs["json"])
    except Exception as exc:  # report artifact defect without obscuring the case
        return {
            "name": case["name"],
            "status": "FAIL",
            "reason": f"invalid JSON output: {exc}",
        }

    required_sections = ("metadata", "statistics", "scalars", "flags", "tables")
    missing_sections = [name for name in required_sections if name not in exported]
    if missing_sections:
        return {
            "name": case["name"],
            "status": "FAIL",
            "reason": "missing JSON sections: " + ", ".join(missing_sections),
        }

    counts = {
        name: len(exported.get(name) or []) for name in ("scalars", "flags", "tables")
    }
    expected = case.get("expected")
    if expected and counts != expected:
        return {
            "name": case["name"],
            "status": "FAIL",
            "reason": f"count drift: expected {expected}, got {counts}",
        }
    if counts["scalars"] + counts["flags"] + counts["tables"] == 0:
        return {
            "name": case["name"],
            "status": "FAIL",
            "reason": "export contains no scalar, flag, or table elements",
        }

    sentinel_failures = check_sentinels(exported, tuple(case.get("sentinels") or ()))
    if sentinel_failures:
        return {
            "name": case["name"],
            "status": "FAIL",
            "reason": "sentinel drift: " + "; ".join(sentinel_failures),
        }

    metadata = exported.get("metadata") or {}
    source_bin = str(metadata.get("binary_file") or metadata.get("binary") or "")
    if source_bin and binary.name.lower() not in source_bin.lower():
        return {
            "name": case["name"],
            "status": "FAIL",
            "reason": f"JSON source mismatch: {source_bin!r}",
        }

    return {
        "name": case["name"],
        "status": "PASS",
        "counts": counts,
        "csv_rows": count_csv_rows(outputs["csv"]),
        "sizes": {name: path.stat().st_size for name, path in outputs.items()},
    }


def main() -> int:
    args = parse_args()
    selected = [case for case in CASES if not args.case or case["name"] in args.case]
    unknown = sorted(set(args.case) - {case["name"] for case in CASES})
    if unknown:
        print("Unknown case(s): " + ", ".join(unknown), file=sys.stderr)
        return 2
    if not selected:
        print("No cases selected.", file=sys.stderr)
        return 2

    temp_root: Path | None = None
    if args.keep_output:
        output_root = args.keep_output.resolve()
        output_root.mkdir(parents=True, exist_ok=True)
    else:
        temp_root = Path(tempfile.mkdtemp(prefix="kingai_exporter_regression_"))
        output_root = temp_root

    print(f"Exporter: {EXPORTER}")
    print(f"Output:   {output_root}")
    results: list[dict[str, Any]] = []
    try:
        for case in selected:
            print(f"\n--- {case['name']} ---")
            result = run_case(case, output_root)
            results.append(result)
            if result["status"] == "PASS":
                print(f"PASS counts={result['counts']} csv_rows={result['csv_rows']}")
            else:
                print(f"FAIL {result['reason']}")
                if result.get("stderr"):
                    print(result["stderr"])
        passed = sum(result["status"] == "PASS" for result in results)
        failed = len(results) - passed
        print(f"\nPASSED: {passed}  FAILED: {failed}  TOTAL: {len(results)}")
        return 1 if failed else 0
    finally:
        if temp_root is not None:
            resolved = temp_root.resolve()
            safe_parent = Path(tempfile.gettempdir()).resolve()
            if safe_parent in resolved.parents and resolved.name.startswith(
                "kingai_exporter_regression_"
            ):
                shutil.rmtree(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
