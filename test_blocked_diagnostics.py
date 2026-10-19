"""A failed parse can produce failure evidence, never a clean subset grade."""

import hashlib
import json
import sys

import pytest

import tunerpro_exporter as module


def run(monkeypatch, xdf, binary, output, *flags):
    monkeypatch.setattr(sys, "argv", ["exporter", str(xdf), str(binary), str(output), *flags])
    with pytest.raises(SystemExit) as result:
        module.main()
    return result.value.code


@pytest.mark.parametrize("text,reason", [
    ("<XDFFORMAT>", "parse XDF"),
    ('<XDFFORMAT><XDFCONSTANT><title>Bad</title>'
     '<EMBEDDEDDATA mmedaddress="not-an-address"/></XDFCONSTANT></XDFFORMAT>', "mmedaddress"),
    ('<XDFFORMAT><XDFCONSTANT uniqueid="2"><title>Already parsed</title>'
     '<EMBEDDEDDATA mmedaddress="8" mmedelementsizebits="8"/><MATH equation="X"/></XDFCONSTANT>'
     '<XDFTABLE uniqueid="1"><title>Missing link</title>'
     '<XDFAXIS id="x"><indexcount>2</indexcount><embedinfo type="3"/></XDFAXIS>'
     '<XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0" mmedelementsizebits="8" '
     'mmedrowcount="1" mmedcolcount="2"/><MATH equation="X"/></XDFAXIS>'
     '</XDFTABLE></XDFFORMAT>', "linkobjid"),
])
def test_blocked_parse_diagnostic_has_identity_and_no_grade_claim(tmp_path, monkeypatch, text, reason):
    xdf, binary = tmp_path / "source.xdf", tmp_path / "source.bin"
    xdf.write_text(text, encoding="utf-8")
    binary.write_bytes(bytes(range(64)))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (xdf, binary)}
    assert run(monkeypatch, xdf, binary, tmp_path / "review", "--diagnostics") == 1
    report = json.loads((tmp_path / "review_diagnostics.json").read_text())
    assert report["report_kind"] == "blocked_input"
    assert report["failure_phase"] == "xdf_parse"
    assert report["grade"] == "INCOMPLETE" and report["validation_complete"] is False
    assert report["elements_graded"] == 0 and report["refuted_count"] is None
    assert reason.lower() in " ".join(report["validation_errors"]).lower()
    assert report["input_identity"]["xdf"]["sha256"] == before[xdf]
    assert report["input_identity"]["bin"]["sha256"] == before[binary]
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (xdf, binary)}
    assert not (tmp_path / "review.txt").exists()


def test_ordinary_export_parse_failure_writes_nothing(tmp_path, monkeypatch):
    xdf, binary = tmp_path / "source.xdf", tmp_path / "source.bin"
    xdf.write_text("<broken>", encoding="utf-8")
    binary.write_bytes(bytes(64))
    assert run(monkeypatch, xdf, binary, tmp_path / "review.json", "--no-zerosexport") == 1
    assert not (tmp_path / "review.json").exists()
    assert not (tmp_path / "review_diagnostics.json").exists()


def test_blocked_report_cannot_replace_existing_file(tmp_path, monkeypatch):
    xdf, binary = tmp_path / "source.xdf", tmp_path / "source.bin"
    xdf.write_text("<broken>", encoding="utf-8")
    binary.write_bytes(bytes(64))
    report = tmp_path / "review_diagnostics.json"
    report.write_bytes(b"keep this report")
    assert run(monkeypatch, xdf, binary, tmp_path / "review", "--diagnostics") == 1
    assert report.read_bytes() == b"keep this report"


@pytest.mark.parametrize("missing", ["xdf", "bin"])
def test_missing_input_is_identified_without_inventing_a_hash(tmp_path, monkeypatch, missing):
    xdf, binary = tmp_path / "source.xdf", tmp_path / "source.bin"
    if missing != "xdf":
        xdf.write_text("<XDFFORMAT/>", encoding="utf-8")
    if missing != "bin":
        binary.write_bytes(bytes(64))
    assert run(monkeypatch, xdf, binary, tmp_path / "review", "--diagnostics") == 1
    report = json.loads((tmp_path / "review_diagnostics.json").read_text())
    assert report["failure_phase"] == ("binary_validation" if missing == "bin" else "xdf_parse")
    assert report["input_identity"][missing]["sha256"] is None
    assert report["input_identity"][missing]["identity_error"]


def test_temporary_error_capture_is_removed_after_failure(tmp_path, monkeypatch):
    xdf, binary = tmp_path / "source.xdf", tmp_path / "source.bin"
    xdf.write_text("<broken>", encoding="utf-8")
    binary.write_bytes(bytes(64))
    logger = module.logging.getLogger(module.__name__)
    before = list(logger.handlers)
    assert run(monkeypatch, xdf, binary, tmp_path / "review", "--diagnostics") == 1
    assert logger.handlers == before


def test_report_write_failure_stays_a_cli_error(tmp_path, monkeypatch, capsys):
    xdf, binary = tmp_path / "source.xdf", tmp_path / "source.bin"
    xdf.write_text("<broken>", encoding="utf-8")
    binary.write_bytes(bytes(64))
    def refused(*args, **kwargs):
        raise PermissionError("simulated destination denied")
    monkeypatch.setattr(module.UniversalXDFExporter, "_open_output", refused)
    assert run(monkeypatch, xdf, binary, tmp_path / "review", "--diagnostics") == 1
    assert "Cannot write diagnostics" in capsys.readouterr().out
    assert not (tmp_path / "review_diagnostics.json").exists()
