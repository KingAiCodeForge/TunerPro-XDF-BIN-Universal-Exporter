"""Portable source utility checks with generated data only."""
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

import csv_json_input_batch_exporter as batch
import hash_dedup_dualmode as dedup

HERE = Path(__file__).resolve().parent


def run_script(script, args, cwd):
    return subprocess.run([sys.executable, str(HERE / script), *map(str, args)],
                          cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


@pytest.fixture
def pair(tmp_path):
    root = tmp_path / "portable fixture folder"
    root.mkdir()
    (root / "source.bin").write_bytes(bytes(range(256))*4)
    (root / "source.xdf").write_text('''<XDFFORMAT><XDFHEADER><deftitle>Synthetic</deftitle></XDFHEADER>
      <XDFCONSTANT uniqueid="1"><title>Scalar</title>
      <EMBEDDEDDATA mmedaddress="0" mmedelementsizebits="8"/>
      <MATH equation="X"><VAR id="X"/></MATH></XDFCONSTANT></XDFFORMAT>''', encoding="utf-8")
    return root


@pytest.mark.parametrize("module", ["quick_scan", "scan_bin_cal_ids", "hash_dedup_dualmode", "csv_json_input_batch_exporter", "public_collection_cli"])
def test_import_has_no_collection_or_report_side_effect(module, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    importlib.reload(importlib.import_module(module))
    assert list(tmp_path.iterdir()) == []
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("script", ["quick_scan.py", "scan_bin_cal_ids.py"])
def test_scans_work_from_unrelated_space_path_and_refuse_report_overwrite(script, tmp_path):
    folder = tmp_path / "collection space"
    folder.mkdir()
    binary = folder / "synthetic.bin"
    binary.write_bytes(b"ca0110C6" + b"\0"*1024)
    report = tmp_path / "new report.txt"
    before = binary.read_bytes()
    result = run_script(script, [folder, "--output", report], tmp_path)
    assert result.returncode == 0, result.stderr
    assert report.is_file()
    assert binary.read_bytes() == before
    saved = report.read_bytes()
    refused = run_script(script, [folder, "--output", report], tmp_path)
    assert refused.returncode == 2
    assert report.read_bytes() == saved
    missing = run_script(script, [tmp_path / "absent"], tmp_path)
    assert missing.returncode == 2
    assert "not found" in missing.stderr.lower()


def test_dedup_full_hash_and_no_copy_or_implicit_identity(tmp_path):
    source = tmp_path / "source space"
    collection = tmp_path / "existing space"
    source.mkdir(); collection.mkdir()
    (source / "a.bin").write_bytes(b"new synthetic")
    (source / "b.bin").write_bytes(b"new synthetic")
    (collection / "old.bin").write_bytes(b"existing synthetic")
    result = run_script("hash_dedup_dualmode.py", [source, "--collection", collection], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "source duplicate=1" in result.stdout
    assert "unclassified" in result.stdout
    assert len(dedup.sha16(source / "a.bin")) == 64
    assert sorted(path.name for path in source.iterdir()) == ["a.bin", "b.bin"]


def test_batch_resolves_manifest_relative_paths_and_preserves_outputs(pair, tmp_path):
    manifest = pair / "jobs.json"
    manifest.write_text(json.dumps({"xdf":"source.xdf", "bin":"source.bin", "output":"report.json", "format":"json"}),encoding="utf-8")
    result = run_script("csv_json_input_batch_exporter.py", [manifest], tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    report = pair / "report.json"
    assert json.loads(report.read_text(encoding="utf-8"))["scalars"]
    original = report.read_bytes()
    second = run_script("csv_json_input_batch_exporter.py", [manifest], tmp_path)
    assert second.returncode == 2
    assert report.read_bytes() == original


def test_batch_cross_job_collision_stops_before_any_output(pair):
    row = {"xdf":"source.xdf", "bin":"source.bin", "output":"new.json", "format":"json"}
    jobs = [batch._normalise_row(row,"one",pair), batch._normalise_row(dict(row,output="source.bin"),"two",pair)]
    before = (pair / "source.bin").read_bytes()
    with pytest.raises(ValueError):
        batch.validate_batch_plan(jobs)
    assert not (pair / "new.json").exists()
    assert (pair / "source.bin").read_bytes() == before


def test_batch_invalid_row_not_silently_skipped(pair):
    manifest = pair / "bad.csv"
    manifest.write_text("xdf,bin,output\nsource.xdf,source.bin,new.json\nmissing.xdf,source.bin,other.json\n",encoding="utf-8")
    with pytest.raises(ValueError, match="not found"):
        batch.load_manifest_csv(manifest)
    assert not (pair / "new.json").exists()


@pytest.mark.parametrize("content", [[], 1, "text", [{"xdf": "source.xdf"}]])
def test_batch_malformed_json_fails_cleanly(content, pair):
    manifest = pair / "bad.json"
    manifest.write_text(json.dumps(content),encoding="utf-8")
    result = run_script("csv_json_input_batch_exporter.py",[manifest],pair)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_regression_runner_explicit_roots_missing_corpus_is_failure(tmp_path):
    result = run_script("run_regression_suite.py", ["--repos-root", tmp_path, "--guides-root", tmp_path,
                        "--case", "BMW_MS42_0110C6"], tmp_path)
    assert result.returncode == 1
    assert "missing fixture" in result.stdout
    assert "PASSED: 0  FAILED: 1" in result.stdout


def test_regression_runner_refuses_existing_keep_output(tmp_path):
    output = tmp_path / "existing output"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("preserve",encoding="utf-8")
    result = run_script("run_regression_suite.py", ["--case", "Synthetic_Positive_Major_Stride", "--keep-output", output], tmp_path)
    assert result.returncode == 2
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert sorted(p.name for p in output.iterdir()) == ["keep.txt"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch launcher")
def test_windows_launchers_paths_spaces_exit_codes_and_install_help(tmp_path, monkeypatch):
    import os
    import shutil
    folder = tmp_path / "launcher folder space"
    folder.mkdir()
    for name in ("install.bat", "launch_cli.bat", "launch_gui.bat"):
        shutil.copy2(HERE/name,folder/name)
    (folder/"tunerpro_exporter.py").write_text("import sys\nprint('FORWARDED', sys.argv[1:])\nraise SystemExit(7)\n",encoding="utf-8")
    monkeypatch.setenv("KINGAI_PYTHON",sys.executable)
    def batch_run(name,*args):
        return subprocess.run([str(folder/name),*args], shell=True,cwd=tmp_path,
                              text=True,capture_output=True)
    installed = batch_run("install.bat","--help")
    assert installed.returncode == 0, installed.stdout+installed.stderr
    assert not (folder/".venv").exists()
    launched = batch_run("launch_cli.bat","--help")
    assert launched.returncode == 7, launched.stdout+launched.stderr
    assert "FORWARDED ['--help']" in launched.stdout
    # An invalid explicit interpreter fails clearly without installing anything.
    monkeypatch.setenv("KINGAI_PYTHON",str(folder/"absent python.exe"))
    missing = batch_run("launch_gui.bat")
    assert missing.returncode == 1
    assert "Python 3.10+ is required" in missing.stdout

@pytest.mark.parametrize("text", ["xdf,bin,output,output\nsource.xdf,source.bin,a.json,b.json\n", "xdf,bin,output\nsource.xdf,source.bin,a.json,extra\n"])
def test_batch_ambiguous_csv_fails_before_export(text,pair):
    manifest=pair/"ambiguous.csv"
    manifest.write_text(text,encoding="utf-8")
    with pytest.raises(ValueError):
        batch.load_manifest_csv(manifest)
    assert not (pair/"a.json").exists()
