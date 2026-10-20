"""Portable, read-only utility regression evidence using generated public data."""
from pathlib import Path
import subprocess
import sys

import pytest

import _validate_xdf_bin as validator
from check_axis_quality import inspect_file
from tunerpro_xdf.xdf_equations import EquationError

HERE = Path(__file__).resolve().parent


def run(script, *args, cwd=None):
    return subprocess.run([sys.executable, str(HERE / script), *map(str, args)],
                          cwd=cwd, capture_output=True, text=True, timeout=30)


def pair(tmp_path):
    folder = tmp_path / "arbitrary folder with spaces"
    folder.mkdir()
    xdf = folder / "generated definition.xdf"
    binary = folder / "generated input.bin"
    binary.write_bytes(bytes(range(32)))
    xdf.write_text('''<XDFFORMAT><XDFHEADER><BASEOFFSET offset="0" subtract="0"/></XDFHEADER>
      <XDFTABLE uniqueid="0x1"><title>Generated table</title>
      <XDFAXIS id="x"><indexcount>2</indexcount><LABEL index="0" value="0"/><LABEL index="1" value="1"/></XDFAXIS>
      <XDFAXIS id="y"><indexcount>1</indexcount><LABEL index="0" value="0"/></XDFAXIS>
      <XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0" mmedelementsizebits="8" mmedrowcount="1" mmedcolcount="2"/>
      <MATH equation="X*2"/></XDFAXIS></XDFTABLE></XDFFORMAT>''', encoding="utf-8")
    return folder, xdf, binary


@pytest.mark.parametrize("script", ["_compare_xml_xdf_addresses.py", "_validate_xdf_bin.py",
                                   "_validate_zeros_and_keys.py", "check_axis_quality.py", "verify_bins.py"])
def test_missing_arguments_are_clear_errors(script, tmp_path):
    result = run(script, cwd=tmp_path)
    assert result.returncode == 2
    assert "usage:" in result.stderr and "required" in result.stderr
    assert "Traceback" not in result.stderr
    assert not list(tmp_path.iterdir())


def test_imports_have_no_scan_or_output_side_effects(tmp_path):
    modules = ["_compare_xml_xdf_addresses", "_validate_xdf_bin", "_validate_zeros_and_keys",
               "check_axis_quality", "verify_bins"]
    code = "import sys; sys.path.insert(0, " + repr(str(HERE)) + "); " + "; ".join("import " + name for name in modules)
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "" and result.stderr == ""
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("script", ["_validate_xdf_bin.py", "_validate_zeros_and_keys.py"])
def test_generated_pair_works_outside_source_and_preserves_inputs(script, tmp_path):
    folder, xdf, binary = pair(tmp_path)
    before = {path.name: path.read_bytes() for path in folder.iterdir()}
    result = run(script, "--xdf", xdf, "--bin", binary, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Read 1 tables" in result.stdout
    assert "range=0..2" in result.stdout
    assert {path.name: path.read_bytes() for path in folder.iterdir()} == before


def test_equations_fail_closed_and_no_empty_zero_claim():
    assert validator.apply_equation([2, 3], "X*2") == [4, 6]
    with pytest.raises(EquationError):
        validator.apply_equation([2], "__import__('os').system('bad')")
    assert not validator.check_all_zeros([])
    assert not validator.check_all_zeros([None])
    assert validator.is_monotonic([0, None]) is None
    with pytest.raises(ValueError, match="beyond"):
        validator.read_values(b"x", 0, 16, 1)


def test_axis_report_distinguishes_missing_literal_and_numeric(tmp_path):
    import json
    report = tmp_path / "generated report.json"
    report.write_text(json.dumps({"tables": [
        {"title": "Numeric", "axes": {"x": {"coordinate_values": [0, 1, 2]}, "y": {"coordinate_values": [2, 1]}}},
        {"title": "Literal", "axes": {"x": {"coordinate_values": [None], "labels": [0]}}},
    ]}), encoding="utf-8")
    result = inspect_file(report)
    assert result[0]["x"] is True and result[0]["y"] is False
    assert result[1]["x"] is None
    completed = run("check_axis_quality.py", report, cwd=tmp_path)
    assert completed.returncode == 0 and "None=unresolved" in completed.stdout


def test_comparison_explicit_mapping_with_spaces_and_missing_evidence(tmp_path):
    folder = tmp_path / "definitions with spaces"
    folder.mkdir()
    xml = folder / "generated.xml"
    xdf = folder / "generated.xdf"
    xml.write_text('''<roms><rom><table name="base"/></rom><rom><romid><internalidstring>TEST</internalidstring><filesize>512kb</filesize></romid>
        <table name="Generated" storageaddress="10"/></rom></roms>''', encoding="utf-8")
    xdf.write_text('''<XDFFORMAT><XDFCONSTANT uniqueid="1"><title>Generated</title><EMBEDDEDDATA mmedaddress="0x10"/></XDFCONSTANT></XDFFORMAT>''', encoding="utf-8")
    result = run("_compare_xml_xdf_addresses.py", "--xml", xml, "--xdf", f"TEST_512kb={xdf}", cwd=tmp_path)
    assert result.returncode == 0 and "1 matched" in result.stdout
    missing = run("_compare_xml_xdf_addresses.py", "--xml", xml, "--xdf", f"OTHER_512kb={xdf}", cwd=tmp_path)
    assert missing.returncode == 2 and "No XML ROM matched" in missing.stderr


def test_verify_inventory_with_explicit_folder_and_read_error(tmp_path):
    folder = tmp_path / "custom collection"
    folder.mkdir()
    binary = folder / "generated.bin"
    binary.write_bytes(b"MS42 generated synthetic string 0110C6")
    result = run("verify_bins.py", folder, cwd=tmp_path)
    assert result.returncode == 0 and "heuristic" in result.stdout
    assert binary.read_bytes() == b"MS42 generated synthetic string 0110C6"
    missing = run("verify_bins.py", tmp_path / "missing", cwd=tmp_path)
    assert missing.returncode == 2 and "not a directory" in missing.stderr


def test_address_comparison_uses_z_storage_and_subtract_flag(tmp_path):
    from _compare_xml_xdf_addresses import parse_xdf_addresses
    xdf = tmp_path / "axis ownership.xdf"
    xdf.write_text('''<XDFFORMAT><XDFHEADER><BASEOFFSET offset="16" subtract="1"/></XDFHEADER>
      <XDFTABLE><title>Generated</title><XDFAXIS id="x"><EMBEDDEDDATA mmedaddress="0x20"/></XDFAXIS>
      <XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0x30"/></XDFAXIS></XDFTABLE></XDFFORMAT>''', encoding="utf-8")
    entries, base = parse_xdf_addresses(xdf)
    assert entries == {0x20: [("table", "Generated")]}
    assert base == 16
