"""Regression coverage for TunerPro 1.11 text and XML XDF dispatch."""

from pathlib import Path
import os
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parent
BIN_DEFINITIONS_BMW = Path(
    os.environ.get("KINGAI_BMW_DEFINITION_ROOT", str(REPO_ROOT / "ignore" / "BMW"))
)
sys.path.insert(0, str(REPO_ROOT))

# Importing the CLI module normally wraps Windows console streams. Pytest owns
# those streams, so suppress only that CLI-only branch during import.
_platform = sys.platform
try:
    sys.platform = "pytest"
    from tunerpro_exporter import UniversalXDFExporter
finally:
    sys.platform = _platform


def _write_legacy_fixture(path: Path) -> None:
    path.write_text(
        """XDF
1.110000

%%HEADER%%
    001005 DefTitle         ="Synthetic legacy regression"
    001006 Desc             ="TunerPro 1.11 text fixture"
    001010 Author           ="KingAI regression"
    001030 BinSize          =0x1FFFF
    001035 BaseOffset       =0
%%END%%

%%TABLE%%
    000002 UniqueID         =0x100
    040005 Title            ="Legacy 2x3 map"
    040010 Desc             ="Address-backed Y axis"
    040100 Address          =0x10
    040200 ZEq              =X*0.5,TH|0|0|0|0|
    040300 Rows             =0x2
    040305 Cols             =0x3
    040320 XUnits           ="load"
    040325 YUnits           ="rpm"
    040330 ZUnits           ="degrees"
    040350 XLabels          =10,20,30
    040354 XEq              =X,TH|0|0|0|0|
    040360 YLabels          =0,0
    040364 YEq              =X,TH|0|0|0|0|
    040700 YAddress         =0x30
    040710 YDataSize        =0x1
    040720 YAddrStep        =2
%%END%%

%%CONSTANT%%
    000002 UniqueID         =0x101
    020005 Title            ="Legacy scalar"
    020010 Desc             ="16-bit constant"
    020020 Units            ="raw"
    020050 SizeInBits       =0x10
    020100 Address          =0x40
    020200 Equation         =X+1,TH|0|0|0|0|
%%END%%

%%FLAG%%
    000002 UniqueID         =0x102
    030005 Title            ="Legacy flag"
    030010 Desc             ="Bit three"
    030100 Address          =0x42
    030200 BitNumber        =0x3
%%END%%
""",
        encoding="latin-1",
    )


def test_legacy_text_xdf_normalizes_into_existing_export_model(tmp_path):
    xdf = tmp_path / "legacy_1_11.xdf"
    binary = tmp_path / "legacy_1_11.bin"
    _write_legacy_fixture(xdf)

    data = bytearray(128 * 1024)
    data[0x10:0x16] = bytes((2, 4, 6, 8, 10, 12))
    data[0x30] = 7
    data[0x32] = 9
    binary.write_bytes(data)

    exporter = UniversalXDFExporter(str(xdf), str(binary))
    assert exporter.validate_bin_file()
    assert exporter.parse_xdf()

    assert exporter.xdf_root.get("legacy_source_version") == "1.110000"
    assert exporter.definition_name == "Synthetic legacy regression"
    assert exporter.base_offset == 0
    assert {key: len(value) for key, value in exporter.elements.items()} == {
        "constants": 1,
        "flags": 1,
        "tables": 1,
        "patches": 0,
    }

    constant = exporter.elements["constants"][0]
    assert constant["size"] == 16
    assert constant["equation"] == "X+1"

    flag = exporter.elements["flags"][0]
    assert flag["address"] == 0x42
    assert flag["mask"] == 0x08

    table = exporter.elements["tables"][0]
    assert table["axes"]["x"]["labels"] == [10.0, 20.0, 30.0]
    assert table["axes"]["y"]["labels"] == [7.0, 9.0]
    assert table["axes"]["z"]["equation"] == "X*0.5"
    assert exporter._read_table_data(table) == [
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ]


def test_real_ms41_legacy_and_xml_fixtures_have_stable_counts(tmp_path):
    legacy = BIN_DEFINITIONS_BMW / "MS41_version641.xdf"
    xml = BIN_DEFINITIONS_BMW / "MS41-2.xdf"
    if not legacy.exists() or not xml.exists():
        pytest.skip("local Bin Definitions MS41 fixtures are unavailable")

    legacy_bin = tmp_path / "legacy.bin"
    xml_bin = tmp_path / "xml.bin"
    legacy_bin.write_bytes(bytes(128 * 1024))
    xml_bin.write_bytes(bytes(256 * 1024))

    legacy_exporter = UniversalXDFExporter(str(legacy), str(legacy_bin))
    assert legacy_exporter.validate_bin_file()
    assert legacy_exporter.parse_xdf()
    assert legacy_exporter.definition_name == (
        "MS41.0 version  E36 328i version 641"
    )
    assert {
        key: len(value) for key, value in legacy_exporter.elements.items()
    } == {
        "constants": 3,
        "flags": 1,
        "tables": 23,
        "patches": 0,
    }

    xml_exporter = UniversalXDFExporter(str(xml), str(xml_bin))
    assert xml_exporter.validate_bin_file()
    assert xml_exporter.parse_xdf()
    assert xml_exporter.xdf_root.get("legacy_source_version") is None
    assert {
        key: len(value) for key, value in xml_exporter.elements.items()
    } == {
        "constants": 15,
        "flags": 0,
        "tables": 21,
        "patches": 2,
    }
