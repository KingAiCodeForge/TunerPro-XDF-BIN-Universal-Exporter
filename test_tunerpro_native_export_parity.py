"""Regression tests for reading TunerPro's native "Export Data To Text File" output."""

from tunerpro_native_export_parity import parse_native_table, parse_scalar_line


def test_hex_output_scalar_is_parsed_as_integer():
    parsed = parse_scalar_line(
        "SCALAR: EPROM ID                                                        0x077E HEX            "
    )
    assert parsed is not None
    title, value, unit = parsed
    assert title == "EPROM ID"
    assert value.value == 0x077E
    assert unit == "HEX"


def test_decimal_scalar_still_parses():
    parsed = parse_scalar_line("SCALAR: Base Injector Rate                                        88.48 MSEC/ GRAM")
    assert parsed is not None
    assert parsed[1].value == 88.48


def test_literal_row_labels_keep_their_rows():
    # A literal XDF label is printed verbatim and can be wider than the label
    # column, shifting its values right. Every row must survive.
    block = [
        "  Cell Units: Msec",
        "",
        "    Msec   Msec  ",
        "            0.00",
        "   0.976      0.11",
        "et cetera 0.732      0.21",
        "no less than 0.488      0.21",
        "only + numbers here 0.000      0.41",
    ]
    table = parse_native_table("Low Pulse Width Injector Offset Vs Base Pulse Width", 1, block)
    assert [row[0].value for row in table.data] == [0.11, 0.21, 0.21, 0.41]
    assert [y.value for y in table.y] == [0.976, 0.732, 0.488, 0.0]
