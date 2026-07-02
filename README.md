# KingAI TunerPro XDF + BIN Universal Exporter

[![Author](https://img.shields.io/badge/Author-Jason%20King-blue)](https://github.com/KingAiCodeForge)
[![GitHub](https://img.shields.io/badge/GitHub-KingAiCodeForge-181717?logo=github)](https://github.com/KingAiCodeForge)
[![License](https://img.shields.io/badge/License-MIT%20with%20Attribution-green)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

**XDF + BIN export helper for regression testing and automation**

A powerful Python tool that exports ECU calibration data from TunerPro XDF definition files combined with matching BIN firmware files to multiple formats: TXT, JSON, Markdown, and CSV.

The exporter is intended to be ECU-family neutral, but compatibility must be proven per XDF/BIN pair. BMW MS42/MS43/MS45, Holden/GM V6/V8, Ford/Barra-adjacent Bosch work, and other XDF-defined projects can use different addressing, axis, math, and patch conventions. This tool is a companion/export layer for automation and regression testing; it is not a replacement for TunerPro validation.

Older Holden VY/VX/V6 Enhanced and stock BIN pairs remain important regression targets, and the `v2.09` XDF family needs fresh verification against current TunerPro behavior and current public XDFs. Before changing parser math, axis handling, endian handling, or BASEOFFSET behavior, re-export those pairs plus the BMW fixtures and compare outputs so fixes for one family do not break another.

### XDF Iteration + Reverse Engineering Workflow

This exporter is useful while building or repairing XDFs during reverse engineering. A practical loop is:

1. Load the firmware in Ghidra/IDA and use Ghidra `analyzeHeadless` to export labels, xrefs, immediate-hit windows, and function context.
2. Add or adjust candidate XDF entries from RR/A2L/DAMOS/ASM evidence.
3. Run this exporter against the candidate XDF + matching BIN.
4. Check whether axes, dimensions, units, endian, signedness, and table values look sane.
5. Diff the export against known-good stock/stage files and repeat until the XDF is stable.

That makes it a fast feedback tool for XDF development: disassembly finds likely addresses and code-use, while the exporter shows whether the candidate XDF renders consistently as calibration data. Final truth still comes from comparing against TunerPro, known-good bins, and platform-specific test fixtures.

---

## 💡 Why This Tool Exists

**Some historical XDF/BIN export paths produced zero-filled table data in text exports.**

During earlier testing, some XDF/BIN combinations produced table cell values as `0.00` in exported text even though the data displayed correctly in the GUI. TunerPro has continued to evolve, so treat this as a regression target to verify against the current TunerPro build rather than a permanent claim about TunerPro itself. Historical examples include:

- **Holden VY V6 $060A** - Enhanced v2.09a XDF + Enhanced v1.0 BIN → zeros
- **Holden VS Supercharged $51** - Various XDF/BIN combos → zeros  
- **Other GM/Holden platforms** - VT, VX, VE with certain Enhanced OS XDFs

This tool was built to make those cases testable from the command line. It reads the XDF definition and BIN file directly, exports resolved values where the parser supports the XDF pattern, and produces repeatable output for comparison with TunerPro and known-good fixtures.

---

## 🌟 Features

### Data Extraction for CLI Workflows

| Feature | Status |
|---------|--------|
| Scalar values | Supported where the XDF math/addressing pattern is implemented |
| Flag values | Supported where the XDF math/addressing pattern is implemented |
| Table headers | Supported |
| Table cell data | Supported for verified XDF/BIN fixtures |
| Axis values | Displayed when axis linking or embedded axis data resolves correctly |
| Statistics (min/max/avg) | Included for resolved tables |
| Zero-value warnings | Warns when output looks suspicious |
| Multi-format export | TXT/JSON/MD/CSV |
| XDFPATCH detection | Shows applied/not-applied status for supported patch patterns |

### 🔧 Supported XDF Variations

- Standard format (`mmedaddress`, `mmedelementsizebits`)
- Alternative format (`mmedtypeflags`)
- All element types: `XDFCONSTANT`, `XDFFLAG`, `XDFTABLE`, `XDFHEADER`, `XDFPATCH`
- Various structural variations

### 🔌 XDFPATCH Support (Community Patchlist)

**NEW in v3.2.0!** Full support for BMW MS4X and similar Community Patchlist XDF files:

- Detects all `XDFPATCH` elements (Immobilizer Bypass, Alpha/N, Launch Control, etc.)
- Checks if each patch is **Applied**, **Not Applied**, or **Partial**
- Exports patch status in all output formats (TXT, JSON, Markdown)
- Useful for analyzing supported BMW MS42/MS43 community patchlist fixtures

Example output:
```
PATCHES (Community Patchlist)
============================================================
Total Patches: 27
  ✓ Applied: 11
  ✗ Not Applied: 12

✓ APPLIED PATCHES:
  [PATCH] Alpha/N
    → Uses ip_maf_1_diag__n__tps_av table for load values
  [PATCH] Launch Control & Rolling Anti Lag
  [PATCH] Immobilizer Bypass
```

### 📄 Output Formats

1. **TXT** - TunerPro-compatible text format
2. **JSON** - Structured data for programmatic use
3. **Markdown** - Documentation-ready format
4. **CSV** - Spreadsheet-compatible format
5. **TEXT/TEST** - Testing format (same as TXT)

---

## 📥 Installation

### Windows (Recommended)

1. Download or clone this repository:
   ```batch
   git clone https://github.com/KingAiCodeForge/kingai_tunerpro_bin_xdf_combined_export_to_any_document.git
   cd kingai_tunerpro_bin_xdf_combined_export_to_any_document
   ```

2. Run the installer (as Administrator for PATH setup):
   ```batch
   install.bat
   ```

3. Restart your terminal for PATH changes to take effect.

### Manual Installation

1. Ensure Python 3.8+ is installed
2. Install dependencies:
   ```batch
   pip install -r requirements.txt
   ```

---

## 📋 XDF Element Types Explained

The exporter handles three distinct XDF element types, each requiring different processing:

### 1. XDFCONSTANT (Scalars)

Single-value parameters like rev limiters, idle speed, fuel trims.

```xml
<XDFCONSTANT uniqueid="0x5678">
    <title>Rev Limiter Hard</title>
    <EMBEDDEDDATA mmedaddress="0x3C42" mmedelementsizebits="16" mmedtypeflags="0x00"/>
    <MATH equation="X"/>
    <units>RPM</units>
    <decimalpl>0</decimalpl>
</XDFCONSTANT>
```

**Processing Pipeline:**
1. Extract address from `EMBEDDEDDATA`
2. Apply BASEOFFSET translation
3. Read raw bytes from BIN (respecting size and endianness)
4. Apply math equation to convert raw value
5. Format with specified decimal places

### 2. XDFFLAG (Binary Flags)

On/off switches for features like VE tuning, speed limiter, diagnostics.

```xml
<XDFFLAG uniqueid="0x9ABC">
    <title>Speed Density Mode</title>
    <EMBEDDEDDATA mmedaddress="0x0108" mmedelementsizebits="8"/>
    <mask>0x08</mask>
</XDFFLAG>
```

**Processing Pipeline:**
1. Read byte from address
2. Apply bitmask via `(byte_value & mask) != 0`
3. Report as "Set" or "Not Set"

### 3. XDFTABLE (2D/3D Tables)

Multi-dimensional calibration tables for fuel, timing, VE, etc.

```xml
<XDFTABLE uniqueid="0x1234">
    <title>Fuel VE Table</title>
    <XDFAXIS id="x">
        <EMBEDDEDDATA mmedaddress="0x1E00" mmedelementsizebits="8"/>
        <indexcount>17</indexcount>
        <MATH equation="X*25"/>
        <units>RPM</units>
    </XDFAXIS>
    <XDFAXIS id="y">
        <EMBEDDEDDATA mmedaddress="0x1E11" mmedelementsizebits="8"/>
        <indexcount>16</indexcount>
        <MATH equation="X*0.75"/>
        <units>kPa</units>
    </XDFAXIS>
    <XDFAXIS id="z">
        <EMBEDDEDDATA mmedaddress="0x1E22" mmedrowcount="16" mmedcolcount="17"/>
        <MATH equation="X*0.00390625"/>
        <units>%</units>
    </XDFAXIS>
</XDFTABLE>
```

**Processing Pipeline:**
1. Extract X-axis labels (column headers)
2. Extract Y-axis labels (row headers)
3. Read Z-axis data matrix (rows × cols)
4. Apply math equation to all values
5. Calculate statistics (min/max/avg/unique)
6. Detect all-zero patterns (XDF/BIN mismatch warning)

---

## 🔬 How It Works (Technical Deep-Dive)

### Core Architecture

The exporter uses a modular pipeline approach:

```
XDF File (XML) ──► Parse Structure ──► Extract Elements ──► Read Binary ──► Apply Math ──► Export
     │                  │                    │                  │              │            │
     └─ ET.parse()      └─ _extract_*()     └─ 3 types:        └─ struct     └─ eval()    └─ TXT/JSON/MD
                                                Constants         unpack                     CSV
                                                Flags
                                                Tables
```

### XDF Format Variations Handled

The `UniversalXDFExporter` class handles multiple XDF structural variations:

| XDF Variation | Detection Method | Example |
|---------------|------------------|---------|
| Standard `mmedaddress` | `EMBEDDEDDATA` element | `mmedaddress="0x3C42"` |
| Alternative `mmedtypeflags` | Flag + address combo | `mmedtypeflags="0x02"` + `mmedaddress` |
| Direct `address` attribute | Element attribute | `<XDFCONSTANT address="0x1234">` |
| Child `mem`/`memory` element | Nested element | `<mem>0x1234</mem>` |

### BASEOFFSET Handling (Critical for 68HC11 ECUs)

The BASEOFFSET mechanism in XDF files maps ECU memory addresses to binary file offsets:

```xml
<!-- Format 1: Standard with subtract flag -->
<BASEOFFSET offset="32768" subtract="1" />

<!-- Format 2: Simple lowercase -->
<baseoffset>0</baseoffset>
```

**Address Translation Logic:**

```python
# subtract="1": ECU addresses start at offset, file starts at 0
# Common for 68HC11 (Ford AU, Holden VN-VY)
# XDF addr 0x8000 with offset 0x8000, subtract=1 → file offset 0x0000
file_offset = xdf_address - base_offset

# subtract="0": File has header/padding before calibration
# XDF addr 0x0000 with offset 0x48000 → file offset 0x48000  
file_offset = xdf_address + base_offset
```

### Binary Reading with Endianness Support

The exporter correctly handles both big-endian and little-endian data:

```python
# mmedtypeflags bit meanings:
# Bit 0 (0x01): LSB first (little-endian)
# Bit 1 (0x02): Signed value

# Supported data sizes: 8-bit, 16-bit, 32-bit
# Format specifiers: B/b (8), H/h (16), I/i (32)
# Endianness: < (little-endian), > (big-endian)
```

### Math Equation Evaluation

Handles TunerPro's math syntax with edge case handling:

```python
# Standard: "0.75 * X - 40"
# Named variables: "X1000 / 100" → replaced with raw value
# Operator prefix: "*2**14" → prepended with X
# Case-insensitive: "x", "X", "e", "E" all work
```

**Safe Evaluation:** Uses restricted `eval()` with `__builtins__: {}` for security.

### Data Validation Pipeline

Every table goes through validation checks:

1. **Zero Detection** - Warns if >95% cells are zero (XDF/BIN mismatch)
2. **Uniformity Check** - Flags if all cells have identical values
3. **Boundary Validation** - Ensures addresses don't exceed BIN size
4. **Statistics Calculation** - min/max/avg/unique count for sanity checking

---

## 🖥️ GUI Features (v3.2.0)

The PySide6 Qt GUI (`exporter_gui.py`) provides:

### Input/Output Features

- 📂 **Browse Dialogs** - File picker for XDF, BIN, and output folder
- 🖱️ **Drag & Drop** - Drop XDF/BIN files directly onto the window
- 📝 **Recent Files** - Quick access to last 10 XDF/BIN pairs (QSettings)
- 🔍 **Auto-Detect** - Finds matching BIN when XDF is selected

### Export Options

- ☑️ **Format Checkboxes** - Select TXT, JSON, MD, CSV individually
- 📊 **Preview Mode** - Shows element count before export
- 📁 **Open Folder** - Option to open output folder after export
- ⚡ **Skip Validation** - Bypass BIN size checks for WIP/experimental XDFs

### Processing

- ⚙️ **Background Thread** - `ExportWorker(QThread)` for non-blocking export
- 📈 **Progress Updates** - Real-time status messages via Qt signals
- ⌨️ **Keyboard Shortcuts** - Standard shortcuts for common operations

### User Experience

- 🎨 **Dark Theme** - Comfortable viewing
- 📋 **Log Output** - Detailed operation log in scrollable text area
- ⚠️ **Error Dialogs** - Clear QMessageBox for failures

---

## 🚀 Usage

### Command Line Interface (CLI)

**Basic Usage:**
```batch
python tunerpro_exporter.py <xdf_file> <bin_file> <output_file> [format]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `<xdf_file>` | Path to XDF definition file |
| `<bin_file>` | Path to BIN firmware file |
| `<output_file>` | Output file path (extension optional) |
| `[format]` | Optional: `txt`, `json`, `md`, `text`, `all` (default: `txt`) |

**Examples:**

```batch
# Export to TXT (TunerPro-style)
python tunerpro_exporter.py "VY_V6_Enhanced.xdf" "92118883.bin" "export.txt" txt

# Export to JSON
python tunerpro_exporter.py "VY_V6_Enhanced.xdf" "92118883.bin" "export.json" json

# Export to Markdown
python tunerpro_exporter.py "VY_V6_Enhanced.xdf" "92118883.bin" "export.md" md

# Export to ALL formats at once
python tunerpro_exporter.py "VY_V6_Enhanced.xdf" "92118883.bin" "export" all
```

**After Installation (from any directory):**
```batch
tunerpro-export "tune.xdf" "ecu.bin" "output.txt" txt
```

### Graphical User Interface (GUI)

**Launch the GUI:**
```batch
python exporter_gui.py
```

**Or after installation:**
```batch
tunerpro-export-gui
```

**GUI Features:**
- 📂 Browse buttons for XDF, BIN, and output folder selection
- ✏️ Custom output filename input
- ☑️ Checkboxes for selecting export formats (TXT, JSON, MD, TEST)
- 📊 Progress indicator and log output
- 🎨 Dark theme for comfortable use

---

## 📊 Output Examples

### TXT Format (TunerPro-Style)

```
================================================================================
 SOURCE FILE:       92118883.bin
 SOURCE DEFINITION: VY_V6_$060A_Enhanced_v2.09a.xdf
================================================================================

SCALAR: Rev Limiter Hard                                                6000.00
SCALAR: Idle Target RPM                                                  750.00

FLAG: Speed Density Mode                                                    Set
FLAG: VE Tuning Enabled                                                 Not Set

TABLE: Fuel VE Table (16 x 17)
  Axis X (RPM): 400, 800, 1200, 1600, 2000, 2400, ...
  Axis Y (MAP kPa): 15, 25, 35, 45, 55, 65, 75, ...
  Min: 45.2  Max: 112.8  Avg: 78.4  Unique values: 156
  
  Data:
    45.2  48.1  52.3  55.8  ...
    47.1  51.2  56.7  60.2  ...
    ...
```

### JSON Format

```json
{
  "metadata": {
    "bin_file": "92118883.bin",
    "xdf_file": "VY_V6_$060A_Enhanced_v2.09a.xdf",
    "export_date": "2025-01-15T14:30:00"
  },
  "scalars": [
    {
      "title": "Rev Limiter Hard",
      "value": 6000.0,
      "unit": "RPM",
      "address": "0x3C42"
    }
  ],
  "tables": [
    {
      "title": "Fuel VE Table",
      "rows": 16,
      "cols": 17,
      "statistics": {"min": 45.2, "max": 112.8, "avg": 78.4},
      "data": [[45.2, 48.1, ...], ...]
    }
  ]
}
```

---

## 🔍 Data Validation

The exporter includes comprehensive built-in validation to catch errors early:

### Automatic Checks

| Check | Threshold | Warning Triggered |
|-------|-----------|-------------------|
| Zero-value detection | >95% cells are zero | "All data appears to be zero - XDF/BIN mismatch?" |
| Uniform value detection | 100% cells identical | "All values identical - possible misconfiguration" |
| Address boundary | Address > BIN size | "Address 0xXXXX out of range for BIN size" |
| Binary size validation | Not 128/256/512/1024KB | "Unusual binary size" (warning only) |

### BIN File Integrity

On load, the exporter calculates and reports:

- **File size** in bytes and KB
- **MD5 hash** for file identification/verification
- **Common size validation** (128KB, 256KB, 512KB, 1MB)

### Table Statistics

Every table includes statistical analysis in the output:

```text
TABLE: Fuel VE Table (16 x 17)
  Min: 45.20  Max: 112.80  Avg: 78.43  Unique values: 156
```

This helps identify:

- **Zero-filled tables** = Wrong XDF for this BIN
- **Very low unique count** = Possible flat/unused table
- **Min/Max outside expected range** = Possible address misalignment

### Validation Messages in Console

```text
INFO: Binary validated: 524288 bytes, MD5: a1b2c3d4e5f6...
INFO: BASEOFFSET detected: offset=32768 (0x8000), subtract=1
WARNING: Table "Fuel VE" has 98% zero values - check XDF/BIN match
ERROR: Address 0x90000 out of range for 512KB BIN file
```

---

## ⚠️ Compatibility Status & Known Issues

### Historical Regression Fixtures

| Platform | XDF | BIN Example | Status | Notes |
|----------|-----|-------------|--------|-------|
| **Holden VY V6 $060A** | Enhanced v2.09b | VY_V6_Enhanced.bin | Needs re-test | 1310 scalars, 548 flags, 330 tables in historical snapshot |
| **Holden VY V6 $060A** | Enhanced v2.09a | VX-VY_V6_$060A_Enhanced_v1.0a.bin | Needs re-test | 1310 scalars, 351 flags, 330 tables in historical snapshot |
| **Holden VY V6 $060A** | Enhanced v2.04 | VX-VY_V6_$060A_Enhanced_v1.1a.bin | Snapshot | 1163 scalars, 94 flags, 338 tables |
| **Holden VX/VY V6 SC $07** | Enhanced v2.6h | VX-VY_V6_SC_$07_Enhanced_v1.2.bin | Snapshot | 354 scalars, 60 flags, 175 tables |
| **Holden VS V6 $51** | Enhanced v1.4f | VS_V6_$51_Enhanced_v1.4b.bin | Snapshot | 681 scalars, 147 flags, 256 tables |
| **Holden VS V6 SC $51** | Enhanced v1.0c | VS_V6_SC_$51_Enhanced_v1.0a.bin | Snapshot | 679 scalars, 167 flags, 253 tables |
| **Holden VS V8 $A6F** | Enhanced v0.90 | VS_V8_$A6F_Enhanced_v0.90.bin | Snapshot | 110 scalars, 5 flags, 74 tables |
| **Holden VT V6 $A5G** | Enhanced v1.0h | VT_V6_AUTO_$A5G_Enhanced_v1.1.bin | Snapshot | 166 scalars, 8 flags, 108 tables |
| **Holden VT V6 SC $A5G** | Enhanced v1.3h | VT_V6_SC_$A5G_Enhanced_v1.3.bin | Snapshot | 158 scalars, 6 flags, 119 tables |
| **Holden VT V8 $A6E** | Enhanced v1.03 | VT_V8_$A6E_Enhanced_v1.00.bin | Snapshot | 81 scalars, 6 flags, 77 tables |
| **Ford AU OSE 11P** | V104 decrypted | OSE_$11P V104 CAKH V6.BIN | Snapshot | 616 scalars, 332 flags, 195 tables |
| **Ford AU OSE 11B** | V106 | OSE_$11P V104 CAKH V6.BIN | Snapshot | 746 scalars, 280 flags, 242 tables |
| **BMW MS42 0110C6** | ENG 512K v1.1 | cfm54b30.bin | Snapshot | 1384 scalars, 597 tables |
| **BMW MS42 0110AD** | ENG 32KB | 25_MS42_0110AD_32KB_cut.bin | Snapshot | 1347 scalars, 974 tables |
| **BMW MS42 Community** | Patchlist v1.7.1 | cfm54b30.bin | Snapshot | 1384 scalars, 597 tables |

### 🔄 FIXED in v3.3.0 & v3.4.0

| Bug | Formula/Feature | Root Cause | Fix |
|-----|-----------------|-----------|-----|
| **#8** | `if(cond ; true ; false)` | TunerPro ternary syntax not valid Python | Convert to `(true) if (cond) else (false)` |
| **#9** | Bitshift on float (`Y>>6`) | Python `>>` requires int operands | Auto-wrap vars in `int()` when bitshift ops present |
| **#10** | `E` namespace collision | `E: math.e` was overwriting `E: row_index` | Removed `math.e` override for `E` |
| **#11** | `X/(128/B)/C` div-by-zero | `B`, `C` are linked vars (`VAR type="link"`) not resolved | New `_resolve_linked_vars()` reads linked element values from binary |
| **#11b** | `X/2.56/E` div-by-zero | `E` defaulted to `0` for scalars | `E` defaults to `1` (element count) for scalars |
| **Embedinfo** | MS42/MS43 axis linking | Axis breakpoints stored in separate linked tables | `_build_uniqueid_index()` + `_resolve_embedinfo_axis()` |

### 🔄 FIXED in v3.1.0

| Platform | Issue | Fix Applied | Verified |
|----------|-------|-------------|----------|
| **Ford AU OSE12P V6** | All addresses "out of range" | Fixed BASEOFFSET subtract=1 handling | ✅ 401 scalars, 148 flags, 90 tables |
| **68HC11-based ECUs** | Memory offset calculation wrong | Now correctly subtracts offset when subtract="1" | ✅ Full data extraction |

**Technical Fix Details (v3.1.0):**
```
XDF Element: <BASEOFFSET offset="32768" subtract="1" />

Before fix: file_offset = xdf_address + 32768  (WRONG - goes past file end)
After fix:  file_offset = xdf_address - 32768  (CORRECT - maps 0x8000→0x0000)
```

This fix applies to all 68HC11-based ECUs including Ford AU Falcon EL/EF/AU, some older Holden/GM platforms, and others using high-memory mapped address spaces.

### ⚠️ NEEDS HELP - XDF/Definition Gaps

The following platforms have BIN files but **NO matching XDF definitions**:

#### Nissan/Infiniti (Skip for now - Different Format Issues)
- **350+ BIN files** but only **13 XDFs** available
- Most XDFs don't match available BINs (wrong engine/ECU type)
- SR20VE XDF used with SR20DET BINs = garbage output
- **Alternative**: Use RomRaider XML definitions (different software)

#### Other Brands Needing bin and XDF Definitions export testings and handling
If you have proper TunerPro XDF files for these, please contribute:

| Brand | BINs Available | XDFs Available | Need |
|-------|----------------|----------------|------|
| Toyota | Various | None | Any Toyota XDFs |
| Mazda | Various | None | Any Mazda XDFs |
| Subaru | Various | None | Any Subaru XDFs (non-RomRaider) |
| Mitsubishi | Various | Limited | EVO/DSM XDFs |
| Alfa Romeo | GTV/156 | 1 (testing) | More Alfa definitions |

### 🐛 Known XDF Format Variations

Some older XDF files use non-standard formats:

| Format Issue | Status | Workaround |
|--------------|--------|------------|
| No `<XDFHEADER>` section | ⚠️ Partial | Uses filename as definition name |
| `mmedtypeflags` instead of `mmedaddress` | ✅ Handled | Auto-detected and parsed |
| Negative BASEOFFSET values | ✅ Fixed | Now handles subtract flag properly |
| HTML entities in descriptions | ✅ Fixed | Decoded automatically |
| Row-major vs column-major tables | ⚠️ Check | May need manual verification |

---

## 📁 Project Structure

```
kingai_tunerpro_bin_xdf_combined_export_to_any_document/
├── tunerpro_exporter.py   # Main CLI exporter (v3.4.0)
├── exporter_gui.py        # PySide6 Qt GUI frontend (v3.2.0)
├── regression_test.py     # Automated regression tests (16 XDF/BIN pairs)
├── install.bat            # Windows installer with PATH setup
├── launch_cli.bat         # Quick CLI launcher
├── launch_gui.bat         # Quick GUI launcher
├── requirements.txt       # Python dependencies
├── README.md              # This documentation
├── LICENSE                # MIT with Attribution license
└── .gitignore             # Git ignore rules
```

---

## 🏗️ Class & Method Reference

### UniversalXDFExporter (Main Class)

```python
class UniversalXDFExporter:
    """Universal XDF parser and exporter with TunerPro-style output"""
```

| Method | Purpose |
|--------|---------|
| `__init__(xdf_path, bin_path)` | Initialize with XDF definition and BIN file paths |
| `validate_bin_file()` | Check BIN exists, calculate MD5/SHA256, validate size |
| `parse_xdf()` | Load XDF XML, extract header/categories/elements |
| `export_to_text(path)` | TunerPro-compatible TXT export |
| `export_to_json(path)` | Structured JSON export |
| `export_to_markdown(path)` | Documentation-ready MD export |
| `export(path)` | Convenience wrapper (validates + parses + exports) |

### Internal Processing Methods

| Method | Purpose |
|--------|---------|
| `_extract_header()` | Parse `<XDFHEADER>`, get definition name, BASEOFFSET |
| `_extract_categories()` | Build category index → name mapping |
| `_extract_constants()` | Parse all `<XDFCONSTANT>` elements |
| `_extract_flags()` | Parse all `<XDFFLAG>` elements |
| `_extract_tables()` | Parse all `<XDFTABLE>` elements with axes |
| `_build_uniqueid_index()` | Build lookup index for linked variable resolution |
| `_resolve_linked_vars()` | Resolve `VAR type="link"` elements to their binary values |
| `_resolve_embedinfo_axis()` | Resolve MS42/MS43 embedinfo-linked axis breakpoints |
| `_get_address(element)` | Universal address extraction (4 fallback methods) |
| `_parse_embedded_data(element)` | Extract size, signedness, endianness from `mmedtypeflags` |
| `_xdf_addr_to_file_offset(addr)` | Apply BASEOFFSET translation |
| `read_value_from_bin(addr, size)` | Read raw bytes from BIN with correct endianness |
| `evaluate_math(equation, raw)` | Apply XDF math equation (safe eval, linked vars, ternary) |
| `_read_table_data(table)` | Extract full 2D data matrix from table definition |
| `_format_value(value, decimalpl)` | Format numeric value with correct decimals |

### GUI Classes (exporter_gui.py)

| Class | Purpose |
|-------|---------|
| `ExportWorker(QThread)` | Background thread for non-blocking export |
| `MainWindow(QMainWindow)` | Main application window with controls |

---

## 🛠️ Development

### Requirements

- Python 3.8 or higher
- PySide6 (for GUI only - CLI works without it)

### Dependencies

```
PySide6>=6.5.0  # Only required for GUI
```

Standard library modules used:
- `xml.etree.ElementTree` - XDF parsing
- `struct` - Binary data reading
- `pathlib` - File path handling
- `json` - JSON export format
- `statistics` - Data analysis

---

## 🤝 Contributing

This project is open for contributions from the PCMHacking community!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 License

Copyright (c) 2025 KingAi PTY LTD - Jason King

This software is provided for educational and personal use.
Commercial use requires written permission from the author.

---

## 👤 Author

**Jason King**
- 🐙 GitHub: [@KingAiCodeForge](https://github.com/KingAiCodeForge)
- 💬 PCMHacking: kingaustraliagg
- 🌐 Website: [kingai.com.au](https://www.kingai.com.au)
- 📧 Email: jason.king@kingai.com.au

**KingAi PTY LTD**
- Specializing in Australian automotive ECU tuning
- Holden VT/VX/VY/VZ | Ford Falcon BA/BF/FG | BMW E36/E46/E60

---

## 🙏 Acknowledgments

- PCMHacking.net community for ECU tuning knowledge
- TunerPro RT for XDF format reference
- All Holden/GM tuning enthusiasts

---

*Made with ❤️ in Australia*
