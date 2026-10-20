"""Exercise the GUI worker without opening a window or requiring Qt."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


class Signal:
    def __init__(self, *args):
        self.events = []

    def emit(self, *args):
        self.events.append(args)


@pytest.fixture
def worker_class():
    source = Path(__file__).with_name("exporter_gui.py").read_text(encoding="utf-8-sig")
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == "ExportWorker")
    import tunerpro_exporter
    namespace = {"QThread": object, "Signal": Signal, "Path": Path,
                 "UniversalXDFExporter": tunerpro_exporter.UniversalXDFExporter}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "exporter_gui.py", "exec"), namespace)
    return namespace["ExportWorker"]


def test_worker_rejects_whole_plan_before_writing(worker_class, tmp_path):
    binary = tmp_path / "source.bin"
    binary.write_bytes(bytes(1024))
    xdf = tmp_path / "source.xdf"
    xdf.write_text('<XDFFORMAT><XDFCONSTANT><title>Scalar</title>'
                   '<EMBEDDEDDATA mmedaddress="0" mmedelementsizebits="8"/>'
                   '<MATH equation="X"/></XDFCONSTANT></XDFFORMAT>')
    output = tmp_path / "report"
    existing = tmp_path / "report.csv"
    existing.write_bytes(b"preserve")
    worker = worker_class(str(xdf), str(binary), str(output), ["json", "csv"])
    worker.run()
    assert worker.finished.events[-1][0] is False
    assert existing.read_bytes() == b"preserve"
    assert not (tmp_path / "report.json").exists()


def test_csv_wrapper_reports_core_failure(worker_class):
    worker = worker_class("source.xdf", "source.bin", "report", ["csv"])
    with pytest.raises(RuntimeError, match="CSV export failed"):
        worker._export_csv(SimpleNamespace(export_to_csv=lambda output: False), "report.csv")


def test_legacy_skip_flag_still_runs_binary_validation(worker_class, tmp_path, monkeypatch):
    validations = []
    def reject_binary():
        validations.append(True)
        return False
    monkeypatch.setitem(worker_class.run.__globals__, "UniversalXDFExporter",
                        lambda *args: SimpleNamespace(validate_bin_file=reject_binary))
    worker = worker_class("source.xdf", "source.bin", str(tmp_path / "report"), ["json"], True)
    worker.run()
    assert validations == [True]
    assert worker.finished.events[-1][0] is False
    assert not (tmp_path / "report.json").exists()
