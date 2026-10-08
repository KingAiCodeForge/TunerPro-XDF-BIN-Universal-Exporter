"""Portable regressions for shared addressing and explicit MATH selectors."""

import xml.etree.ElementTree as ET

import pytest

from tunerpro_exporter import UniversalXDFExporter
from tunerpro_xdf.xdf_addressing import TableLayout, file_offset


def test_contiguous_explicit_row_stride():
    layout = TableLayout(0x10, 2, 3, 8, 24, 8)
    assert [layout.cell_address(r, c) for r in range(2) for c in range(3)] == list(range(0x10, 0x16))
    assert layout.file_span() == (0x10, 0x16)
    layout.validate_write()


def test_interleaved_float_review_layout_and_write_hold():
    layout = TableLayout(0x34, 1, 4, 32, 64, 64)
    assert [layout.cell_address(0, c) for c in range(4)] == [0x34, 0x3C, 0x44, 0x4C]
    assert layout.file_span() == (0x34, 0x50)
    with pytest.raises(ValueError, match="native TunerPro parity"):
        layout.validate_write()


def test_positive_major_only_curve_review_layout():
    assert TableLayout(0, 1, 3, 16, 64).file_span() == (0, 18)
    assert TableLayout(0, 3, 1, 16, 64).file_span() == (0, 18)


def test_64_bit_storage_is_retained():
    assert TableLayout(0, 2, 2, 64).file_span() == (0, 32)


def test_invalid_base_mode_is_rejected():
    with pytest.raises(ValueError, match="subtract"):
        file_offset(10, 2, 3)


@pytest.mark.parametrize("major,minor", [(-8, 0), (0, -8), (12, 0)])
def test_unproven_negative_and_bit_aligned_layouts_are_rejected(major, minor):
    with pytest.raises(ValueError):
        TableLayout(0, 2, 2, 8, major, minor)


def selector(body, index_base=0):
    exporter = UniversalXDFExporter("unused.xdf", "unused.bin")
    z = {"xml_element": ET.fromstring('<XDFAXIS id="z">' + body + '</XDFAXIS>'),
         "equation": "X", "linked_vars": {}}
    z["math_index_base"] = index_base
    return exporter._cell_equation_selector(z)


def test_explicit_one_based_scoped_math():
    pick = selector(
        '<MATH equation="X"/><MATH row="1" equation="X+10"/>'
        '<MATH row="2" col="2" equation="X+20"/>',
        index_base=1,
    )
    assert pick(0, 0)[0] == "X+10"
    assert pick(1, 1)[0] == "X+20"
    assert pick(1, 0)[0] == "X"


@pytest.mark.parametrize("index_base", [-1, 2, "1", None, True])
def test_invalid_scoped_math_index_base_is_rejected(index_base):
    with pytest.raises(ValueError, match="index base"):
        selector('<MATH equation="X"/><MATH row="1" equation="X+1"/>', index_base)


def test_explicit_one_based_scoped_math_rejects_zero_selector():
    with pytest.raises(ValueError, match="below index base"):
        selector('<MATH equation="X"/><MATH row="0" equation="X+1"/>', 1)


def test_second_row_selector_never_changes_first_row():
    pick = selector('<MATH equation="X"/><MATH row="1" equation="X*2"/>')
    assert pick(0, 0)[0] == "X"
    assert pick(1, 0)[0] == "X*2"


def test_cell_row_column_global_precedence():
    pick = selector('<MATH equation="X"/><MATH col="1" equation="X+1"/>'
                    '<MATH row="1" equation="X+2"/><MATH row="1" col="1" equation="X+3"/>')
    assert [pick(r, c)[0] for r, c in ((0, 0), (0, 1), (1, 0), (1, 1))] == ["X", "X+1", "X+2", "X+3"]


def test_single_scoped_equation_does_not_become_global():
    pick = selector('<MATH row="1" equation="X*2"/>')
    assert pick(1, 0)[0] == "X*2"
    with pytest.raises(ValueError, match="No global MATH"):
        pick(0, 0)


@pytest.mark.parametrize("index", ["garbage", "-1"])
def test_invalid_scoped_index_is_not_reinterpreted_as_global(index):
    with pytest.raises(ValueError, match="scoped MATH index"):
        selector(f'<MATH equation="X"/><MATH row="{index}" equation="X*2"/>')


def test_duplicate_scoped_selector_is_not_last_writer_wins():
    with pytest.raises(ValueError, match="Duplicate"):
        selector('<MATH row="1" equation="X"/><MATH row="1" equation="X*2"/>')
