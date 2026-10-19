"""Malformed or ragged data must not become a partial parity PASS."""

import json
import sys

import pytest

import tunerpro_native_export_parity as parity


def number(value):
    return parity.DisplayNumber(value, 2, f"{value:.2f}")


def native():
    return {"scalars": [], "parse_errors": [], "tables": [
        parity.NativeTable("Grid", 1, "ms", [number(100), number(200)],
                           [number(1000), number(2000)],
                           [[number(5), number(6)], [number(7), number(8)]])
    ]}


def exported():
    return {"tables": [{"title": "Grid", "data": [[5, 6], [7, 8]],
                        "axes": {"x": {"labels": [100, 200]},
                                 "y": {"labels": [1000, 2000]}, "z": {"unit": "ms"}}}]}


@pytest.mark.parametrize("matrix", [[[5, 6], [7]], [[5, 6], [7, 8, 999]], [[5, 6], []]])
def test_matrix_comparison_never_discards_ragged_cells(matrix):
    result = parity.compare_matrix(native()["tables"][0].data, matrix, 0.0)
    assert result["shape_mismatch"] is True
    assert result["mismatches"] > 0


@pytest.mark.parametrize("key,value", [
    ("data", [[5, 6], [7]]), ("data", [5, 6]), ("data", [[5, None], [7, 8]]),
    ("axes", []), ("axes", {"x": []}), ("axes", {"x": {"labels": [None]}}),
])
def test_malformed_table_evidence_is_rejected(key, value):
    candidate = exported()
    candidate["tables"][0][key] = value
    with pytest.raises(ValueError, match="Grid"):
        parity.compare_exports(native(), candidate, 0.0)


def test_valid_rectangular_table_still_matches():
    assert parity.compare_exports(native(), exported(), 0.0)["status"] == "PASS"


def test_malformed_table_cli_error_is_bounded_and_writes_no_report(tmp_path, monkeypatch, capsys):
    source = tmp_path / "native.txt"
    source.write_text("No native comparison evidence\n", encoding="utf-8")
    candidate = exported()
    candidate["tables"][0]["axes"] = []
    data = tmp_path / "export.json"
    data.write_text(json.dumps(candidate), encoding="utf-8")
    report = tmp_path / "parity.json"
    monkeypatch.setattr(sys, "argv", ["parity", str(source), str(data), "--out", str(report)])
    assert parity.main() == 2
    assert "Grid" in capsys.readouterr().err
    assert not report.exists()
