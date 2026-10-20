#!/usr/bin/env python3
"""Read-only axis-coordinate review for exported JSON files.

Monotonic coordinates are not necessarily correct or smooth calibration data.
Missing, literal, or non-finite coordinates are reported as unresolved.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path


def monotonic(values):
    if not values or any(not isinstance(value, (int, float)) or
                         not math.isfinite(value) for value in values):
        return None
    return all(left <= right for left, right in zip(values, values[1:]))


def inspect_file(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("tables"), list):
        raise ValueError(f"Not an exporter JSON object with tables: {path}")
    reports = []
    for table in data["tables"]:
        if not isinstance(table, dict):
            raise ValueError(f"Malformed table in {path}")
        axes = table.get("axes", {})
        result = {"title": table.get("title", "Unnamed table")}
        for axis in ("x", "y"):
            metadata = axes.get(axis, {})
            values = metadata.get("coordinate_values", metadata.get("labels", table.get(f"{axis}_labels", [])))
            result[axis] = monotonic(values)
        reports.append(result)
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="JSON files or directories (recursive)")
    args = parser.parse_args(argv)
    files = []
    for path in args.inputs:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.json")))
        elif path.is_file():
            files.append(path)
        else:
            parser.error(f"Input does not exist: {path}")
    if not files:
        parser.error("No JSON files found")
    try:
        for path in dict.fromkeys(files):
            reports = inspect_file(path)
            print(f"{path.name}: {len(reports)} tables; non-decreasing numeric coordinates:")
            for result in reports:
                print(f"  {result['title']}: X={result['x']} Y={result['y']} (None=unresolved)")
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
