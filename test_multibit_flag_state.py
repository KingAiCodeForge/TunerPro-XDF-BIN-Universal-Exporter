"""Regression for overlapping one-bit and combined XDF flag masks."""

from tunerpro_exporter import UniversalXDFExporter


def test_combined_flag_requires_the_full_mask():
    is_set = UniversalXDFExporter.flag_is_set
    assert is_set(0x10, 0x10)
    assert not is_set(0x10, 0x20)
    assert not is_set(0x10, 0x30)
    assert is_set(0x30, 0x30)
    assert not is_set(0xFF, 0x00)
