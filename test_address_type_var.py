"""VAR type="address" resolution -- a fixed absolute BIN address, not a link
to another XDF object.

Found broken 2026-09-11 while grading the OSE-encrypted GM corpus decrypted
that day: `_resolve_linked_vars` raised on any VAR whose type was not 'link',
so any file using this legitimate TunerPro feature failed to parse entirely
(not just the affected entry -- the whole export). Confirmed pattern on the
real corpus, every instance the same shape and always an implicit 8-bit
unsigned read:

    <VAR id="Y" type="address" address="0x6003" />

used in a config-byte bit test:

    if ( ((Y>>7)&0x01) > 0 ; (1.22 * X) + 2.2 ; (0.781 * X) + 8 )

`OSE $11P V104.xdf` (converted from the encrypted source that day) went from
a hard parse failure to 615 constants / 332 flags / 192 tables / 0 refuted
once this was fixed.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tunerpro_exporter import EquationError, UniversalXDFExporter

BIN_SIZE = 0x1000
CONFIG_BYTE_ADDR = 0x0100
CONST_ADDR = 0x0200


def _build_bin(path: Path, config_byte: int, const_byte: int) -> None:
    data = bytearray([0x00] * BIN_SIZE)
    data[CONFIG_BYTE_ADDR] = config_byte
    data[CONST_ADDR] = const_byte
    path.write_bytes(bytes(data))


def _xdf(path: Path) -> None:
    path.write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n<XDFFORMAT version=\"1.70\">\n"
        "  <XDFHEADER>\n    <deftitle>address-var fixture</deftitle>\n"
        "    <baseoffset offset=\"0\" subtract=\"0\" />\n"
        "  </XDFHEADER>\n"
        f"""  <XDFCONSTANT uniqueid="0x1" flags="0x0">
    <title>bit-tested scalar</title>
    <EMBEDDEDDATA mmedaddress="0x{CONST_ADDR:X}" mmedelementsizebits="8" />
    <MATH equation="if ( ((Y&gt;&gt;7)&amp;0x01) &gt; 0 ; X + 100 ; X + 1 )">
      <VAR id="Y" type="address" address="0x{CONFIG_BYTE_ADDR:X}" />
      <VAR id="X" />
    </MATH>
  </XDFCONSTANT>
</XDFFORMAT>
""",
        encoding="utf-8",
    )


class AddressTypeVarTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.xdf_path = self.root / "fixture.xdf"
        _xdf(self.xdf_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _exporter_for(self, config_byte: int, const_byte: int = 5) -> UniversalXDFExporter:
        bin_path = self.root / "fixture.bin"
        _build_bin(bin_path, config_byte, const_byte)
        exporter = UniversalXDFExporter(str(self.xdf_path), str(bin_path))
        self.assertTrue(exporter.validate_bin_file())
        self.assertTrue(exporter.parse_xdf())
        return exporter

    def test_bit_clear_takes_the_low_branch(self) -> None:
        exporter = self._exporter_for(config_byte=0x00, const_byte=5)
        item = exporter.elements["constants"][0]
        raw, value = exporter.read_constant(item)
        self.assertEqual(raw, 5)
        self.assertEqual(value, 6)  # X + 1

    def test_bit_set_takes_the_high_branch(self) -> None:
        exporter = self._exporter_for(config_byte=0x80, const_byte=5)
        item = exporter.elements["constants"][0]
        raw, value = exporter.read_constant(item)
        self.assertEqual(raw, 5)
        self.assertEqual(value, 105)  # X + 100

    def test_address_var_reads_the_fixed_address_not_the_cells_own_byte(self) -> None:
        """The two addresses are different bytes; changing only the config
        byte must flip the branch even though the scalar's own byte (X) is
        unchanged -- proving Y is read from its own fixed address, not
        aliased to X."""
        low = self._exporter_for(config_byte=0x00, const_byte=42)
        high = self._exporter_for(config_byte=0xFF, const_byte=42)
        _, low_value = low.read_constant(low.elements["constants"][0])
        _, high_value = high.read_constant(high.elements["constants"][0])
        self.assertNotEqual(low_value, high_value)

    def test_out_of_bounds_address_raises_rather_than_returning_zero(self) -> None:
        exporter = self._exporter_for(config_byte=0x00)
        # Corrupt the resolved address to something past the tiny fixture BIN.
        item = exporter.elements["constants"][0]
        math_elem = item.get("math_element")
        var = math_elem.find("VAR[@type='address']")
        var.set("address", "0xFFFFFF")
        with self.assertRaises(EquationError):
            exporter.read_constant(item)


if __name__ == "__main__":
    unittest.main()
