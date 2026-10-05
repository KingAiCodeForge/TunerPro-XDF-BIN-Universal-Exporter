"""Synthetic bounds and layout checks; no private firmware fixtures."""

import pytest

from tunerpro_xdf.xdf_addressing import TableLayout, file_offset


@pytest.mark.parametrize("bits", [8, 16, 32, 64])
@pytest.mark.parametrize("explicit", [False, True])
def test_contiguous_cells_and_file_span(bits, explicit):
    step = bits if explicit else 0
    layout = TableLayout(0x100, 2, 3, bits, step, step)
    width = bits // 8
    assert [layout.cell_address(r, c) for r in range(2) for c in range(3)] == [
        0x100 + i * width for i in range(6)
    ]
    assert layout.file_span(0x100, 1) == (0, 6 * width)


@pytest.mark.parametrize("major,minor", [(32, 0), (0, 32), (-8, 0), (0, -8), (9, 0)])
def test_unproven_layouts_do_not_guess_addresses(major, minor):
    with pytest.raises(ValueError):
        TableLayout(0, 2, 2, 8, major, minor)


def test_base_offset_matches_documented_add_and_subtract_examples():
    assert file_offset(0xF0, 0x4000, 0) == 0x40F0
    assert file_offset(0x80F0, 0x8000, 1) == 0xF0
    with pytest.raises(ValueError):
        file_offset(0xF0, 0x4000, 2)


def test_column_major_cells_follow_tunerpro_flag_semantics():
    layout = TableLayout(0x100, 2, 3, 8, row_major=False)
    assert [[layout.cell_address(r, c) for c in range(3)] for r in range(2)] == [
        [0x100, 0x102, 0x104],
        [0x101, 0x103, 0x105],
    ]
    assert layout.file_span() == (0x100, 0x106)


def test_table_layout_derives_column_major_from_type_flags_bit_2():
    from tunerpro_xdf.xdf_addressing import table_layout
    table = {"axes": {"z": {"address": 0x200, "row_count": 17, "col_count": 3,
                              "size_bits": 8, "type_flags": 0x04}}}
    layout = table_layout(table)
    assert layout.row_major is False
    assert [layout.cell_address(0, c) for c in range(3)] == [0x200, 0x211, 0x222]
    assert [layout.cell_address(16, c) for c in range(3)] == [0x210, 0x221, 0x232]
