"""
MS42 Address Comparison Tool
------------------------------
Compares table addresses between XML definition and XDF definition files
for explicitly mapped OSID/size pairs. Address overlap is a review signal only.

Usage:
  python _compare_xml_xdf_addresses.py --xml definitions.xml --xdf OSID_SIZE=file.xdf

Output:
  Per-OSID report showing matched, mismatched, and missing tables.
"""
import argparse
import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# =================================================================
# XML Parser
# =================================================================
def parse_xml_tables(xml_path):
    """Returns {rom_key: {table_name: abs_address}}."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    roms = root.findall("rom")

    if not roms:
        raise ValueError("XML definition contains no rom elements")
    base_tables = {}
    for t in roms[0].findall("table"):
        name = (t.get("name") or "").strip()
        ttype = (t.get("type") or "").strip()
        cat = (t.get("category") or "").strip()
        base_tables[name] = {"type": ttype, "category": cat}

    rom_tables = {}
    for rom in roms[1:]:
        romid = rom.find("romid")
        if romid is None:
            continue
        osid = (romid.findtext("internalidstring") or "").strip()
        fs = (romid.findtext("filesize") or "").strip()
        key = f"{osid}_{fs}".lower().replace(" ", "")

        tables = {}
        for t in rom.findall("table"):
            tname = (t.get("name") or "").strip()
            addr = (t.get("storageaddress") or "").strip()
            if tname and addr:
                try:
                    tables[tname] = int(addr, 16)
                except ValueError:
                    pass
        rom_tables[key] = tables

    return rom_tables, base_tables


# =================================================================
# XDF Parser
# =================================================================
def parse_xdf_addresses(xdf_path):
    """Return direct constant/Z-storage file offsets, without guessing axis ownership."""
    from tunerpro_xdf.xdf_addressing import file_offset
    root = ET.parse(xdf_path).getroot()
    base_node = root.find(".//BASEOFFSET")
    base = int(base_node.get("offset", "0"), 0) if base_node is not None else 0
    subtract = int(base_node.get("subtract", "0"), 0) if base_node is not None else 0
    entries = {}
    for tag, nodes in (("const", root.findall(".//XDFCONSTANT")),
                       ("table", root.findall(".//XDFTABLE"))):
        for node in nodes:
            storage = node.find("EMBEDDEDDATA") if tag == "const" else node.find("XDFAXIS[@id='z']/EMBEDDEDDATA")
            if storage is None:
                continue
            raw_text = storage.get("mmedaddress")
            if raw_text is None:
                raise ValueError("Explicit storage has no mmedaddress")
            raw = int(raw_text, 0)
            address = file_offset(raw, base, subtract)
            entries.setdefault(address, []).append((tag, node.findtext("title", "Unnamed")))
    return entries, base


# =================================================================
# BIN Hash Scanner
# =================================================================
def scan_bins(bin_dir):
    """Returns {md5: {path, size, osid}}."""
    if not bin_dir.exists():
        return {}
    results = {}
    for f in sorted(bin_dir.glob("*.bin")):
        data = f.read_bytes()
        md5 = hashlib.md5(data).hexdigest()
        osid = "unknown"
        # Try to find OSID string at known locations
        for offset in [0x48000 + 0x7F00, 0x48000 + 0x7E00, 0x0]:
            if offset + 10 < len(data):
                chunk = data[offset:offset + 20]
                for pat in [b"0110C6", b"0110CA", b"0110AD", b"011025",
                            b"0110AB", b"0110SA"]:
                    if pat in chunk:
                        osid = pat.decode()
                        break
                if osid != "unknown":
                    break
        # Fallback: scan the full calibration area header
        if osid == "unknown" and len(data) >= 0x50000:
            cal_area = data[0x48000:0x48100]
            for pat in [b"0110C6", b"0110CA", b"0110AD", b"011025",
                        b"0110AB", b"0110SA"]:
                if pat in cal_area:
                    osid = pat.decode()
                    break
        results[f.name] = {"md5": md5, "size": len(data), "osid": osid}
    return results


# =================================================================
# Main Comparison
# =================================================================
def compare(xml_path, xdf_map, osid_filter=None, verbose=False):
    print("=" * 70)
    print("MS42 XML / XDF Address Comparison Report (address overlap only)")
    print("=" * 70)

    rom_tables, base_tables = parse_xml_tables(xml_path)

    compared = 0
    total_matched = 0
    total_xml_only = 0
    total_xdf_only = 0

    for rom_key, xml_tables in sorted(rom_tables.items()):
        osid = rom_key.split("_")[0].upper()
        if osid_filter and osid.upper() != osid_filter.upper():
            continue

        xdf_key = f"{osid}_{rom_key.split('_')[1]}"
        xdf_path = xdf_map.get(xdf_key)
        if not xdf_path or not xdf_path.exists():
            print(f"\n--- {rom_key} --- SKIPPED (no XDF at {xdf_key})")
            continue

        compared += 1
        xdf_addrs, xdf_base = parse_xdf_addresses(xdf_path)

        print(f"\n--- {rom_key} (XDF: {xdf_path.name}, base=0x{xdf_base:X}) ---")
        print(f"  XML tables: {len(xml_tables)}")
        print(f"  XDF unique addresses: {len(xdf_addrs)}")

        matched = []
        xml_only = []
        for name, addr in sorted(xml_tables.items()):
            if addr in xdf_addrs:
                xdf_names = "; ".join(f"{t}:{n}" for t, n in xdf_addrs[addr])
                matched.append((name, addr, xdf_names))
            else:
                xml_only.append((name, addr))

        # Find XDF addresses not in XML
        xml_addr_set = set(xml_tables.values())
        xdf_only = [(addr, entries) for addr, entries
                     in sorted(xdf_addrs.items())
                     if addr not in xml_addr_set]

        total_matched += len(matched)
        total_xml_only += len(xml_only)
        total_xdf_only += len(xdf_only)

        print(f"  MATCHED: {len(matched)}")
        print(f"  XML-only (no XDF at that address): {len(xml_only)}")
        print(f"  XDF-only (no XML at that address): {len(xdf_only)}")

        if verbose:
            if matched:
                print(f"\n  {'XML Name':<45} {'Addr':<10} XDF Name(s)")
                print(f"  {'-'*45} {'-'*10} {'-'*40}")
                for name, addr, xdf_names in matched[:20]:
                    print(f"  {name:<45} 0x{addr:05X}  {xdf_names}")
                if len(matched) > 20:
                    print(f"  ... and {len(matched) - 20} more")

            if xml_only:
                print(f"\n  XML-only tables:")
                for name, addr in xml_only[:10]:
                    print(f"    {name:<45} 0x{addr:05X}")
                if len(xml_only) > 10:
                    print(f"    ... and {len(xml_only) - 10} more")

    print(f"\n{'='*70}")
    if not compared:
        raise ValueError("No XML ROM matched an explicitly supplied XDF mapping")
    print(f"TOTALS: {total_matched} matched, {total_xml_only} XML-only, "
          f"{total_xdf_only} XDF-only")
    print(f"{'='*70}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare XML/XDF address overlap; overlap alone does not prove semantic parity.")
    parser.add_argument("--xml", type=Path, required=True, help="XML definition file")
    parser.add_argument("--xdf", action="append", required=True, metavar="OSID_SIZE=PATH",
                        help="Explicit mapping, e.g. 0110C6_512kb=definitions/file.xdf; repeatable")
    parser.add_argument("--osid", help="Filter to a specific OSID")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)
    xdf_map = {}
    for mapping in args.xdf:
        key, separator, value = mapping.partition("=")
        if not separator or not key or not value:
            parser.error("--xdf requires OSID_SIZE=PATH")
        path = Path(value)
        if not path.is_file():
            parser.error(f"XDF input is not a file: {path}")
        if key in xdf_map:
            parser.error(f"Duplicate XDF mapping: {key}")
        xdf_map[key] = path
    if not args.xml.is_file():
        parser.error(f"XML input is not a file: {args.xml}")
    try:
        compare(args.xml, xdf_map, args.osid, args.verbose)
    except (OSError, ValueError, ET.ParseError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
