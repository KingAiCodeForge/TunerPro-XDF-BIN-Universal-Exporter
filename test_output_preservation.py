"""Negative output-path and zero-evidence regressions; synthetic inputs only."""

import json
import os
from pathlib import Path
import sys

import pytest

import tunerpro_exporter as exporter_module
import tunerpro_native_export_parity as parity
from tunerpro_xdf.output_safety import open_new_output, preflight_output_paths


@pytest.fixture
def exporter(tmp_path):
    binary = tmp_path / "source.bin"
    binary.write_bytes(bytes(range(256)) * 4)
    xdf = tmp_path / "source.xdf"
    xdf.write_text('''<XDFFORMAT><XDFHEADER><deftitle>Output safety</deftitle></XDFHEADER>
      <XDFCONSTANT uniqueid="1"><title>Scalar</title>
        <EMBEDDEDDATA mmedaddress="0" mmedelementsizebits="8"/>
        <MATH equation="X"><VAR id="X"/></MATH>
      </XDFCONSTANT></XDFFORMAT>''', encoding="utf-8")
    result = exporter_module.UniversalXDFExporter(str(xdf), str(binary))
    assert result.validate_bin_file() and result.parse_xdf()
    return result


EXPORT_METHODS = ["export_to_text", "export_to_json", "export_to_markdown",
                  "export_to_csv", "export_zeros_report"]


@pytest.mark.parametrize("method", EXPORT_METHODS)
@pytest.mark.parametrize("source", ["xdf_path", "bin_path"])
def test_every_export_method_preserves_input_aliases(exporter, method, source):
    path = getattr(exporter, source)
    before = path.read_bytes()
    assert getattr(exporter, method)(str(path)) is False
    assert path.read_bytes() == before


@pytest.mark.parametrize("method", EXPORT_METHODS)
def test_every_export_method_refuses_existing_output(exporter, method, tmp_path):
    path = tmp_path / "existing.txt"
    path.write_bytes(b"preserve this output")
    assert getattr(exporter, method)(str(path)) is False
    assert path.read_bytes() == b"preserve this output"


def test_exclusive_open_refuses_creation_race(tmp_path):
    output = tmp_path / "race.txt"
    preflight_output_paths([output])
    output.write_bytes(b"other process owns this")
    with pytest.raises(FileExistsError):
        with open_new_output(output, encoding="utf-8"):
            pytest.fail("Existing output must not open")
    assert output.read_bytes() == b"other process owns this"


def test_duplicate_resolved_outputs_are_refused(tmp_path):
    path = tmp_path / "output.txt"
    with pytest.raises(ValueError, match="distinct"):
        preflight_output_paths([path, path.parent / "." / path.name])
    assert not path.exists()


def test_existing_hardlink_to_source_is_preserved(exporter, tmp_path):
    alias = tmp_path / "hardlink.txt"
    os.link(exporter.bin_path, alias)
    before = alias.read_bytes()
    assert exporter.export_to_text(str(alias)) is False
    assert exporter.bin_path.read_bytes() == alias.read_bytes() == before


def test_symlink_to_source_is_preserved(exporter, tmp_path):
    alias = tmp_path / "symlink.txt"
    try:
        alias.symlink_to(exporter.bin_path)
    except OSError as exc:
        pytest.skip(f"Symlink creation is not enabled: {exc}")
    before = exporter.bin_path.read_bytes()
    assert exporter.export_to_text(str(alias)) is False
    assert exporter.bin_path.read_bytes() == before


def run_export_cli(monkeypatch, exporter, output, *extra):
    monkeypatch.setattr(sys, "argv", ["exporter", str(exporter.xdf_path),
                        str(exporter.bin_path), str(output), *extra])
    with pytest.raises(SystemExit) as result:
        exporter_module.main()
    return result.value.code


@pytest.mark.parametrize("collision", ["csv", "zeros"])
def test_all_preflights_later_format_and_sidecar_before_any_write(
        exporter, tmp_path, monkeypatch, collision):
    output = tmp_path / "report"
    existing = tmp_path / ("report.csv" if collision == "csv" else "report_zeros.md")
    existing.write_bytes(b"preserve")
    assert run_export_cli(monkeypatch, exporter, output, "all") == 1
    assert existing.read_bytes() == b"preserve"
    assert not output.with_suffix(".txt").exists()
    assert not output.with_suffix(".json").exists()
    assert not output.with_suffix(".md").exists()


def test_new_all_format_export_remains_successful(exporter, tmp_path, monkeypatch):
    output = tmp_path / "fresh"
    assert run_export_cli(monkeypatch, exporter, output, "all") == 0
    for name in ("fresh.txt", "fresh.json", "fresh.md", "fresh.csv", "fresh_zeros.md"):
        path = tmp_path / name
        assert path.is_file() and path.stat().st_size > 0
    assert json.loads(output.with_suffix(".json").read_text())["scalars"][0]["value"] == 0


def test_derived_diagnostic_path_cannot_replace_an_input(exporter, monkeypatch):
    source = exporter.xdf_path.parent / "source_diagnostics.json"
    source.write_bytes(exporter.bin_path.read_bytes())
    before = source.read_bytes()
    exporter.bin_path = source
    assert run_export_cli(monkeypatch, exporter, source.parent / "source", "--diagnostics") == 1
    assert source.read_bytes() == before


def test_existing_diagnostic_report_is_preserved(exporter, tmp_path, monkeypatch):
    report = tmp_path / "report_diagnostics.json"
    report.write_bytes(b"preserve")
    assert run_export_cli(monkeypatch, exporter, tmp_path / "report", "--diagnostics") == 1
    assert report.read_bytes() == b"preserve"


def test_zero_graded_diagnostics_are_incomplete_not_clean(exporter):
    exporter.elements = {kind: [] for kind in ("constants", "flags", "tables", "patches")}
    exporter.xdf_root = exporter_module.ET.fromstring("<XDFFORMAT><XDFHEADER/></XDFFORMAT>")
    report = exporter.run_diagnostics()
    assert report["elements_graded"] == 0
    assert report["validation_complete"] is False
    assert report["grade"] == "INCOMPLETE"
    assert report["validation_errors"] == ["No scalar, flag or table elements were graded"]


def native_empty():
    return {"scalars": [], "tables": [], "parse_errors": []}


def test_empty_and_metadata_only_exports_cannot_pass():
    result = parity.compare_exports(native_empty(), {"metadata": {"name": "Only metadata"}}, 1e-9)
    assert result["status"] == "INCONCLUSIVE"
    assert result["summary"]["compared_objects"] == 0
    assert result["validation_errors"] == ["No scalar or table objects were compared"]


def test_empty_table_cannot_turn_zero_cell_comparison_into_pass():
    native = native_empty()
    native["tables"] = [parity.NativeTable("Empty", 1, "", [], [], [])]
    result = parity.compare_exports(native, {"tables": [{"title": "Empty", "data": []}]}, 1e-9)
    assert result["status"] == "FAIL"
    assert "no data cells" in result["tables"][0]["reason"]


def test_one_real_scalar_comparison_still_passes():
    native = native_empty()
    native["scalars"] = [{"title": "Scalar", "occurrence": 1, "unit": "",
                          "value": parity.DisplayNumber(10.0, 1, "10.0")}]
    result = parity.compare_exports(native, {"scalars": [{"title": "Scalar", "value": 10}]}, 1e-9)
    assert result["status"] == "PASS"
    assert result["summary"]["compared_objects"] == 1


@pytest.fixture
def parity_inputs(tmp_path):
    native = tmp_path / "native.txt"
    native.write_text("SCALAR: Scalar                    10.0\n", encoding="utf-8")
    exported = tmp_path / "exported.json"
    exported.write_text(json.dumps({"scalars": [{"title": "Scalar", "value": 10}]}), encoding="utf-8")
    return native, exported


@pytest.mark.parametrize("collision", ["native", "exported", "existing_csv", "same_outputs"])
def test_parity_preflights_all_reports_before_writing(parity_inputs, tmp_path, monkeypatch, collision):
    native, exported = parity_inputs
    before = {path: path.read_bytes() for path in parity_inputs}
    out = tmp_path / "parity.json"
    csv = tmp_path / "parity.csv"
    if collision == "native":
        out = native
    elif collision == "exported":
        csv = exported
    elif collision == "existing_csv":
        csv.write_bytes(b"preserve existing report")
    else:
        csv = out
    monkeypatch.setattr(sys, "argv", ["parity", str(native), str(exported), "--out", str(out), "--csv", str(csv)])
    assert parity.main() == 2
    for path, content in before.items():
        assert path.read_bytes() == content
    if collision == "existing_csv":
        assert csv.read_bytes() == b"preserve existing report"
    if out not in parity_inputs:
        assert not out.exists()


def test_new_parity_reports_write_successfully(parity_inputs, tmp_path, monkeypatch):
    native, exported = parity_inputs
    out = tmp_path / "parity.json"
    monkeypatch.setattr(sys, "argv", ["parity", str(native), str(exported), "--out", str(out)])
    assert parity.main() == 0
    report = json.loads(out.read_text())
    assert report["status"] == "PASS" and report["summary"]["compared_objects"] == 1
    assert out.with_suffix(".csv").is_file()
