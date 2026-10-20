"""Synthetic execution checks for opt-in, copy-only inventory utilities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = ("organize_bins.py", "clean_and_dedup_bins.py", "sort_tuning_db_to_bins.py")


def run(script, *args):
    return subprocess.run([sys.executable, str(HERE / script), *(str(arg) for arg in args)],
                          cwd=HERE.parent, text=True, capture_output=True)


@pytest.mark.parametrize("script", SCRIPTS)
def test_preview_and_apply_preserve_sources_and_refuse_rerun(script, tmp_path):
    source = tmp_path / "source files with spaces"
    destination = tmp_path / "copies with spaces"
    source.mkdir()
    originals = {"BMW_MS42_01100AD.Stage1": b"a" * 16384,
                 "BMW_MS43_430069.bin": b"b" * 16384,
                 "BMW_MS43_430069_variant.bin": b"b" * 16384,
                 "unknown.bin": b"c" * 16384}
    for name, data in originals.items():
        (source / name).write_bytes(data)
    preview = run(script, source, destination)
    assert preview.returncode == 0, preview.stderr
    assert "PREVIEW" in preview.stdout
    assert not destination.exists()
    applied = run(script, source, destination, "--apply")
    assert applied.returncode == 0, applied.stderr
    assert {p.name: p.read_bytes() for p in source.iterdir()} == originals
    manifest_path, = destination.glob("*.json")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert report["source_files_preserved"] is True
    assert report["files"]
    for entry in report["files"]:
        assert len(entry["sha256"]) == 64
        copied = destination / entry["destination"]
        assert hashlib.sha256(copied.read_bytes()).hexdigest() == entry["sha256"]
        assert copied.read_bytes() == originals[Path(entry["source"]).name]
    before = {p.relative_to(destination).as_posix(): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
    repeat = run(script, source, destination, "--apply")
    assert repeat.returncode == 2
    assert "Refusing existing" in repeat.stderr
    assert {p.relative_to(destination).as_posix(): p.read_bytes() for p in destination.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("script", SCRIPTS)
def test_missing_inputs_and_output_inside_source_fail_without_writing(script, tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    missing = run(script, source, destination, "--apply")
    assert missing.returncode == 2
    assert "Source directory not found" in missing.stderr
    assert not destination.exists()
    source.mkdir()
    nested = run(script, source, source / "output", "--apply")
    assert nested.returncode == 2
    assert "outside the source" in nested.stderr
    assert list(source.iterdir()) == []


def test_existing_output_preflight_prevents_partial_copies(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "MS42_a.bin").write_bytes(b"a")
    (source / "MS42_z.bin").write_bytes(b"z")
    folder = destination / "all_ms42_bins"
    folder.mkdir(parents=True)
    (folder / "MS42_z.bin").write_bytes(b"existing")
    result = run("organize_bins.py", source, destination, "--apply")
    assert result.returncode == 2
    assert not (folder / "MS42_a.bin").exists()
    assert (folder / "MS42_z.bin").read_bytes() == b"existing"


def test_duplicate_basename_variants_keep_relative_identity(tmp_path):
    source = tmp_path / "source"
    for subdir, data in (("prototype one", b"first"), ("prototype two", b"second")):
        folder = source / subdir
        folder.mkdir(parents=True)
        (folder / "MS42.bin").write_bytes(data)
    destination = tmp_path / "destination"
    result = run("organize_bins.py", source, destination, "--apply")
    assert result.returncode == 0, result.stderr
    assert (destination / "all_ms42_bins/prototype one/MS42.bin").read_bytes() == b"first"
    assert (destination / "all_ms42_bins/prototype two/MS42.bin").read_bytes() == b"second"


def test_cleanup_retains_duplicate_and_filename_hint_in_review_lanes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.bin").write_bytes(b"same")
    (source / "b.bin").write_bytes(b"same")
    (source / "Mustang.bin").write_bytes(b"different")
    destination = tmp_path / "destination"
    result = run("clean_and_dedup_bins.py", source, destination, "--apply")
    assert result.returncode == 0, result.stderr
    assert (destination / "selected/a.bin").read_bytes() == b"same"
    assert (destination / "duplicate-content/b.bin").read_bytes() == b"same"
    assert (destination / "review-name-heuristic/Mustang.bin").read_bytes() == b"different"
    assert len(list(source.iterdir())) == 3


def test_import_has_no_scan_or_write_side_effects(tmp_path):
    code = "import organize_bins, clean_and_dedup_bins, sort_tuning_db_to_bins"
    result = subprocess.run([sys.executable, "-c", code], cwd=HERE,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""

def test_tuning_name_normalization_keeps_distinct_variants(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    originals = {"BMW.MS43.430069.a": b"a" * 16384,
                 "BMW_MS43_430069_a": b"b" * 16384}
    for name, data in originals.items():
        (source / name).write_bytes(data)
    destination = tmp_path / "destination"
    result = run("sort_tuning_db_to_bins.py", source, destination, "--apply")
    assert result.returncode == 0, result.stderr
    copied = list((destination / "all_ms43_bins").glob("*.bin"))
    assert len(copied) == 2
    assert {p.read_bytes() for p in copied} == set(originals.values())
    manifest = json.loads((destination / "tuning-inventory.json").read_text(encoding="utf-8"))
    assert {entry["source"] for entry in manifest["files"]} == set(originals)
