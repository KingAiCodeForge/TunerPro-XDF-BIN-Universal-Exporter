#!/usr/bin/env python3
"""
Scan all .bin files in ms42/ms43/ms45 folders and identify files
that don't belong based on embedded cal ID / firmware strings.

MS42 bins have "0110" cal IDs (e.g. 0110C6, 01100AD, 0110SA)
MS43 bins have "4300" cal IDs (e.g. 430037, 430055, 430056, 430064, 430066, 430069, 430070)
MS45 bins have "456" or "457" or "452" cal IDs

Other bins (GS8604, SMG, Bosch ME7, etc.) should be flagged.
"""
import argparse
import os, re, struct, json, sys
from public_collection_cli import collection_arguments, write_report



# Known cal ID patterns and what ECU they map to
CAL_PATTERNS = [
    # MS42: 0110xx (e.g. 0110C6, 01100AD, 0110SA)  
    (re.compile(rb'(0110[A-Z0-9]{2,4})', re.IGNORECASE), 'MS42'),
    # MS43: 4300xx (e.g. 430037, 430055, 430056, 430064, 430066, 430069, 430070)
    (re.compile(rb'(4300[0-9]{2})', re.IGNORECASE), 'MS43'),
    # MS43 alternate: MS430xxx
    (re.compile(rb'(MS430[0-9]{2,3})', re.IGNORECASE), 'MS43'),
    # MS45: 456x, 457x, 452x
    (re.compile(rb'(45[2567][0-9A-Z]{1,6})', re.IGNORECASE), 'MS45'),
    # Bosch GS8604/GS8602/GS8600 (EGS/TCU)
    (re.compile(rb'(GS86[0-9]{2})', re.IGNORECASE), 'EGS_TCU'),
    (re.compile(rb'(GD86[0-9]{2})', re.IGNORECASE), 'EGS_TCU'),
    (re.compile(rb'(5HP19|5HP24)', re.IGNORECASE), 'EGS_TCU'),
    # SMG
    (re.compile(rb'(SMG)', re.IGNORECASE), 'SMG'),
    # Bosch ME7
    (re.compile(rb'(ME7\.[0-9])', re.IGNORECASE), 'ME7'),
    # Siemens GS20
    (re.compile(rb'(GS20|G10C)', re.IGNORECASE), 'GS20_TCU'),
    # MS45 flash emu  
    (re.compile(rb'(MS4X)', re.IGNORECASE), 'MS4X_FLASH'),
]

# Known size ranges per ECU type
SIZE_HINTS = {
    'MS42': [32768, 524288],      # 32KB or 512KB
    'MS43': [65536, 524288],      # 64KB or 512KB
    'MS45': [786304, 1048576],    # ~768KB or 1MB
    'EGS_TCU': [262144, 524288],  # 256KB or 512KB (GS8604 full dumps)
}


def identify_bin(filepath):
    """Read a binary and try to identify what ECU type it is."""
    size = os.path.getsize(filepath)
    name = os.path.basename(filepath).lower()
    result = {
        'path': filepath,
        'name': os.path.basename(filepath),
        'size': size,
        'size_kb': f"{size/1024:.0f}KB",
        'cal_ids_found': [],
        'ecu_types_found': set(),
        'ascii_strings': [],
    }
    
    with open(filepath, 'rb') as f:
        data = f.read()
    
    # Search first 2KB and last 2KB for cal IDs
    search_regions = [
        data[:2048],
        data[-2048:] if len(data) > 2048 else b'',
        data[0x7F00:0x8100] if len(data) > 0x8100 else b'',  # Common MS42/43 cal area
        data[0x7E00:0x7F00] if len(data) > 0x7F00 else b'',  # Another common spot
    ]
    
    full_search = b''.join(search_regions)
    
    for pattern, ecu_type in CAL_PATTERNS:
        matches = pattern.findall(full_search)
        for m in matches:
            decoded = m.decode('ascii', errors='replace')
            if decoded not in [x[0] for x in result['cal_ids_found']]:
                result['cal_ids_found'].append((decoded, ecu_type))
                result['ecu_types_found'].add(ecu_type)
    
    # Also extract printable ASCII strings from the header area for identification
    ascii_region = data[:512]
    strings = re.findall(rb'[\x20-\x7E]{6,}', ascii_region)
    result['ascii_strings'] = [s.decode('ascii', errors='replace') for s in strings[:5]]
    
    # Also check filename for hints
    for hint, ecu_type in [
        ('ms42', 'MS42'), ('0110', 'MS42'),
        ('ms43', 'MS43'), ('4300', 'MS43'), ('430', 'MS43'),
        ('ms45', 'MS45'), ('456', 'MS45'), ('457', 'MS45'),
        ('gs86', 'EGS_TCU'), ('gd86', 'EGS_TCU'), ('5hp', 'EGS_TCU'), ('egs', 'EGS_TCU'),
        ('smg', 'SMG'), ('me7', 'ME7'), ('alpina', 'ALPINA'),
        ('gs20', 'GS20_TCU'), ('flash_emu', 'MS4X_FLASH'),
    ]:
        if hint in name:
            result['ecu_types_found'].add(ecu_type)
    
    result['ecu_types_found'] = sorted(result['ecu_types_found'])
    return result


def classify_belongs(folder_name, result):
    """Check if a file belongs in its folder based on ECU type."""
    expected_types = {
        'all_ms42_bins': ['MS42'],
        'all_ms43_bins': ['MS43'],
        'all_ms45_bins': ['MS45', 'MS4X_FLASH'],
        'ms42_damos': ['MS42'],
        'ms42_outputs_and_bins_xdfs': ['MS42'],
        'ms43_damos': ['MS43'],
        'ms43_outputs_and_bins_xdfs': ['MS43'],
        'ms45_damos': ['MS45'],
        'ms45_work': ['MS45'],
        'ms45_combo_output': ['MS45'],
        'gs8604_egs_work': ['EGS_TCU'],
        'checksum_files': [],  # can have anything
    }
    
    expected = expected_types.get(folder_name, [])
    if not expected:
        return True, "any type allowed"
    
    ecu_types = result['ecu_types_found']
    # Check if any of the file's ECU types match the expected folder types
    for t in ecu_types:
        if t in expected:
            return True, f"matches {t}"
    
    if not ecu_types:
        return None, "unknown ECU type"
    
    return False, f"has {ecu_types}, expected {expected}"


def _main(argv=None):
    args = collection_arguments(argparse.ArgumentParser(description="Read-only heuristic calibration ID scan; identities are hints, not qualification."), argv)
    scan_dirs = {str(folder): folder for folder in args.folders}
    print("=" * 80)
    print("  BMW MS42/MS43/MS45 Bin Folder Scanner - Cal ID Checker")
    print("=" * 80)
    
    all_results = {}
    misplaced = []
    unknown = []
    
    for folder_name, folder_path in sorted(scan_dirs.items()):
        if not os.path.exists(folder_path):
            print(f"\n  [SKIP] {folder_name}: path not found")
            continue
        
        bins = [f for f in os.listdir(folder_path) 
                if f.lower().endswith(('.bin', '.hex', '.0da', '.0pa'))]
        
        if not bins:
            print(f"\n  [{folder_name}] No binary files found")
            continue
        
        print(f"\n{'='*60}")
        print(f"  {folder_name} ({len(bins)} binary files)")
        print(f"{'='*60}")
        
        folder_results = []
        for fname in sorted(bins):
            fpath = os.path.join(folder_path, fname)
            result = identify_bin(fpath)
            folder_results.append(result)
            
            belongs, reason = classify_belongs(os.path.basename(folder_name), result)
            
            cal_str = ", ".join([f"{cid}({etype})" for cid, etype in result['cal_ids_found']]) or "none found"
            types_str = ", ".join(result['ecu_types_found']) or "UNKNOWN"
            
            if belongs is False:
                icon = "!!! MISPLACED"
                misplaced.append((folder_name, result))
            elif belongs is None:
                icon = "??? UNKNOWN"
                unknown.append((folder_name, result))
            else:
                icon = "    OK"
            
            print(f"  {icon} | {fname}")
            print(f"         Size: {result['size_kb']} | Types: {types_str} | Cal IDs: {cal_str}")
            if result['ascii_strings']:
                print(f"         Header: {result['ascii_strings'][:2]}")
        
        all_results[folder_name] = folder_results
    
    # Summary
    print(f"\n{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    
    total_bins = sum(len(v) for v in all_results.values())
    print(f"  Total binary files scanned: {total_bins}")
    print(f"  Misplaced files:            {len(misplaced)}")
    print(f"  Unknown type files:         {len(unknown)}")
    
    if misplaced:
        print(f"\n  MISPLACED FILES (wrong folder):")
        for folder_name, result in misplaced:
            types = ", ".join(result['ecu_types_found'])
            print(f"    [{folder_name}] {result['name']} -> is {types}")
    
    if unknown:
        print(f"\n  UNKNOWN TYPE FILES:")
        for folder_name, result in unknown:
            print(f"    [{folder_name}] {result['name']} ({result['size_kb']})")
            if result['ascii_strings']:
                print(f"      Header strings: {result['ascii_strings'][:3]}")
    
    # Save JSON report
    json_data = {
        'total_files': total_bins,
        'misplaced_count': len(misplaced),
        'unknown_count': len(unknown),
        'misplaced': [(f, r['name'], r['ecu_types_found']) for f, r in misplaced],
        'unknown': [(f, r['name'], r['size_kb'], r['ascii_strings'][:3]) for f, r in unknown],
        'folders': {k: [{
            'name': r['name'],
            'size_kb': r['size_kb'],
            'ecu_types': r['ecu_types_found'],
            'cal_ids': r['cal_ids_found'],
        } for r in v] for k, v in all_results.items()}
    }
    report = json.dumps(json_data, indent=2) + "\n"
    write_report(args.output, report)
    if args.output:
        print(f"Report: {args.output}")
    else:
        print(report)
    return 0


def main(argv=None):
    try:
        return _main(argv)
    except (OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
