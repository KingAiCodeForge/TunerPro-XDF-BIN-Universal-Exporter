from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from bmw_0pa_0da_to_bin import (
    ECU_ADDR_MAP,
    combine_pa_da,
    convert_file,
    intel_hex_to_binary,
)


EXACT_SPDATEN_ROOT = Path(
    os.environ.get("KINGAI_SPDATEN_ROOT", str(Path(__file__).resolve().parent / "ignore" / "spdaten"))
)
EXACT_MDS450_PROGRAM = EXACT_SPDATEN_ROOT / "MDS450" / "7549387A.0pa"
EXACT_MDS450_CALIBRATION = EXACT_SPDATEN_ROOT / "MDS450" / "P7550114.0da"


def ihex(address: int, record_type: int, payload: bytes = b"") -> str:
    raw = bytes(
        [
            len(payload),
            (address >> 8) & 0xFF,
            address & 0xFF,
            record_type,
        ]
    ) + payload
    checksum = (-sum(raw)) & 0xFF
    return ":" + (raw + bytes([checksum])).hex().upper()


def record_stream(*records: str) -> bytes:
    return ("\n".join(records) + "\n").encode("ascii")


def package(file_type: str, reference: str, records: list[str]) -> str:
    return "\n".join(
        [
            ";==========================================",
            f"; Austausch-Datei    {file_type}",
            ";;ZL_System: MDS42",
            f"$REFERENZ {reference} U",
            *records,
            "",
        ]
    )


@pytest.mark.parametrize("kind", ["trailing", "checksum", "nonhex", "missing_eof"])
def test_strict_hex_validation_blocks_materialization(kind: str) -> None:
    valid_data = ihex(0, 0x00, b"\x01")
    if kind == "trailing":
        records = [valid_data + "DEADBEEF", ihex(0, 0x01)]
        expected = "record length mismatch"
    elif kind == "checksum":
        bad_checksum = valid_data[:-2] + ("00" if valid_data[-2:] != "00" else "FF")
        records = [bad_checksum, ihex(0, 0x01)]
        expected = "checksum mismatch"
    elif kind == "nonhex":
        records = [valid_data[:9] + "GG" + valid_data[11:], ihex(0, 0x01)]
        expected = "non-hexadecimal"
    else:
        records = [valid_data]
        expected = "Missing Intel HEX EOF"

    binary, info = intel_hex_to_binary(record_stream(*records))

    assert binary is None
    assert any(expected in error for error in info["errors"])


def test_conflicting_raw_source_overlap_fails_closed() -> None:
    data = record_stream(
        ihex(0, 0x00, b"\x11"),
        ihex(0, 0x00, b"\x22"),
        ihex(0, 0x01),
    )

    binary, info = intel_hex_to_binary(data)

    assert binary is None
    assert info["source_conflicting_overlap_bytes"] == 1
    assert any("Conflicting source-address overlap" in error for error in info["errors"])


@pytest.mark.parametrize("ecu_type", ["MDS450", "MDS451"])
def test_ms45_regions_are_explicit_and_legacy_overlay_is_reported(
    ecu_type: str,
) -> None:
    data = record_stream(
        ihex(0, 0x04, b"\x00\x00"),
        ihex(0, 0x00, b"\x11\x33"),
        ihex(0, 0x04, b"\x02\x00"),
        ihex(0, 0x00, b"\x22\x33"),
        ihex(0, 0x01),
    )
    options = {"addr_map": ECU_ADDR_MAP[ecu_type], "ecu_type": ecu_type}

    ambiguous, ambiguous_info = intel_hex_to_binary(data, **options)
    mpc, mpc_info = intel_hex_to_binary(data, source_region="mpc", **options)
    external, external_info = intel_hex_to_binary(
        data, source_region="external", **options
    )
    legacy, legacy_info = intel_hex_to_binary(
        data, mapped_overlap_policy="legacy-last-wins", **options
    )

    assert ambiguous is None
    assert ambiguous_info["mapped_identical_alias_bytes"] == 1
    assert ambiguous_info["mapped_conflicting_alias_bytes"] == 1
    assert any("Ambiguous mixed MPC" in error for error in ambiguous_info["errors"])
    assert bytes(mpc) == b"\x11\x33"
    assert mpc_info["source_region"] == "mpc"
    assert bytes(external) == b"\x22\x33"
    assert external_info["source_region"] == "external"
    assert bytes(legacy) == b"\x22\x33"
    assert legacy_info["lossy"] is True
    assert legacy_info["discarded_conflicting_bytes"] == 1
    assert any("LOSSY" in warning for warning in legacy_info["warnings"])


def test_clean_non_conflicting_input_keeps_flat_binary_behavior() -> None:
    data = record_stream(
        ihex(0x0010, 0x00, b"\xAA\xBB"),
        ihex(0, 0x01),
    )

    binary, info = intel_hex_to_binary(data, force_base=0, force_size=0x20)

    assert binary is not None
    assert bytes(binary[0x10:0x12]) == b"\xAA\xBB"
    assert info["mapped_unique_bytes"] == 2
    assert info["source_defined_output_bytes"] == 2
    assert info["fill_only_output_bytes"] == 0x1E
    assert info["errors"] == []


def test_combine_uses_only_defined_bytes_not_flat_fill(tmp_path: Path) -> None:
    program = tmp_path / "program.0PA"
    calibration = tmp_path / "calibration.0DA"
    output_dir = tmp_path / "out"
    program.write_text(
        package(
            "Programm",
            "TEST",
            [ihex(0x1000, 0x00, b"\xAA\xBB\xCC"), ihex(0, 0x01)],
        ),
        encoding="ascii",
    )
    calibration.write_text(
        package(
            "Daten",
            "TESTCAL",
            [
                ihex(0x1000, 0x00, b"\xAA"),
                ihex(0x1002, 0x00, b"\xCC"),
                ihex(0, 0x01),
            ],
        ),
        encoding="ascii",
    )

    result = combine_pa_da(
        str(program), str(calibration), output_dir=str(output_dir), force_ecu="MDS42"
    )

    assert result["success"] is True
    combined = Path(result["output"]).read_bytes()
    assert combined[0x1000:0x1003] == b"\xAA\xBB\xCC"
    assert result["combine_info"]["identical_cross_file_overlap_bytes"] == 2
    assert result["combine_info"]["conflicting_cross_file_overlap_bytes"] == 0


def test_combine_conflict_fails_before_output_is_created(tmp_path: Path) -> None:
    program = tmp_path / "program.0PA"
    calibration = tmp_path / "calibration.0DA"
    output_dir = tmp_path / "must_not_exist"
    program.write_text(
        package("Programm", "TEST", [ihex(0x1000, 0x00, b"\xAA"), ihex(0, 0x01)]),
        encoding="ascii",
    )
    calibration.write_text(
        package("Daten", "TESTCAL", [ihex(0x1000, 0x00, b"\xBB"), ihex(0, 0x01)]),
        encoding="ascii",
    )

    result = combine_pa_da(
        str(program), str(calibration), output_dir=str(output_dir), force_ecu="MDS42"
    )

    assert result["success"] is False
    assert "Conflicting combine overlap" in result["error"]
    assert not output_dir.exists()


@pytest.mark.skipif(
    not EXACT_MDS450_PROGRAM.is_file(), reason="exact local SP-Daten fixture unavailable"
)
def test_exact_7549387a_fails_closed_and_legacy_hash_is_pinned() -> None:
    strict = convert_file(str(EXACT_MDS450_PROGRAM), info_only=True)
    assert strict["success"] is False
    assert "Ambiguous mixed MPC" in strict["error"]
    assert strict["hex_info"]["mapped_identical_alias_bytes"] == 5_918
    assert strict["hex_info"]["mapped_conflicting_alias_bytes"] == 59_542

    raw = EXACT_MDS450_PROGRAM.read_bytes()
    from bmw_0pa_0da_to_bin import parse_austausch_header

    header = parse_austausch_header(raw)
    legacy, info = intel_hex_to_binary(
        raw,
        start_offset=header["hex_data_offset"],
        fill_byte=0xFF,
        force_base=0,
        force_size=1024 * 1024,
        addr_map=ECU_ADDR_MAP["MDS450"],
        ecu_type="MDS450",
        mapped_overlap_policy="legacy-last-wins",
    )

    assert legacy is not None
    assert info["lossy"] is True
    assert hashlib.sha256(legacy).hexdigest().upper() == (
        "005C6047B204DB493E2E0141AD1E14BA588808ED07174262E2D8E4896A68EE62"
    )


@pytest.mark.skipif(
    not (EXACT_MDS450_PROGRAM.is_file() and EXACT_MDS450_CALIBRATION.is_file()),
    reason="exact local paired SP-Daten fixtures unavailable",
)
def test_exact_mds450_external_combine_is_collision_free(tmp_path: Path) -> None:
    output_dir = tmp_path / "external"
    result = combine_pa_da(
        str(EXACT_MDS450_PROGRAM),
        str(EXACT_MDS450_CALIBRATION),
        output_dir=str(output_dir),
        source_region="external",
    )

    assert result["success"] is True
    assert Path(result["output"]).stat().st_size == 1024 * 1024
    assert result["combine_info"]["unique_target_bytes"] == 773_800
    assert result["combine_info"]["conflicting_cross_file_overlap_bytes"] == 0
    assert result["combine_info"]["fill_only_output_bytes"] == 274_776
