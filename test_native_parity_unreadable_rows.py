"""An incomplete native text capture cannot establish display parity."""

import json
import sys

import pytest

import tunerpro_native_export_parity as parity


def native_lines(bad_row=None):
    lines = [
        "TABLE: Grid",
        "  Cell Units: ms",
        "",
        "    Msec   Msec",
        "            0.00",
        "   0.976      0.11",
    ]
    if bad_row is not None:
        lines.append(bad_row)
    return lines


def exported_subset():
    return {
        "tables": [{
            "title": "Grid",
            "axes": {"x": {"labels": [0.0]},
                     "y": {"labels": [0.976]}, "z": {"unit": "ms"}},
            "data": [[0.11]],
        }],
    }


@pytest.mark.parametrize("bad_row", [
    "bad row 0.732      BROKEN",
    "   0.732      0.21 EXTRA",
    "garbage row",
])
def test_unreadable_native_row_cannot_disappear_from_parity(tmp_path, bad_row):
    source = tmp_path / "native.txt"
    source.write_text("\n".join(native_lines(bad_row)) + "\n", encoding="utf-8")
    native = parity.parse_native_export(source)
    assert native["parse_errors"]
    assert "unreadable data rows" in native["parse_errors"][0]
    assert parity.compare_exports(native, exported_subset(), 0.0)["status"] == "FAIL"


def test_ordinary_header_text_and_blank_lines_still_allow_complete_table(tmp_path):
    source = tmp_path / "native.txt"
    source.write_text("\n".join(native_lines() + ["", "  "]) + "\n", encoding="utf-8")
    native = parity.parse_native_export(source)
    assert native["parse_errors"] == []
    assert parity.compare_exports(native, exported_subset(), 0.0)["status"] == "PASS"


def test_numeric_only_truncated_row_cannot_match_one_row_subset(tmp_path):
    source = tmp_path / "native.txt"
    source.write_text("\n".join(native_lines("   0.732")) + "\n", encoding="utf-8")
    native = parity.parse_native_export(source)
    # Fixed-width parsing can reinterpret this ambiguous row. It must still
    # retain evidence of that row instead of approving the one-row subset.
    assert parity.compare_exports(native, exported_subset(), 0.0)["status"] == "FAIL"


def test_incomplete_native_capture_cli_reports_failure(tmp_path, monkeypatch, capsys):
    source = tmp_path / "native.txt"
    source.write_text("\n".join(native_lines("   0.732      0.21 EXTRA")) + "\n", encoding="utf-8")
    exported = tmp_path / "exported.json"
    exported.write_text(json.dumps(exported_subset()), encoding="utf-8")
    report = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["parity", str(source), str(exported), "--out", str(report)])
    assert parity.main() == 1
    assert "FAIL" in capsys.readouterr().out
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["summary"]["native_parse_errors"] == 1
    assert result["status"] == "FAIL"


@pytest.mark.parametrize("kind", ["scalar", "table", "axis", "hex_scalar", "imprecise_hex_scalar"])
def test_oversized_numeric_evidence_cli_returns_useful_error(tmp_path, monkeypatch, capsys, kind):
    source = tmp_path / "native.txt"
    exported = tmp_path / "exported.json"
    report = tmp_path / "report.json"
    source_text = "\n".join(native_lines()) + "\n"
    candidate = exported_subset()
    if kind == "scalar":
        candidate = {"scalars": [{"title": "Huge", "value": 10**400}]}
    elif kind == "table":
        candidate["tables"][0]["data"][0][0] = 10**400
    elif kind == "axis":
        candidate["tables"][0]["axes"]["x"]["labels"][0] = 10**400
    elif kind == "hex_scalar":
        source_text = "SCALAR: Huge  0x" + "F" * 1000 + " HEX\n"
    else:
        source_text = "SCALAR: Huge  0x20000000000001 HEX\n"
        candidate = {"scalars": [{"title": "Huge", "value": 9007199254740992, "unit": "HEX"}]}
    source.write_text(source_text, encoding="utf-8")
    exported.write_text(json.dumps(candidate), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["parity", str(source), str(exported), "--out", str(report)])
    assert parity.main() == 2
    error = capsys.readouterr().err
    assert "ERROR:" in error
    assert "Traceback" not in error
    assert not report.exists()
    assert not report.with_suffix(".csv").exists()
