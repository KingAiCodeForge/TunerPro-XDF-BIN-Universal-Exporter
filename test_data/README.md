# Test Data for XDF/BIN Universal Exporter

This directory contains test files for validating the exporter across multiple XDF formats and ECU platforms.

---

## 🎯 Primary Test XDFs

### Holden/GM Enhanced OS (Priority 1)

| XDF File | BIN File | Location | Notes |
|----------|----------|----------|-------|
| `VX VY_V6_$060A_Enhanced_v2.09a.xdf` | `VY_V6_Enhanced.bin` or `92118883_STOCK.bin` | `A:\repos\VY_V6_Assembly_Modding\` | Main development target. Extended spark tables (14-col layout issue). |
| `VS_V6_$51_Enhanced_v1.4f.xdf` | `VS_V6_$51_Enhanced_v1.4b.bin` | `E:\Users\jason\Documents\TunerPro Files\` | VS Ecotec V6 |
| `VS_V6_SC_$51_Enhanced_v1.0e.xdf` | `VS_V6_SC_$51_Enhanced_v1.0a.bin` | `E:\Users\jason\Documents\TunerPro Files\` | Supercharged V6 |
| `VS_V8_$A6F_Enhanced_v0.90.xdf` | `VS_V8_$A6F_Enhanced_v0.90.bin` | `E:\Users\jason\Documents\TunerPro Files\` | VS V8 |
| `VT_V6_$A5G_Enhanced_v1.0h.xdf` | `VT_V6_AUTO_$A5G_Enhanced_v1.1.bin` | `E:\Users\jason\Documents\TunerPro Files\` | VT Ecotec |
| `VT_V6_SC_$A5G_Enhanced_v1.3h.xdf` | `VT_V6_SC_$A5G_Enhanced_v1.3.bin` | `E:\Users\jason\Documents\TunerPro Files\` | Supercharged VT |
| `VT_V8_$A6E_Enhanced_v1.03.xdf` | `VT_V8_$A6E_Enhanced_v1.00.bin` | `E:\Users\jason\Documents\TunerPro Files\` | VT LS1 V8 |
| `VX VY_V6_SC_$07_Enhanced_v2.6h.xdf` | `VX-VY_V6_SC_$07_Enhanced_v1.2.bin` | `E:\Users\jason\Documents\TunerPro Files\` | Supercharged VX/VY |

### BMW Siemens MS42/MS43 (Priority 2)

| XDF File | BIN File | Location | Notes |
|----------|----------|----------|-------|
| `Siemens_MS42_0110C6_ENG_512K_v1.1.xdf` | Any 0110C6 512KB bin | `E:\Users\jason\Documents\TunerPro Files\Bin Definitions\` | MS42 M52TU English |
| `Siemens_MS42_0110C6_ENG_32K_v1.1.xdf` | Any 0110C6 32KB bin | `E:\Users\jason\Documents\TunerPro Files\Bin Definitions\` | MS42 M52TU 32KB |
| `Siemens_MS43_430069_512K_1.1.3v.xdf` | Any 430069 512KB bin | `E:\Users\jason\Documents\TunerPro Files\Bin Definitions\` | MS43 M54 512KB |
| `Siemens_MS43_430069_64K_113.xdf` | Any 430069 64KB bin | `E:\Users\jason\Documents\TunerPro Files\Bin Definitions\` | MS43 M54 64KB |
| `Siemens_MS42_0110C6_Community_Patchlist_v1.7.1.xdf` | 0110C6 bin | `E:\Users\jason\Documents\TunerPro Files\Bin Definitions\` | Patchlist overlay |
| `Siemens_MS43_MS430069_Community_Patchlist_v2.9.2.xdf` | 430069 bin | `E:\Users\jason\Documents\TunerPro Files\Bin Definitions\` | Patchlist overlay |

**Sample BMW BIN files:**
- `Siemens_MS42_0110C6_E46_M52TUB28_EU3_RHD.bin`
- `MS42_WBABM52010JM22048_0110C6_512KB*.bin` (tuned files)
- `m52tub28_MS43_430069_512KB.bin`
- `Siemens_MS43_MS430069_E46_M54B30_EU4_LHD.bin`

### Gearhead EFI / Legacy XDFs (Priority 3)

| XDF Source | Location | Notes |
|------------|----------|-------|
| `*_11.xdf`, `*_12.xdf` etc | `A:\repos\gearhead_efi_complete\` | Legacy GM EFI definitions |
| Various `.xdf` files | `A:\repos\PCM_SCRAPING_TOOLS\FULL_ARCHIVE_V2\downloads\` | Scraped XDF archive |

### OSE Enhanced (Priority 4)

| XDF File | BIN File | Location | Notes |
|----------|----------|----------|-------|
| `OSE12P V112-Catagorised*.xdf` | OSE BIN files | `E:\Users\jason\Documents\TunerPro Files\` | OSE 12P Enhanced OS |
| `OSE_$12PV112_1BAR*.adx` | - | `E:\Users\jason\Documents\TunerPro Files\` | ADX definition |

---

## 📁 XDF/BIN Source Directories

### Primary Sources
```
A:\repos\VY_V6_Assembly_Modding\
├── VX VY_V6_$060A_Enhanced_v2.09a.xdf
├── 92118883_STOCK.bin
├── VY_V6_Enhanced.bin
└── VX-VY_V6_$060A_Enhanced_v1.0a - Copy.bin

E:\Users\jason\Documents\TunerPro Files\Bin Definitions\
├── BMW/
├── Siemens_MS42_0110C6_*.xdf
├── Siemens_MS43_430069_*.xdf
└── [Community Patchlist XDFs]

E:\Users\jason\Documents\TunerPro Files\Bins\
├── BMW/
├── HOLDEN/
├── GM/
├── 92118883.BIN - 92118889.BIN (Holden VY)
├── Siemens_MS42_*.bin
├── Siemens_MS43_*.bin
└── [200+ BIN files]
```

### Secondary Sources
```
A:\repos\gearhead_efi_complete\
A:\repos\PCM_SCRAPING_TOOLS\FULL_ARCHIVE_V2\downloads\
E:\Users\jason\Documents\TunerPro Files\
├── VS_V6_$51_Enhanced_v1.4f/
├── VT_V6_$A5G_Enhanced_v1.0h/
├── VT_V8_$A6E_Enhanced_v1.03/
├── VX VY_V6_$060A_Enhanced_v2.09a/
└── VX VY_V6_SC_$07_Enhanced_v2.6h/
```

---

## 🧪 Test Scenarios

### 1. Holden Enhanced OS Tables
- **Known Issue:** Spark tables show wrong values due to XDF row/col mismatch
- **Test:** Export `Main High-Octane Spark Table < 4800 RPM` and verify smooth transitions
- **XDF:** `VX VY_V6_$060A_Enhanced_v2.09a.xdf` + `92118883_STOCK.bin`

### 2. BMW MS42/MS43 Address Mapping
- **Challenge:** Different memory layouts (32KB vs 512KB)
- **Test:** Verify BASEOFFSET handling for both flash sizes
- **XDFs:** `0110C6` and `430069` variants

### 3. Patchlist XDF Overlays
- **Challenge:** Community patchlists add definitions on top of base XDFs
- **Test:** Export with patchlist attached
- **XDFs:** `*_Community_Patchlist_*.xdf`

### 4. Legacy Gearhead EFI
- **Challenge:** Older XDF format variations
- **Test:** Parse `_11.xdf` style definitions
- **Source:** `A:\repos\gearhead_efi_complete\`

---

## 📋 How to Generate TunerPro Reference Exports

1. Open XDF with matching BIN file in TunerPro RT
2. File → Export → Text Export
3. Save to this directory with naming convention:
   - `tunerpro_export_[platform]_[version].txt`

**Examples:**
- `tunerpro_export_vy_v6_v209a.txt`
- `tunerpro_export_ms42_0110c6_512k.txt`
- `tunerpro_export_ms43_430069_512k.txt`
- `tunerpro_export_ose12p_v112.txt`

---

## ⚠️ Known XDF Issues

| XDF | Issue | Status |
|-----|-------|--------|
| `VX VY_V6_$060A_Enhanced_v2.09a.xdf` | Spark tables claim 17x17 but data is 14-column layout | Investigating |
| BMW patchlists | May override base XDF addresses | Needs testing |
| OSE ADX files | Different format than XDF | Partial support |

---

## 📁 Additional Test Files (Optional)

Place in this directory for automated testing:
- Source XDF files (for direct comparison)
- Source BIN files (for data verification)
- Expected output `.txt` files (for regression testing)

---

**Note:** These files are for development/testing only. Do not commit proprietary tuning data to version control.
