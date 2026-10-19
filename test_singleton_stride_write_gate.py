"""Regression: partial singleton strides must not open non-contiguous writes."""

import pytest

from tunerpro_xdf.xdf_addressing import TableLayout


@pytest.mark.parametrize("bits", [8, 16, 32, 64])
@pytest.mark.parametrize("cols", [3, 7])
def test_single_row_major_equal_row_width_remains_read_only(bits, cols):
    layout = TableLayout(0x20, 1, cols, bits, bits * cols, 0)
    # The existing reader treats a lone major stride as a singleton cell step.
    # A row-width-looking declaration therefore does not imply packed cells.
    assert [layout.cell_address(0, c) for c in range(cols)] == [
        0x20 + c * cols * (bits // 8) for c in range(cols)
    ]
    with pytest.raises(ValueError, match="Non-contiguous"):
        layout.validate_write()


@pytest.mark.parametrize("bits", [8, 16, 32, 64])
@pytest.mark.parametrize("shape", [(1, 3), (3, 1), (2, 3)])
def test_explicit_packed_row_pitch_still_allows_contiguous_writes(bits, shape):
    rows, cols = shape
    layout = TableLayout(0x20, rows, cols, bits, bits * cols, bits)
    layout.validate_write()
    assert [layout.cell_address(r, c) for r in range(rows) for c in range(cols)] == [
        0x20 + index * (bits // 8) for index in range(rows * cols)
    ]


def test_every_admitted_small_layout_has_a_packed_cell_footprint():
    admitted = 0
    for bits in (8, 16, 32, 64):
        for rows, cols in ((1, 1), (1, 3), (3, 1), (2, 3)):
            for major in {0, bits, 2 * bits, cols * bits}:
                for minor in (0, bits, 2 * bits):
                    layout = TableLayout(0x20, rows, cols, bits, major, minor)
                    try:
                        layout.validate_write()
                    except ValueError:
                        continue
                    admitted += 1
                    assert [layout.cell_address(r, c) for r in range(rows) for c in range(cols)] == [
                        0x20 + index * (bits // 8) for index in range(rows * cols)
                    ]
    assert admitted > 0
