#!/usr/bin/env python3
"""Read-only XDF/BIN diagnostics using the shared parser.

Zero values, ranges, and axis monotonicity are review signals. They do not
establish native TunerPro parity, correct calibration meaning, or flash safety.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from tunerpro_xdf.xdf_equations import evaluate_equation


def read_values(data, addr, sizebits, count, *, byteorder="big", signed=False):
    """Read explicit integer storage; incomplete or unsupported ranges fail."""
    if sizebits not in (8, 16, 32, 64) or count < 0 or addr < 0:
        raise ValueError("Unsupported integer size, count, or address")
    width = sizebits // 8
    if addr + width * count > len(data):
        raise ValueError("Requested values extend beyond the BIN")
    return [int.from_bytes(data[pos:pos + width], byteorder, signed=signed)
            for pos in range(addr, addr + width * count, width)]


def apply_equation(raw_values, equation):
    """Use the bounded shared equation evaluator and fail on unsupported syntax."""
    return [None if value is None else evaluate_equation(equation, {"X": value})
            for value in raw_values]


def is_monotonic(values):
    """Return a review signal only when every coordinate is finite numeric data."""
    if not values or any(not isinstance(v, (int, float)) or not math.isfinite(v)
                         for v in values):
        return None
    return all(left <= right for left, right in zip(values, values[1:]))


def check_all_zeros(values):
    """Empty or unresolved values cannot establish an all-zero signal."""
    return bool(values) and all(v is not None and v == 0 for v in values)


def load_exporter(xdf_path, bin_path):
    from tunerpro_exporter import UniversalXDFExporter
    exporter = UniversalXDFExporter(str(xdf_path), str(bin_path))
    if not exporter.validate_bin_file() or not exporter.parse_xdf():
        raise ValueError("Shared parser rejected the XDF/BIN pair; see diagnostics above")
    exporter._require_complete_export()
    return exporter


def table_diagnostics(exporter):
    """Read each table with shared storage/scoped-equation/axis semantics."""
    reports = []
    for table in exporter.elements["tables"]:
        matrix = exporter._read_table_data(table)
        if not matrix or not matrix[0]:
            raise ValueError(f"No readable cells for table {table['title']!r}")
        values = [cell for row in matrix for cell in row]
        reports.append({
            "title": table["title"], "data": matrix,
            "rows": len(matrix), "cols": len(matrix[0]),
            "minimum": min(values), "maximum": max(values),
            "all_zero": check_all_zeros(values),
            "axes": {axis: is_monotonic(table.get("axes", {}).get(axis, {}).get(
                "coordinate_values", [])) for axis in ("x", "y")},
        })
    return reports


def report_pair(xdf_path, bin_path):
    exporter = load_exporter(xdf_path, bin_path)
    reports = table_diagnostics(exporter)
    print(f"XDF: {xdf_path.name}; BIN: {bin_path.name}; bytes: {exporter.bin_size}")
    for report in reports:
        print(f"{report['title']}: {report['rows']}x{report['cols']} "
              f"range={report['minimum']}..{report['maximum']} "
              f"all_zero={report['all_zero']} axes_non_decreasing={report['axes']}")
    print(f"Read {len(reports)} tables. Review signals do not prove mapping or tuning safety.")
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xdf", type=Path, required=True)
    parser.add_argument("--bin", dest="binary", type=Path, required=True)
    parser.add_argument("--compare-xdf", type=Path)
    parser.add_argument("--compare-bin", type=Path)
    args = parser.parse_args(argv)
    if bool(args.compare_xdf) != bool(args.compare_bin):
        parser.error("--compare-xdf and --compare-bin must be supplied together")
    for path in (args.xdf, args.binary, args.compare_xdf, args.compare_bin):
        if path is not None and not path.is_file():
            parser.error(f"Input is not a file: {path}")
    try:
        reports = report_pair(args.xdf, args.binary)
        if args.compare_xdf:
            comparison = report_pair(args.compare_xdf, args.compare_bin)
            left = {item["title"]: item for item in reports}
            right = {item["title"]: item for item in comparison}
            if len(left) != len(reports) or len(right) != len(comparison):
                raise ValueError("Duplicate table titles prevent unambiguous name comparison")
            for title in sorted(left.keys() & right.keys()):
                print(f"Exact title {title!r}: equal_values={left[title]['data'] == right[title]['data']}")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
