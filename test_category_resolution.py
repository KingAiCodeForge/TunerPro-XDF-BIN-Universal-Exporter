"""Regression tests for per-XDF CATEGORYMEM ID resolution."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

# The CLI module wraps Windows console streams at import time. Pytest replaces
# those streams with capture objects, so suppress only that CLI-only branch
# while importing the parser for an in-process unit test.
_platform = sys.platform
try:
    sys.platform = "pytest"
    from tunerpro_exporter import UniversalXDFExporter
finally:
    sys.platform = _platform


def _parse_category(tmp_path, category_index, membership_id):
    xdf = tmp_path / "category_fixture.xdf"
    xdf.write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<XDFFORMAT version="1.70">
  <XDFHEADER>
    <deftitle>Category regression</deftitle>
    <BASEOFFSET offset="0" subtract="0" />
    <DEFAULTS datasizeinbits="8" signed="0" lsbfirst="0" />
    <CATEGORY index="{category_index}" name="Knock" />
  </XDFHEADER>
  <XDFCONSTANT uniqueid="0x1">
    <title>Knock scalar</title>
    <CATEGORYMEM index="0" category="{membership_id}" />
    <EMBEDDEDDATA mmedaddress="0x0" mmedelementsizebits="8"
                  mmedmajorstridebits="0" mmedminorstridebits="0" />
    <MATH equation="X"><VAR id="X" /></MATH>
  </XDFCONSTANT>
</XDFFORMAT>
""",
        encoding="utf-8",
    )

    exporter = UniversalXDFExporter(str(xdf), str(tmp_path / "unused.bin"))
    assert exporter.parse_xdf()
    return exporter, exporter.elements["constants"][0]["category"]


def test_one_based_decimal_membership_resolves_to_hex_category(tmp_path):
    # Real 0110CA shape: CATEGORY 0x9C (156), CATEGORYMEM 157.
    exporter, category = _parse_category(tmp_path, "0x9C", "157")

    assert exporter.category_member_offset == -1
    assert category == "Knock"


def test_direct_membership_remains_supported(tmp_path):
    exporter, category = _parse_category(tmp_path, "0X9C", "0X9C")

    assert exporter.category_member_offset == 0
    assert category == "Knock"
