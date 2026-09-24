"""An all-zero table only refutes a definition when it sits in live calibration.

A zero table inside a contiguous zero region is the ordinary signature of a
feature the vehicle does not have; the definition is describing an unpopulated
bank correctly. Grading every all-zero table as refuting downgrades correct
XDFs -- on the E38 12609099 code-confirmed set it flagged 30 tables of which 24
were unpopulated banks, taking the refuted rate from 1.4% to 6.8%.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tunerpro_exporter import UniversalXDFExporter


BIN_SIZE = 0x1000
LIVE_BYTE = 0x5A

# One zero table stranded in live data, one inside a zero region.
ISOLATED_ADDR = 0x0100
REGION_ADDR = 0x0800
# A table whose stored bytes are written data but whose equation maps them to
# 0.0 -- the MS45 IVVT case (320 bytes of 0x5F meaning "no ignition offset").
DECODES_ZERO_ADDR = 0x0400
DECODES_ZERO_BYTE = 0x5F
TABLE_CELLS = 16  # 4x4 uint8


def _build_bin(path: Path) -> None:
    data = bytearray([LIVE_BYTE] * BIN_SIZE)
    # a table of zeros with live calibration either side
    data[ISOLATED_ADDR:ISOLATED_ADDR + TABLE_CELLS] = bytes(TABLE_CELLS)
    # a wide unpopulated bank containing a table of zeros
    data[REGION_ADDR - 0x80:REGION_ADDR + TABLE_CELLS + 0x80] = bytes(
        0x100 + TABLE_CELLS
    )
    # written calibration that happens to DECODE to zero, in live surroundings
    data[DECODES_ZERO_ADDR:DECODES_ZERO_ADDR + TABLE_CELLS] = bytes(
        [DECODES_ZERO_BYTE] * TABLE_CELLS
    )
    path.write_bytes(bytes(data))


def _table(uid: int, title: str, addr: int, equation: str = "X") -> str:
    return f"""  <XDFTABLE uniqueid="0x{uid:X}" flags="0x30">
    <title>{title}</title>
    <XDFAXIS id="x"><indexcount>4</indexcount></XDFAXIS>
    <XDFAXIS id="y"><indexcount>4</indexcount></XDFAXIS>
    <XDFAXIS id="z">
      <EMBEDDEDDATA mmedaddress="0x{addr:X}" mmedelementsizebits="8"
                    mmedrowcount="4" mmedcolcount="4" />
      <MATH equation="{equation}"><VAR id="X" /></MATH>
    </XDFAXIS>
  </XDFTABLE>"""


def _build_xdf(path: Path) -> None:
    path.write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n<XDFFORMAT version=\"1.70\">\n"
        "  <XDFHEADER>\n    <deftitle>zero table diagnostics fixture</deftitle>\n"
        "    <baseoffset offset=\"0\" subtract=\"0\" />\n"
        "  </XDFHEADER>\n"
        + _table(0x1, "stranded in live data", ISOLATED_ADDR) + "\n"
        + _table(0x2, "inside a zero region", REGION_ADDR) + "\n"
        + _table(0x3, "written bytes that decode to zero", DECODES_ZERO_ADDR,
                 equation=f"X-{DECODES_ZERO_BYTE}") + "\n"
        "</XDFFORMAT>\n",
        encoding="utf-8",
    )


class ZeroTableDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.bin_path = root / "fixture.bin"
        self.xdf_path = root / "fixture.xdf"
        _build_bin(self.bin_path)
        _build_xdf(self.xdf_path)
        self.exporter = UniversalXDFExporter(str(self.xdf_path), str(self.bin_path))
        assert self.exporter.validate_bin_file()
        assert self.exporter.parse_xdf()
        self.report = self.exporter.run_diagnostics()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_zero_tables_are_separated_by_surrounding_context(self) -> None:
        counts = self.report["counts"]
        self.assertEqual(counts["all_zero_isolated"], 1)
        self.assertEqual(counts["all_zero_in_zero_region"], 1)

    def test_only_the_stranded_table_counts_as_refuting(self) -> None:
        self.assertEqual(self.report["refuted_count"], 1)
        titles = [f["title"] for f in self.report["findings"]["all_zero_isolated"]]
        self.assertEqual(titles, ["stranded in live data"])

    def test_unpopulated_bank_is_reported_but_does_not_refute(self) -> None:
        region = self.report["findings"]["all_zero_in_zero_region"]
        self.assertEqual([f["title"] for f in region], ["inside a zero region"])
        self.assertIn("feature likely absent", region[0]["detail"])

    def test_written_bytes_that_decode_to_zero_do_not_refute(self) -> None:
        """A decoded zero is a value; only unwritten bytes are a gap.

        MS45 4560BN00 has two of these: the IVVT ignition offset tables at
        0x4AAA4 and 0x4ABE4 hold 320 bytes of 0x5F, which the equation maps to
        0 degrees. Testing the decoded value for zero and then asking the RAW
        neighbours whether it is stranded refuted both, taking a correct
        definition from A_clean to B_minor.
        """
        counts = self.report["counts"]
        self.assertEqual(counts["all_zero_written_bytes"], 1)
        written = self.report["findings"]["all_zero_written_bytes"]
        self.assertEqual([f["title"] for f in written],
                         ["written bytes that decode to zero"])
        self.assertIn("raw bytes are written data", written[0]["detail"])
        # it sits in live calibration, so the OLD logic would have refuted it
        self.assertTrue(
            self.exporter._zero_table_is_isolated(DECODES_ZERO_ADDR, TABLE_CELLS)
        )
        # but the raw bytes say it was written, so it must not count as refuting
        self.assertEqual(self.report["refuted_count"], 1)

    def test_raw_block_is_unwritten_only_for_padding(self) -> None:
        unwritten = self.exporter._raw_block_is_unwritten
        self.assertTrue(unwritten(ISOLATED_ADDR, TABLE_CELLS))       # all 0x00
        self.assertFalse(unwritten(DECODES_ZERO_ADDR, TABLE_CELLS))  # all 0x5F
        self.assertFalse(unwritten(0, 0))                            # fail-closed

    def test_missing_neighbour_bytes_do_not_refute(self) -> None:
        """With nothing to compare against, report nothing rather than refute."""
        self.assertFalse(self.exporter._zero_table_is_isolated(0, BIN_SIZE))


if __name__ == "__main__":
    unittest.main()
