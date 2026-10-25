"""Ordered output and safety regressions using synthetic bytes only."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

import verify_bins


def legacy_result(data):
    result = {"size": len(data)}
    for marker in verify_bins.SW_VERSIONS:
        needle = marker.encode("ascii")
        index = data.find(needle)
        if index >= 0:
            context = data[max(0, index - 4):index + len(needle) + 20]
            shown = "".join(chr(value) if 32 <= value < 127 else "." for value in context)
            result[marker] = f"@0x{index:05X} [{shown}]"
    return result


@pytest.mark.parametrize("chunk", [7, 31, 65536])
def test_dictionary_order_matches_legacy_not_physical_arrival(tmp_path, monkeypatch, chunk):
    monkeypatch.setattr(verify_bins, "MAX_CHUNK", chunk)
    data = b"MSV70" + b"_" * (chunk + 40) + b"430069" + b"_" * 40 + b"0110C6"
    source = tmp_path / "synthetic.bin"
    source.write_bytes(data)
    assert list(verify_bins.check_strings(source).items()) == list(legacy_result(data).items())
    assert source.read_bytes() == data


def test_metadata_only_change_is_rejected_without_changing_bytes(tmp_path, monkeypatch):
    source = tmp_path / "synthetic.bin"
    data = b"MS45" + b"_" * 200
    source.write_bytes(data)
    original_open = Path.open
    changed = []

    class Reader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def read(self, count=-1):
            result = self.stream.read(count)
            if result and not changed:
                before = source.stat()
                os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
                changed.append(source.stat().st_mtime_ns != before.st_mtime_ns)
            return result

    def wrapped(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return Reader(stream) if path == source else stream

    monkeypatch.setattr(Path, "open", wrapped)
    with pytest.raises(ValueError, match="changed while scanning"):
        verify_bins.check_strings(source)
    assert changed == [True]
    with original_open(source, "rb") as stream:
        assert stream.read() == data


@pytest.mark.parametrize("short_read", [1, 3, 11])
def test_short_reads_preserve_first_offset_context_and_order(tmp_path, monkeypatch, short_read):
    data = b"MS45" + b"_" * 53 + b"0110C6 Siemens SIEMENS MS45"
    source = tmp_path / "synthetic.bin"
    source.write_bytes(data)
    original_open = Path.open
    requests = []

    class Reader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def read(self, count=-1):
            requests.append(count)
            assert 0 < count <= 65536
            return self.stream.read(min(count, short_read))

    def wrapped(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return Reader(stream) if path == source else stream

    monkeypatch.setattr(Path, "open", wrapped)
    assert list(verify_bins.check_strings(source).items()) == list(legacy_result(data).items())
    assert requests


def test_directory_is_refused(tmp_path):
    with pytest.raises(ValueError, match="ordinary firmware file"):
        verify_bins.check_strings(tmp_path)


def test_all_markers_still_scan_to_end_and_preserve_source(tmp_path):
    data = b"|".join(marker.encode("ascii") for marker in reversed(verify_bins.SW_VERSIONS))
    data += b"_" * (verify_bins.MAX_CHUNK * 3 + 13)
    source = tmp_path / "synthetic.bin"
    source.write_bytes(data)
    before = hashlib.sha256(data).hexdigest()
    actual = verify_bins.check_strings(source)
    assert list(actual.items()) == list(legacy_result(data).items())
    assert actual["size"] == len(data)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_native_cli_preserves_mismatch_detail_order_and_warning(tmp_path):
    folder = tmp_path / "all_ms45_bins"
    folder.mkdir()
    (folder / "synthetic.bin").write_bytes(b"MSV70 " + b"_" * 70000 + b"430069 0110C6")
    process = subprocess.run([sys.executable, str(Path(verify_bins.__file__).resolve()), str(folder)],
                             capture_output=True, text=True, check=False)
    assert process.returncode == 0, process.stderr
    details = [line.strip().split(":", 1)[0] for line in process.stdout.splitlines()
               if line.startswith("      ") and ": @0x" in line]
    assert details == ["0110C6", "430069", "MSV70"]
    assert "String/size hints are heuristic" in process.stdout
    assert process.stderr == ""


def test_native_cli_missing_directory_returns_two(tmp_path):
    process = subprocess.run([sys.executable, str(Path(verify_bins.__file__).resolve()),
                              str(tmp_path / "absent")], capture_output=True, text=True, check=False)
    assert process.returncode == 2
    assert "Input is not a directory" in process.stderr
