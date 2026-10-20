#!/usr/bin/env python3
"""Preview a filename-based tuning-file inventory; --apply creates copies only.

Supply a source directory and an output directory outside it. Legacy filename
and size heuristics remain hints; they do not prove ECU/XDF/tune compatibility.
No originals are renamed, removed or moved. Existing outputs are refused.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
from organize_bins import execute_plan, plan_entry, source_files, validate_roots

# === PATTERNS ===

# MS42 software numbers (in filename)
MS42_SW = re.compile(r'01100AD|01100AB|01100C6|01100CA|011025', re.IGNORECASE)
# MS42 explicit mention
MS42_EXPLICIT = re.compile(r'\bMS42\b', re.IGNORECASE)
# MS42 hardware on E46/E38/E39 (5WK9020, 5WK90329, 5WK9037 - NOT on E60+)
MS42_HW_E46 = re.compile(r'5WK9020|5WK90329|5WK9037', re.IGNORECASE)
MS42_CHASSIS = re.compile(r'E46|E38|E39|E36', re.IGNORECASE)

# MS43 software numbers
MS43_SW = re.compile(r'430037|430055|430056|430064|430066|430069', re.IGNORECASE)
# MS43 explicit mention
MS43_EXPLICIT = re.compile(r'\bMS43\b|MS430\b', re.IGNORECASE)

# MS45 hardware (5WK930xx series)
MS45_HW = re.compile(r'5WK9301[0-9]|5WK9302[0-9]', re.IGNORECASE)
# MS45 explicit
MS45_EXPLICIT = re.compile(r'\bMS45\b', re.IGNORECASE)

# Exclusions
EXCLUDE_PATTERNS = re.compile(
    r'\.ols$|\.tun_pdg|M3_|_M3_|M5_|_M5_|M6_|_M6_|MSS53|MSS54|V10|V8|'
    r'Diesel|diesel|Turbodiesel|Turbo-Diesel|turbodiesel|EDC16|DPF|EGR|'
    r'Limited_Mappack|SuperMappack',
    re.IGNORECASE
)

# For MS42/MS43 we ALSO exclude M3
EXCLUDE_M3 = re.compile(r'_M3[_\s]|_M3$|^BMW_E46_M3|^BMW_E36_M3|^BMW_E46___M3', re.IGNORECASE)

# MSV70/N52 indicator - these are NOT MS45
MSV70_HW = re.compile(r'5WK980[0-9][0-9]', re.IGNORECASE)


def clean_name(original_name):
    """
    Replace all dots with underscores, then append .bin
    Example: BMW_E46_328i_1999...Stage1 -> BMW_E46_328i_1999..._Stage1.bin
    Also clean up +++ to _plus
    """
    # Replace dots with underscores
    cleaned = original_name.replace('.', '_')
    # Clean up +++ sequences
    cleaned = re.sub(r'\+{2,}', '_plus', cleaned)
    cleaned = cleaned.replace('+', '_')
    # Clean up multiple consecutive underscores
    cleaned = re.sub(r'_{2,}', '_', cleaned)
    # Remove trailing underscores before adding .bin
    cleaned = cleaned.rstrip('_')
    # Add .bin extension
    cleaned = cleaned + '.bin'
    return cleaned


def classify_file(name):
    """
    Returns 'ms42', 'ms43', 'ms45', or None
    """
    
    # Skip excluded patterns (diesel, M3, M5, M6, .ols, etc.)
    if EXCLUDE_PATTERNS.search(name):
        return None
    if EXCLUDE_M3.search(name):
        return None
    
    # === MS45 check first (most specific) ===
    if MS45_HW.search(name) or MS45_EXPLICIT.search(name):
        # Confirm it's NOT MSV70/N52
        if MSV70_HW.search(name):
            return None
        return 'ms45'
    
    # === MS43 check ===
    if MS43_SW.search(name) or MS43_EXPLICIT.search(name):
        return 'ms43'
    
    # === MS42 check ===
    if MS42_SW.search(name) or MS42_EXPLICIT.search(name):
        return 'ms42'
    
    # MS42 hardware but only on E46/E38/E39/E36 chassis
    if MS42_HW_E46.search(name) and MS42_CHASSIS.search(name):
        # Make sure it doesn't also have MS43 software numbers
        if MS43_SW.search(name):
            return 'ms43'
        return 'ms42'
    
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--recursive", action="store_true", help="Include source subdirectories")
    parser.add_argument("--apply", action="store_true", help="Create copies and a manifest")
    args = parser.parse_args(argv)
    try:
        source, destination = validate_roots(args.source, args.destination)
        entries = []
        skipped = 0
        for path in source_files(source, recursive=args.recursive):
            ecu = classify_file(path.name)
            size = path.stat().st_size
            if ecu is None or size < 16384 or (ecu == "ms45" and size > 1572864):
                skipped += 1
                continue
            # The full source-relative name digest prevents two names normalizing
            # to the same filename from overwriting either variant.
            normalized = clean_name(path.name)
            relative = path.relative_to(source)
            identity = hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()
            target_name = f"{Path(normalized).stem}__{identity}.bin"
            entries.append(plan_entry(source, path, f"all_{ecu}_bins", target_name))
        print(f"Skipped {skipped} files by filename/size heuristics; originals remain unchanged.")
        execute_plan(source, destination, entries, args.apply, "tuning-inventory.json")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
