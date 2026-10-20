"""Synthetic converter collision and portable input checks."""
from pathlib import Path
import subprocess
import sys
import pytest

import bmw_0pa_0da_to_bin as converter
from test_bmw_0pa_0da_to_bin import ihex, package


def test_repeated_conversion_never_replaces_hash_fallback(tmp_path):
    source = tmp_path / "synthetic input.0da"
    source.write_text(package("0DA", "SYNTHETIC", [ihex(0, 0, b"\x01"), ihex(0, 1)]))
    output = tmp_path / "output with spaces"
    first = converter.convert_file(str(source), str(output), force_ecu="MDS42")
    second = converter.convert_file(str(source), str(output), force_ecu="MDS42")
    assert first["success"] and second["success"]
    fallback = Path(second["output"])
    fallback.write_bytes(b"existing fallback owned by user")
    third = converter.convert_file(str(source), str(output), force_ecu="MDS42")
    assert not third["success"]
    assert fallback.read_bytes() == b"existing fallback owned by user"
    assert source.is_file()


def test_converter_scan_requires_explicit_roots(monkeypatch):
    monkeypatch.delenv("KINGAI_SPDATEN_PATHS", raising=False)
    assert converter.get_spdaten_paths() == []


def test_missing_converter_input_fails_without_outputs(tmp_path):
    assert converter.process_path(str(tmp_path / "missing.0da"))[0]["success"] is False


def test_info_combine_is_refused_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["converter", "--info", "--combine", "a.0pa", "b.0da"])
    with pytest.raises(SystemExit) as result:
        converter.main()
    assert result.value.code == 2
    assert not list(tmp_path.iterdir())


def test_cli_fill_reaches_normal_conversion(tmp_path, monkeypatch):
    source = tmp_path / "input.0da"
    source.write_text(package("Daten", "SYNTHETIC", [ihex(1, 0, b"\x01"), ihex(0, 1)]))
    output = tmp_path / "output"
    monkeypatch.setattr(sys, "argv", ["converter", str(source), "-o", str(output), "--fill", "0"])
    assert converter.main() == 0
    binary = next(output.glob("*.bin")).read_bytes()
    assert binary[:2] == b"\x00\x01"
