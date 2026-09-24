"""XDF address translation for the supported contiguous row-major layout.

Non-default strides require a retained native TunerPro comparison before
they can be interpreted by this release. Reject them instead of guessing.
"""

from dataclasses import dataclass


def file_offset(address: int, base_offset: int = 0, subtract: int = 0) -> int:
    if subtract not in (0, 1):
        raise ValueError("XDF BASEOFFSET subtract must be 0 or 1")
    return address - base_offset if subtract else address + base_offset


@dataclass(frozen=True)
class TableLayout:
    address: int
    rows: int
    cols: int
    size_bits: int = 8
    major_stride: int = 0
    minor_stride: int = 0

    def __post_init__(self):
        if self.rows < 1 or self.cols < 1:
            raise ValueError("XDF table dimensions must be positive")
        if self.size_bits not in (8, 16, 32, 64):
            raise ValueError(f"Unsupported XDF element width: {self.size_bits} bits")
        if self.major_stride % 8 or self.minor_stride % 8:
            raise ValueError("Non-byte-aligned XDF table strides are unsupported")
        if self.major_stride not in (0, self.size_bits) or self.minor_stride not in (0, self.size_bits):
            raise ValueError("Non-default XDF table strides require native TunerPro parity")

    @property
    def width(self) -> int:
        return self.size_bits // 8

    def cell_address(self, row: int, col: int) -> int:
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise IndexError("XDF table cell is outside its declared dimensions")
        return self.address + (row * self.cols + col) * self.width

    def validate_write(self) -> None:
        # Kept as a public guard for editor callers. Construction already
        # rejects non-default layouts for both reads and writes.
        if self.major_stride < 0 or self.minor_stride < 0:
            raise ValueError("Negative-stride XDF writes require native TunerPro parity")
        if 0 < self.minor_stride < self.size_bits:
            raise ValueError("Overlapping XDF table cells cannot be edited independently")
        row_bits = self.cols * (self.minor_stride or self.size_bits)
        if self.major_stride not in (0, self.size_bits) and self.major_stride < row_bits:
            raise ValueError("Ambiguous XDF major stride requires native TunerPro parity")

    def file_span(self, base_offset: int = 0, subtract: int = 0) -> tuple[int, int]:
        corners = [self.cell_address(r, c) for r in (0, self.rows - 1) for c in (0, self.cols - 1)]
        return (file_offset(min(corners), base_offset, subtract),
                file_offset(max(corners), base_offset, subtract) + self.width)


def table_layout(table: dict) -> TableLayout:
    axes = table.get("axes", {})
    z = axes.get("z", {})
    rows, cols = z.get("row_count", 1), z.get("col_count", 1)
    if rows < 1 or cols < 1:
        raise ValueError("Explicit XDF table dimensions must be positive")
    if rows <= 1 and cols <= 1:
        rows = max(axes.get("y", {}).get("count", 1), 1)
        cols = max(axes.get("x", {}).get("count", 1), 1)
    if z.get("address") is None:
        raise ValueError("XDF table has no Z-axis address")
    return TableLayout(z["address"], rows, cols, z.get("size_bits", 8),
                       z.get("major_stride", 0), z.get("minor_stride", 0))
