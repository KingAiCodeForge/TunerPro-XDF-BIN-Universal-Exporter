#!/usr/bin/env python3
"""
===============================================================================
 KingAI TunerPro XDF + BIN Universal Exporter
===============================================================================
 
 XDF + BIN export helper for regression testing and automation
 
 Supports a broad set of XDF format variations:
 - Standard format (mmedaddress, mmedelementsizebits)
 - Alternative format (mmedtypeflags)
 - Different element types (XDFCONSTANT, XDFFLAG, XDFTABLE, XDFHEADER)
 - Various structural variations (title/table/mem/desc/setups)
 
 Output Format: TunerPro-style text plus automation-friendly exports
 - Clean header with SOURCE FILE and SOURCE DEFINITION
 - SCALAR: format (single line, right-aligned)
 - FLAG: format (simple "Set" or "Not Set")
 - TABLE: format with resolved data for verified XDF/BIN fixtures
   * Complete data matrices (all cell values)
   * X-axis and Y-axis label values displayed
   * Statistical analysis (min/max/avg/unique count)
   * Zero-value detection for mismatched XDF/BIN pairs
   * Suspicious data pattern warnings
 - Optional hex addresses (--addresses flag for XDF creation)
 - Case-insensitive math evaluation
 - Comprehensive validation and error handling
 
 Automation features:
 ✅ Table data extraction for verified fixtures
 ✅ Axis value display when axis data resolves correctly
 ✅ Statistical analysis (min/max/avg for validation)
 ✅ Zero-value detection (catches XDF/BIN mismatches)
 ✅ Data integrity warnings
 ✅ Multiple output formats (TXT, JSON, MD, TEXT)
 needs adding - full xdf meta data and address and constants and cpu address for high and low banked binarys? maybe a v2 for this with more handling 
===============================================================================
 AUTHOR INFORMATION
===============================================================================
 
 Author:       Jason King
 GitHub:       https://github.com/KingAiCodeForge
 Email:        jason.king@kingai.com.au
 
 Project:      KingAI TunerPro Exporter
 Repository:   github.com/KingAiCodeForge/kingai_tunerpro_bin_xdf_combined_export_to_any_document
 
 Company:      KingAi PTY LTD
 Website:      kingai.com.au
 
===============================================================================
 VERSION HISTORY
===============================================================================
 
 v1.0 - Initial release with basic XDF parsing
 v2.0 - Added JSON and Markdown export formats
 v3.0 - Enhanced data extraction, validation, and statistics
 v3.1 - Added author headers, PySide6 GUI support, Windows installer
 
===============================================================================
 LICENSE
===============================================================================
 
 Copyright (c) 2025 KingAI Pty Ltd - Jason King
 
 This software is provided for educational and personal use.
 Commercial use requires written permission from the author.
 
===============================================================================
"""

import xml.etree.ElementTree as ET
import struct
import hashlib
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import re
import sys
import statistics
import json
from datetime import datetime
import io
import csv
from decimal import Decimal, InvalidOperation
from tunerpro_xdf.xdf_addressing import file_offset, table_layout
from tunerpro_xdf.xdf_values import FLOAT_FLAG, read_integer, read_value
from tunerpro_xdf.xdf_equations import EquationError, evaluate_equation

# Fix Windows console encoding for UTF-8 characters.
# Only rewrap a real interactive console. Importing this module must not replace
# a stream that something else owns -- a test harness's captured stdout, or a
# redirect -- because the replacement outlives the owner and tears down as
# "I/O operation on closed file". safe_print() covers the non-console cases.
def _utf8_console(stream):
    """Switch a stream to UTF-8 in place, without taking ownership of it.

    reconfigure() mutates the existing wrapper, so a console and a redirect to a
    file both get UTF-8 while a stream someone else owns (a test harness's
    capture object) is left alone -- replacing it would outlive its owner and
    tear down as "I/O operation on closed file".
    """
    try:
        stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError, io.UnsupportedOperation):
        pass
    return stream


if sys.platform == 'win32':
    sys.stdout = _utf8_console(sys.stdout)
    sys.stderr = _utf8_console(sys.stderr)


def safe_print(text: str):
    """Print text safely, replacing unicode characters that can't be encoded on Windows"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Replace common unicode symbols with ASCII equivalents
        replacements = {
            '✅': '[OK]',
            '❌': '[FAIL]',
            '⚠️': '[WARN]',
            '•': '*',
            '°': 'deg',
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        print(text.encode('ascii', 'replace').decode('ascii'))


def clean_output_text(value: Any) -> str:
    """Normalize common mojibake/replacement symbols for plain evidence exports."""
    if value is None:
        return ""
    text = str(value)
    replacements = {
        "\ufffd": "deg ",
        "Â°": "deg ",
        "°": "deg ",
        "Ã—": "x",
        "×": "x",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    if "deg " in text:
        text = " ".join(text.split())
    return text


__version__ = "3.7.3"  # Shared XDF implementation for exporter and CLI editor.
__author__ = "Jason King"
__author_github__ = "KingAiCodeForge"
__author_alias__ = "kingaustraliagg"  # PCMHacking forum username
__email__ = "jason.king@kingai.com.au"
__copyright__ = "Copyright (c) 2025 KingAI Pty Ltd"

# TunerPro itself does not require a power-of-two BIN. Keep this warning-only
# inventory broad enough for common calibration windows as well as full
# images. In particular, BMW MS42 uses 32 KiB calibration reads and MS45 uses
# 116 KiB (0x1D000) calibration reads alongside their larger full images.
COMMON_BINARY_SIZES = (
    8 * 1024,
    16 * 1024,
    32 * 1024,
    64 * 1024,
    116 * 1024,
    128 * 1024,
    256 * 1024,
    448 * 1024,
    512 * 1024,
    768 * 1024,
    1024 * 1024,
    2 * 1024 * 1024,
    4 * 1024 * 1024,
    8 * 1024 * 1024,
    16 * 1024 * 1024,
)


def is_common_binary_size(size: int) -> bool:
    """Return whether *size* is a commonly encountered ECU image/window."""
    return size in COMMON_BINARY_SIZES


class UniversalXDFExporter:
    """Universal XDF parser and exporter with TunerPro-style output"""
    
    VERSION = __version__
    AUTHOR = __author__
    AUTHOR_GITHUB = __author_github__
    AUTHOR_ALIAS = __author_alias__
    
    def __init__(self, xdf_path: str, bin_path: str):
        """
        Initialize exporter with XDF definition and BIN file
        
        Args:
            xdf_path: Path to XDF definition file
            bin_path: Path to binary ECU firmware file
        """
        self.xdf_path = Path(xdf_path)
        self.bin_path = Path(bin_path)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Storage for parsed data
        self.xdf_root = None
        self.bin_data = None
        self.bin_size = 0
        self.bin_md5 = ""
        
        # XDF metadata
        self.definition_name = "Unknown"
        self.categories = {}
        # CATEGORYMEM IDs are stored either as CATEGORY indices or as
        # one-based references (CATEGORY index + 1), depending on the XDF.
        # _extract_categories() detects the convention once per file.
        self.category_member_offset = 0
        self.elements = {
            'constants': [],
            'flags': [],
            'tables': [],
            'patches': []  # XDFPATCH elements (Community Patchlist support)
        }
        
        # BASEOFFSET handling for 512KB and other large bin files
        # When subtract=0: file_address = xdf_address + base_offset (offset is added to XDF address)
        # When subtract=1: file_address = xdf_address - base_offset (XDF addresses are memory-mapped)
        self.base_offset = 0
        self.base_subtract = 0  # 0 or 1
        
        # Index of elements by uniqueid for embedinfo axis linking (MS42/MS43 style XDFs)
        self.uniqueid_index = {}
        
        # Validation statistics
        self.validation_warnings = []
        self.suspicious_tables = []
        
        # Output options
        self.show_addresses = False  # Show hex addresses in output
        self.flip_rpm = False        # Flip Y-axis (RPM: high→low)
        self.flip_load = False       # Flip X-axis (load: high→low)
        self.no_stats = False        # Omit statistics from output
        self.zeros_export = True     # Export zeros report (default ON)
    
    def _format_value(self, value: float, decimalpl: int = 2) -> str:
        """
        Format a numeric value with correct decimal places
        
        Args:
            value: The numeric value to format
            decimalpl: Number of decimal places (from XDF)
            
        Returns:
            str: Formatted value string
        """
        if decimalpl <= 0:
            return str(int(round(value)))
        return f"{value:.{decimalpl}f}"

    def _apply_axis_flips(self, table_data, axes):
        """
        Apply --flip-rpm and --flip-load axis transforms.

        Reverses axis labels and corresponding data rows/columns
        so the presentation order changes without altering raw data.

        Args:
            table_data: 2D list of floats (rows x cols)
            axes: dict with 'x', 'y', 'z' axis info

        Returns:
            tuple: (flipped_data, flipped_axes)
        """
        import copy
        data = [list(row) for row in table_data]
        ax = copy.deepcopy(axes)

        # Flip Y-axis (RPM) → reverse row order
        if self.flip_rpm and 'y' in ax:
            data = list(reversed(data))
            if ax['y'].get('labels'):
                ax['y']['labels'] = list(
                    reversed(ax['y']['labels']))
            if ax['y'].get('display_labels'):
                ax['y']['display_labels'] = list(
                    reversed(ax['y']['display_labels']))

        # Flip X-axis (load) → reverse column order
        if self.flip_load and 'x' in ax:
            data = [list(reversed(row)) for row in data]
            if ax['x'].get('labels'):
                ax['x']['labels'] = list(
                    reversed(ax['x']['labels']))
            if ax['x'].get('display_labels'):
                ax['x']['display_labels'] = list(
                    reversed(ax['x']['display_labels']))

        return data, ax
        
    def validate_bin_file(self) -> bool:
        """
        Validate binary file integrity
        
        Returns:
            bool: True if valid, False otherwise
        """
        if not self.bin_path.exists():
            self.logger.error(f"Binary file not found: {self.bin_path}")
            return False
        
        # Read binary data
        try:
            with open(self.bin_path, 'rb') as f:
                self.bin_data = f.read()
                self.bin_size = len(self.bin_data)
        except Exception as e:
            self.logger.error(f"Failed to read binary: {e}")
            return False
        
        # Calculate MD5
        self.bin_md5 = hashlib.md5(self.bin_data).hexdigest()
        
        # Validate size
        if not is_common_binary_size(self.bin_size):
            self.logger.warning(
                f"Unusual binary size: {self.bin_size} bytes. "
                "TunerPro may still use it; verify the XDF address window."
            )
        
        self.logger.info(
            f"Binary validated: {self.bin_size} bytes, "
            f"MD5: {self.bin_md5}"
        )
        return True
    
    def parse_xdf(self) -> bool:
        """
        Parse XDF file and extract all elements
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.xdf_path.exists():
            self.logger.error(f"XDF file not found: {self.xdf_path}")
            return False
        
        try:
            tree = ET.parse(self.xdf_path)
            self.xdf_root = tree.getroot()
        except ET.ParseError as e:
            # BUG FIX #13: Handle non-UTF-8 XDF files (e.g. German XDFs with
            # Latin-1 encoded characters like ° 0xB0, ü 0xFC, etc.)
            # Re-read as Latin-1, encode to UTF-8, then parse from string
            raw = self.xdf_path.read_bytes()
            try:
                text = raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = raw.decode('latin-1')

            if self._looks_like_legacy_text_xdf(text):
                try:
                    self.xdf_root = self._parse_legacy_text_xdf(text)
                    self.logger.info(
                        "Legacy TunerPro text XDF detected and normalized: %s",
                        self.xdf_path.name,
                    )
                except ValueError as legacy_error:
                    self.logger.error(
                        "Failed to parse legacy TunerPro text XDF: %s",
                        legacy_error,
                    )
                    return False
            else:
                self.logger.warning(
                    f"XML parse failed ({e}), retrying with Latin-1 encoding..."
                )
                try:
                    text = raw.decode('latin-1')
                    text = re.sub(
                        r'<\?xml[^?]*\?>',
                        '<?xml version="1.0" encoding="utf-8"?>',
                        text,
                        count=1,
                    )
                    self.xdf_root = ET.fromstring(text)
                except Exception as e2:
                    self.logger.error(
                        f"Failed to parse XDF even with Latin-1 fallback: {e2}"
                    )
                    return False

        # Extract all elements (universal approach). During extraction, defer a
        # dangling VAR link (a defect in some community XDFs) so one bad element
        # does not abort the whole file; the strict read-time path still reports
        # it per element.
        self._lenient_links = True
        try:
            self._extract_header()
            self._extract_categories()
            self._build_uniqueid_index()
            self._extract_constants()
            self._extract_flags()
            self._extract_tables()
            self._extract_patches()
        except ValueError as exc:
            self.logger.error("Cannot resolve XDF conversion: %s", exc)
            return False
        finally:
            self._lenient_links = False
        
        self.logger.info(
            f"Parsed XDF: {len(self.elements['constants'])} constants, "
            f"{len(self.elements['flags'])} flags, "
            f"{len(self.elements['tables'])} tables, "
            f"{len(self.elements['patches'])} patches"
        )
        
        return True

    @staticmethod
    def _looks_like_legacy_text_xdf(text: str) -> bool:
        """Return True for TunerPro 1.x block-oriented text definitions."""
        prefix = text.lstrip('\ufeff\x00 \t\r\n')
        return (
            prefix.startswith('XDF')
            and '%%HEADER%%' in prefix
            and '%%END%%' in prefix
        )

    @staticmethod
    def _legacy_text_value(raw_value: str) -> str:
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            return value[1:-1].replace(r'\"', '"')
        return value

    @classmethod
    def _legacy_int(cls, raw_value: str, default: int = 0) -> int:
        value = cls._legacy_text_value(raw_value)
        if not value.strip():
            return default
        try:
            return int(value, 0)
        except ValueError:
            try:
                number = Decimal(value)
            except InvalidOperation as exc:
                raise ValueError(f'Invalid legacy XDF integer: {raw_value!r}') from exc
            if not number.is_finite() or number != number.to_integral_value():
                raise ValueError(f'Invalid legacy XDF integer: {raw_value!r}')
            return int(number)

    @classmethod
    def _legacy_equation(cls, raw_value: str) -> str:
        """Remove the old text format's trailing display metadata."""
        equation = cls._legacy_text_value(raw_value)
        display_suffix = re.search(r',T[A-Z0-9]*\|', equation, re.IGNORECASE)
        if display_suffix:
            equation = equation[:display_suffix.start()]
        return equation.strip() or 'X'

    @classmethod
    def _legacy_labels(cls, raw_value: str) -> List[str]:
        value = cls._legacy_text_value(raw_value)
        if not value:
            return []
        try:
            return [item.strip() for item in next(csv.reader([value]))]
        except (csv.Error, StopIteration):
            return [item.strip() for item in value.split(',')]

    @classmethod
    def _parse_legacy_text_xdf(cls, text: str) -> ET.Element:
        """Normalize a TunerPro 1.11 text XDF into the existing XML model.

        The adapter handles the primitive block types consumed by this
        exporter: HEADER, TABLE, CONSTANT, and FLAG. XML definitions never
        pass through this adapter.
        """
        block_re = re.compile(r'^%%([A-Z]+)%%$')
        field_re = re.compile(
            r'^\s*\d{6}\s+([A-Za-z][A-Za-z0-9]*)\s*=(.*)$'
        )
        blocks: List[Tuple[str, Dict[str, str]]] = []
        current_type: Optional[str] = None
        current_fields: Dict[str, str] = {}

        for raw_line in text.splitlines():
            line = raw_line.strip()
            marker = block_re.match(line)
            if marker:
                marker_type = marker.group(1)
                if marker_type == 'END':
                    if current_type is not None:
                        blocks.append((current_type, current_fields))
                    current_type = None
                    current_fields = {}
                else:
                    if current_type is not None:
                        blocks.append((current_type, current_fields))
                    current_type = marker_type
                    current_fields = {}
                continue

            if current_type is None:
                continue
            field = field_re.match(raw_line)
            if field:
                current_fields[field.group(1)] = field.group(2).strip()

        if current_type is not None:
            blocks.append((current_type, current_fields))

        headers = [fields for kind, fields in blocks if kind == 'HEADER']
        if not headers:
            raise ValueError('missing %%HEADER%% block')

        preamble = [line.strip() for line in text.splitlines()[:5]]
        source_version = next(
            (line for line in preamble if re.fullmatch(r'\d+\.\d+', line)),
            '1.x',
        )
        root = ET.Element(
            'XDFFORMAT',
            {'version': '1.70', 'legacy_source_version': source_version},
        )

        header_fields = headers[0]
        header = ET.SubElement(root, 'XDFHEADER')
        ET.SubElement(header, 'deftitle').text = cls._legacy_text_value(
            header_fields.get('DefTitle', 'Legacy TunerPro definition')
        )
        ET.SubElement(header, 'description').text = cls._legacy_text_value(
            header_fields.get('Desc', '')
        )
        ET.SubElement(header, 'author').text = cls._legacy_text_value(
            header_fields.get('Author', '')
        )
        base_offset = cls._legacy_int(header_fields.get('BaseOffset', '0'))
        ET.SubElement(
            header,
            'BASEOFFSET',
            {
                'offset': str(abs(base_offset)),
                'subtract': '1' if base_offset < 0 else '0',
            },
        )

        def add_text(parent: ET.Element, tag: str, value: str) -> ET.Element:
            child = ET.SubElement(parent, tag)
            child.text = cls._legacy_text_value(value)
            return child

        def add_math(parent: ET.Element, raw_equation: str) -> None:
            math_element = ET.SubElement(
                parent,
                'MATH',
                {'equation': cls._legacy_equation(raw_equation)},
            )
            ET.SubElement(math_element, 'VAR', {'id': 'X'})

        def storage_bits(fields: Dict[str, str]) -> int:
            return max(1, cls._legacy_int(fields.get('SizeInBits', '8'), 8))

        def axis_storage_bits(fields: Dict[str, str], axis: str) -> int:
            raw_size = cls._legacy_int(fields.get(f'{axis}DataSize', '1'), 1)
            # Legacy X/YDataSize stores bytes; tolerate already-bit-sized files.
            return raw_size * 8 if raw_size in (1, 2, 4) else max(1, raw_size)

        def add_axis(
            table: ET.Element,
            fields: Dict[str, str],
            axis_id: str,
            count: int,
        ) -> None:
            prefix = axis_id.upper()
            axis = ET.SubElement(table, 'XDFAXIS', {'id': axis_id})
            address = fields.get(f'{prefix}Address')
            size_bits = axis_storage_bits(fields, prefix)
            step_bytes = cls._legacy_int(
                fields.get(f'{prefix}AddrStep', str(max(1, size_bits // 8))),
                max(1, size_bits // 8),
            )
            embedded_attributes = {
                'mmedtypeflags': '0x00',
                'mmedelementsizebits': str(size_bits),
                'mmedmajorstridebits': str(step_bytes * 8),
                'mmedminorstridebits': '0',
            }
            if address:
                embedded_attributes['mmedaddress'] = cls._legacy_text_value(address)
            ET.SubElement(axis, 'EMBEDDEDDATA', embedded_attributes)
            add_text(axis, 'indexcount', str(count))
            add_text(axis, 'decimalpl', '0')
            add_text(axis, 'units', fields.get(f'{prefix}Units', ''))
            for label in cls._legacy_labels(fields.get(f'{prefix}Labels', '')):
                ET.SubElement(axis, 'LABEL', {'value': label})
            if address:
                ET.SubElement(axis, 'embedinfo', {'type': '1'})
            add_math(axis, fields.get(f'{prefix}Eq', 'X'))

        for block_type, fields in blocks:
            if block_type == 'TABLE':
                table = ET.SubElement(
                    root,
                    'XDFTABLE',
                    {
                        'uniqueid': cls._legacy_text_value(
                            fields.get('UniqueID', '0')
                        ),
                        'flags': cls._legacy_text_value(fields.get('Flags', '0')),
                    },
                )
                add_text(table, 'title', fields.get('Title', 'Unknown'))
                add_text(table, 'description', fields.get('Desc', ''))
                add_text(table, 'decimalpl', '0')

                rows = max(1, cls._legacy_int(fields.get('Rows', '1'), 1))
                cols = max(1, cls._legacy_int(fields.get('Cols', '1'), 1))
                add_axis(table, fields, 'x', cols)
                add_axis(table, fields, 'y', rows)

                z_size = storage_bits(fields)
                z_axis = ET.SubElement(table, 'XDFAXIS', {'id': 'z'})
                z_attributes = {
                    'mmedtypeflags': '0x00',
                    'mmedelementsizebits': str(z_size),
                    'mmedrowcount': str(rows),
                    'mmedcolcount': str(cols),
                    # Legacy contiguous tables need default storage strides;
                    # row width is not TunerPro's major-stride definition.
                    'mmedmajorstridebits': '0',
                    'mmedminorstridebits': '0',
                }
                if fields.get('Address'):
                    z_attributes['mmedaddress'] = cls._legacy_text_value(
                        fields['Address']
                    )
                ET.SubElement(z_axis, 'EMBEDDEDDATA', z_attributes)
                add_text(z_axis, 'indexcount', str(rows * cols))
                add_text(z_axis, 'decimalpl', '0')
                add_text(z_axis, 'units', fields.get('ZUnits', ''))
                add_math(z_axis, fields.get('ZEq', 'X'))

            elif block_type == 'CONSTANT':
                constant = ET.SubElement(
                    root,
                    'XDFCONSTANT',
                    {
                        'uniqueid': cls._legacy_text_value(
                            fields.get('UniqueID', '0')
                        )
                    },
                )
                add_text(constant, 'title', fields.get('Title', 'Unknown'))
                add_text(constant, 'description', fields.get('Desc', ''))
                add_text(constant, 'decimalpl', '0')
                add_text(constant, 'units', fields.get('Units', ''))
                attributes = {
                    'mmedtypeflags': '0x00',
                    'mmedelementsizebits': str(storage_bits(fields)),
                    'mmedmajorstridebits': '0',
                    'mmedminorstridebits': '0',
                }
                if fields.get('Address'):
                    attributes['mmedaddress'] = cls._legacy_text_value(
                        fields['Address']
                    )
                ET.SubElement(constant, 'EMBEDDEDDATA', attributes)
                add_math(constant, fields.get('Equation', 'X'))

            elif block_type == 'FLAG':
                address = cls._legacy_text_value(fields.get('Address', ''))
                flag_attributes = {
                    'uniqueid': cls._legacy_text_value(
                        fields.get('UniqueID', '0')
                    )
                }
                if address:
                    flag_attributes['address'] = address
                flag = ET.SubElement(root, 'XDFFLAG', flag_attributes)
                add_text(flag, 'title', fields.get('Title', 'Unknown'))
                add_text(flag, 'description', fields.get('Desc', ''))
                bit_number = cls._legacy_int(fields.get('BitNumber', '0'))
                add_text(flag, 'mask', hex(1 << max(0, bit_number)))

        return root

    def _extract_header(self):
        """Extract definition name and BASEOFFSET from XDF header"""
        header = self.xdf_root.find('.//XDFHEADER')
        if header is not None:
            # Try multiple possible tags for definition name
            for tag in ['deftitle', 'title', 'name']:
                elem = header.find(tag)
                if elem is not None and elem.text:
                    self.definition_name = elem.text.strip()
                    break
            
            # Extract BASEOFFSET - critical for 512KB and full-dump bin files
            # Format 1: <BASEOFFSET offset="294912" subtract="0" />
            baseoffset = header.find('.//BASEOFFSET')
            if baseoffset is not None:
                self.base_offset = self._metadata_integer(baseoffset, 'offset', 0)
                self.base_subtract = self._metadata_integer(baseoffset, 'subtract', 0)
                if self.base_subtract not in (0, 1):
                    raise ValueError('BASEOFFSET subtract must be 0 or 1')
                    
                if self.base_offset != 0:
                    self.logger.info(f"BASEOFFSET detected: offset={self.base_offset} (0x{self.base_offset:X}), subtract={self.base_subtract}")
            
            # Format 2: <baseoffset>0</baseoffset> (lowercase simple format)
            if self.base_offset == 0:
                baseoffset_simple = header.find('.//baseoffset')
                if baseoffset_simple is not None and baseoffset_simple.text:
                    offset_text = baseoffset_simple.text.strip()
                    self.base_offset = self._metadata_number(offset_text, 'baseoffset')
                    if self.base_offset != 0:
                        self.logger.info(f"BASEOFFSET (simple format) detected: offset={self.base_offset} (0x{self.base_offset:X})")
    
    def _extract_categories(self):
        """Extract categories and detect this XDF's membership-ID convention."""
        for cat in self.xdf_root.findall('.//CATEGORY'):
            index = cat.get('index')
            name = cat.get('name', 'Unknown')
            if index:
                # Handle hex or decimal index
                try:
                    idx = int(index, 16) if index.lower().startswith('0x') else int(index)
                    self.categories[idx] = name
                except ValueError:
                    self.logger.warning(f"Ignoring invalid CATEGORY index: {index!r}")

        # TunerPro files in the wild use both direct CATEGORY indices and
        # one-based CATEGORYMEM references.  Select the interpretation that
        # resolves the most memberships in this file; ties retain the legacy
        # direct interpretation so existing direct-ID definitions do not move.
        direct_matches = 0
        one_based_matches = 0
        for cat_mem in self.xdf_root.findall('.//CATEGORYMEM'):
            raw_value = cat_mem.get('category')
            if not raw_value:
                continue
            try:
                member_id = (
                    int(raw_value, 16)
                    if raw_value.lower().startswith('0x')
                    else int(raw_value)
                )
            except ValueError:
                continue
            direct_matches += member_id in self.categories
            one_based_matches += (member_id - 1) in self.categories

        if one_based_matches > direct_matches:
            self.category_member_offset = -1
            self.logger.info(
                "CATEGORYMEM uses one-based category IDs "
                f"({one_based_matches} resolved vs {direct_matches} direct)"
            )
    
    @staticmethod
    def _is_unassigned_uniqueid(uid):
        """Zero IDs are unassigned placeholders, never usable link targets."""
        try:
            return int(uid, 16 if uid.strip().lower().startswith('0x') else 10) == 0
        except ValueError:
            return False

    def _build_uniqueid_index(self):
        """
        Build index of all elements by uniqueid for embedinfo axis linking.
        
        MS42/MS43 XDFs use embedinfo to link axes to shared axis tables.
        Example: <embedinfo type="3" linkobjid="0xAA0D" />
        This links to a table with uniqueid="0xAA0D" containing axis values.
        
        This index allows O(1) lookup of linked elements.
        """
        self.uniqueid_index = {}
        # Index all XDFTABLE elements
        for table in self.xdf_root.findall('.//XDFTABLE'):
            uid = table.get('uniqueid')
            if uid and not self._is_unassigned_uniqueid(uid):
                if uid in self.uniqueid_index:
                    raise ValueError(f"Duplicate XDF uniqueid {uid!r}; linked values are ambiguous")
                self.uniqueid_index[uid] = table
        
        # Index all XDFCONSTANT elements (scalars can be axis sources too)
        for const in self.xdf_root.findall('.//XDFCONSTANT'):
            uid = const.get('uniqueid')
            if uid and not self._is_unassigned_uniqueid(uid):
                if uid in self.uniqueid_index:
                    raise ValueError(f"Duplicate XDF uniqueid {uid!r}; linked values are ambiguous")
                self.uniqueid_index[uid] = const
        
        if self.uniqueid_index:
            self.logger.info(
                f"Built uniqueid index: {len(self.uniqueid_index)} elements "
                f"(embedinfo axis linking enabled)"
            )
    
    def _resolve_linked_vars_lenient(self, math_elem) -> Dict[str, float]:
        """Extraction-time link resolution that does not abort the whole file.

        A single element whose MATH links to a missing XDF object (a dangling
        VAR link - a genuine authoring defect in some community XDFs) must not
        prevent every other element from parsing. Return {} here; the strict
        read-time path (linked_vars_for) still raises for that one element, which
        run_diagnostics catches and reports as a per-element decode_error.
        """
        try:
            return self._resolve_linked_vars(math_elem)
        except EquationError as exc:
            self.logger.warning("Deferring dangling XDF link at parse: %s", exc)
            return {}

    def _resolve_linked_vars(self, math_elem, _seen=()) -> Dict[str, float]:
        """Resolve scalar VAR links; during parse, defer a dangling link.

        While `self._lenient_links` is set (only during element extraction), a
        VAR that links to a missing XDF object returns {} with a warning instead
        of aborting the whole file. The strict read-time path leaves the flag
        off, so run_diagnostics still catches and reports that one element.
        """
        if getattr(self, '_lenient_links', False) and not _seen:
            try:
                return self._resolve_linked_vars_strict(math_elem, _seen)
            except EquationError as exc:
                self.logger.warning("Deferring dangling XDF link at parse: %s", exc)
                return {}
        return self._resolve_linked_vars_strict(math_elem, _seen)

    def _resolve_linked_vars_strict(self, math_elem, _seen=()) -> Dict[str, float]:
        """Resolve scalar VAR links recursively, refusing absent or circular sources."""
        if math_elem is None:
            return {}
        if len(_seen) >= 32:
            raise EquationError("XDF variable link depth exceeds 32")
        result = {}
        for var in math_elem.findall('VAR'):
            name, kind = var.get('id', ''), var.get('type', '')
            if not kind:
                continue
            if kind == 'address':
                # A fixed absolute BIN address, not a link to another XDF
                # object -- e.g. <VAR id="Y" type="address" address="0x6003" />
                # used to test a config-byte bit: "if ((Y>>7)&0x01) > 0 ...".
                # Address variables default to a single unsigned byte; an
                # explicit sizeinbits/signed override is honored when supplied.
                addr_str = var.get('address', '')
                try:
                    addr = int(addr_str, 16) if addr_str.lower().startswith('0x') \
                        else int(addr_str)
                except ValueError:
                    raise EquationError(f"VAR {name!r} has an unparseable address {addr_str!r}")
                size_bits = int(var.get('sizeinbits', 8))
                signed = var.get('signed', '0') not in ('0', '', None)
                raw = self.read_value_from_bin(addr, size_bits, signed, False)
                if raw is None:
                    raise EquationError(f"VAR {name!r} address 0x{addr:X} is outside the BIN")
                result[name] = raw
                continue
            if kind != 'link':
                raise EquationError(f"VAR {name!r} uses unsupported source type {kind!r}")
            uid = var.get('linkid', '')
            if uid in _seen:
                raise EquationError(f"Circular XDF VAR link: {' -> '.join((*_seen, uid))}")
            target = self.uniqueid_index.get(uid)
            if target is None:
                raise EquationError(f"VAR {name!r} links to missing XDF object {uid!r}")
            if target.tag != 'XDFCONSTANT':
                raise EquationError(f"VAR {name!r} links to {target.tag}; a scalar source is required")
            storage = self._parse_embedded_data(target)
            self._require_integer_storage(storage)
            if storage['address'] is None:
                raise EquationError(f"VAR {name!r} source {uid} has no BIN address")
            raw = self.read_value_from_bin(storage['address'], storage['size_bits'],
                storage['signed'], storage['lsb_first'], storage.get('is_float', False))
            if raw is None:
                raise EquationError(f"VAR {name!r} source {uid} is outside the BIN")
            conversion = target.find('MATH')
            linked = self._resolve_linked_vars(conversion, (*_seen, uid))
            equation = conversion.get('equation', '') if conversion is not None else ''
            result[name] = self.evaluate_math(equation, raw, linked_vars=linked)[0]
        return result
    
    def _resolve_embedinfo_axis(self, axis_elem) -> List[float]:
        """Read linked breakpoints through the source table's shared reader."""
        info = axis_elem.find('embedinfo')
        if info is None or info.get('type') != '3':
            return []
        uid = info.get('linkobjid', '')
        if not uid:
            raise EquationError('Embedded-axis link has no source object ID')
        target = self.uniqueid_index.get(uid)
        if target is None:
            raise EquationError(f"Missing embedded-axis source {uid!r}")
        active = getattr(self, '_axis_link_stack', ())
        if uid in active or len(active) >= 32:
            raise EquationError(f"Circular or excessive embedded-axis link {uid!r}")
        self._axis_link_stack = (*active, uid)
        try:
            if target.tag == 'XDFCONSTANT':
                storage = self._parse_embedded_data(target)
                conversion = target.find('MATH')
                item = dict(storage, size=storage['size_bits'], title=self._get_title(target),
                            equation=conversion.get('equation', '') if conversion is not None else '',
                            math_element=conversion)
                values = [self.read_constant(item)[1]]
            elif target.tag == 'XDFTABLE':
                axes = {}
                for axis in target.findall('XDFAXIS'):
                    storage = self._parse_embedded_data(axis)
                    conversion = axis.find('MATH')
                    axes[axis.get('id')] = dict(storage, count=int(axis.findtext('indexcount', '1')),
                        equation=conversion.get('equation', '') if conversion is not None else '',
                        math_element=conversion, xml_element=axis)
                data = self._read_table_data({'title': self._get_title(target), 'axes': axes})
                if data is None:
                    raise EquationError(f"Embedded-axis source {uid!r} cannot be read")
                values = [value for row in data for value in row]
            else:
                raise EquationError(f"Unsupported embedded-axis source type {target.tag}")
            count = int(axis_elem.findtext('indexcount', str(len(values))))
            if count < 1:
                raise EquationError('Embedded-axis count must be positive')
            if count > len(values):
                raise EquationError(f"Embedded-axis source {uid!r} has {len(values)} values; {count} required")
            return values
        finally:
            self._axis_link_stack = active
    
    def _extract_direct_labels(self, axis_elem) -> List[float]:
        """
        Extract LABEL values directly without embedinfo resolution.
        Helper for _resolve_embedinfo_axis fallback.
        """
        labels = []
        for label_elem in axis_elem.findall('.//LABEL'):
            value_str = label_elem.get('value', '')
            if value_str:
                try:
                    labels.append(float(value_str))
                except ValueError:
                    pass
        return labels

    def _get_address(self, element) -> Optional[int]:
        """
        Universal address extraction - handles all XDF variations
        
        Tries multiple methods:
        1. EMBEDDEDDATA mmedaddress attribute
        2. EMBEDDEDDATA mmedtypeflags with address
        3. Direct address attribute
        4. mem/memory child element
        
        Args:
            element: XML element to extract address from
            
        Returns:
            int: Address or None if not found
        """
        # Method 1: EMBEDDEDDATA with mmedaddress
        embedded = element.find('.//EMBEDDEDDATA')
        if embedded is not None:
            addr = embedded.get('mmedaddress')
            if addr is not None:
                return self._metadata_number(addr, 'mmedaddress')
            
            # Check for mmedtypeflags format
            if embedded.get('mmedtypeflags'):
                addr = embedded.get('mmedaddress')
                if addr:
                    try:
                        return int(addr, 16) if addr.startswith('0x') else int(addr)
                    except ValueError:
                        pass
        
        # Method 2: Direct address attribute
        addr = element.get('address')
        if addr is not None:
            return self._metadata_number(addr, 'address')
        
        # Method 3: mem/memory child element
        for tag in ['mem', 'memory', 'addr']:
            mem = element.find(f'.//{tag}')
            if mem is not None and mem.text:
                return self._metadata_number(mem.text, tag)
        
        return None
    
    @staticmethod
    def _metadata_number(value: str, field: str) -> int:
        try:
            text = value.strip()
            return int(text, 16) if text.lower().startswith(('0x', '-0x', '+0x')) else int(text)
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"Invalid XDF {field}: {value!r}") from exc

    @classmethod
    def _metadata_integer(cls, element, field: str, default: int) -> int:
        value = element.get(field)
        return default if value is None else cls._metadata_number(value, field)

    def _parse_embedded_data(self, element) -> Dict:
        """
        Parse EMBEDDEDDATA attributes for address, size, signedness, and endianness
        
        XDF mmedtypeflags bit meanings (TunerPro spec):
        - Bit 0 (0x01): Signed value. If not set, unsigned
        - Bit 1 (0x02): LSB first (little-endian). If not set, MSB first (big-endian)
        - Other bits: Various flags (row/col major, etc.)
        
        Args:
            element: XML element containing EMBEDDEDDATA
            
        Returns:
            Dict with keys: address, size_bits, signed, lsb_first, row_count, col_count
        """
        result = {
            'address': None,
            'storage_attributes': {},
            'type_flags': 0,
            'size_bits': 8,
            'signed': False,
            'lsb_first': False,  # False = big-endian (MSB first)
            'is_float': False,
            'row_count': 1,
            'col_count': 1,
            'major_stride': 0,
            'minor_stride': 0
        }
        
        embedded = element.find('.//EMBEDDEDDATA')
        if embedded is None:
            return result
        result['storage_attributes'] = dict(embedded.attrib)
        
        # Address
        addr_str = embedded.get('mmedaddress')
        if addr_str is not None:
            result['address'] = self._metadata_number(addr_str, 'mmedaddress')
        elif element.tag == 'XDFCONSTANT' and element.find('EMBEDDEDDATA') is embedded:
            # A constant with explicit storage defaults an omitted address to
            # zero. Constants without storage remain section headings.
            result['address'] = 0
        
        # Size in bits
        result['size_bits'] = self._metadata_integer(embedded, 'mmedelementsizebits', 8)
        
        # Type flags (signedness and endianness)
        # TunerPro XDF spec: Bit 0 = Signed, Bit 1 = LSB first (little-endian)
        # 0x00 = Unsigned MSB, 0x01 = Signed MSB, 0x02 = Unsigned LSB, 0x03 = Signed + LSB
        flags = self._metadata_integer(embedded, 'mmedtypeflags', 0)
        result['type_flags'] = flags
        result['signed'] = bool(flags & 0x01)
        result['lsb_first'] = bool(flags & 0x02)
        result['is_float'] = bool(flags & FLOAT_FLAG)
        
        # Row/column counts for tables
        result['row_count'] = self._metadata_integer(embedded, 'mmedrowcount', 1)
        result['col_count'] = self._metadata_integer(embedded, 'mmedcolcount', 1)
        
        # Strides for non-contiguous data
        # BUG FIX #6: Support NEGATIVE strides (BMW backwards addressing)
        result['major_stride'] = self._metadata_integer(embedded, 'mmedmajorstridebits', 0)
        result['minor_stride'] = self._metadata_integer(embedded, 'mmedminorstridebits', 0)
        
        return result
    
    def _get_element_size(self, element) -> int:
        """
        Get element size in bits (legacy method, kept for compatibility)
        
        Args:
            element: XML element
            
        Returns:
            int: Size in bits (default 8)
        """
        embedded_data = self._parse_embedded_data(element)
        return embedded_data['size_bits']
    
    def _xdf_addr_to_file_offset(self, xdf_address: int) -> int:
        """Translate BASEOFFSET without substituting a different address."""
        return file_offset(xdf_address, self.base_offset, self.base_subtract)
    
    def _get_title(self, element) -> str:
        """
        Universal title extraction
        
        Args:
            element: XML element
            
        Returns:
            str: Title or "Unknown"
        """
        # Try multiple possible tags
        for tag in ['title', 'name', 'label', 'desc']:
            elem = element.find(f'.//{tag}')
            if elem is not None and elem.text:
                return elem.text.strip()
        
        return "Unknown"
    
    def _get_category_name(self, element) -> str:
        """
        Get category name for element
        
        Args:
            element: XML element
            
        Returns:
            str: Category name
        """
        cat_mem = element.find('.//CATEGORYMEM')
        if cat_mem is not None:
            cat_idx = cat_mem.get('category')
            if cat_idx:
                try:
                    idx = int(cat_idx, 16) if cat_idx.lower().startswith('0x') else int(cat_idx)
                    idx += self.category_member_offset
                    return self.categories.get(idx, 'Unknown')
                except ValueError:
                    pass
        return 'Uncategorized'
    
    def _extract_constants(self):
        """Extract all constants (SCALAR values) with bug fixes"""
        for const in self.xdf_root.findall('.//XDFCONSTANT'):
            # Parse embedded data for full info
            embedded = self._parse_embedded_data(const)
            address = embedded['address']
            
            # BUG FIX #5: Validate address exists before processing
            if address is None:
                title = self._get_title(const)
                embedded_elem = const.find('.//EMBEDDEDDATA')
                declared_address = (
                    embedded_elem.get('mmedaddress')
                    if embedded_elem is not None
                    else None
                )
                if declared_address:
                    self.logger.warning(
                        "Constant %r declares address %r but it could not be parsed; "
                        "skipping",
                        title,
                        declared_address,
                    )
                else:
                    # Antus/legacy XDFs intentionally use addressless
                    # XDFCONSTANT elements as visual section headings.
                    self.logger.debug(
                        "Skipping addressless XDF section heading %r", title
                    )
                continue
            
            title = self._get_title(const)
            category = self._get_category_name(const)
            
            # Get unit
            unit_elem = const.find('.//units')
            unit = clean_output_text(unit_elem.text.strip()) if unit_elem is not None and unit_elem.text else ""
            
            # Get math equation
            math_elem = const.find('.//MATH')
            equation = None
            linked_vars = {}
            if math_elem is not None:
                equation = math_elem.get('equation', '')
                linked_vars = self._resolve_linked_vars_lenient(math_elem)
            
            # Get decimal places for precision (BUG FIX #9)
            decimalpl = 2  # Default
            dec_elem = const.find('.//decimalpl')
            if dec_elem is not None and dec_elem.text:
                try:
                    decimalpl = int(dec_elem.text.strip())
                except ValueError:
                    pass
            
            # BUG FIX #8: Extract range validation metadata
            min_val = None
            max_val = None
            rangelow_elem = const.find('.//rangelow')
            rangehigh_elem = const.find('.//rangehigh')
            
            if rangelow_elem is not None and rangelow_elem.text:
                try:
                    min_val = float(rangelow_elem.text.strip())
                except ValueError:
                    pass
            if rangehigh_elem is not None and rangehigh_elem.text:
                try:
                    max_val = float(rangehigh_elem.text.strip())
                except ValueError:
                    pass
            
            # Legacy min/max tags (fallback)
            if min_val is None:
                min_elem = const.find('.//min')
                if min_elem is not None and min_elem.text:
                    try:
                        min_val = float(min_elem.text.strip())
                    except ValueError:
                        pass
            if max_val is None:
                max_elem = const.find('.//max')
                if max_elem is not None and max_elem.text:
                    try:
                        max_val = float(max_elem.text.strip())
                    except ValueError:
                        pass
            
            self.elements['constants'].append({
                'title': title,
                'math_element': math_elem,
                'uniqueid': const.get('uniqueid'),
                'address': address,
                'size': embedded['size_bits'],
                'type_flags': embedded['type_flags'],
                'storage_attributes': embedded['storage_attributes'],
                'signed': embedded['signed'],
                'lsb_first': embedded['lsb_first'],
                'is_float': embedded['is_float'],
                'unit': unit,
                'equation': equation,
                'linked_vars': linked_vars,
                'category': category,
                'decimalpl': decimalpl,
                'min': min_val,
                'max': max_val
            })
    
    def _extract_flags(self):
        """Extract all flags (bit flags)"""
        for flag in self.xdf_root.findall('.//XDFFLAG'):
            address = self._get_address(flag)
            if address is None:
                raise ValueError(f"Flag {self._get_title(flag)!r} has no BIN address")
            
            title = self._get_title(flag)
            category = self._get_category_name(flag)
            
            # Get mask
            mask_elem = flag.find('.//mask')
            mask = 0x01  # Default mask
            if mask_elem is not None and mask_elem.text:
                mask = self._metadata_number(mask_elem.text, 'flag mask')
            if not 0 < mask <= 0xFF:
                raise ValueError('XDF flag mask must fit a nonzero unsigned byte')
            
            self.elements['flags'].append({
                'title': title,
                'address': address,
                'mask': mask,
                'category': category
            })
    
    def _extract_axis_labels(self, axis_elem) -> List[float]:
        """
        Extract and process axis label values.
        
        Supports three native TunerPro axis sources:
        1. embedinfo linking (MS42/MS43 style) - axis values from linked table
        2. Embedded axis breakpoint data (TunerPro type=1/common MS45 style)
        3. Direct LABEL values (VY V6/legacy style) - hardcoded in XDF
        
        Args:
            axis_elem: XDF XDFAXIS element
            
        Returns:
            List[float]: Processed label values
        """
        # Method 1/2: embedinfo selects linked or embedded breakpoint data.
        # Do not infer an embedded axis from mmedaddress alone. Native TunerPro
        # leaves that axis at its literal/default values unless type="1" is
        # present; reading the address anyway can make a broken XDF look valid.
        embedinfo = axis_elem.find('.//embedinfo')
        if embedinfo is not None:
            link_type = embedinfo.get('type')
            if link_type == '3':
                return self._resolve_embedinfo_axis(axis_elem)
            if link_type == '1':
                return self._resolve_embedded_axis_values(axis_elem)

        embedded = axis_elem.find('.//EMBEDDEDDATA')
        literal_labels = axis_elem.findall('.//LABEL')
        if embedded is not None:
            try:
                literal_major_stride = int(
                    embedded.get('mmedmajorstridebits', '0')
                )
            except ValueError:
                literal_major_stride = 0
            if (
                literal_major_stride < 0
                and not embedded.get('mmedaddress')
                and all(not label.get('value', '') for label in literal_labels)
            ):
                # Native TunerPro uses this generated-XDF shape as a
                # suppressed/dimensionless singleton axis in text exports.
                return []

        # Method 3: Direct LABEL extraction (VY V6/legacy XDFs)
        #
        # Typed ("External (Manual)") labels remain literal display values;
        # their axis MATH is not applied to the displayed label.
        math_elem = axis_elem.find('.//MATH')
        equation = math_elem.get('equation', '') if math_elem is not None else ''
        linked_vars = (
            self._resolve_linked_vars(math_elem) if math_elem is not None else {}
        )

        labels = []
        for label_elem in axis_elem.findall('.//LABEL'):
            value_str = label_elem.get('value', '')
            try:
                value = float(value_str) if value_str else 0.0
            except ValueError:
                # Native numeric export renders blank/textual LABEL values as
                # zero. Preserve the original strings separately in
                # display_labels while keeping numeric parity here.
                labels.append(0.0)
                continue

            # Literal numeric labels remain literal in TunerPro's display, but
            # their declared conversion must still be defined for that input.
            # Validate the MATH domain and deliberately discard its result.
            # Otherwise values such as LABEL="-1" with MATH="sqrt(X)" can be
            # silently accepted as -1 (or later retried as textual zero),
            # concealing a broken definition from every downstream table read.
            if equation and value_str:
                self.evaluate_math(equation, value, linked_vars=linked_vars)
            labels.append(value)

        count_elem = axis_elem.find('.//indexcount')
        try:
            expected_count = int(count_elem.text.strip()) if (
                count_elem is not None and count_elem.text
            ) else len(labels)
        except ValueError:
            expected_count = len(labels)

        # Literal axes without LABEL entries display as zero-valued slots in
        # TunerPro's native Bin Data Export.
        while len(labels) < max(0, expected_count):
            labels.append(0.0)

        return labels

    def _resolve_embedded_axis_values(self, axis_elem) -> List[float]:
        """
        Resolve axis labels from an axis EMBEDDEDDATA mmedaddress.

        This covers TunerPro axes with <embedinfo type="1" />. Z axes are
        skipped because their EMBEDDEDDATA is table data, not row/column labels.
        """
        if axis_elem.get('id') == 'z':
            return []
        if axis_elem.find('.//EMBEDDEDDATA') is None:
            raise ValueError('Required embedded axis has no EMBEDDEDDATA storage')
        storage = self._parse_embedded_data(axis_elem)
        self._require_integer_storage(storage)
        address = storage['address']
        if address is None:
            # Explicit embedded storage defaults an omitted address to zero.
            # BASEOFFSET still applies; malformed explicit values are rejected
            # by _parse_embedded_data, and every resulting read stays bounded.
            address = 0

        count_elem = axis_elem.find('.//indexcount')
        if count_elem is None or not count_elem.text:
            raise ValueError('Required embedded axis has no indexcount')
        count = self._metadata_number(count_elem.text, 'embedded axis indexcount')
        if count <= 0 or count > 4096:
            raise ValueError('Required embedded axis indexcount must be between 1 and 4096')

        size_bits = storage['size_bits']
        supported_widths = (32, 64) if storage['is_float'] else (8, 16, 32)
        if size_bits not in supported_widths:
            raise ValueError(f'Unsupported embedded axis element width: {size_bits}')
        byte_size = size_bits // 8

        major_stride_bits = storage['major_stride']
        if major_stride_bits % 8:
            raise ValueError('Embedded axis major stride must be byte-aligned')
        if storage['minor_stride'] not in (0, size_bits):
            raise ValueError('Unsupported embedded axis minor stride')
        # TunerPro permits an axis stride smaller than the element width. MS42
        # uses this for overlapping 16-bit breakpoints with an 8-bit stride.
        # Clamping to byte_size silently skipped every second breakpoint.
        byte_stride = (
            major_stride_bits // 8 if major_stride_bits else byte_size
        )

        math_elem = axis_elem.find('.//MATH')
        equation = math_elem.get('equation', '') if math_elem is not None else ''
        linked_vars = self._resolve_linked_vars(math_elem) if math_elem is not None else {}

        values = []
        for index in range(count):
            raw = self.read_value_from_bin(
                address + (index * byte_stride),
                size_bits,
                signed=storage['signed'],
                lsb_first=storage['lsb_first'],
                is_float=storage['is_float']
            )
            if raw is None:
                raise ValueError(f'Required embedded axis cell {index} cannot be read from BIN')
            if equation:
                value, _ = self.evaluate_math(
                    equation,
                    raw,
                    linked_vars=linked_vars
                )
                values.append(float(value if value is not None else raw))
            else:
                values.append(float(raw))

        return values
    
    def _extract_tables(self):
        """Extract all tables (2D/3D lookup tables)"""
        for table in self.xdf_root.findall('.//XDFTABLE'):
            title = self._get_title(table)
            category = self._get_category_name(table)
            
            # Get decimal places for precision
            decimalpl = 2  # Default
            dec_elem = table.find('.//decimalpl')
            if dec_elem is not None and dec_elem.text:
                try:
                    decimalpl = int(dec_elem.text.strip())
                except ValueError:
                    pass
            
            # Extract axes information
            axes = {}
            for axis in table.findall('.//XDFAXIS'):
                axis_id = axis.get('id', 'unknown')
                
                # Parse EMBEDDEDDATA for full info
                embedded = self._parse_embedded_data(axis)
                
                # Get axis size/count from indexcount element
                count_elem = axis.find('.//indexcount')
                count = 1
                if count_elem is not None and count_elem.text:
                    try:
                        count = int(count_elem.text.strip())
                    except ValueError:
                        pass
                
                # For Z-axis, also check row/col counts from EMBEDDEDDATA
                if axis_id == 'z':
                    if embedded['row_count'] > 1:
                        count = embedded['row_count'] * embedded['col_count']
                
                # Get axis unit
                unit_elem = axis.find('.//units')
                unit = ""
                if unit_elem is not None and unit_elem.text:
                    unit = clean_output_text(unit_elem.text.strip())
                
                # Get math equation and linked vars
                math_elem = axis.find('.//MATH')
                equation = None
                axis_linked_vars = {}
                if math_elem is not None:
                    equation = math_elem.get('equation', '')
                    axis_linked_vars = self._resolve_linked_vars_lenient(
                        math_elem
                    )
                
                # Get axis-specific decimal places
                axis_decimalpl = decimalpl  # Default to table's decimalpl
                axis_dec_elem = axis.find('.//decimalpl')
                if axis_dec_elem is not None and axis_dec_elem.text:
                    try:
                        axis_decimalpl = int(axis_dec_elem.text.strip())
                    except ValueError:
                        pass
                
                # Extract axis labels with processing
                try:
                    axis_labels = self._extract_axis_labels(axis)
                except ValueError as exc:
                    raise ValueError(
                        f"Table {title!r} (uniqueid={table.get('uniqueid')!r}), "
                        f"axis {axis_id!r}: {exc}"
                    ) from exc
                display_labels = [
                    label.get('value', '')
                    for label in axis.findall('.//LABEL')
                ]
                
                axes[axis_id] = {
                    'address': embedded['address'],
                    'math_element': math_elem,
                    'xml_element': axis,
                    'count': count,
                    'unit': unit,
                    'equation': equation,
                    'linked_vars': axis_linked_vars,
                    'labels': axis_labels,
                    'display_labels': display_labels,
                    'size_bits': embedded['size_bits'],
                    'type_flags': embedded['type_flags'],
                    'storage_attributes': embedded['storage_attributes'],
                    'signed': embedded['signed'],
                    'lsb_first': embedded['lsb_first'],
                    'is_float': embedded['is_float'],
                    'row_count': embedded['row_count'],
                    'col_count': embedded['col_count'],
                    'major_stride': embedded['major_stride'],
                    'minor_stride': embedded['minor_stride'],
                    'decimalpl': axis_decimalpl
                }
            
            # Get Z-axis (data) information
            z_axis = axes.get('z', {})
            data_address = z_axis.get('address')
            
            if data_address is not None:
                self.elements['tables'].append({
                    'title': title,
                    'uniqueid': table.get('uniqueid'),
                    'category': category,
                    'axes': axes,
                    'decimalpl': decimalpl
                })
            else:
                raise ValueError(f"Table {title!r} has no Z-axis BIN address")
    
    def _extract_patches(self):
        """
        Extract all XDFPATCH elements (Community Patchlist support)
        
        XDFPATCH elements define binary patches that can be applied/unapplied.
        Each patch has:
        - title: Patch name (e.g., "[PATCH] Alpha/N")
        - description: What the patch does
        - XDFPATCHENTRY elements with address, patchdata, and basedata
        
        This checks the BIN to determine if each patch is applied or not.
        """
        for patch in self.xdf_root.findall('.//XDFPATCH'):
            title = self._get_title(patch)
            category = self._get_category_name(patch)
            
            # Get description
            desc_elem = patch.find('.//description')
            description = ""
            if desc_elem is not None and desc_elem.text:
                description = desc_elem.text.strip()
                # Clean up XML entities
                description = description.replace('&#013;&#010;', '\n')
                description = description.replace('&#013;', '\r')
                description = description.replace('&#010;', '\n')
            
            # Extract all patch entries
            entries = []
            for entry in patch.findall('.//XDFPATCHENTRY'):
                entry_name = entry.get('name', 'Unknown')
                try:
                    address = self._metadata_number(entry.get('address'), 'patch address')
                    datasize = self._metadata_number(entry.get('datasize'), 'patch datasize')
                    if address < 0 or datasize <= 0:
                        raise ValueError('Patch address must be nonnegative and datasize positive')
                    payloads = {}
                    for field in ('patchdata', 'basedata'):
                        value = entry.get(field)
                        if value is None:
                            payloads[field] = ''
                            continue
                        data = bytes.fromhex(value)
                        if len(data) != datasize:
                            raise ValueError(f'{field} byte count does not match datasize {datasize}')
                        payloads[field] = data.hex().upper()
                    if not any(payloads.values()):
                        raise ValueError('Patch entry has no patchdata or basedata')
                    entries.append({
                        'name': entry_name,
                        'address': address,
                        'datasize': datasize,
                        **payloads,
                    })
                except ValueError as exc:
                    raise ValueError(f'Patch {title!r}, entry {entry_name!r}: {exc}') from exc
            
            if entries:
                # Check if patch is applied
                patch_status = self._check_patch_status(entries)
                
                self.elements['patches'].append({
                    'title': title,
                    'description': description,
                    'category': category,
                    'entries': entries,
                    'status': patch_status
                })
    
    def _check_patch_status(self, entries: List[Dict]) -> str:
        """
        Check if a patch is applied, not applied, or partially applied
        
        Args:
            entries: List of XDFPATCHENTRY dictionaries
            
        Returns:
            str: 'applied', 'not_applied', 'partial', or 'unknown'
        """
        if not entries or self.bin_data is None:
            return 'unknown'
        
        applied_count = 0
        base_count = 0
        total = len(entries)
        
        for entry in entries:
            address = entry['address']
            datasize = entry['datasize']
            patch_data = entry['patchdata']
            base_data = entry['basedata']
            
            # Convert address to file offset
            file_offset = self._xdf_addr_to_file_offset(address)
            
            # Validate offset
            if file_offset < 0 or file_offset + datasize > self.bin_size:
                return 'unknown'
            
            # Read actual bytes from BIN
            actual_bytes = self.bin_data[file_offset:file_offset + datasize]
            actual_hex = actual_bytes.hex().upper()
            
            # Check if matches patch or base data
            if patch_data and actual_hex == patch_data:
                applied_count += 1
            elif base_data and actual_hex == base_data:
                base_count += 1
            else:
                return 'unknown'
        
        # Determine status
        if applied_count == total:
            return 'applied'
        elif base_count == total:
            return 'not_applied'
        elif applied_count > 0 and base_count > 0:
            return 'partial'
        else:
            return 'unknown'

    def read_value_from_bin(self, address: int, size_bits: int,
                            signed: bool = False,
                            lsb_first: bool = False,
                            is_float: bool = False):
        """Read one cell (integer, or IEEE754 when the XDF float flag is set)."""
        offset = self._xdf_addr_to_file_offset(address)
        try:
            return read_value(self.bin_data, offset, size_bits, signed, lsb_first, is_float)
        except (IndexError, ValueError, TypeError, struct.error) as exc:
            self.logger.warning("Cannot read XDF address %#x: %s", address, exc)
            return None
    
    def run_diagnostics(self) -> Dict[str, Any]:
        """Grade every element against the loaded BIN and report concrete errors.

        This does not decide the definition is "correct" -- it reports where the
        XDF, applied to THIS bin, produces something impossible (out-of-bounds,
        span overrun) or non-credible (all-zero / single-value multi-cell table).
        A clean report means "not refuted", never "proven".
        """
        bs = self.bin_size
        findings = {
            'address_missing': [], 'address_out_of_bounds': [],
            'span_overruns_bin': [],
            'all_zero_isolated': [], 'all_zero_in_zero_region': [],
            'all_zero_written_bytes': [],
            'degenerate_uniform': [],
            'decode_error': [],
        }
        graded = 0

        def note(bucket, title, detail):
            findings[bucket].append({'title': title, 'detail': detail})

        # --- scalars & flags: bounds only ---
        for kind in ('constants', 'flags'):
            for e in self.elements.get(kind, []):
                graded += 1
                addr = e.get('address')
                if addr is None:
                    note('address_missing', e.get('title', '?'), f'{kind} has no address')
                    continue
                width = max(1, (e.get('size', 8) or 8) // 8) if kind == 'constants' else 1
                addr = self._xdf_addr_to_file_offset(addr)
                if not (0 <= addr < bs):
                    note('address_out_of_bounds', e.get('title', '?'),
                         f'0x{addr:X} outside 0..0x{bs:X}')
                elif addr + width > bs:
                    note('span_overruns_bin', e.get('title', '?'),
                         f'0x{addr:X}+{width} > 0x{bs:X}')
                elif kind == 'constants':
                    try:
                        self.read_constant(e)
                    except (ValueError, IndexError) as exc:
                        note('decode_error', e.get('title', '?'), str(exc))

        # --- tables: bounds + degenerate content ---
        for t in self.elements.get('tables', []):
            graded += 1
            title = t.get('title', '?')
            z = t.get('axes', {}).get('z', {})
            addr = z.get('address')
            if addr is None:
                note('address_missing', title, 'table Z-axis has no address')
                continue
            try:
                layout = table_layout(t)
                addr, end = layout.file_span(self.base_offset, self.base_subtract)
            except (ValueError, IndexError) as exc:
                note('decode_error', title, str(exc))
                continue
            rows, cols, width = layout.rows, layout.cols, layout.width
            span = end - addr
            if not (0 <= addr < bs):
                note('address_out_of_bounds', title, f'0x{addr:X} outside 0..0x{bs:X}')
                continue
            if addr + span > bs:
                note('span_overruns_bin', title,
                     f'0x{addr:X}+{span} ({rows}x{cols}x{width}) > 0x{bs:X}')
                continue
            try:
                data = self._read_table_data(t)
            except Exception as exc:  # noqa: BLE001 - report, don't crash the run
                note('decode_error', title, str(exc)[:80])
                continue
            if not data:
                note('decode_error', title, 'No table data could be read')
                continue
            flat = [c for row in data for c in row if isinstance(c, (int, float))]
            if not flat:
                continue
            cell_count = len(flat)
            uniq = len(set(flat))
            if set(flat) == {0}:
                # An all-zero table is only evidence of a WRONG ADDRESS when it
                # sits inside live calibration. A zero table that is part of a
                # contiguous zero region is the ordinary signature of a feature
                # the vehicle does not have -- the bank is simply unpopulated,
                # and the definition may describe it correctly. An all-zero
                # table inside a contiguous zero region is reported separately.
                #
                # A conversion can map nonzero stored bytes to zero-valued
                # calibration. Check the raw bytes before classifying decoded
                # zeros as possible padding; decoded zero alone is insufficient.
                if not self._raw_block_is_unwritten(addr, span):
                    note('all_zero_written_bytes', title,
                         f'{cell_count} cells decode to 0 @0x{addr:X}, but the '
                         f'raw bytes are written data (not padding)')
                elif self._zero_table_is_isolated(addr, span):
                    note('all_zero_isolated', title,
                         f'{cell_count} cells, all zero @0x{addr:X}, '
                         f'unwritten and surrounded by live data')
                else:
                    note('all_zero_in_zero_region', title,
                         f'{cell_count} cells, all zero @0x{addr:X}, '
                         f'inside a contiguous zero region (feature likely absent)')
            elif uniq == 1 and cell_count > 4:
                note('degenerate_uniform', title,
                     f'{cell_count} cells all == {flat[0]} @0x{addr:X}')

        # Only impossible geometry and zero tables stranded in live calibration
        # refute a definition. Uniform-value tables and unpopulated feature
        # banks are reported for review but are frequently correct.
        refuted = sum(len(findings[k]) for k in
                      ('address_out_of_bounds', 'span_overruns_bin',
                       'all_zero_isolated'))
        report = {
            'xdf': str(self.xdf_path), 'bin': str(self.bin_path),
            'bin_size': bs, 'definition': self.definition_name,
            'elements_graded': graded,
            'refuted_count': refuted,
            'decode_error_count': len(findings['decode_error']),
            'validation_complete': not findings['decode_error'] and not findings['address_missing'],
            'refuted_pct': round(100 * refuted / graded, 1) if graded else 0.0,
            'counts': {k: len(v) for k, v in findings.items()},
            'findings': findings,
            'grade': ('INCOMPLETE' if findings['decode_error'] or findings['address_missing'] else
                      'A_clean' if refuted == 0 else
                      'B_minor' if refuted <= graded * 0.10 else
                      'C_significant' if refuted <= graded * 0.30 else
                      'D_poor_fit'),
            'caveat': 'A clean grade means NOT REFUTED for this bin. It is not '
                      'proof the XDF is correct; only a controlled edit proves a '
                      'physical mapping.',
        }
        return report

    def _raw_block_is_unwritten(self, addr: int, span: int) -> bool:
        """Are the RAW bytes at addr unwritten padding (all 0x00 or all 0xFF)?

        This must be asked of the raw bytes, never of the decoded value. A
        storage byte that the equation maps to 0.0 is real calibration; only an
        unwritten block is evidence that a definition points at nothing.

        Fail-closed: with no bytes to inspect it returns False, so an absent
        image cannot refute a definition.
        """
        if self.bin_data is None:
            return False
        raw = self.bin_data[addr:addr + span]
        if not raw:
            return False
        distinct = set(raw)
        return distinct in ({0x00}, {0xFF})

    def _zero_table_is_isolated(self, addr: int, span: int,
                                window: int = 64, zero_ratio: float = 0.9) -> bool:
        """Is an all-zero table stranded in live calibration, or in a zero region?

        Returns True only when BOTH neighbouring windows contain substantial
        non-zero data -- the case where an all-zero decode really does suggest a
        wrong address. If either side is predominantly zero the table belongs to
        a contiguous unpopulated block (a feature the vehicle does not have),
        which is not evidence against the definition.

        Deliberately fail-closed: with no neighbour bytes to inspect (table at
        the very start or end of the image) it reports False rather than
        refuting a definition on absent evidence.
        """
        if self.bin_data is None:
            return False
        before = self.bin_data[max(0, addr - window):addr]
        after = self.bin_data[addr + span:addr + span + window]
        if not before and not after:
            return False
        sides = []
        for chunk in (before, after):
            if chunk:
                sides.append(chunk.count(0) / len(chunk))
        return all(ratio < zero_ratio for ratio in sides)

    def _read_table_data(self, table: Dict) -> Optional[List[List[float]]]:
        """Read table cells using the shared XDF address calculation."""
        self._require_integer_storage(table.get('axes', {}).get('z', {}))
        layout = table_layout(table)
        start, end = layout.file_span(self.base_offset, self.base_subtract)
        if start < 0 or end > self.bin_size:
            self.logger.warning("Table %r spans invalid BIN offsets %#x..%#x",
                                table['title'], start, end)
            return None
        axes = table.get('axes', {})
        z = axes.get('z', {})
        pick_equation = self._cell_equation_selector(z, layout.rows, layout.cols)
        axis_values = {}
        for name in ('x', 'y'):
            axis = axes.get(name, {})
            xml = axis.get('xml_element')
            axis_values[name] = self._extract_axis_labels(xml) if xml is not None else axis.get('labels', [])
        data = []
        for row in range(layout.rows):
            values = []
            for col in range(layout.cols):
                address = layout.cell_address(row, col)
                raw = self.read_value_from_bin(address, layout.size_bits,
                    signed=z.get('signed', False), lsb_first=z.get('lsb_first', False),
                    is_float=z.get('is_float', False))
                if raw is None:
                    return None
                context = {'row_index': row, 'col_index': col}
                for name, index, key in (('x', col, 'x_axis_value'), ('y', row, 'y_axis_value')):
                    if index < len(axis_values[name]):
                        context[key] = axis_values[name][index]
                equation, linked = pick_equation(row, col)
                value, error = self.evaluate_math(equation, raw,
                    context, linked_vars=linked)
                if value is None:
                    raise ValueError(f"Table {table['title']!r} cell [{row + 1},{col + 1}]: {error}")
                values.append(value)
            data.append(values)
        return data
    
    def _validate_table_data(self, table: Dict, data: List[List[float]]) -> Dict[str, Any]:
        """Validate table data for suspicious patterns"""
        if not data or not data[0]:
            return {'valid': True, 'warnings': []}
        
        # Flatten data for analysis
        flat_data = [cell for row in data for cell in row]
        
        # Check for all zeros
        all_zeros = all(cell == 0.0 for cell in flat_data)
        
        # Check for all same value
        unique_values = set(flat_data)
        all_same = len(unique_values) == 1
        
        # Check for suspicious patterns
        warnings = []
        
        if all_zeros:
            warnings.append("All cells are zero - possible XDF/BIN mismatch")
        elif all_same and len(flat_data) > 4:  # Allow small tables with same value
            warnings.append(f"All cells have same value ({flat_data[0]}) - verify data integrity")
        
        # Calculate statistics
        stats = {
            'min': min(flat_data),
            'max': max(flat_data),
            'avg': statistics.mean(flat_data),
            'unique_count': len(unique_values)
        }
        
        return {
            'valid': not all_zeros,
            'warnings': warnings,
            'all_zeros': all_zeros,
            'all_same': all_same,
            'stats': stats
        }
    
    def evaluate_math(self, equation: str, raw_value: int,
                       axis_context: Optional[Dict] = None,
                       linked_vars: Optional[Dict[str, float]] = None
                       ) -> Tuple[Optional[float], str]:
        """Evaluate a numeric XDF conversion; unsupported conversions raise EquationError."""
        variables = self.math_variables(axis_context, linked_vars)
        variables.setdefault('X', raw_value)
        # These raw-variable names occur in retained legacy XDF fixtures.
        for name in re.findall(r'\bX\d+\b', equation or '', flags=re.IGNORECASE):
            variables.setdefault(name.upper(), raw_value)
        try:
            return evaluate_equation(equation or '', variables), ""
        except EquationError as exc:
            raise EquationError(f"MATH {equation!r}, raw={raw_value!r}: {exc}") from exc

    @staticmethod
    def math_variables(axis_context=None, linked_vars=None):
        """Bind only supplied context; missing variables must remain errors."""
        variables = {'PI': math.pi}
        context = axis_context or {}
        for name, key in (('A', 'row_index'), ('B', 'col_index'),
                          ('E', 'row_index'), ('Y', 'y_axis_value'), ('Z', 'x_axis_value')):
            if key in context:
                variables[name] = context[key]
        for name, value in (linked_vars or {}).items():
            variables[name.upper() if isinstance(name, str) else name] = value
        return variables

    def linked_vars_for(self, item):
        """Resolve links against the currently selected BIN bytes."""
        if item.get('math_element') is not None:
            return self._resolve_linked_vars(item['math_element'])
        return item.get('linked_vars', {})

    def _cell_equation_selector(self, z: Dict, rows=None, cols=None):
        """Build a per-cell (equation, linked_vars) resolver for a Z axis.

        TunerPro V5 tables may carry per-row, per-column and per-cell conversion
        equations via multiple <MATH> children with row=/col= attributes, each
        with its own linked VARs. Precedence is cell > row > column > global
        (TunerPro help: XDF Table Editor, Conversion tab). Row/col attributes are
        zero-based, as documented by TunerPro RT 5.00.10305's XDF Table Editor
        help. Sparse scopes keep their declared indices; no base is inferred.
        """
        xml = z.get('xml_element')
        global_eq = z.get('equation', '')
        if xml is None:
            global_lv = self.linked_vars_for(z)
            return lambda r, c: (global_eq, global_lv)
        maths = xml.findall('MATH')
        if not maths:
            return lambda r, c: ('', {})

        def _idx(v):
            if v is None:
                return None
            value = self._metadata_number(v, 'MATH row/col index')
            if value < 0:
                raise EquationError('MATH row/col index must be nonnegative')
            return value

        cell, rowm, colm = {}, {}, {}
        g_eq, g_lv = '', {}
        scopes_seen = set()
        cache = {}

        def _lv(elem):
            key = id(elem)
            if key not in cache:
                cache[key] = self._resolve_linked_vars(elem)
            return cache[key]

        for m in maths:
            r, c = _idx(m.get('row')), _idx(m.get('col'))
            eq = m.get('equation', '')
            if ((r is not None and rows is not None and r >= rows)
                    or (c is not None and cols is not None and c >= cols)):
                raise EquationError('MATH row/col index exceeds table dimensions')
            if (r, c) in scopes_seen:
                raise EquationError(f'Duplicate MATH scope row={r}, col={c}')
            scopes_seen.add((r, c))
            if r is not None and c is not None:
                cell[(r, c)] = (eq, m)
            elif r is not None:
                rowm[r] = (eq, m)
            elif c is not None:
                colm[c] = (eq, m)
            else:
                g_eq, g_lv = eq, _lv(m)
        def pick(r, c):
            ra, ca = r, c
            if (ra, ca) in cell:
                eq, m = cell[(ra, ca)]
                return eq, _lv(m)
            if ra in rowm:
                eq, m = rowm[ra]
                return eq, _lv(m)
            if ca in colm:
                eq, m = colm[ca]
                return eq, _lv(m)
            return g_eq, g_lv

        return pick

    @staticmethod
    def _require_integer_storage(item):
        flags = item.get('type_flags', 0)
        # Bits: 0x01 signed, 0x02 LSB-first, 0x10000 float (all handled at read).
        # Additional flags need controlled native parity; plausible numerical
        # output alone cannot establish their storage semantics.
        if flags & ~(0x07 | FLOAT_FLAG):
            raise ValueError("Unsupported XDF storage flags; integer decoding is not established")
        if flags & FLOAT_FLAG and item.get('size', item.get('size_bits')) not in (32, 64):
            raise ValueError("XDF float cells must be 32 or 64 bits wide")

    def read_constant(self, item):
        self._require_integer_storage(item)
        raw = self.read_value_from_bin(item['address'], item['size'],
            item.get('signed', False), item.get('lsb_first', False),
            item.get('is_float', False))
        if raw is None:
            raise ValueError(f"Scalar {item.get('title')!r} cannot be read")
        value, _ = self.evaluate_math(item.get('equation', ''), raw,
                                     linked_vars=self.linked_vars_for(item))
        return raw, value

    def _scalar_export_value(self, item, raw_value):
        """Return a decoded scalar or an explicit per-item conversion error."""
        if not item.get('equation'):
            return raw_value, None
        try:
            value, _ = self.evaluate_math(
                item['equation'], raw_value,
                linked_vars=self.linked_vars_for(item)
            )
            return value, None
        except EquationError as exc:
            error = str(exc)
            self.logger.warning(f"{item['title']}: {error}")
            return None, error

    def _require_complete_export(self):
        """Validate every object's values before opening an output file."""
        for item in self.elements.get('constants', []):
            self.read_constant(item)
        for item in self.elements.get('flags', []):
            if self.read_value_from_bin(item['address'], 8) is None:
                raise ValueError(f"Flag {item.get('title')!r} cannot be read")
        for item in self.elements.get('tables', []):
            if self._read_table_data(item) is None:
                raise ValueError(f"Table {item.get('title')!r} cannot be read")

    def _validate_output_paths(self, *output_paths):
        """Refuse to overwrite either input, including links and path aliases."""
        inputs = (self.xdf_path, self.bin_path)
        for output in map(Path, output_paths):
            resolved = output.resolve()
            for source in inputs:
                if resolved == source.resolve() or (
                    output.exists() and source.exists() and output.samefile(source)
                ):
                    raise ValueError(f"Output path would overwrite an input file: {output}")

    def table_context(self, table, row, col):
        context = {'row_index': row, 'col_index': col}
        for name, index, key in (('x', col, 'x_axis_value'), ('y', row, 'y_axis_value')):
            axis = table.get('axes', {}).get(name, {})
            xml = axis.get('xml_element')
            labels = self._extract_axis_labels(xml) if xml is not None else axis.get('labels', [])
            if index < len(labels):
                context[key] = labels[index]
        return context
    
    def export_to_text(self, output_path: str) -> bool:
        """
        Export data in TunerPro format with enhancements
        
        Args:
            output_path: Output file path
            
        Returns:
            bool: True if successful
        """
        try:
            self._validate_output_paths(output_path)
            self._require_complete_export()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                # Write TunerPro-style header
                f.write("=" * 60 + "\n")
                f.write("TunerPro Bin Data Export\n")
                f.write("=" * 60 + "\n")
                f.write(f"SOURCE FILE: {self.bin_path.name}\n")
                f.write(f"SOURCE DEFINITION: {self.definition_name}\n")
                f.write(f"Binary Size: {self.bin_size} bytes\n")
                f.write(f"MD5 Checksum: {self.bin_md5}\n")
                f.write(f"Exporter: KingAI TunerPro Exporter v{self.VERSION}\n")
                f.write(f"Author: {self.AUTHOR_ALIAS} ({self.AUTHOR})\n")
                f.write("=" * 60 + "\n\n")
                
                # Export SCALARS (constants)
                if self.elements['constants']:
                    f.write("=" * 60 + "\n")
                    f.write("SCALAR VALUES\n")
                    f.write("=" * 60 + "\n\n")
                    
                    for const in self.elements['constants']:
                        raw_value = self.read_value_from_bin(
                            const['address'],
                            const['size'],
                            signed=const.get('signed', False),
                            lsb_first=const.get('lsb_first', False),
                    is_float=const.get('is_float', False)
                        )
                        
                        if raw_value is None:
                            continue
                        
                        value, conversion_error = self._scalar_export_value(
                            const, raw_value
                        )
                        
                        # Format value with unit using stored decimal places
                        decimalpl = const.get('decimalpl', 2)
                        if conversion_error:
                            value_str = (
                                f"ERROR: {conversion_error}; raw={raw_value}"
                            )
                        elif isinstance(value, float):
                            value_str = f"{value:.{decimalpl}f}"
                        else:
                            value_str = str(value)
                        
                        # Add unit if present
                        if const['unit']:
                            value_str += f" {const['unit']}"
                        
                        # Write in TunerPro format: single line, right-aligned
                        title = const['title']  # Full title, no truncation
                        if self.show_addresses and const['address'] is not None:
                            addr_str = f"[0x{const['address']:04X}]"
                            f.write(f"SCALAR: {addr_str} {title:<60} {value_str:>18}\n")
                        else:
                            f.write(f"SCALAR: {title:<60} {value_str:>22}\n")
                
                # Export FLAGS
                if self.elements['flags']:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("FLAG VALUES\n")
                    f.write("=" * 60 + "\n\n")
                    
                    for flag in self.elements['flags']:
                        byte_value = self.read_value_from_bin(
                            flag['address'],
                            8
                        )
                        
                        if byte_value is None:
                            continue
                        
                        # Check if flag is set
                        is_set = (byte_value & flag['mask']) != 0
                        status = "Set" if is_set else "Not Set"
                        
                        # Write in TunerPro format: simple Set/Not Set
                        if self.show_addresses and flag['address'] is not None:
                            addr_str = f"[0x{flag['address']:04X}]"
                            mask_str = f"mask=0x{flag['mask']:02X}"
                            f.write(f"FLAG: {addr_str} {mask_str} {flag['title']:<40} {status:>10}\n")
                        else:
                            f.write(f"FLAG: {flag['title']:<50} {status:>20}\n")
                
                # Export TABLES with FULL DATA
                if self.elements['tables']:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("TABLE DATA (FULL EXTRACTION)\n")
                    f.write("=" * 60 + "\n\n")
                    
                    zero_tables = []
                    
                    for table in self.elements['tables']:
                        f.write(f"TABLE: {table['title']}\n")
                        f.write(f"  Category: {table['category']}\n")
                        if self.show_addresses:
                            z_axis = table['axes'].get('z', {})
                            if z_axis.get('address') is not None:
                                f.write(f"  Address: 0x{z_axis['address']:04X}\n")
                            elif table.get('address') is not None:
                                f.write(f"  Address: 0x{table['address']:04X}\n")
                        
                        # Write axis information with labels
                        axes = table['axes']
                        
                        if 'x' in axes:
                            x_axis = axes['x']
                            f.write(f"  X-Axis: {x_axis['count']} points")
                            if x_axis['unit']:
                                f.write(f" ({x_axis['unit']})")
                            f.write("\n")
                            
                            # Show ALL axis values
                            if x_axis.get('labels'):
                                x_decpl = x_axis.get('decimalpl', 2)
                                labels_str = ", ".join(
                                    self._format_value(v, x_decpl) for v in x_axis['labels']
                                )
                                f.write(f"    Values: [{labels_str}]\n")
                        
                        if 'y' in axes:
                            y_axis = axes['y']
                            f.write(f"  Y-Axis: {y_axis['count']} points")
                            if y_axis['unit']:
                                f.write(f" ({y_axis['unit']})")
                            f.write("\n")
                            
                            # Show ALL axis values
                            if y_axis.get('labels'):
                                y_decpl = y_axis.get('decimalpl', 2)
                                labels_str = ", ".join(
                                    self._format_value(v, y_decpl) for v in y_axis['labels']
                                )
                                f.write(f"    Values: [{labels_str}]\n")
                        
                        if 'z' in axes:
                            z_axis = axes['z']
                            if z_axis['unit']:
                                f.write(f"  Data Unit: {z_axis['unit']}\n")
                        
                        # Get decimal places for Z-axis (data values)
                        z_decimalpl = z_axis.get('decimalpl', 2)
                        
                        # Extract and validate table data
                        table_data = self._read_table_data(table)
                        
                        if table_data is not None:
                            # Apply axis flips
                            if self.flip_rpm or self.flip_load:
                                table_data, axes = (
                                    self._apply_axis_flips(
                                        table_data, axes))

                            validation = self._validate_table_data(
                                table, table_data
                            )
                            
                            # Show statistics
                            if ('stats' in validation
                                    and not self.no_stats):
                                stats = validation['stats']
                                f.write("  Statistics:\n")
                                f.write(
                                    f"    Min: "
                                    f"{self._format_value(stats['min'], z_decimalpl)}"
                                )
                                if z_axis.get('unit'):
                                    f.write(f" {z_axis['unit']}")
                                f.write("\n")
                                
                                f.write(
                                    f"    Max: "
                                    f"{self._format_value(stats['max'], z_decimalpl)}"
                                )
                                if z_axis.get('unit'):
                                    f.write(f" {z_axis['unit']}")
                                f.write("\n")
                                
                                f.write(
                                    f"    Avg: "
                                    f"{self._format_value(stats['avg'], z_decimalpl)}"
                                )
                                if z_axis.get('unit'):
                                    f.write(f" {z_axis['unit']}")
                                f.write("\n")
                                
                                f.write(
                                    f"    Unique Values: "
                                    f"{stats['unique_count']}\n"
                                )
                            
                            # Show warnings
                            if validation.get('warnings'):
                                for warning in validation['warnings']:
                                    f.write(f"  ⚠️ {warning}\n")
                                
                                if validation.get('all_zeros'):
                                    zero_tables.append(table['title'])
                            
                            # Output FULL data matrix (all rows and columns)
                            if len(table_data) > 0:
                                cols = len(table_data[0])
                                f.write(
                                    f"  Data Matrix "
                                    f"({len(table_data)} rows x {cols} cols):\n"
                                )
                                
                                # Get decimal places for formatting
                                z_decimalpl = z_axis.get('decimalpl', 2)
                                y_decimalpl = axes.get('y', {}).get(
                                    'decimalpl', 2
                                )
                                
                                # Output ALL rows (full export)
                                for i, row in enumerate(table_data):
                                    # Get Y-axis label for row if available
                                    y_label = ""
                                    if 'y' in axes:
                                        y_ax = axes['y']
                                        if y_ax.get('labels'):
                                            y_labels = y_ax['labels']
                                            if i < len(y_labels):
                                                y_val = y_labels[i]
                                                y_label = f" ({self._format_value(y_val, y_decimalpl)})"
                                    
                                    # Show ALL columns (no truncation)
                                    values_str = ", ".join(
                                        self._format_value(v, z_decimalpl)
                                        for v in row
                                    )
                                    
                                    f.write(
                                        f"    Row {i}{y_label}: "
                                        f"[{values_str}]\n"
                                    )
                        else:
                            f.write(
                                "  ⚠️ Could not extract table data "
                                "(address out of range)\n"
                            )
                        
                        f.write("\n")
                    
                    # Summary warnings for zero tables
                    if zero_tables:
                        f.write("\n" + "=" * 60 + "\n")
                        f.write("📊 ZERO-VALUE TABLES REPORT\n")
                        f.write("=" * 60 + "\n\n")
                        total = len(self.elements['tables'])
                        f.write(
                            f"Found {len(zero_tables)} of {total} "
                            f"tables with all-zero values:\n\n"
                        )
                        # Show ALL zero tables (not truncated)
                        for table_title in zero_tables:
                            f.write(f"  • {table_title}\n")
                        f.write(
                            "\n" + "-" * 60 + "\n"
                            "NOTE: Zero tables may indicate:\n"
                            "  1. XDF/BIN version mismatch (wrong definition file)\n"
                            "  2. Intentional OEM zeroing (e.g., Alpina B3 strategy)\n"
                            "  3. Unused features in this calibration variant\n"
                            "\nAlpina 'Zero Complex, Tune Simple' strategy intentionally\n"
                            "zeros interacting tables to force simpler fallback paths.\n"
                        )
                
                # Export PATCHES (Community Patchlist support)
                if self.elements['patches']:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("PATCHES (Community Patchlist)\n")
                    f.write("=" * 60 + "\n\n")
                    
                    # Group by status
                    applied = [p for p in self.elements['patches'] 
                               if p['status'] == 'applied']
                    not_applied = [p for p in self.elements['patches'] 
                                   if p['status'] == 'not_applied']
                    partial = [p for p in self.elements['patches'] 
                               if p['status'] == 'partial']
                    unknown = [p for p in self.elements['patches'] 
                               if p['status'] == 'unknown']
                    
                    # Summary
                    f.write(f"Total Patches: {len(self.elements['patches'])}\n")
                    f.write(f"  ✓ Applied: {len(applied)}\n")
                    f.write(f"  ✗ Not Applied: {len(not_applied)}\n")
                    if partial:
                        f.write(f"  ⚠ Partial: {len(partial)}\n")
                    if unknown:
                        f.write(f"  ? Unknown: {len(unknown)}\n")
                    f.write("\n" + "-" * 60 + "\n\n")
                    
                    # Applied patches
                    if applied:
                        f.write("✓ APPLIED PATCHES:\n")
                        f.write("-" * 40 + "\n")
                        for patch in applied:
                            f.write(f"  {patch['title']}\n")
                            if patch['description']:
                                f.write(f"    → {patch['description']}\n")
                        f.write("\n")
                    
                    # Not applied patches
                    if not_applied:
                        f.write("✗ NOT APPLIED PATCHES:\n")
                        f.write("-" * 40 + "\n")
                        for patch in not_applied:
                            f.write(f"  {patch['title']}\n")
                            if patch['description']:
                                f.write(f"    → {patch['description']}\n")
                        f.write("\n")
                    
                    # Partial patches (potential issues)
                    if partial:
                        f.write("⚠ PARTIALLY APPLIED PATCHES:\n")
                        f.write("-" * 40 + "\n")
                        for patch in partial:
                            f.write(f"  {patch['title']}\n")
                            f.write("    → WARNING: Patch may be corrupted or incompletely applied\n")
                        f.write("\n")
                
                self.logger.info(f"Export complete: {output_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return False
    
    def export_to_json(self, output_path: str) -> bool:
        """
        Export data to JSON format for programmatic use
        
        Args:
            output_path: Output JSON file path
            
        Returns:
            bool: True if successful
        """
        try:
            self._validate_output_paths(output_path)
            self._require_complete_export()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            export_data = {
                'metadata': {
                    'source_file': self.bin_path.name,
                    'source_definition': self.definition_name,
                    'binary_size': self.bin_size,
                    'base_offset': self.base_offset,
                    'base_subtract': self.base_subtract,
                    'md5_checksum': self.bin_md5,
                    'export_timestamp': datetime.now().isoformat(),
                    'exporter_version': self.VERSION,
                    'author': self.AUTHOR_ALIAS,
                    'author_name': self.AUTHOR,
                    'author_github': self.AUTHOR_GITHUB
                },
                'statistics': {
                    'scalars_count': len(self.elements['constants']),
                    'flags_count': len(self.elements['flags']),
                    'tables_count': len(self.elements['tables']),
                    'patches_count': len(self.elements['patches'])
                },
                'scalars': [],
                'flags': [],
                'tables': [],
                'patches': []
            }
            
            # Export scalars
            for const in self.elements['constants']:
                raw_value = self.read_value_from_bin(
                    const['address'], const['size'],
                    signed=const.get('signed', False),
                    lsb_first=const.get('lsb_first', False),
                    is_float=const.get('is_float', False)
                )
                if raw_value is None:
                    continue
                
                value, conversion_error = self._scalar_export_value(
                    const, raw_value
                )
                
                decimalpl = const.get('decimalpl', 2)
                export_data['scalars'].append({
                    'title': const['title'],
                    'category': const['category'],
                    'address': f"0x{const['address']:04X}",
                    'file_offset': self._xdf_addr_to_file_offset(const['address']),
                    'uniqueid': const.get('uniqueid'),
                    'size': const['size'],
                    'storage_attributes': const.get('storage_attributes', {}),
                    'variables': [dict(v.attrib) for v in const['math_element'].findall('VAR')] if const.get('math_element') is not None else [],
                    'raw_value': raw_value,
                    'value': (
                        round(value, decimalpl)
                        if isinstance(value, float) else value
                    ),
                    'conversion_error': conversion_error,
                    'unit': const['unit'],
                    'equation': const['equation'],
                    'signed': const.get('signed', False),
                    'lsb_first': const.get('lsb_first', False),
                    'decimalpl': decimalpl
                })
            
            # Export flags
            for flag in self.elements['flags']:
                byte_value = self.read_value_from_bin(flag['address'], 8)
                if byte_value is None:
                    continue
                
                is_set = (byte_value & flag['mask']) != 0
                
                export_data['flags'].append({
                    'title': flag['title'],
                    'category': flag['category'],
                    'address': f"0x{flag['address']:04X}",
                    'file_offset': self._xdf_addr_to_file_offset(flag['address']),
                    'mask': f"0x{flag['mask']:02X}",
                    'is_set': is_set
                })
            
            # Export tables with full data
            for table in self.elements['tables']:
                table_entry = {
                    'title': table['title'],
                    'uniqueid': table.get('uniqueid'),
                    'category': table['category'],
                    'axes': {}
                }
                
                # Add axis info
                for axis_id, axis in table['axes'].items():
                    addr = axis['address']
                    addr_str = f"0x{addr:04X}" if addr is not None else None
                    table_entry['axes'][axis_id] = {
                        'count': axis['count'],
                        'unit': axis['unit'],
                        'address': addr_str,
                        'file_offset': self._xdf_addr_to_file_offset(addr) if addr is not None else None,
                        'size_bits': axis.get('size_bits'),
                        'storage_attributes': axis.get('storage_attributes', {}),
                        'variables': [dict(v.attrib) for v in axis['math_element'].findall('VAR')] if axis.get('math_element') is not None else [],
                        'labels': axis.get('labels', []),
                        'display_labels': axis.get('display_labels', []),
                        'equation': axis.get('equation', ''),
                        'major_stride': axis.get('major_stride', 0),
                        'minor_stride': axis.get('minor_stride', 0),
                        'decimalpl': axis.get('decimalpl', 2)
                    }
                
                # Get decimalpl from Z-axis for proper rounding
                z_axis = table.get('axes', {}).get('z', {})
                z_decimalpl = z_axis.get('decimalpl', 2)
                z_signed = z_axis.get('signed', False)
                z_lsb_first = z_axis.get('lsb_first', False)
                
                # Extract full table data
                table_data = self._read_table_data(table)
                if table_data is not None:
                    # Apply axis flips (uses deep copy)
                    flipped_axes = table['axes']
                    if self.flip_rpm or self.flip_load:
                        table_data, flipped_axes = (
                            self._apply_axis_flips(
                                table_data,
                                table['axes']))
                        # Update JSON labels
                        for aid in ('x', 'y'):
                            fa = flipped_axes.get(aid)
                            te = table_entry['axes'].get(
                                aid)
                            if fa and te and fa.get(
                                    'labels'):
                                te['labels'] = fa[
                                    'labels']
                            if fa and te and fa.get(
                                    'display_labels'):
                                te['display_labels'] = fa[
                                    'display_labels']

                    # Round values for JSON
                    table_entry['data'] = [
                        [round(v, z_decimalpl) for v in row]
                        for row in table_data
                    ]
                    table_entry['dimensions'] = {
                        'rows': len(table_data),
                        'cols': len(table_data[0]) if table_data else 0
                    }
                    table_entry['data_format'] = {
                        'signed': z_signed,
                        'lsb_first': z_lsb_first,
                        'decimalpl': z_decimalpl
                    }
                    
                    # Add statistics
                    if not self.no_stats:
                        flat = [v for row in table_data
                                for v in row]
                        if flat:
                            table_entry['statistics'] = {
                                'min': round(
                                    min(flat), z_decimalpl),
                                'max': round(
                                    max(flat), z_decimalpl),
                                'avg': round(
                                    statistics.mean(flat),
                                    z_decimalpl),
                                'unique_count': len(set(
                                    round(v, z_decimalpl)
                                    for v in flat))
                            }
                
                export_data['tables'].append(table_entry)
            
            # Export patches
            for patch in self.elements['patches']:
                patch_entry = {
                    'title': patch['title'],
                    'category': patch['category'],
                    'description': patch['description'],
                    'status': patch['status'],
                    'entries_count': len(patch['entries'])
                }
                export_data['patches'].append(patch_entry)
            
            # Write JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"JSON export complete: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"JSON export failed: {e}")
            return False
    
    def export_to_markdown(self, output_path: str) -> bool:
        """
        Export data to Markdown format for documentation
        
        Args:
            output_path: Output Markdown file path
            
        Returns:
            bool: True if successful
        """
        try:
            self._validate_output_paths(output_path)
            self._require_complete_export()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                # Header
                f.write(f"# ECU Calibration Export\n\n")
                f.write(f"## Metadata\n\n")
                f.write(f"| Property | Value |\n")
                f.write(f"|----------|-------|\n")
                f.write(f"| Source File | `{self.bin_path.name}` |\n")
                f.write(f"| Definition | `{self.definition_name}` |\n")
                f.write(f"| Binary Size | {self.bin_size:,} bytes |\n")
                f.write(f"| MD5 Checksum | `{self.bin_md5}` |\n")
                f.write(f"| Export Date | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
                f.write(f"| Exporter | KingAI TunerPro Exporter v{self.VERSION} |\n")
                f.write(f"| Author | {self.AUTHOR_ALIAS} ({self.AUTHOR}) |\n")
                f.write(f"| GitHub | [{self.AUTHOR_GITHUB}](https://github.com/{self.AUTHOR_GITHUB}) |\n\n")
                
                # Summary
                f.write(f"## Summary\n\n")
                f.write(f"- **Scalars:** {len(self.elements['constants'])}\n")
                f.write(f"- **Flags:** {len(self.elements['flags'])}\n")
                f.write(f"- **Tables:** {len(self.elements['tables'])}\n\n")
                
                # Table of Contents
                f.write(f"## Table of Contents\n\n")
                f.write(f"1. [Scalar Values](#scalar-values)\n")
                f.write(f"2. [Flags](#flags)\n")
                f.write(f"3. [Tables](#tables)\n\n")
                
                # Scalars
                f.write(f"---\n\n## Scalar Values\n\n")
                f.write(f"| Parameter | Value | Unit | Address | Category |\n")
                f.write(f"|-----------|-------|------|---------|----------|\n")
                
                for const in self.elements['constants']:
                    raw_value = self.read_value_from_bin(
                        const['address'], const['size'],
                        signed=const.get('signed', False),
                        lsb_first=const.get('lsb_first', False),
                    is_float=const.get('is_float', False)
                    )
                    if raw_value is None:
                        continue
                    
                    value, conversion_error = self._scalar_export_value(
                        const, raw_value
                    )
                    
                    decimalpl = const.get('decimalpl', 2)
                    if conversion_error:
                        val_str = (
                            f"ERROR: {conversion_error}; raw={raw_value}"
                        )
                    else:
                        val_str = (
                            f"{value:.{decimalpl}f}"
                            if isinstance(value, float) else str(value)
                        )
                    unit = const['unit'] or '-'
                    cat = const['category'] or 'Uncategorized'
                    title = const['title'].replace('|', '\\|')
                    addr_str = f"0x{const['address']:04X}" if const['address'] is not None else '-'
                    
                    f.write(f"| {title} | {val_str} | {unit} | {addr_str} | {cat} |\n")
                
                # Flags
                f.write(f"\n---\n\n## Flags\n\n")
                f.write(f"| Flag | Status | Category |\n")
                f.write(f"|------|--------|----------|\n")
                
                for flag in self.elements['flags']:
                    byte_value = self.read_value_from_bin(flag['address'], 8)
                    if byte_value is None:
                        continue
                    
                    is_set = (byte_value & flag['mask']) != 0
                    status = "✅ Set" if is_set else "❌ Not Set"
                    cat = flag['category'] or 'Uncategorized'
                    title = flag['title'].replace('|', '\\|')
                    
                    f.write(f"| {title} | {status} | {cat} |\n")
                
                # Tables
                f.write(f"\n---\n\n## Tables\n\n")
                
                for i, table in enumerate(self.elements['tables'], 1):
                    title = table['title']
                    f.write(f"### {i}. {title}\n\n")
                    
                    # Table metadata
                    f.write(f"**Category:** {table['category'] or 'Uncategorized'}\n\n")
                    
                    # Axes info
                    axes = table['axes']
                    if axes:
                        f.write(f"**Axes:**\n")
                        for axis_id, axis in axes.items():
                            axis_name = {'x': 'X-Axis', 'y': 'Y-Axis', 'z': 'Z-Axis (Data)'}.get(axis_id, axis_id)
                            unit = f" ({axis['unit']})" if axis['unit'] else ""
                            f.write(f"- {axis_name}: {axis['count']} points{unit}\n")
                        f.write("\n")
                    
                    # Extract table data
                    table_data = self._read_table_data(table)
                    if table_data is not None:
                        # Apply axis flips
                        if self.flip_rpm or self.flip_load:
                            table_data, axes = (
                                self._apply_axis_flips(
                                    table_data, axes))

                        # Statistics
                        flat = [v for row in table_data
                                for v in row]
                        if flat and not self.no_stats:
                            z_unit = axes.get('z', {}).get('unit', '')
                            z_dp = axes.get('z', {}).get('decimalpl', 2)
                            f.write(f"**Statistics:**\n")
                            f.write(f"- Min: {min(flat):.{z_dp}f} {z_unit}\n")
                            f.write(f"- Max: {max(flat):.{z_dp}f} {z_unit}\n")
                            f.write(f"- Avg: {statistics.mean(flat):.{z_dp}f} {z_unit}\n")
                            f.write(f"- Dimensions: {len(table_data)} x {len(table_data[0])}\n\n")
                        
                        # Full Data Table (all rows and columns)
                        if len(table_data) > 0 and len(table_data[0]) > 0:
                            cols = len(table_data[0])
                            z_decimalpl = axes.get('z', {}).get('decimalpl', 2)
                            y_decimalpl = axes.get('y', {}).get('decimalpl', 2)
                            
                            f.write(f"**Full Data Table** ({len(table_data)} rows x {cols} cols):\n\n")
                            
                            # Get X-axis labels for header if available
                            x_labels = axes.get('x', {}).get('labels', [])
                            x_decimalpl = axes.get('x', {}).get('decimalpl', 2)
                            
                            # Get Y-axis labels for row labels
                            y_labels = axes.get('y', {}).get('labels', [])
                            
                            # Header row with X-axis values
                            if x_labels:
                                f.write("| Y \\ X |")
                                for c, label in enumerate(x_labels[:cols]):
                                    f.write(f" {self._format_value(label, x_decimalpl)} |")
                                f.write("\n")
                            else:
                                f.write("| Row |")
                                for c in range(cols):
                                    f.write(f" C{c} |")
                                f.write("\n")
                            
                            # Separator row
                            f.write("|-----|")
                            for c in range(cols):
                                f.write("------|")
                            f.write("\n")
                            
                            # All data rows
                            for r, row_data in enumerate(table_data):
                                # Row label from Y-axis if available
                                if y_labels and r < len(y_labels):
                                    row_label = self._format_value(y_labels[r], y_decimalpl)
                                else:
                                    row_label = str(r)
                                
                                f.write(f"| {row_label} |")
                                for val in row_data:
                                    f.write(f" {self._format_value(val, z_decimalpl)} |")
                                f.write("\n")
                    
                    f.write("\n")
                
                # Export patches
                if self.elements['patches']:
                    f.write("\n---\n\n## Patches (Community Patchlist)\n\n")
                    
                    applied = [p for p in self.elements['patches'] 
                               if p['status'] == 'applied']
                    not_applied = [p for p in self.elements['patches'] 
                                   if p['status'] == 'not_applied']
                    
                    f.write(f"**Total Patches:** {len(self.elements['patches'])}\n")
                    f.write(f"- ✅ Applied: {len(applied)}\n")
                    f.write(f"- ❌ Not Applied: {len(not_applied)}\n\n")
                    
                    if applied:
                        f.write("### ✅ Applied Patches\n\n")
                        for patch in applied:
                            f.write(f"- **{patch['title']}**")
                            if patch['description']:
                                f.write(f": {patch['description']}")
                            f.write("\n")
                        f.write("\n")
                    
                    if not_applied:
                        f.write("### ❌ Not Applied Patches\n\n")
                        for patch in not_applied:
                            f.write(f"- **{patch['title']}**")
                            if patch['description']:
                                f.write(f": {patch['description']}")
                            f.write("\n")
                        f.write("\n")
                
                # Footer
                f.write("---\n\n")
                f.write(f"*Generated by KingAI TunerPro Exporter v{self.VERSION}*\n")
                f.write(f"*Author: {self.AUTHOR_ALIAS} ({self.AUTHOR})*\n")
            
            self.logger.info(f"Markdown export complete: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Markdown export failed: {e}")
            return False

    def export_to_csv(self, output_path: str) -> bool:
        """
        Export data to CSV format for spreadsheet analysis.

        Produces one row per scalar/flag and per table cell, with
        columns: Type, Category, Title, Address, RawValue, Value,
        Unit, Row, Col, RowLabel, ColLabel.

        Args:
            output_path: Output CSV file path

        Returns:
            bool: True if successful
        """
        import csv
        try:
            self._validate_output_paths(output_path)
            self._require_complete_export()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', newline='',
                       encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Type', 'Category', 'Title', 'Address',
                    'RawValue', 'Value', 'Unit',
                    'Row', 'Col', 'RowLabel', 'ColLabel'
                ])

                # Scalars
                for const in self.elements['constants']:
                    raw = self.read_value_from_bin(
                        const['address'], const['size'],
                        signed=const.get('signed', False),
                        lsb_first=const.get('lsb_first', False),
                    is_float=const.get('is_float', False)
                    )
                    if raw is None:
                        continue
                    value = raw
                    if const['equation']:
                        cv, _ = self.evaluate_math(
                            const['equation'], raw,
                            linked_vars=const.get(
                                'linked_vars', {}
                            )
                        )
                        if cv is not None:
                            value = cv
                    dp = const.get('decimalpl', 2)
                    val_str = self._format_value(
                        value, dp) if isinstance(
                            value, float) else str(value)
                    addr = f"0x{const['address']:04X}"
                    writer.writerow([
                        'Scalar', const['category'],
                        const['title'], addr,
                        raw, val_str, const['unit'],
                        '', '', '', ''
                    ])

                # Flags
                for flag in self.elements['flags']:
                    bv = self.read_value_from_bin(
                        flag['address'], 8)
                    if bv is None:
                        continue
                    is_set = (bv & flag['mask']) != 0
                    addr = f"0x{flag['address']:04X}"
                    writer.writerow([
                        'Flag', flag['category'],
                        flag['title'], addr,
                        bv,
                        'Set' if is_set else 'Not Set',
                        f"mask=0x{flag['mask']:02X}",
                        '', '', '', ''
                    ])

                # Tables — one row per cell
                for table in self.elements['tables']:
                    axes = table['axes']
                    z_axis = axes.get('z', {})
                    z_addr = z_axis.get('address')
                    if z_addr is None:
                        continue
                    addr = f"0x{z_addr:04X}"
                    tdata = self._read_table_data(table)
                    if tdata is None:
                        continue
                    # Apply axis flips
                    if self.flip_rpm or self.flip_load:
                        tdata, axes = (
                            self._apply_axis_flips(
                                tdata, axes))
                    y_labels = axes.get(
                        'y', {}).get('labels', [])
                    x_labels = axes.get(
                        'x', {}).get('labels', [])
                    z_dp = z_axis.get('decimalpl', 2)
                    z_unit = z_axis.get('unit', '')
                    for r, row in enumerate(tdata):
                        rl = (self._format_value(
                            y_labels[r],
                            axes.get('y', {}).get(
                                'decimalpl', 2))
                            if r < len(y_labels)
                            else str(r))
                        for c, val in enumerate(row):
                            cl = (self._format_value(
                                x_labels[c],
                                axes.get('x', {}).get(
                                    'decimalpl', 2))
                                if c < len(x_labels)
                                else str(c))
                            writer.writerow([
                                'Table',
                                table['category'],
                                table['title'],
                                addr,
                                '',
                                self._format_value(
                                    val, z_dp),
                                z_unit,
                                r, c, rl, cl
                            ])

            self.logger.info(
                f"CSV export complete: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"CSV export failed: {e}")
            return False

    def export_zeros_report(self, output_path: str) -> bool:
        """
        Export a Markdown report of all zero-value scalars and all-zero tables.
        
        Scalars: included if their computed value == 0
        Tables: included if EVERY cell in the data matrix == 0
        
        Args:
            output_path: Output .md file path
            
        Returns:
            bool: True if successful
        """
        try:
            self._validate_output_paths(output_path)
            self._require_complete_export()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            zero_scalars = []
            zero_tables = []
            total_scalars = 0
            total_tables = 0

            # Scan scalars
            for const in self.elements['constants']:
                raw_value = self.read_value_from_bin(
                    const['address'],
                    const['size'],
                    signed=const.get('signed', False),
                    lsb_first=const.get('lsb_first', False),
                    is_float=const.get('is_float', False)
                )
                if raw_value is None:
                    continue
                total_scalars += 1

                value = raw_value
                if const['equation']:
                    calc_value, _ = self.evaluate_math(
                        const['equation'], raw_value,
                        linked_vars=const.get('linked_vars', {})
                    )
                    if calc_value is not None:
                        value = calc_value

                if value == 0 or value == 0.0:
                    zero_scalars.append(const)

            # Scan tables
            for table in self.elements['tables']:
                table_data = self._read_table_data(table)
                if table_data is None:
                    continue
                total_tables += 1

                flat = [cell for row in table_data for cell in row]
                if flat and all(cell == 0.0 for cell in flat):
                    zero_tables.append({
                        'title': table['title'],
                        'category': table['category'],
                        'axes': table['axes'],
                        'rows': len(table_data),
                        'cols': len(table_data[0]) if table_data else 0,
                    })

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# Zero-Value Report\n\n")
                f.write(f"## Metadata\n\n")
                f.write(f"| Property | Value |\n")
                f.write(f"|----------|-------|\n")
                f.write(f"| Source File | `{self.bin_path.name}` |\n")
                f.write(f"| Definition | `{self.definition_name}` |\n")
                f.write(f"| Export Date | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
                f.write(f"| Exporter | KingAI TunerPro Exporter v{self.VERSION} |\n\n")

                f.write(f"## Summary\n\n")
                f.write(f"| Category | Zero | Total | Percentage |\n")
                f.write(f"|----------|------|-------|------------|\n")
                s_pct = f"{len(zero_scalars)/total_scalars*100:.1f}%" if total_scalars else "N/A"
                t_pct = f"{len(zero_tables)/total_tables*100:.1f}%" if total_tables else "N/A"
                f.write(f"| Scalars | {len(zero_scalars)} | {total_scalars} | {s_pct} |\n")
                f.write(f"| Tables | {len(zero_tables)} | {total_tables} | {t_pct} |\n\n")

                # Zero Scalars
                f.write(f"---\n\n## Zero Scalars ({len(zero_scalars)})\n\n")
                if zero_scalars:
                    f.write(f"| # | Parameter | Address | Unit | Category |\n")
                    f.write(f"|---|-----------|---------|------|----------|\n")
                    for i, const in enumerate(zero_scalars, 1):
                        title = const['title'].replace('|', '\\|')
                        addr = f"0x{const['address']:04X}" if const['address'] is not None else '-'
                        unit = const['unit'] or '-'
                        cat = const['category'] or 'Uncategorized'
                        f.write(f"| {i} | {title} | {addr} | {unit} | {cat} |\n")
                else:
                    f.write(f"No zero-value scalars found.\n")

                # Zero Tables
                f.write(f"\n---\n\n## All-Zero Tables ({len(zero_tables)})\n\n")
                if zero_tables:
                    f.write(f"| # | Table | Size | Category |\n")
                    f.write(f"|---|-------|------|----------|\n")
                    for i, t in enumerate(zero_tables, 1):
                        title = t['title'].replace('|', '\\|')
                        size = f"{t['rows']}x{t['cols']}"
                        cat = t['category'] or 'Uncategorized'
                        f.write(f"| {i} | {title} | {size} | {cat} |\n")
                    f.write(f"\n---\n\n")
                    f.write(f"> **Note:** All-zero tables may indicate:\n")
                    f.write(f"> 1. XDF/BIN version mismatch (wrong definition file)\n")
                    f.write(f"> 2. Intentional OEM zeroing (e.g., Alpina B3 strategy)\n")
                    f.write(f"> 3. Unused features in this calibration variant\n")
                else:
                    f.write(f"No all-zero tables found.\n")

            self.logger.info(f"Zeros report exported: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Zeros report export failed: {e}")
            return False

    def export(self, output_path: str) -> bool:
        """
        Main export function - validates, parses, and exports
        
        Args:
            output_path: Output file path
            
        Returns:
            bool: True if successful
        """
        # Validate binary
        if not self.validate_bin_file():
            return False
        
        # Parse XDF
        if not self.parse_xdf():
            return False
        
        # Export to text
        return self.export_to_text(output_path)


def main():
    """Command-line interface with multi-format support"""
    help_requested = any(arg in ('-h', '--help') for arg in sys.argv[1:])
    known_options = {'--addresses', '--flip-rpm', '--flip-load', '--no-stats',
                     '--no-zerosexport', '--diagnostics', '--help', '-h'}
    unknown_options = [arg for arg in sys.argv[1:]
                       if arg.startswith('-') and arg not in known_options]
    if unknown_options and not help_requested:
        print(f"ERROR: Unknown option(s): {', '.join(unknown_options)}")
        sys.exit(1)
    # Filter out option flags for argument count check
    positional_args = [a for a in sys.argv[1:] if a not in known_options]
    if help_requested or len(positional_args) < 3 or len(positional_args) > 4:
        print("=" * 70)
        print("  KingAI TunerPro XDF + BIN Universal Exporter")
        print("=" * 70)
        print(f"  Version: {__version__}")
        print(f"  Author:  {__author_alias__} ({__author__})")
        print(f"  GitHub:  {__author_github__}")
        print("=" * 70)
        print()
        print("Usage:")
        print(f"  python {sys.argv[0]} <xdf> <bin> <output> [format]")
        print()
        print("Formats (auto-detected from output extension):")
        print("  txt  - TunerPro-style text export (default)")
        print("  text - Same as txt")
        print("  json - JSON format for programmatic use")
        print("  md   - Markdown format for documentation")
        print("  csv  - Spreadsheet-compatible CSV format")
        print("  all  - Export all formats (txt, json, md, csv)")
        print()
        print("Options:")
        print("  --addresses    Include hex addresses in output (useful for XDF creation)")
        print("  --flip-rpm     Flip RPM axis (high-to-low instead of low-to-high)")
        print("  --flip-load    Flip load axis for presentation")
        print("  --no-stats     Omit statistical analysis from output")
        print("  --no-zerosexport  Disable zeros report (ON by default)")
        print("  --diagnostics  Grade XDF vs BIN (bounds/overrun/degenerate) then exit")
        print()
        print("Examples:")
        print(f"  python {sys.argv[0]} def.xdf fw.bin out.txt")
        print(f"  python {sys.argv[0]} def.xdf fw.bin out.json json")
        print(f"  python {sys.argv[0]} def.xdf fw.bin export all")
        print(f"  python {sys.argv[0]} def.xdf fw.bin export.txt --flip-rpm")
        print()
        print("Features:")
        safe_print("  ✅ Table data extraction for verified fixtures")
        safe_print("  ✅ Axis label values displayed")
        safe_print("  ✅ Statistical analysis (min/max/avg)")
        safe_print("  ✅ Data integrity validation")
        safe_print("  ✅ Multiple output formats (TXT, JSON, MD, CSV)")
        safe_print("  ✅ Axis flip options for presentation preference")
        safe_print("  ✅ Auto-format detection from file extension")
        safe_print("  ✅ Zero-value report (_zeros.md) generated by default")
        print()
        sys.exit(0 if help_requested else 1)
    
    xdf_file = positional_args[0]
    bin_file = positional_args[1]
    output_base = positional_args[2]

    # Determine format: explicit arg > auto-detect from extension > default txt
    if len(positional_args) > 3:
        export_format = positional_args[3].lower()
    else:
        # Auto-detect from output file extension
        ext = Path(output_base).suffix.lower().lstrip('.')
        ext_map = {'txt': 'txt', 'text': 'txt', 'json': 'json',
                   'md': 'md', 'markdown': 'md', 'csv': 'csv'}
        export_format = ext_map.get(ext, 'txt')

    # Normalize format
    if export_format == 'text':
        export_format = 'txt'
    if export_format == 'markdown':
        export_format = 'md'

    # Validate format
    if export_format not in {'txt', 'json', 'md', 'csv', 'all'}:
        print(f"ERROR: Unknown format '{export_format}'")
        print(f"  Valid formats: txt, json, md, csv, all")
        sys.exit(1)
    
    # Parse option flags
    show_addresses = '--addresses' in sys.argv
    flip_rpm = '--flip-rpm' in sys.argv
    flip_load = '--flip-load' in sys.argv
    no_stats = '--no-stats' in sys.argv
    zeros_export = '--no-zerosexport' not in sys.argv
    
    # Create exporter
    exporter = UniversalXDFExporter(xdf_file, bin_file)
    exporter.show_addresses = show_addresses
    exporter.flip_rpm = flip_rpm
    exporter.flip_load = flip_load
    exporter.no_stats = no_stats
    exporter.zeros_export = zeros_export

    # Validate the entire output plan before writing its first file. In all
    # mode a later format, zeros report, or diagnostic sidecar can alias input.
    output_path = Path(output_base)
    if '--diagnostics' in sys.argv:
        planned_outputs = [output_path.with_name(f'{output_path.stem}_diagnostics.json')]
    else:
        planned_outputs = (
            [output_path.with_suffix(f'.{fmt}') for fmt in ('txt', 'json', 'md', 'csv')]
            if export_format == 'all' else [output_path]
        )
        if zeros_export:
            planned_outputs.append(output_path.with_name(f'{output_path.stem}_zeros.md'))
    try:
        exporter._validate_output_paths(*planned_outputs)
    except (ValueError, OSError) as exc:
        print(f'ERROR: {exc}')
        sys.exit(1)
    
    # Validate and parse
    if not exporter.validate_bin_file():
        print("❌ Binary validation failed")
        sys.exit(1)
    
    if not exporter.parse_xdf():
        print("❌ XDF parsing failed")
        sys.exit(1)

    # --diagnostics: grade the XDF against this BIN and report concrete errors,
    # then exit. Writes <output_base>_diagnostics.json next to the output path.
    if '--diagnostics' in sys.argv:
        import json as _json
        rep = exporter.run_diagnostics()
        diag_path = Path(output_base).parent / f"{Path(output_base).stem}_diagnostics.json"
        diag_path.parent.mkdir(parents=True, exist_ok=True)
        diag_path.write_text(_json.dumps(rep, indent=2), encoding='utf-8')
        print("=" * 70)
        safe_print(f"  DIAGNOSTICS  {exporter.definition_name}")
        print("=" * 70)
        print(f"  bin: {exporter.bin_path.name}  ({rep['bin_size']:,} bytes)")
        print(f"  elements graded : {rep['elements_graded']}")
        print(f"  REFUTED         : {rep['refuted_count']} ({rep['refuted_pct']}%)")
        print(f"  GRADE           : {rep['grade']}")
        print("\n  breakdown:")
        for k, n in rep['counts'].items():
            if n:
                print(f"    {k:<22} {n}")
        # show a few concrete examples of hard refutations
        for bucket in ('address_out_of_bounds', 'span_overruns_bin',
                       'all_zero_isolated'):
            ex = rep['findings'][bucket][:4]
            if ex:
                print(f"\n  {bucket} (first {len(ex)}):")
                for f in ex:
                    print(f"    - {f['title'][:44]:<46} {f['detail']}")
        print(f"\n  full report: {diag_path}")
        print(f"  NOTE: {rep['caveat']}")
        sys.exit(0)

    success = True
    outputs = []
    
    # Determine output paths and export
    base_path = Path(output_base)
    base_name = base_path.stem
    base_dir = base_path.parent
    
    if export_format in ('txt', 'all'):
        txt_path = base_dir / f"{base_name}.txt" if export_format == 'all' else output_base
        if exporter.export_to_text(str(txt_path)):
            outputs.append(('TXT', str(txt_path)))
        else:
            success = False
    
    if export_format in ('json', 'all'):
        json_path = base_dir / f"{base_name}.json" if export_format == 'all' else output_base
        if exporter.export_to_json(str(json_path)):
            outputs.append(('JSON', str(json_path)))
        else:
            success = False
    
    if export_format in ('md', 'markdown', 'all'):
        md_path = base_dir / f"{base_name}.md" if export_format == 'all' else output_base
        if exporter.export_to_markdown(str(md_path)):
            outputs.append(('Markdown', str(md_path)))
        else:
            success = False
    
    if export_format in ('csv', 'all'):
        csv_path = (base_dir / f"{base_name}.csv"
                    if export_format == 'all'
                    else output_base)
        if exporter.export_to_csv(str(csv_path)):
            outputs.append(('CSV', str(csv_path)))
        else:
            success = False
    
    # Zeros report (default ON, generates _zeros.md alongside output)
    if zeros_export and success:
        zeros_path = base_dir / f"{base_name}_zeros.md"
        if exporter.export_zeros_report(str(zeros_path)):
            outputs.append(('Zeros MD', str(zeros_path)))

    # Summary
    print()
    print("=" * 70)
    if success and outputs:
        safe_print("✅ Export Successful!")
        print("=" * 70)
        print(f"Definition: {exporter.definition_name}")
        print(f"Binary: {exporter.bin_path.name}")
        print()
        print("Elements exported:")
        safe_print(f"  • {len(exporter.elements['constants'])} scalars")
        safe_print(f"  • {len(exporter.elements['flags'])} flags")
        safe_print(f"  • {len(exporter.elements['tables'])} tables")
        if exporter.elements['patches']:
            applied = len([p for p in exporter.elements['patches'] 
                          if p['status'] == 'applied'])
            total = len(exporter.elements['patches'])
            safe_print(f"  • {total} patches ({applied} applied)")
        print()
        print("Output files:")
        for fmt, path in outputs:
            print(f"  [{fmt}] {path}")
        print()
        print(f"Exporter: KingAI TunerPro Exporter v{__version__}")
        print(f"Author: {__author_alias__} ({__author__})")
        sys.exit(0)
    else:
        safe_print("❌ Export Failed - Check log messages above")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
