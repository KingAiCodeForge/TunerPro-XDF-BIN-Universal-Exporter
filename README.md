# KingAI TunerPro XDF + BIN Universal Exporter

[![Author](https://img.shields.io/badge/Author-Jason%20King-blue)](https://github.com/KingAiCodeForge)
[![GitHub](https://img.shields.io/badge/GitHub-KingAiCodeForge-181717?logo=github)](https://github.com/KingAiCodeForge)
[![License](https://img.shields.io/badge/License-MIT%20with%20Attribution-green)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

**Universal XDF to Text Exporter - Enhanced Beyond TunerPro**

A powerful Python tool that exports ECU calibration data from TunerPro XDF definition files combined with BIN firmware files to multiple formats: TXT, JSON, and Markdown.

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

The exporter includes built-in validation:

- **Zero-Value Detection**: Warns when >95% of table cells are zero (indicates XDF/BIN mismatch)
- **Boundary Checking**: Validates addresses don't exceed BIN file size
- **Checksum Verification**: Calculates MD5/SHA256 for BIN verification
- **Statistics Analysis**: Provides min/max/avg for quick sanity checks

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

#### Other Brands Needing bin and XDF Definitions
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
- Holden VT/VX/VY/VZ | Ford Falcon BA/BF/FG | BMW E36/E46

---

## 🙏 Acknowledgments

- PCMHacking.net community for ECU tuning knowledge
- TunerPro RT for XDF format reference
- All Holden/GM tuning enthusiasts

---

*Made with ❤️ in Australia*
