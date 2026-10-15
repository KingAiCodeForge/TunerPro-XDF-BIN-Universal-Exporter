"""Synthetic parity and source-preservation checks; no ECU files are used."""

from contextlib import redirect_stderr, redirect_stdout
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tunerpro_native_export_parity as parity


def display(value):
    return parity.DisplayNumber(float(value), 2, f"{value:.2f}")


def native_fixture():
    return {
        "metadata": {},
        "parse_errors": [],
        "scalars": [
            {"title": "Current", "occurrence": 1, "value": display(10), "unit": "mA"}
        ],
        "tables": [
            parity.NativeTable(
                title="Pressure",
                occurrence=1,
                unit="kPa",
                x=[display(0), display(1)],
                y=[display(10), display(20)],
                data=[[display(100), display(101)], [display(102), display(103)]],
            )
        ],
    }


def exported_fixture():
    return {
        "metadata": {},
        "scalars": [{"title": "Current", "value": 10.0, "unit": "mA"}],
        "tables": [
            {
                "title": "Pressure",
                "axes": {
                    "x": {"labels": [0, 1]},
                    "y": {"labels": [10, 20]},
                    "z": {"unit": "kPa"},
                },
                "data": [[100, 101], [102, 103]],
            }
        ],
    }


class UnitVerdictTests(unittest.TestCase):
    def compare(self, native=None, exported=None):
        return parity.compare_exports(
            native_fixture() if native is None else native,
            exported_fixture() if exported is None else exported,
            1e-9,
        )

    def test_valid_scalar_and_table_pass_with_two_comparisons(self):
        report = self.compare()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["summary"]["compared_objects"], 2)
        self.assertEqual(report["summary"]["scalar_unit_mismatches"], 0)
        self.assertEqual(report["summary"]["table_unit_mismatches"], 0)

    def test_si_prefix_case_is_not_erased(self):
        for left, right in [("mA", "MA"), ("ms", "Ms"), ("mW", "MW"), ("kPa", "KPa")]:
            with self.subTest(native=left, exported=right):
                result = parity.compare_units(left, right)
                self.assertFalse(result["unit_matches"])
                self.assertEqual(result["unit_status"], "MISMATCH")

    def test_whitespace_normalization_preserves_unit_agreement(self):
        self.assertTrue(parity.compare_units("  mA \t", "mA")["unit_matches"])
        self.assertTrue(parity.compare_units("g  /\t s", "g / s")["unit_matches"])

    def test_whitespace_does_not_join_different_unit_tokens(self):
        self.assertFalse(parity.compare_units("m A", "mA")["unit_matches"])

    def test_aliases_and_temperature_conversions_are_not_inferred(self):
        for left, right in [("ms", "msec"), ("degC", "degF"), ("psi", "kPa")]:
            with self.subTest(native=left, exported=right):
                self.assertFalse(parity.compare_units(left, right)["unit_matches"])

    def test_one_missing_unit_is_a_mismatch(self):
        for left, right in [(None, "mA"), ("mA", ""), (" ", "mA")]:
            with self.subTest(native=left, exported=right):
                self.assertEqual(parity.compare_units(left, right)["unit_status"], "MISMATCH")

    def test_two_missing_units_are_unspecified_not_proven(self):
        result = parity.compare_units(None, " \t")
        self.assertTrue(result["unit_matches"])
        self.assertEqual(result["unit_status"], "UNSPECIFIED")
        self.assertIn("unverified", result["unit_reason"])

    def test_equal_scalar_values_with_different_units_fail(self):
        exported = exported_fixture()
        exported["scalars"][0]["unit"] = "MA"
        report = self.compare(exported=exported)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["scalars"][0]["value_status"], "MATCH")
        self.assertEqual(report["scalars"][0]["unit_status"], "MISMATCH")
        self.assertEqual(report["summary"]["scalar_unit_mismatches"], 1)
        self.assertEqual(report["summary"]["scalar_mismatches"], 1)

    def test_equal_table_values_with_different_units_fail(self):
        exported = exported_fixture()
        exported["tables"][0]["axes"]["z"]["unit"] = "psi"
        report = self.compare(exported=exported)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["tables"][0]["value_status"], "MATCH")
        self.assertEqual(report["tables"][0]["unit_status"], "MISMATCH")
        self.assertEqual(report["summary"]["table_unit_mismatches"], 1)
        self.assertEqual(report["tables"][0]["data"]["mismatches"], 0)

    def test_omitted_scalar_unit_fails(self):
        exported = exported_fixture()
        del exported["scalars"][0]["unit"]
        self.assertEqual(self.compare(exported=exported)["status"], "FAIL")

    def test_omitted_table_unit_fails(self):
        exported = exported_fixture()
        del exported["tables"][0]["axes"]["z"]
        self.assertEqual(self.compare(exported=exported)["status"], "FAIL")

    def test_both_unspecified_are_counted_with_an_explicit_scope_limit(self):
        native, exported = native_fixture(), exported_fixture()
        native["scalars"][0]["unit"] = ""
        native["tables"][0].unit = ""
        exported["scalars"][0]["unit"] = ""
        exported["tables"][0]["axes"]["z"]["unit"] = ""
        report = self.compare(native, exported)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["summary"]["objects_with_unspecified_units"], 2)
        self.assertIn("do not prove", report["scope"])

    def test_numeric_difference_still_fails_when_units_match(self):
        exported = exported_fixture()
        exported["scalars"][0]["value"] = 11.0
        report = self.compare(exported=exported)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["scalars"][0]["value_status"], "MISMATCH")
        self.assertEqual(report["scalars"][0]["unit_status"], "MATCH")

    def test_transpose_does_not_bypass_unit_mismatch(self):
        exported = exported_fixture()
        table = exported["tables"][0]
        table["axes"]["x"]["labels"] = [10, 20]
        table["axes"]["y"]["labels"] = [0, 1]
        table["data"] = [[100, 102], [101, 103]]
        table["axes"]["z"]["unit"] = "psi"
        report = self.compare(exported=exported)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["tables"][0]["orientation"], "transpose")
        self.assertEqual(report["tables"][0]["value_status"], "MATCH")

    def test_empty_exports_cannot_pass(self):
        native = {"metadata": {}, "scalars": [], "tables": [], "parse_errors": []}
        report = self.compare(native, {"scalars": [], "tables": []})
        self.assertEqual(report["status"], "INCONCLUSIVE")
        self.assertEqual(report["summary"]["compared_objects"], 0)
        self.assertTrue(report["validation_errors"])

    def test_missing_table_prevents_partial_scalar_success(self):
        exported = exported_fixture()
        exported["tables"] = []
        report = self.compare(exported=exported)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["summary"]["compared_objects"], 1)
        self.assertEqual(report["summary"]["missing_tables"], 1)

    def test_native_parse_error_prevents_pass(self):
        native = native_fixture()
        native["parse_errors"] = ["Synthetic malformed native scalar"]
        self.assertEqual(self.compare(native=native)["status"], "FAIL")

    def test_empty_and_unrelated_native_text_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "native.txt"
            for text in ["", "A note with no native calibration objects.\n"]:
                with self.subTest(text=text):
                    path.write_text(text, encoding="utf-8")
                    report = self.compare(native=parity.parse_native_export(path))
                    self.assertEqual(report["status"], "FAIL")
                    self.assertEqual(report["summary"]["compared_objects"], 0)


class CliPreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native = self.root / "native.txt"
        self.exported = self.root / "exported.json"
        self.native.write_text("SCALAR: Current  10.00 mA\n", encoding="utf-8")
        self.exported.write_text(
            json.dumps({"scalars": [{"title": "Current", "value": 10.0, "unit": "mA"}], "tables": []}),
            encoding="utf-8",
        )
        self.originals = {path: path.read_bytes() for path in [self.native, self.exported]}

    def run_cli(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["parity", str(self.native), str(self.exported), *map(str, arguments)]
        with patch("sys.argv", argv), redirect_stdout(stdout), redirect_stderr(stderr):
            code = parity.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_inputs_preserved(self):
        for path, content in self.originals.items():
            self.assertEqual(path.read_bytes(), content)

    def test_valid_cli_writes_json_and_csv_without_changing_inputs(self):
        output = self.root / "report.json"
        code, stdout, stderr = self.run_cli("--out", output)
        self.assertEqual(code, 0, stderr)
        self.assertIn("PASS:", stdout)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["summary"]["compared_objects"], 1)
        with output.with_suffix(".csv").open(encoding="utf-8", newline="") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["unit_status"], "MATCH")
        self.assertEqual(row["value_status"], "MATCH")
        self.assert_inputs_preserved()

    def test_unit_mismatch_cli_returns_failure_and_reports_it(self):
        payload = json.loads(self.exported.read_text(encoding="utf-8"))
        payload["scalars"][0]["unit"] = "MA"
        self.exported.write_text(json.dumps(payload), encoding="utf-8")
        self.originals[self.exported] = self.exported.read_bytes()
        output = self.root / "report.json"
        code, stdout, stderr = self.run_cli("--out", output)
        self.assertEqual(code, 1, stderr)
        self.assertIn("1 declared-unit mismatch(es)", stdout)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["scalars"][0]["native_unit"], "mA")
        self.assertEqual(report["scalars"][0]["exporter_unit"], "MA")
        self.assert_inputs_preserved()

    def test_direct_input_alias_is_refused_before_any_output(self):
        code, stdout, stderr = self.run_cli("--out", self.native)
        self.assertEqual(code, 2)
        self.assertIn("ERROR:", stderr)
        self.assertNotIn("PASS:", stdout)
        self.assertFalse(self.native.with_suffix(".csv").exists())
        self.assert_inputs_preserved()

    def test_csv_input_alias_preflights_the_whole_output_plan(self):
        output = self.root / "report.json"
        code, _, stderr = self.run_cli("--out", output, "--csv", self.exported)
        self.assertEqual(code, 2)
        self.assertIn("ERROR:", stderr)
        self.assertFalse(output.exists())
        self.assert_inputs_preserved()

    def test_json_csv_path_collision_is_refused(self):
        output = self.root / "report.json"
        code, _, _ = self.run_cli("--out", output, "--csv", output)
        self.assertEqual(code, 2)
        self.assertFalse(output.exists())
        self.assert_inputs_preserved()

    def test_existing_report_is_not_overwritten(self):
        output = self.root / "report.json"
        output.write_bytes(b"existing report must survive")
        code, _, _ = self.run_cli("--out", output)
        self.assertEqual(code, 2)
        self.assertEqual(output.read_bytes(), b"existing report must survive")
        self.assertFalse(output.with_suffix(".csv").exists())
        self.assert_inputs_preserved()

    def test_hardlinked_input_is_not_truncated(self):
        output = self.root / "alias.json"
        try:
            os.link(self.native, output)
        except OSError as exc:
            self.skipTest(f"Temporary filesystem does not permit hardlinks: {exc}")
        code, _, _ = self.run_cli("--out", output)
        self.assertEqual(code, 2)
        self.assertEqual(output.read_bytes(), self.originals[self.native])
        self.assert_inputs_preserved()


if __name__ == "__main__":
    unittest.main(verbosity=2)
