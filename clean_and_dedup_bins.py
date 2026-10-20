#!/usr/bin/env python3
"""Preview a collection cleanup; --apply copies every file into review lanes.

Unlike the historical script, this never deletes or moves source files. Unique
files go into selected/, repeated contents into duplicate-content/, and filename
heuristic matches into review-name-heuristic/. These hints do not identify an ECU
or establish that a file is safe to discard. All originals remain in place.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
from organize_bins import execute_plan, get_file_hash, plan_entry, source_files, validate_roots

# Patterns for non-BMW files (GM, Ford, Holden, etc.)
NON_BMW_PATTERNS = [
    r'LM7|LR4|LQ4|LQ9|LS1|LS2|LS3|LS6|L18|L83|L86|L96',  # GM engines
    r'Chevy|Chevrolet|GMC|Cadillac|Pontiac|Buick',  # GM brands
    r'K1500|K2500|C1500|C2500|Silverado|Sierra|Tahoe|Yukon|Suburban|Blazer',  # GM trucks/SUVs
    r'Camaro|Corvette|Impala|Malibu|Monte_Carlo',  # GM cars
    r'os\d{8}',  # GM OS identifiers like os12208322
    r'12202088|12208322|12216125|12579405|12593058',  # Known GM OS numbers
    r'Mustang|Explorer|F150|F250|Ranger|Bronco|Focus|Fusion|Taurus',  # Ford
    r'Commodore|Calais|Statesman|Berlina|Monaro|VT|VX|VY|VZ|VE|VF',  # Holden
    r'Sonic_ABM|ABMW_Flex',  # Sonic BMW badge variant (GM product)
    r'Subaru|Toyota|Honda|Nissan|Mazda|Mitsubishi|Kia|Hyundai',  # Asian brands
    r'Audi|VW|Volkswagen|Porsche|Mercedes|Benz',  # Audi/VW/Merc (not BMW)
]

NON_BMW_RE = re.compile('|'.join(NON_BMW_PATTERNS), re.IGNORECASE)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Collection to analyze")
    parser.add_argument("destination", type=Path, help="Copy destination outside the source")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Copy files into review lanes")
    args = parser.parse_args(argv)
    try:
        source, destination = validate_roots(args.source, args.destination)
        entries = []
        seen = {}
        for path in source_files(source, recursive=args.recursive):
            digest = get_file_hash(path)
            if NON_BMW_RE.search(path.name):
                lane = "review-name-heuristic"
            elif digest in seen:
                lane = "duplicate-content"
            else:
                lane = "selected"
            entry = plan_entry(source, path, lane)
            if digest in seen:
                entry["same_content_as"] = seen[digest]
            seen.setdefault(digest, path.relative_to(source).as_posix())
            entries.append(entry)
        execute_plan(source, destination, entries, args.apply, "cleanup-inventory.json")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
