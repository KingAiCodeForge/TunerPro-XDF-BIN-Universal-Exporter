"""Read-only verify_bins streaming equivalence using generated, non-ECU bytes."""
from pathlib import Path

import pytest

import verify_bins


def previous_results(data: bytes) -> dict[str, object]:
    # The pre-change single-buffer implementation is the expected text contract.
    sw_versions = ['0110C6', '0110CA', '0110AD', '0110AB', '0110SA', '011025',
                   '430069', '430066', '430064', '430056', '430055', '430037', '430070',
                   '43X001', '0060041', '4560', '457L', '456B',
                   '5WK90', '5WK93', '5WK98',
                   'MS42', 'MS43', 'MS45', 'MSV70', 'MS41', 'SIEMENS', 'Siemens']
    results: dict[str, object] = {'size': len(data)}
    for sw in sw_versions:
        needle = sw.encode('ascii')
        index = data.find(needle)
        if index < 0:
            continue
        ctx = data[max(0, index - 4):min(len(data), index + len(needle) + 20)]
        shown = ''.join(chr(byte) if 32 <= byte < 127 else '.' for byte in ctx)
        results[sw] = f'@0x{index:05X} [{shown}]'
    return results


@pytest.mark.parametrize("markers", [
    [(0, b'MS42')],
    [(4, b'0110C6')],
    [(5, b'430069'), (55, b'MS45')],
    [(3, b'MS42'), (42, b'MS42'), (119, b'MS42')],
    [(26, b'Siemens'), (140, b'SIEMENS')],
    [(255, b'MSV70'), (512, b'4560'), (1024, b'5WK98')],
    [],
])
def test_streaming_matches_old_offsets_and_context(tmp_path: Path, monkeypatch, markers):
    # Small read blocks force arbitrary signature/context splits at boundaries.
    monkeypatch.setattr(verify_bins, "SCAN_BLOCK_SIZE", 7)
    data = bytearray(b'\x00' * 2048)
    for offset, token in markers:
        data[offset:offset + len(token)] = token
    source = tmp_path / "synthetic.bin"
    source.write_bytes(data)
    before = source.read_bytes()
    assert verify_bins.check_strings(source) == previous_results(before)
    assert source.read_bytes() == before


def test_large_file_reports_entire_size_without_large_reads(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(verify_bins, "SCAN_BLOCK_SIZE", 8192)
    source = tmp_path / "large.bin"
    with source.open("wb") as stream:
        for _ in range(256):
            stream.write(b'_' * 8192)
        stream.write(b'0110CA')
    result = verify_bins.check_strings(source)
    assert result['size'] == 256 * 8192 + 6
    assert '@0x200000' in result['0110CA']


def test_missing_file_is_clear_value_error(tmp_path: Path):
    with pytest.raises(ValueError, match="Cannot read"):
        verify_bins.check_strings(tmp_path / "absent.bin")
