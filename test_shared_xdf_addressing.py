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


@pytest.mark.parametrize("major,minor", [(-8, 0), (0, -8), (9, 0)])
def test_unproven_layouts_do_not_guess_addresses(major, minor):
    with pytest.raises(ValueError):
        TableLayout(0, 2, 2, 8, major, minor)


@pytest.mark.parametrize('major,minor,addresses', [
    (32, 0, [0, 1, 4, 5]),
    (0, 32, [0, 4, 8, 12]),
])
def test_positive_stride_review_reads_have_explicit_addresses_but_no_write(major, minor, addresses):
    # Positive-stride reads predate this reconciliation. Check exact offsets
    # rather than retaining an obsolete blanket read rejection. No native
    # semantics are inferred, and the independent write guard stays closed.
    layout = TableLayout(0, 2, 2, 8, major, minor)
    assert [layout.cell_address(r, c) for r in range(2) for c in range(2)] == addresses
    with pytest.raises(ValueError, match='Non-contiguous'):
        layout.validate_write()


def test_base_offset_matches_documented_add_and_subtract_examples():
    assert file_offset(0xF0, 0x4000, 0) == 0x40F0
    assert file_offset(0x80F0, 0x8000, 1) == 0xF0
    with pytest.raises(ValueError):
        file_offset(0xF0, 0x4000, 2)
