"""Fail-closed integer geometry tests for the shared XDF layout model."""
import pytest
from tunerpro_xdf.xdf_addressing import TableLayout

@pytest.mark.parametrize(("field", "value"), [
    ("address", 1.0), ("address", -1), ("address", True),
    ("rows", 2.0), ("rows", True), ("cols", 3.0),
    ("size_bits", 16.0), ("major_stride", 8.0),
    ("minor_stride", "0"),
])
def test_invalid_numeric_geometry_is_rejected(field, value):
    kwargs = {"address": 0x100, "rows": 2, "cols": 3,
              "size_bits": 16, "major_stride": 0, "minor_stride": 0}
    kwargs[field] = value
    with pytest.raises(ValueError):
        TableLayout(**kwargs)

@pytest.mark.parametrize(("row", "col"), [
    (0.0, 0), (0, 0.0), (True, 0), (0, False), ("1", 1)
])
def test_noninteger_cell_coordinates_are_rejected(row, col):
    layout = TableLayout(0x100, 2, 3, 16)
    with pytest.raises(TypeError, match="coordinates"):
        layout.cell_address(row, col)

def test_valid_packed_and_review_only_strided_layouts_unchanged():
    packed = TableLayout(0x100, 2, 3, 16)
    assert packed.file_span() == (0x100, 0x10C)
    packed.validate_write()
    strided = TableLayout(0x100, 2, 3, 16, major_stride=96, minor_stride=16)
    assert strided.cell_address(1, 2) == 0x100 + 12 + 4
    with pytest.raises(ValueError, match="Non-contiguous"):
        strided.validate_write()
