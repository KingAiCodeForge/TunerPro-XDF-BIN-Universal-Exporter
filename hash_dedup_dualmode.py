#!/usr/bin/env python3
"""Read-only full-SHA256 analysis for explicit BIN collections.

No files are copied, moved or removed. Filename hints do not establish ECU
identity. Pass source and collection directories explicitly on every machine.
"""
import argparse
import hashlib
from pathlib import Path
from public_collection_cli import write_report


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha16(path):
    """Legacy function name; returns complete SHA256 for reliable identity."""
    return sha256(path)


def build_hash_map(folder):
    result = {}
    for path in sorted(Path(folder).iterdir()):
        if path.is_file() and not path.is_symlink():
            result.setdefault(sha256(path), []).append(path.name)
    return result


def route(fname_lower, path_lower):
    text = (fname_lower + " " + path_lower).lower()
    if any(hint in text for hint in ("ms_42", "0110c6", "0110ad", "ms42")):
        return "ms42 filename hint"
    if any(hint in text for hint in ("ms_43", "430", "m54b", "ms43")):
        return "ms43 filename hint"
    return "unclassified"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Source directory to scan recursively")
    parser.add_argument("--collection", action="append", type=Path, default=[],
                        help="Existing collection directory; repeat as needed")
    parser.add_argument("--ms42", type=Path, help="Explicit legacy MS42 collection path")
    parser.add_argument("--ms43", type=Path, help="Explicit legacy MS43 collection path")
    parser.add_argument("-o", "--output", type=Path, help="New report; existing files refused")
    args = parser.parse_args(argv)
    collections = args.collection + [p for p in (args.ms42, args.ms43) if p is not None]
    if not collections:
        parser.error("Provide at least one --collection, --ms42 or --ms43 directory")
    for folder in [args.source] + collections:
        if not folder.is_dir():
            parser.error(f"Directory not found: {folder}")
    if args.output and (args.output.exists() or args.output.is_symlink()):
        parser.error(f"Refusing to overwrite report: {args.output}")
    try:
        known = set()
        for folder in collections:
            known.update(build_hash_map(folder))
        lines = ["Read-only duplicate analysis (filename hints do not qualify ECU identity)"]
        seen = {}
        counts = {"existing": 0, "source duplicate": 0, "new": 0}
        for path in sorted(args.source.rglob("*")):
            if not path.is_file() or path.is_symlink() or path.suffix.lower() != ".bin":
                continue
            digest = sha256(path)
            status = "existing" if digest in known else "source duplicate" if digest in seen else "new"
            counts[status] += 1
            relative = path.relative_to(args.source)
            lines.append(f"{status}\t{digest}\t{path.stat().st_size}\t{relative}\t{route(path.name, str(relative.parent))}")
            seen.setdefault(digest, relative)
        lines.append("Summary: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
        report = "\n".join(lines) + "\n"
        write_report(args.output, report)
        print(report, end="")
        return 0
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
