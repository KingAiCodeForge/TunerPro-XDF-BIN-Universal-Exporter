"""
Read-only firmware string inventory. Names and strings provide heuristic
review signals; exact ECU identity and compatibility require independent evidence.
"""
import argparse
import os
from pathlib import Path

# Bounded scanner memory irrespective of BIN length; retain the full file-size
# report and the same first-match offsets/contexts as the original implementation.
SCAN_BLOCK_SIZE = 1024 * 1024


def check_strings(filepath):
    sw_versions = ['0110C6', '0110CA', '0110AD', '0110AB', '0110SA', '011025',
                   '430069', '430066', '430064', '430056', '430055', '430037', '430070',
                   '43X001', '0060041',
                   '4560', '457L', '456B',
                   '5WK90', '5WK93', '5WK98',
                   'MS42', 'MS43', 'MS45', 'MSV70', 'MS41',
                   'SIEMENS', 'Siemens']
    signatures = [(sw, sw.encode('ascii')) for sw in sw_versions]
    overlap = max(len(raw) for _, raw in signatures) - 1
    hits = {}
    try:
        with open(filepath, 'rb') as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(0)
            scanned = 0
            tail = b''
            while chunk := stream.read(SCAN_BLOCK_SIZE):
                window = tail + chunk
                origin = scanned - len(tail)
                for sw, raw in signatures:
                    if sw in hits:
                        continue
                    index = window.find(raw)
                    if index >= 0:
                        hits[sw] = origin + index
                scanned += len(chunk)
                tail = window[-overlap:]
                if len(hits) == len(signatures):
                    break

            results = {'size': size}
            # Seek back only for found markers, avoiding a whole-image RAM copy.
            for sw, raw in signatures:
                index = hits.get(sw)
                if index is None:
                    continue
                before = max(0, index - 4)
                after = min(size, index + len(raw) + 20)
                stream.seek(before)
                context = stream.read(after - before)
                printable = ''.join(chr(b) if 32 <= b < 127 else '.' for b in context)
                results[sw] = f'@0x{index:05X} [{printable}]'
            return results
    except OSError as exc:
        raise ValueError(f'Cannot read {filepath}: {exc}') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only heuristic firmware string inventory; no ECU identity certification.")
    parser.add_argument("directories", nargs="+", type=Path, help="Folders to inspect; names all_ms42_bins/all_ms43_bins/all_ms45_bins enable expected-type hints")
    args = parser.parse_args(argv)
    for folder in args.directories:
        if not folder.is_dir():
            parser.error(f"Input is not a directory: {folder}")
    try:
        for folder in args.directories:
            folder_name = folder.name.lower()
            files = sorted([f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))])
            print(f'\n{"="*80}')
            print(f'{folder_name.upper()} - {len(files)} files')
            print(f'{"="*80}')

            mismatches = []
            for fname in files:
                fpath = os.path.join(folder, fname)
                res = check_strings(fpath)
                size = res.get('size', 0)

                has_ms42_sw = any(k in res for k in ['0110C6','0110CA','0110AD','0110AB','0110SA','011025'])
                has_ms43_sw = any(k in res for k in ['430069','430066','430064','430056','430055','430037','430070','43X001'])
                has_ms45_sw = any(k in res for k in ['4560','457L','456B'])
                has_ms41 = '0060041' in res or 'MS41' in res
                has_5wk93 = '5WK93' in res
                has_5wk98 = '5WK98' in res

                if 'ms42' in folder_name:
                    expected = 'MS42'
                    if has_ms43_sw and not has_ms42_sw:
                        actual = 'MS43!'
                    elif has_ms41:
                        actual = 'MS41!'
                    elif has_ms42_sw:
                        actual = 'MS42'
                    elif size == 256*1024:
                        actual = 'MS41?'
                    else:
                        actual = '???'
                elif 'ms43' in folder_name:
                    expected = 'MS43'
                    if has_ms42_sw and not has_ms43_sw:
                        actual = 'MS42!'
                    elif has_ms43_sw:
                        actual = 'MS43'
                    else:
                        actual = '???'
                elif 'ms45' in folder_name:
                    expected = 'MS45'
                    if has_5wk93 and not has_5wk98:
                        actual = 'MS45'
                    elif has_5wk98:
                        actual = 'MSV70!'
                    elif has_ms45_sw:
                        actual = 'MS45'
                    else:
                        actual = '???'
                else:
                    expected = '?'
                    actual = '?'

                if actual != expected:
                    mismatches.append((fname, expected, actual, res))

                sw_found = [k for k in ['0110C6','0110CA','0110AD','0110AB','011025',
                                         '430069','430066','430064','430056','430055','430037',
                                         '4560','457L','456B','5WK90','5WK93','5WK98','0060041','MS41'] if k in res]
                flag = ' *** MISMATCH ***' if actual != expected else ''
                print(f'  {size:>10,}  {actual:6}  SW:[{",".join(sw_found):40}]  {fname[:70]}{flag}')

            if mismatches:
                print(f'\n  !!! {len(mismatches)} MISMATCHED FILES IN {folder_name} !!!')
                for fname, exp, act, res in mismatches:
                    print(f'    {fname[:80]}')
                    print(f'      expected={exp}  actual={act}')
                    for k, v in res.items():
                        if k != 'size':
                            print(f'      {k}: {v}')
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print("String/size hints are heuristic; verify identity using authorized exact hashes and definitions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
