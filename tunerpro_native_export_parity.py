#!/usr/bin/env python3
"""Compare Universal exporter JSON with a native TunerPro text export.

This checks displayed values, axes, dimensions, and table orientation. It does
not prove raw addresses, checksums, patches, or unsupported TunerPro equations.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Sequence


SECTION_RE = re.compile(r"^(TABLE|SCALAR|FLAG|PATCH|CHECKSUM):\s*", re.IGNORECASE)
NUMBER_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?$"
)
NUMBER_TOKEN_RE = re.compile(
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
)
SCALAR_RE = re.compile(
    r"^SCALAR:\s*(.*?)\s{2,}"
    r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)"
    r"(?:\s+(.*?))?\s*$",
    re.IGNORECASE,
)
HEX_SCALAR_RE = re.compile(
    r"^SCALAR:\s*(.*?)\s{2,}(0x[0-9A-Fa-f]+)(?:\s+(.*?))?\s*$",
    re.IGNORECASE,
)
TRAILING_NUMBER_RE = re.compile(
    r"(?:^|\s)([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)$"
)


@dataclass(frozen=True)
class DisplayNumber:
    value: float
    decimals: int
    text: str


@dataclass
class NativeTable:
    title: str
    occurrence: int
    unit: str
    x: list[DisplayNumber]
    y: list[DisplayNumber]
    data: list[list[DisplayNumber]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tunerpro_export", type=Path)
    parser.add_argument("exporter_json", type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        help="Write the detailed JSON report here.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Write the item-level CSV report here (defaults beside --out).",
    )
    parser.add_argument(
        "--absolute-tolerance",
        type=float,
        default=1e-9,
        help="Minimum numeric tolerance in addition to native display precision.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def normalize_title(value: str) -> str:
    return " ".join(value.strip().split())


def parse_display_number(token: str) -> DisplayNumber:
    text = token.strip()
    mantissa = re.split(r"[Ee]", text, maxsplit=1)[0]
    decimals = len(mantissa.rsplit(".", 1)[1]) if "." in mantissa else 0
    return DisplayNumber(float(text), decimals, text)


def numeric_line(line: str) -> list[DisplayNumber] | None:
    tokens = line.strip().split()
    if not tokens or any(NUMBER_RE.fullmatch(token) is None for token in tokens):
        return None
    return [parse_display_number(token) for token in tokens]


def numeric_tokens_with_spans(line: str) -> list[tuple[DisplayNumber, int, int]]:
    matches = list(NUMBER_TOKEN_RE.finditer(line))
    if not matches:
        return []
    remainder = NUMBER_TOKEN_RE.sub("", line)
    if remainder.strip():
        return []
    return [
        (parse_display_number(match.group()), match.start(), match.end())
        for match in matches
    ]


def parse_fixed_width_values(
    line: str,
    start: int,
    width: int,
    count: int,
) -> list[DisplayNumber] | None:
    values: list[DisplayNumber] = []
    for index in range(count):
        field = line[start + index * width : start + (index + 1) * width].strip()
        if NUMBER_RE.fullmatch(field) is None:
            return None
        values.append(parse_display_number(field))
    return values


def parse_fixed_width_header(line: str) -> list[DisplayNumber] | None:
    """Parse TunerPro's eight-character numeric export columns.

    Native export does not insert a delimiter when a positive value fills its
    complete field, so whitespace tokenization is insufficient for bad or
    byte-swapped calibrations with large displayed values.
    """
    text = line.rstrip()
    candidates = [(8, 8)]
    candidates.extend(
        (start, width)
        for width in range(6, 13)
        for start in range(0, min(20, len(text)) + 1)
        if (start, width) != (8, 8)
    )
    for start, width in candidates:
        if text[:start].strip():
            continue
        remaining = len(text) - start
        if remaining <= 0 or remaining % width:
            continue
        count = remaining // width
        values = parse_fixed_width_values(text, start, width, count)
        if values:
            return values
    return None


def parse_concatenated_decimal_line(line: str) -> list[DisplayNumber] | None:
    """Split adjacent fixed-precision numbers that exceed TunerPro's columns."""
    stripped = line.strip()
    if not stripped:
        return None
    for decimals in range(1, 10):
        pattern = re.compile(
            rf"[+-]?\d+?\.\d{{{decimals}}}(?:[Ee][+-]?\d+)?"
        )
        matches = list(pattern.finditer(stripped))
        if not matches:
            continue
        if pattern.sub("", stripped).strip():
            continue
        return [parse_display_number(match.group()) for match in matches]
    return None


def parse_scalar_line(line: str) -> tuple[str, DisplayNumber, str] | None:
    # Hex-output scalars are printed as e.g. "0x077E HEX". Try this first:
    # SCALAR_RE would otherwise read only the leading "0" of "0x077E".
    hex_match = HEX_SCALAR_RE.match(line.rstrip())
    if hex_match:
        title, number, unit = hex_match.groups()
        value = DisplayNumber(float(int(number, 16)), 0, number)
        return normalize_title(title), value, (unit or "").strip()
    match = SCALAR_RE.match(line.rstrip())
    if not match:
        return None
    title, number, unit = match.groups()
    return normalize_title(title), parse_display_number(number), (unit or "").strip()


def trailing_label_number(prefix: str) -> DisplayNumber | None:
    """Return the numeric part of a row label, allowing literal text before it.

    XDF axes may carry literal labels. TunerPro prints them verbatim, so a
    row can read ``et cetera 0.732      0.21``: the label is ``et cetera 0.732``
    and its numeric breakpoint is the trailing ``0.732``.
    """
    if NUMBER_RE.fullmatch(prefix or "") is not None:
        return parse_display_number(prefix)
    match = TRAILING_NUMBER_RE.search(prefix or "")
    return parse_display_number(match.group(1)) if match else None


def parse_native_table(
    title: str,
    occurrence: int,
    block: Sequence[str],
) -> NativeTable:
    unit = ""
    header_line = ""
    header_index = -1
    x: list[DisplayNumber] = []
    for index, line in enumerate(block):
        stripped = line.strip()
        if stripped.lower().startswith("cell units:"):
            unit = stripped.split(":", 1)[1].strip()
            continue
        parsed = (
            numeric_line(line)
            or parse_concatenated_decimal_line(line)
            or parse_fixed_width_header(line)
        )
        if parsed is not None:
            header_line = line
            header_index = index
            x = parsed
            break

    if header_index < 0 or not x:
        raise ValueError(
            f"table {title!r} occurrence {occurrence} has no readable X header"
        )

    header_spans = numeric_tokens_with_spans(header_line)
    starts = [item[1] for item in header_spans]
    if len(header_spans) != len(x):
        starts = [8 + index * 8 for index in range(len(x))]
    pitches = [
        later - earlier
        for earlier, later in zip(starts, starts[1:])
        if later > earlier
    ]
    if pitches:
        ordered_pitches = sorted(pitches)
        middle = len(ordered_pitches) // 2
        if len(ordered_pitches) % 2:
            field_width = ordered_pitches[middle]
        else:
            field_width = round(
                (ordered_pitches[middle - 1] + ordered_pitches[middle]) / 2
            )
    else:
        field_width = 8

    # Letters are allowed only in the row-label prefix (literal XDF labels);
    # the fixed-width value fields must still parse as numbers below.
    candidate_lines = [
        line
        for line in block[header_index + 1 :]
        if NUMBER_TOKEN_RE.search(line)
    ]

    alignments: list[
        tuple[int, int, list[DisplayNumber], list[list[DisplayNumber]]]
    ] = []
    expected_start = max(0, starts[0] - 1)
    candidate_widths = sorted(
        {
            width
            for width in (field_width - 1, field_width, field_width + 1, 8)
            if width >= 4
        }
    )
    for width in candidate_widths:
        max_start = min(
            max((len(line) for line in candidate_lines), default=0),
            starts[0] + width + 2,
        )
        for field_start in range(0, max_start + 1):
            body_data: list[list[DisplayNumber]] = []
            body_y: list[DisplayNumber] = []
            y_presence: bool | None = None
            valid = True
            for line in candidate_lines:
                values = parse_fixed_width_values(
                    line, field_start, width, len(x)
                )
                suffix = (
                    line[field_start + width * len(x) :].strip()
                    if values is not None
                    else ""
                )
                if values is not None and not suffix:
                    prefix = line[:field_start].strip()
                else:
                    # A literal label longer than the label column shifts the
                    # values right; read them as the last len(x) tokens.
                    tokens = line.split()
                    tail = tokens[-len(x):] if len(tokens) > len(x) else None
                    if not tail or any(NUMBER_RE.fullmatch(t) is None for t in tail):
                        continue
                    values = [parse_display_number(t) for t in tail]
                    prefix = " ".join(tokens[: -len(x)])
                prefix_number = trailing_label_number(prefix)
                if prefix and prefix_number is None:
                    continue
                has_y = prefix_number is not None
                if y_presence is None:
                    y_presence = has_y
                if has_y != y_presence:
                    valid = False
                    break
                if prefix_number is not None:
                    body_y.append(prefix_number)
                body_data.append(values)
            if valid and body_data:
                alignments.append((field_start, width, body_y, body_data))

    if not alignments:
        fallback_y: list[DisplayNumber] = []
        fallback_data: list[list[DisplayNumber]] = []
        y_presence: bool | None = None
        for line in candidate_lines:
            values = parse_concatenated_decimal_line(line)
            if values is None:
                continue
            if len(values) == len(x) + 1:
                has_y = True
                y_value = values[0]
                row = values[1:]
            elif len(values) == len(x):
                has_y = False
                y_value = None
                row = values
            else:
                continue
            if y_presence is None:
                y_presence = has_y
            if has_y != y_presence:
                continue
            if y_value is not None:
                fallback_y.append(y_value)
            fallback_data.append(row)
        if not fallback_data:
            raise ValueError(
                f"table {title!r} occurrence {occurrence} has no readable data rows"
            )
        body_y = fallback_y
        body_data = fallback_data
    else:
        _, _, body_y, body_data = max(
            alignments,
            key=lambda item: (
                len(item[3]),
                item[0] == 10 and item[1] == 8,
                item[1] == 8,
                -abs(item[0] - expected_start),
                item[1] == field_width,
            ),
        )

    return NativeTable(
        title=normalize_title(title),
        occurrence=occurrence,
        unit=unit,
        x=x,
        y=body_y,
        data=body_data,
    )


def parse_native_export(path: Path) -> dict[str, Any]:
    lines = read_text(path).splitlines()
    metadata: dict[str, str] = {}
    scalars: list[dict[str, Any]] = []
    tables: list[NativeTable] = []
    scalar_occurrences: dict[str, int] = {}
    table_occurrences: dict[str, int] = {}
    parse_errors: list[str] = []

    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("SOURCE FILE:"):
            metadata["source_file"] = line.split(":", 1)[1].strip()
        elif line.startswith("SOURCE DEFINITION:"):
            metadata["source_definition"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("SCALAR:"):
            parsed = parse_scalar_line(line)
            if parsed is None:
                parse_errors.append(f"unparsed scalar at line {index + 1}: {line!r}")
            else:
                title, value, unit = parsed
                occurrence = scalar_occurrences.get(title, 0) + 1
                scalar_occurrences[title] = occurrence
                scalars.append(
                    {
                        "title": title,
                        "occurrence": occurrence,
                        "value": value,
                        "unit": unit,
                    }
                )
        elif line.upper().startswith("TABLE:"):
            title = normalize_title(line.split(":", 1)[1])
            occurrence = table_occurrences.get(title, 0) + 1
            table_occurrences[title] = occurrence
            end = index + 1
            while end < len(lines) and SECTION_RE.match(lines[end]) is None:
                end += 1
            try:
                tables.append(
                    parse_native_table(title, occurrence, lines[index + 1 : end])
                )
            except ValueError as exc:
                parse_errors.append(str(exc))
            index = end - 1
        index += 1

    return {
        "metadata": metadata,
        "scalars": scalars,
        "tables": tables,
        "parse_errors": parse_errors,
    }


def load_exporter_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("exporter JSON top level is not an object")
    return value


def keyed_items(items: Iterable[Any], title_getter) -> dict[tuple[str, int], Any]:
    counts: dict[str, int] = {}
    output: dict[tuple[str, int], Any] = {}
    for item in items:
        title = normalize_title(str(title_getter(item)))
        occurrence = counts.get(title, 0) + 1
        counts[title] = occurrence
        output[(title, occurrence)] = item
    return output


def display_matches(
    native: DisplayNumber,
    candidate: float,
    absolute_tolerance: float,
) -> tuple[bool, float, float]:
    if not math.isfinite(native.value) or not math.isfinite(candidate):
        matched = (
            math.isnan(native.value)
            and math.isnan(candidate)
            or native.value == candidate
        )
        return matched, 0.0 if matched else math.inf, absolute_tolerance
    tolerance = max(
        absolute_tolerance,
        0.5 * (10.0 ** (-native.decimals)) + 1e-12,
    )
    delta = abs(native.value - candidate)
    return delta <= tolerance, delta, tolerance


def transpose(matrix: list[list[float]]) -> list[list[float]]:
    return [list(row) for row in zip(*matrix)]


def oriented_candidates(table: dict[str, Any]) -> Iterable[dict[str, Any]]:
    axes = table.get("axes") or {}
    x = [float(value) for value in ((axes.get("x") or {}).get("labels") or [])]
    y = [float(value) for value in ((axes.get("y") or {}).get("labels") or [])]
    data = [
        [float(value) for value in row]
        for row in (table.get("data") or [])
    ]

    bases = [("direct", x, y, data)]
    if data and all(len(row) == len(data[0]) for row in data):
        bases.append(("transpose", y, x, transpose(data)))

    for base_name, base_x, base_y, base_data in bases:
        for reverse_y in (False, True):
            for reverse_x in (False, True):
                candidate_x = list(reversed(base_x)) if reverse_x else list(base_x)
                candidate_y = list(reversed(base_y)) if reverse_y else list(base_y)
                candidate_data = [list(row) for row in base_data]
                if reverse_y:
                    candidate_data.reverse()
                if reverse_x:
                    candidate_data = [list(reversed(row)) for row in candidate_data]
                suffix: list[str] = []
                if reverse_y:
                    suffix.append("reverse_y")
                if reverse_x:
                    suffix.append("reverse_x")
                orientation = base_name
                if suffix:
                    orientation += "+" + "+".join(suffix)
                yield {
                    "orientation": orientation,
                    "x": candidate_x,
                    "y": candidate_y,
                    "data": candidate_data,
                }


def compare_number_series(
    native: Sequence[DisplayNumber],
    candidate: Sequence[float],
    absolute_tolerance: float,
) -> dict[str, Any]:
    if len(native) != len(candidate):
        return {
            "count": max(len(native), len(candidate)),
            "mismatches": max(len(native), len(candidate)),
            "max_delta": None,
            "shape_mismatch": True,
        }
    mismatches = 0
    max_delta = 0.0
    for expected, actual in zip(native, candidate):
        matched, delta, _ = display_matches(
            expected, float(actual), absolute_tolerance
        )
        if not matched:
            mismatches += 1
        max_delta = max(max_delta, delta)
    return {
        "count": len(native),
        "mismatches": mismatches,
        "max_delta": max_delta,
        "shape_mismatch": False,
    }


def compare_matrix(
    native: Sequence[Sequence[DisplayNumber]],
    candidate: Sequence[Sequence[float]],
    absolute_tolerance: float,
) -> dict[str, Any]:
    native_shape = (
        len(native),
        len(native[0]) if native else 0,
    )
    candidate_shape = (
        len(candidate),
        len(candidate[0]) if candidate else 0,
    )
    if native_shape != candidate_shape:
        return {
            "count": max(
                native_shape[0] * native_shape[1],
                candidate_shape[0] * candidate_shape[1],
            ),
            "mismatches": max(
                native_shape[0] * native_shape[1],
                candidate_shape[0] * candidate_shape[1],
            ),
            "max_delta": None,
            "shape_mismatch": True,
            "native_shape": list(native_shape),
            "candidate_shape": list(candidate_shape),
        }

    mismatches = 0
    max_delta = 0.0
    for expected_row, actual_row in zip(native, candidate):
        for expected, actual in zip(expected_row, actual_row):
            matched, delta, _ = display_matches(
                expected, float(actual), absolute_tolerance
            )
            if not matched:
                mismatches += 1
            max_delta = max(max_delta, delta)
    return {
        "count": native_shape[0] * native_shape[1],
        "mismatches": mismatches,
        "max_delta": max_delta,
        "shape_mismatch": False,
        "native_shape": list(native_shape),
        "candidate_shape": list(candidate_shape),
    }


def compare_table(
    native: NativeTable,
    exported: dict[str, Any],
    absolute_tolerance: float,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for candidate in oriented_candidates(exported):
        x_result = compare_number_series(
            native.x, candidate["x"], absolute_tolerance
        )
        y_result = compare_number_series(
            native.y, candidate["y"], absolute_tolerance
        )
        data_result = compare_matrix(
            native.data, candidate["data"], absolute_tolerance
        )
        mismatches = (
            x_result["mismatches"]
            + y_result["mismatches"]
            + data_result["mismatches"]
        )
        candidates.append(
            {
                "orientation": candidate["orientation"],
                "mismatches": mismatches,
                "x": x_result,
                "y": y_result,
                "data": data_result,
            }
        )

    if not candidates:
        return {
            "status": "MISMATCH",
            "orientation": None,
            "mismatches": 1,
            "reason": "exporter table has no orientation candidates",
        }
    best = min(
        candidates,
        key=lambda item: (
            item["mismatches"],
            item["x"]["shape_mismatch"]
            + item["y"]["shape_mismatch"]
            + item["data"]["shape_mismatch"],
            item["orientation"] != "direct",
        ),
    )
    best["status"] = "MATCH" if best["mismatches"] == 0 else "MISMATCH"
    return best


def compare_exports(
    native: dict[str, Any],
    exported: dict[str, Any],
    absolute_tolerance: float,
) -> dict[str, Any]:
    native_scalars = {
        (item["title"], item["occurrence"]): item
        for item in native["scalars"]
    }
    exported_scalars = keyed_items(
        exported.get("scalars") or [],
        lambda item: item.get("title", ""),
    )
    native_tables = {
        (item.title, item.occurrence): item for item in native["tables"]
    }
    exported_tables = keyed_items(
        exported.get("tables") or [],
        lambda item: item.get("title", ""),
    )

    scalar_results: list[dict[str, Any]] = []
    for key in sorted(native_scalars.keys() & exported_scalars.keys()):
        expected = native_scalars[key]
        actual = exported_scalars[key]
        matched, delta, tolerance = display_matches(
            expected["value"],
            float(actual.get("value")),
            absolute_tolerance,
        )
        scalar_results.append(
            {
                "type": "scalar",
                "title": key[0],
                "occurrence": key[1],
                "status": "MATCH" if matched else "MISMATCH",
                "native_value": expected["value"].value,
                "exporter_value": actual.get("value"),
                "delta": delta,
                "tolerance": tolerance,
                "native_unit": expected["unit"],
                "exporter_unit": str(actual.get("unit") or ""),
            }
        )

    table_results: list[dict[str, Any]] = []
    for key in sorted(native_tables.keys() & exported_tables.keys()):
        result = compare_table(
            native_tables[key],
            exported_tables[key],
            absolute_tolerance,
        )
        result.update(
            {
                "type": "table",
                "title": key[0],
                "occurrence": key[1],
                "native_unit": native_tables[key].unit,
                "exporter_unit": str(
                    (((exported_tables[key].get("axes") or {}).get("z") or {}).get("unit"))
                    or ""
                ),
            }
        )
        table_results.append(result)

    missing_scalars = sorted(native_scalars.keys() - exported_scalars.keys())
    extra_scalars = sorted(exported_scalars.keys() - native_scalars.keys())
    missing_tables = sorted(native_tables.keys() - exported_tables.keys())
    extra_tables = sorted(exported_tables.keys() - native_tables.keys())
    scalar_mismatches = sum(
        item["status"] != "MATCH" for item in scalar_results
    )
    table_mismatches = sum(
        item["status"] != "MATCH" for item in table_results
    )
    parse_errors = list(native.get("parse_errors") or [])
    passed = not any(
        (
            parse_errors,
            missing_scalars,
            extra_scalars,
            missing_tables,
            extra_tables,
            scalar_mismatches,
            table_mismatches,
        )
    )

    return {
        "schema": "kingai.tunerpro-native-display-parity.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "Displayed scalar/table/axis values only. This does not prove raw "
            "addresses, checksums, patches, or unsupported equation semantics."
        ),
        "status": "PASS" if passed else "FAIL",
        "native_metadata": native.get("metadata") or {},
        "exporter_metadata": exported.get("metadata") or {},
        "summary": {
            "native_parse_errors": len(parse_errors),
            "native_scalars": len(native_scalars),
            "exporter_scalars": len(exported_scalars),
            "common_scalars": len(scalar_results),
            "scalar_mismatches": scalar_mismatches,
            "missing_scalars": len(missing_scalars),
            "extra_scalars": len(extra_scalars),
            "native_tables": len(native_tables),
            "exporter_tables": len(exported_tables),
            "common_tables": len(table_results),
            "table_mismatches": table_mismatches,
            "missing_tables": len(missing_tables),
            "extra_tables": len(extra_tables),
        },
        "native_parse_errors": parse_errors,
        "missing_scalars": [
            {"title": title, "occurrence": occurrence}
            for title, occurrence in missing_scalars
        ],
        "extra_scalars": [
            {"title": title, "occurrence": occurrence}
            for title, occurrence in extra_scalars
        ],
        "missing_tables": [
            {"title": title, "occurrence": occurrence}
            for title, occurrence in missing_tables
        ],
        "extra_tables": [
            {"title": title, "occurrence": occurrence}
            for title, occurrence in extra_tables
        ],
        "scalars": scalar_results,
        "tables": table_results,
    }


def write_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "type",
                "title",
                "occurrence",
                "status",
                "orientation",
                "mismatches",
                "x_mismatches",
                "y_mismatches",
                "data_mismatches",
                "native_value",
                "exporter_value",
                "delta",
                "native_unit",
                "exporter_unit",
            ),
        )
        writer.writeheader()
        for item in report["scalars"]:
            writer.writerow(
                {
                    **{
                        key: item.get(key, "")
                        for key in writer.fieldnames
                    },
                    "mismatches": 0 if item["status"] == "MATCH" else 1,
                }
            )
        for item in report["tables"]:
            writer.writerow(
                {
                    **{
                        key: item.get(key, "")
                        for key in writer.fieldnames
                    },
                    "x_mismatches": (item.get("x") or {}).get("mismatches", ""),
                    "y_mismatches": (item.get("y") or {}).get("mismatches", ""),
                    "data_mismatches": (item.get("data") or {}).get(
                        "mismatches", ""
                    ),
                }
            )


def main() -> int:
    args = parse_args()
    try:
        native = parse_native_export(args.tunerpro_export)
        exported = load_exporter_json(args.exporter_json)
        report = compare_exports(
            native,
            exported,
            max(0.0, args.absolute_tolerance),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    csv_path = args.csv
    if csv_path is None and args.out is not None:
        csv_path = args.out.with_suffix(".csv")
    if csv_path is not None:
        write_csv(csv_path, report)

    summary = report["summary"]
    print(
        f"{report['status']}: "
        f"{summary['common_scalars']}/{summary['native_scalars']} scalars, "
        f"{summary['common_tables']}/{summary['native_tables']} tables; "
        f"{summary['scalar_mismatches']} scalar and "
        f"{summary['table_mismatches']} table mismatch(es); "
        f"{summary['native_parse_errors']} native parse error(s)."
    )
    if args.out:
        print(f"JSON: {args.out.resolve()}")
    if csv_path:
        print(f"CSV:  {csv_path.resolve()}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
