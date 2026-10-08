"""Regression coverage for native binary/protected TunerPro XDF dispatch."""

import logging

from tunerpro_exporter import (
    TUNERPRO_NATIVE_BINARY_XDF_MAGIC,
    UniversalXDFExporter,
    is_tunerpro_native_binary_xdf,
)


def test_native_binary_xdf_magic_is_detected_without_xml_fallback(tmp_path, caplog):
    xdf = tmp_path / "protected.xdf"
    binary = tmp_path / "firmware.bin"
    xdf.write_bytes(TUNERPRO_NATIVE_BINARY_XDF_MAGIC + (b"\0" * 124) + b"payload")
    binary.write_bytes(b"\0" * 128)

    exporter = UniversalXDFExporter(str(xdf), str(binary))
    with caplog.at_level(logging.ERROR):
        assert exporter.parse_xdf() is False

    message = caplog.text
    assert "native binary/protected XDF container" in message
    assert "Native TunerPro can load this file" in message
    assert "no password or decryption bypass is attempted" in message
    assert "Latin-1" not in message


def test_plain_xml_is_not_classified_as_native_binary_xdf():
    assert not is_tunerpro_native_binary_xdf(b"<?xml version='1.0'?><XDFFORMAT />")
