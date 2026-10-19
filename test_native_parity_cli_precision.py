"""Exercise the real CLI precision path using synthetic text/JSON inputs."""

import json
from pathlib import Path
import subprocess
import sys

import pytest
import tunerpro_native_export_parity as parity


@pytest.mark.parametrize(
    "candidate, extra_args, expected_code, expected_status",
    [
        (1.001e-14, [], 0, "PASS"),
        (1.05e-13, [], 1, "FAIL"),
        (1.05e-13, ["--absolute-tolerance", "0"], 1, "FAIL"),
        (1.05e-13, ["--absolute-tolerance", "1e-9"], 0, "PASS"),
    ],
)
def test_cli_scientific_default_and_explicit_override(
    tmp_path, candidate, extra_args, expected_code, expected_status
):
    native, exported, originals = write_inputs(tmp_path, candidate)
    report = tmp_path / "report.json"
    result = run_cli(tmp_path, native, exported, "--out", report, *extra_args)
    assert result.returncode == expected_code, result.stdout + result.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == expected_status
    assert payload["summary"]["compared_objects"] == 1
    assert payload["scalars"][0]["value_status"] == (
        "MATCH" if expected_status == "PASS" else "MISMATCH"
    )
    if not extra_args:
        assert payload["scalars"][0]["tolerance"] < 1e-15
    assert report.with_suffix(".csv").is_file()
    assert [path.read_bytes() for path in (native, exported)] == originals


@pytest.mark.parametrize("tolerance", ["-1", "nan", "inf", "-inf"])
def test_cli_invalid_tolerance_refuses_without_output(tmp_path, tolerance):
    native, exported, originals = write_inputs(tmp_path, 1e-14)
    report = tmp_path / "report.json"
    result = run_cli(
        tmp_path, native, exported, "--out", report,
        "--absolute-tolerance=" + tolerance,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "tolerance" in result.stderr.lower()
    assert not report.exists()
    assert not report.with_suffix(".csv").exists()
    assert [path.read_bytes() for path in (native, exported)] == originals


def write_inputs(root, candidate):
    native = root / "native.txt"
    exported = root / "export.json"
    native.write_text("SCALAR: Tiny  1.00e-14 V\n", encoding="utf-8")
    exported.write_text(json.dumps({
        "scalars": [{"title": "Tiny", "value": candidate, "unit": "V"}],
        "tables": [],
    }), encoding="utf-8")
    return native, exported, [p.read_bytes() for p in (native, exported)]


def run_cli(cwd, *arguments):
    # Use exactly the imported runtime, including an installed wheel during
    # isolated package replay. Propagate optimization to the real CLI process.
    command = [sys.executable]
    if sys.flags.optimize:
        command.append("-" + "O" * sys.flags.optimize)
    command.extend([str(Path(parity.__file__).resolve()), *map(str, arguments)])
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                          timeout=15, check=False)
