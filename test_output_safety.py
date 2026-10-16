"""Synthetic output-path safety regression tests."""

import os

import pytest

from tunerpro_exporter import UniversalXDFExporter
from tunerpro_xdf.output_safety import assert_safe_output_plan


def make_exporter(tmp_path):
    xdf = tmp_path / "source.xdf"
    binary = tmp_path / "source.bin"
    xdf.write_text(
        '<XDFFORMAT><XDFHEADER/>'
        '<XDFCONSTANT uniqueid="1"><title>Scalar</title>'
        '<EMBEDDEDDATA mmedaddress="0"/><MATH equation="X"/>'
        '</XDFCONSTANT></XDFFORMAT>',
        encoding="utf-8",
    )
    binary.write_bytes(bytes([11]) + bytes(63))
    exporter = UniversalXDFExporter(str(xdf), str(binary))
    assert exporter.validate_bin_file()
    assert exporter.parse_xdf()
    return exporter, xdf, binary


@pytest.mark.parametrize("name", ["source.xdf", "source.bin"])
def test_direct_export_preserves_relative_input_alias(tmp_path, name):
    exporter, xdf, binary = make_exporter(tmp_path)
    before = xdf.read_bytes(), binary.read_bytes()
    (tmp_path / "subdir").mkdir()
    alias = tmp_path / "subdir" / ".." / name
    assert not exporter.export_to_json(str(alias))
    assert (xdf.read_bytes(), binary.read_bytes()) == before


def test_complete_plan_fails_before_any_output_is_written(tmp_path):
    exporter, xdf, binary = make_exporter(tmp_path)
    proposed = tmp_path / "first-output.txt"
    with pytest.raises(ValueError, match="aliases an input"):
        assert_safe_output_plan([proposed, xdf], [xdf, binary])
    assert not proposed.exists()


def test_duplicate_planned_outputs_are_rejected(tmp_path):
    exporter, xdf, binary = make_exporter(tmp_path)
    destination = tmp_path / "new.txt"
    with pytest.raises(ValueError, match="Two outputs alias"):
        assert_safe_output_plan(
            [destination, tmp_path / "." / "new.txt"], [xdf, binary]
        )
    assert not destination.exists()


def test_hardlink_output_cannot_modify_binary(tmp_path):
    exporter, xdf, binary = make_exporter(tmp_path)
    alias = tmp_path / "alias.txt"
    try:
        os.link(binary, alias)
    except OSError as exc:
        pytest.skip(f"Hardlinks unavailable: {exc}")
    before = binary.read_bytes()
    assert not exporter.export_to_csv(str(alias))
    assert binary.read_bytes() == before


def test_symlink_destination_is_rejected(tmp_path):
    exporter, xdf, binary = make_exporter(tmp_path)
    alias = tmp_path / "alias.txt"
    try:
        alias.symlink_to(xdf)
    except OSError as exc:
        pytest.skip(f"Symlinks unavailable: {exc}")
    before = xdf.read_bytes()
    assert not exporter.export_to_text(str(alias))
    assert xdf.read_bytes() == before


def test_distinct_output_paths_remain_valid(tmp_path):
    exporter, xdf, binary = make_exporter(tmp_path)
    assert_safe_output_plan(
        [tmp_path / "result.txt", tmp_path / "result_zeros.md"],
        [xdf, binary],
    )
    assert exporter.export_to_json(str(tmp_path / "result.json"))
    assert (tmp_path / "result.json").is_file()
