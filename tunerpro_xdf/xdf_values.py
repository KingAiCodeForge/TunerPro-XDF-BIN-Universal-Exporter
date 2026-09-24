"""Bounded integer BIN access shared by XDF readers and writers."""

import struct


def _format(size_bits: int, signed: bool, lsb_first: bool) -> str:
    formats = {8: ("B", "b"), 16: ("H", "h"), 32: ("I", "i")}
    if size_bits not in formats:
        raise ValueError(f"Unsupported XDF integer width: {size_bits} bits")
    return ("<" if lsb_first else ">") + formats[size_bits][bool(signed)]


def _bounds(data, offset: int, width: int) -> None:
    if offset < 0 or offset + width > len(data):
        raise IndexError(f"BIN offset {offset:#x} with width {width} is out of bounds")


def read_integer(data, offset: int, size_bits: int, signed: bool = False,
                 lsb_first: bool = False) -> int:
    fmt = _format(size_bits, signed, lsb_first)
    _bounds(data, offset, size_bits // 8)
    return struct.unpack_from(fmt, data, offset)[0]


# TunerPro marks IEEE754 cells with this mmedtypeflags bit (seen in TunerPro-
# authored XDFs, e.g. OSE 12691157: mmedtypeflags="0x10000", 32-bit cells).
# Bits 0x01 (signed) and 0x02 (LSB first) keep their meaning; signed is moot.
FLOAT_FLAG = 0x10000


def read_float(data, offset: int, size_bits: int, lsb_first: bool = False) -> float:
    formats = {32: "f", 64: "d"}
    if size_bits not in formats:
        raise ValueError(f"Unsupported XDF float width: {size_bits} bits")
    _bounds(data, offset, size_bits // 8)
    return struct.unpack_from(("<" if lsb_first else ">") + formats[size_bits], data, offset)[0]


def read_value(data, offset: int, size_bits: int, signed: bool = False,
               lsb_first: bool = False, is_float: bool = False):
    """Read one XDF cell: IEEE754 when the float flag is set, else integer."""
    if is_float:
        return read_float(data, offset, size_bits, lsb_first)
    return read_integer(data, offset, size_bits, signed, lsb_first)


def write_integer(data: bytearray, offset: int, size_bits: int, value: int,
                  signed: bool = False, lsb_first: bool = False) -> None:
    fmt = _format(size_bits, signed, lsb_first)
    _bounds(data, offset, size_bits // 8)
    packed = struct.pack(fmt, value)
    data[offset:offset + len(packed)] = packed
