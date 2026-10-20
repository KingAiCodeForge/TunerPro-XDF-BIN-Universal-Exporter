#!/usr/bin/env python3
"""Preview or copy a BIN inventory into heuristic MS42/MS43 folders.

Pass explicit source and destination directories. Preview is the default;
--apply copies files and a SHA-256 manifest without changing source files.
Filename classification is a search hint, not ECU or XDF compatibility proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

def classify_bin(name_lower, path_str_lower):
    """Return 'ms42', 'ms43', 'unknown', or 'skip'."""
    # Skip non-ECU files
    if any(x in name_lower for x in ['325ti', 'jednotka']):
        return 'ms43'  # 325ti is MS43 project
    
    # Explicit MS43 markers
    if any(x in name_lower for x in ['ms43', '430069', '430070', '430037']):
        return 'ms43'
    
    # Explicit MS42 markers  
    if any(x in name_lower for x in ['ms42', '0110c6', '0110ad', '0110sa', '0110ca', '011025']):
        return 'ms42'
    
    # M52TU or M54B in name without MS4x prefix — check path context
    if 'm52tu' in name_lower or 'm54b' in name_lower:
        if 'ms43' in path_str_lower or '430069' in path_str_lower:
            return 'ms43'
        if 'ms42' in path_str_lower or '0110' in path_str_lower:
            return 'ms42'
        # Default: if it has m54b it's likely MS43 territory
        if 'm54b' in name_lower:
            return 'ms43'
        return 'ms42'
    
    # racemode alpha-N is MS43 430069
    if 'racemode' in name_lower:
        return 'ms43'
    
    # alpina
    if 'alpina' in name_lower:
        if '430037' in name_lower or '430070' in name_lower:
            return 'ms43'
        if '0110c6' in name_lower:
            return 'ms42'
    
    return 'unknown'


def get_file_hash(filepath, block_size=65536):
    """Return the complete SHA-256 digest; read failures propagate."""
    digest = hashlib.sha256()
    with open(filepath, "rb") as stream:
        for block in iter(lambda: stream.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def get_size_category(size):
    """Categorize by flash region size."""
    if size <= 35000:  # ~32KB
        return '32KB'
    elif size <= 70000:  # ~64KB
        return '64KB'
    elif size <= 130000:  # ~116KB
        return '116KB'
    elif size <= 530000:  # ~512KB
        return '512KB'
    elif size <= 1100000:  # ~1024KB
        return '1024KB'
    else:
        return f'{size}B'


def validate_roots(source, destination):
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"Source directory not found: {source}")
    if destination == source or source in destination.parents:
        raise ValueError("Destination must be outside the source directory")
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Destination is not a directory: {destination}")
    return source, destination


def source_files(source, recursive=True):
    """Yield regular files deterministically, without following directory links."""
    if recursive:
        for root, dirs, names in os.walk(source, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not (Path(root) / d).is_symlink())
            for name in sorted(names):
                path = Path(root) / name
                if path.is_file() and not path.is_symlink():
                    yield path
    else:
        yield from (p for p in sorted(source.iterdir()) if p.is_file() and not p.is_symlink())


def plan_entry(source, path, category, filename=None):
    """Preserve the relative parent path so equal basenames remain identifiable."""
    relative = path.relative_to(source)
    target = Path(category) / relative.parent / (filename or relative.name)
    return {"source": relative.as_posix(), "destination": target.as_posix(),
            "sha256": get_file_hash(path), "size": path.stat().st_size,
            "category_hint": category}


def execute_plan(source, destination, entries, apply=False, manifest_name="inventory.json"):
    """Preflight the whole plan, then exclusively create copies and a manifest.

    This prevents accidental overwrites; it is not an atomic directory transaction
    or protection against concurrent hostile path replacement. A failure can leave
    partial new outputs, but existing files and source files remain untouched.
    """
    source, destination = validate_roots(source, destination)
    manifest = destination / manifest_name
    targets = []
    seen = set()
    for entry in entries:
        target = destination / entry["destination"]
        resolved = target.resolve()
        if destination not in resolved.parents or resolved == destination:
            raise ValueError(f"Destination escapes output directory: {entry['destination']}")
        key = str(resolved).casefold()
        if key in seen:
            raise ValueError(f"Duplicate planned output: {entry['destination']}")
        seen.add(key)
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Refusing existing output: {target}")
        for parent in target.parents:
            if parent == destination.parent:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"Output parent is not a directory: {parent}")
        targets.append(target)
    if str(manifest.resolve()).casefold() in seen:
        raise ValueError("Manifest conflicts with a planned output")
    if manifest.exists() or manifest.is_symlink():
        raise FileExistsError(f"Refusing existing manifest: {manifest}")
    for entry, target in zip(entries, targets):
        print(f"{'COPY' if apply else 'PREVIEW'} {entry['source']} -> {entry['destination']} sha256={entry['sha256']}")
    if not apply:
        print(f"Preview: {len(entries)} files; no files written. Use --apply to create copies.")
        return
    for entry, target in zip(entries, targets):
        origin = source / entry["source"]
        if get_file_hash(origin) != entry["sha256"]:
            raise ValueError(f"Source changed since planning: {entry['source']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with origin.open("rb") as reader, target.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        if get_file_hash(target) != entry["sha256"]:
            raise OSError(f"Copy hash mismatch: {target}")
    destination.mkdir(parents=True, exist_ok=True)
    with manifest.open("x", encoding="utf-8") as stream:
        json.dump({"schema": "kingai.copy-inventory.v1",
                   "classification": "filename heuristics only; no ECU or XDF qualification",
                   "source_files_preserved": True, "files": entries}, stream, indent=2)
        stream.write("\n")
    print(f"Created {len(entries)} copies; manifest: {manifest}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Source directory containing BIN files")
    parser.add_argument("destination", type=Path, help="Output directory outside source")
    parser.add_argument("--flat", action="store_true", help="Scan only the source directory")
    parser.add_argument("--apply", action="store_true", help="Create copies; preserve all source files")
    args = parser.parse_args(argv)
    try:
        source, destination = validate_roots(args.source, args.destination)
        entries = []
        for path in source_files(source, recursive=not args.flat):
            if path.suffix.lower() != ".bin":
                continue
            relative = path.relative_to(source)
            category = classify_bin(path.name.lower(), relative.as_posix().lower())
            entries.append(plan_entry(source, path, {"ms42": "all_ms42_bins", "ms43": "all_ms43_bins"}.get(category, "unclassified")))
        execute_plan(source, destination, entries, args.apply)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
