"""Synthetic native-parity verdict regressions; no customer BIN/XDF data.

Run in a checkout:
    python -m pytest -q test_tunerpro_native_export_parity.py test_native_parity_verdict.py

The comparator only checks displayed native/exported values and units, not
correct file offsets, checksum, safe tune edits, or physical ECU behavior.
"""
from __future__ import annotations

import csv
from tunerpro_native_export_parity import (
    DisplayNumber, NativeTable, compare_exports, parse_native_export, write_csv,
)


def n(value: float) -> DisplayNumber:
    return DisplayNumber(value=value, decimals=2, text=f"{value:.2f}")


def native(*, scalars=(), tables=(), parse_errors=()):
    return {"metadata": {}, "scalars": list(scalars),
            "tables": list(tables), "parse_errors": list(parse_errors)}


def exporter(*, scalars=(), tables=()):
    return {"metadata": {}, "scalars": list(scalars), "tables": list(tables)}


def scalar_native(unit="kPa", value=100.0, title="Pressure"):
    return {"title": title, "occurrence": 1, "value": n(value), "unit": unit}


def scalar_exporter(unit="kPa", value=100.0, title="Pressure"):
    return {"title": title, "value": value, "unit": unit}


def table_native(unit="ms"):
    return NativeTable(title="Pulse", occurrence=1, unit=unit,
        x=[n(100), n(200)], y=[n(1000)], data=[[n(5), n(6)]])


def table_exporter(unit="ms"):
    return {"title": "Pulse",
            "axes": {"x": {"labels": [100.0, 200.0]},
                     "y": {"labels": [1000.0]}, "z": {"unit": unit}},
            "data": [[5.0, 6.0]]}


def test_two_empty_exports_are_inconclusive():
    result = compare_exports(native(), exporter(), 0.0)
    assert result["status"] == "INCONCLUSIVE"
    assert result["summary"]["compared_objects"] == 0


def test_unrecognized_native_text_does_not_count_as_parity(tmp_path):
    source = tmp_path / "unrelated.txt"
    source.write_text("This is not an XDF export.\n", encoding="utf-8")
    result = compare_exports(parse_native_export(source), exporter(), 0.0)
    assert result["status"] != "PASS"


def test_good_scalar_matches():
    r = compare_exports(native(scalars=[scalar_native()]),
                        exporter(scalars=[scalar_exporter()]), 0.0)
    assert r["status"] == "PASS"
    assert r["summary"]["compared_objects"] == 1
    assert r["scalars"][0]["unit_match"] is True


def test_good_table_matches():
    r = compare_exports(native(tables=[table_native()]),
                        exporter(tables=[table_exporter()]), 0.0)
    assert r["status"] == "PASS"
    assert r["tables"][0]["unit_match"] is True


def test_scalar_different_unit_fails_even_when_value_matches():
    r = compare_exports(native(scalars=[scalar_native(unit="kPa")]),
                        exporter(scalars=[scalar_exporter(unit="psi")]), 0.0)
    assert r["status"] == "FAIL"
    assert r["summary"]["scalar_unit_mismatches"] == 1
    assert r["scalars"][0]["numeric_match"] is True
    assert r["scalars"][0]["status"] == "MISMATCH"


def test_table_different_unit_fails_even_when_cells_match():
    r = compare_exports(native(tables=[table_native(unit="ms")]),
                        exporter(tables=[table_exporter(unit="deg")]), 0.0)
    assert r["status"] == "FAIL"
    assert r["summary"]["table_unit_mismatches"] == 1
    assert r["tables"][0]["mismatches"] >= 1


def test_whitespace_and_case_of_same_unit_are_not_differences():
    r = compare_exports(native(scalars=[scalar_native(unit="kPa  /  s")]),
                        exporter(scalars=[scalar_exporter(unit="KPA / S")]), 0.0)
    assert r["status"] == "PASS"


def test_missing_unit_cannot_match_nonempty_unit():
    r = compare_exports(native(scalars=[scalar_native(unit="")]),
                        exporter(scalars=[scalar_exporter(unit="kPa")]), 0.0)
    assert r["status"] == "FAIL"


def test_missing_items_still_fail():
    r = compare_exports(native(scalars=[scalar_native()]), exporter(), 0.0)
    assert r["status"] == "FAIL"
    assert r["summary"]["missing_scalars"] == 1


def test_mismatched_values_still_fail():
    t = table_exporter()
    t["data"][0][0] = 45.0
    r = compare_exports(native(tables=[table_native()]),
                        exporter(tables=[t]), 0.0)
    assert r["status"] == "FAIL"
    assert r["summary"]["table_mismatches"] == 1


def test_native_parse_error_remains_failure():
    r = compare_exports(native(parse_errors=["unparsed scalar"]), exporter(), 0.0)
    assert r["status"] == "FAIL"


def test_csv_contains_unit_mismatch_flag(tmp_path):
    r = compare_exports(native(scalars=[scalar_native(unit="kPa")]),
                        exporter(scalars=[scalar_exporter(unit="psi")]), 0.0)
    output = tmp_path / "parity.csv"
    write_csv(output, r)
    with output.open(newline="", encoding="utf-8") as file:
        records = list(csv.DictReader(file))
    assert records[0]["status"] == "MISMATCH"
    assert records[0]["unit_match"] == "False"
