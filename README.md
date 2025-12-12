# KingAI TunerPro XDF + BIN Universal Exporter

[![Author](https://img.shields.io/badge/Author-Jason%20King-blue)](https://github.com/KingAiCodeForge)
[![GitHub](https://img.shields.io/badge/GitHub-KingAiCodeForge-181717?logo=github)](https://github.com/KingAiCodeForge)
[![License](https://img.shields.io/badge/License-MIT%20with%20Attribution-green)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

**Universal XDF to Text Exporter - Enhanced Beyond TunerPro**

A powerful Python tool that exports ECU calibration data from TunerPro XDF definition files combined with BIN firmware files to multiple formats: TXT, JSON, and Markdown.

---

## 💡 Why This Tool Exists

**TunerPro exports zeros instead of actual table data.**

When exporting calibration data from TunerPro using certain XDF/BIN combinations, all table cell values show as `0.00` - even though the data displays correctly inside TunerPro itself. This affects:

- **Holden VY V6 $060A** - Enhanced v2.09a XDF + Enhanced v1.0 BIN → zeros
- **Holden VS Supercharged $51** - Various XDF/BIN combos → zeros  
- **Other GM/Holden platforms** - VT, VX, VE with certain Enhanced OS XDFs

This tool was built to solve that problem. It reads the XDF definition and BIN file directly, correctly extracting **all** table cell data, axis values, and statistics that TunerPro fails to export.

---

## 🌟 Features

### ✅ Superior Data Extraction (vs TunerPro)

| Feature | TunerPro Export | KingAI Exporter |
|---------|-----------------|-----------------|
| Scalar values | ✓ | ✓ |
| Flag values | ✓ | ✓ |
| Table headers | ✓ | ✓ |
| **Table cell data** | ✗ (exports zeros) | **✓ Full data** |
| Axis values | ✗ | **✓ Displayed** |
| Statistics (min/max/avg) | ✗ | **✓ Included** |
| Zero-value warnings | ✗ | **✓ Warns user** |
| Multi-format export | ✗ | **✓ TXT/JSON/MD/CSV** |

### 🔧 Supported XDF Variations

- Standard format (`mmedaddress`, `mmedelementsizebits`)
- Alternative format (`mmedtypeflags`)
- All element types: `XDFCONSTANT`, `XDFFLAG`, `XDFTABLE`, `XDFHEADER`
- Various structural variations

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

### ✅ WORKING - Fully Tested XDF/BIN Combinations

| Platform | XDF | BIN Example | Status | Notes |
|----------|-----|-------------|--------|-------|
| **Holden VY V6 $060A** | VY_V6_$060A_Enhanced_V1.2 | 92118883.BIN | ✅ **Perfect** | Scalars, flags, tables all working |
| **Holden VS V6 SC $51** | VS_V6_SC_$51_Enhanced | VS_V6_SC_$51_Enhanced_v1.0a.bin | ✅ **Perfect** | Full data extraction |
| **Holden VX/VY V6 SC $07** | VY_V6_SC_$07_Enhanced | VX-VY_V6_SC_$07_Enhanced_v1.2.bin | ✅ **Perfect** | 175 tables, 245 scalars, 41 flags |
| **BMW MS42 0110C6** | Siemens_MS42_0110C6 | Siemens_MS42_0110C6_512KB.bin | ✅ **Perfect** | 597 tables, 512KB bin support |

### 🔄 FIXED in v3.1.0 - Previously Broken (Now Working)

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
├── tunerpro_exporter.py   # Main CLI exporter (1,690 lines, v3.1.0)
├── exporter_gui.py        # PySide6 Qt GUI frontend (1,073 lines, v3.2.0)
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
| `_get_address(element)` | Universal address extraction (4 fallback methods) |
| `_parse_embedded_data(element)` | Extract size, signedness, endianness from `mmedtypeflags` |
| `_xdf_addr_to_file_offset(addr)` | Apply BASEOFFSET translation |
| `read_value_from_bin(addr, size)` | Read raw bytes from BIN with correct endianness |
| `evaluate_math(equation, raw)` | Apply XDF math equation (safe eval) |
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
