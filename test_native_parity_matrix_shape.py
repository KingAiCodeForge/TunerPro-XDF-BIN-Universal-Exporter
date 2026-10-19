"""Ragged matrices must never pass through zip truncation."""
import pytest
from tunerpro_native_export_parity import DisplayNumber, compare_matrix


@pytest.mark.parametrize("native,candidate", [
    ([[1, 2], [3, 4]], [[1, 2], [3]]),
    ([[1, 2], [3]], [[1, 2], [3, 4]]),
    ([[1, 2], [3, 4]], [[1, 2], [3, 4, 5]]),
    ([[1, 2], []], [[1, 2], []]),
    ([[], [1]], [[], [1]]),
])
def test_ragged_or_unequal_row_lengths_are_shape_failures(native, candidate):
    expected = [[DisplayNumber(float(v), 2, str(v)) for v in row] for row in native]
    report = compare_matrix(expected, candidate, 0.0)
    assert report["shape_mismatch"] is True
    assert report["mismatches"] > 0


def test_rectangular_matrix_still_matches():
    native = [[DisplayNumber(1.0, 2, "1.00"), DisplayNumber(2.0, 2, "2.00")]]
    report = compare_matrix(native, [[1.0, 2.0]], 0.0)
    assert report["shape_mismatch"] is False
    assert report["mismatches"] == 0
