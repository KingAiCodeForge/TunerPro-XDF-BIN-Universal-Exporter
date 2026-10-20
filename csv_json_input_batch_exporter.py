#!/usr/bin/env python3
"""Export explicit XDF/BIN pairs from a CSV or JSON manifest.

Required keys: xdf, bin, output. Optional: format (txt/json/md/csv/all),
options (--addresses --flip-rpm --flip-load --no-stats). Relative paths are
resolved beside the manifest, independent of the current working directory.
All jobs are validated before any output is created; existing files are refused.
"""
import argparse
import csv
import json
import shlex
from pathlib import Path

from tunerpro_exporter import UniversalXDFExporter, __version__, safe_print
from tunerpro_xdf.output_safety import assert_safe_output_plan

FORMATS = {"text": "txt", "markdown": "md"}
ALLOWED_OPTIONS = {"--addresses", "--flip-rpm", "--flip-load", "--no-stats"}


def _normalise_row(row, source, base_dir=None):
    if not isinstance(row, dict):
        raise ValueError(f"{source}: manifest entry must be an object")
    if None in row:
        raise ValueError(f"{source}: too many CSV fields")
    row = {str(k).strip().lower(): v for k, v in row.items()}
    base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
    paths = {}
    for key in ("xdf", "bin", "output"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{source}: missing or invalid '{key}' path")
        path = Path(value.strip())
        paths[key] = str((base_dir / path).resolve() if not path.is_absolute() else path.resolve())
        if key != "output" and not Path(paths[key]).is_file():
            raise ValueError(f"{source}: {key} file not found: {path}")
    fmt = str(row.get("format") or "all").strip().lower()
    fmt = FORMATS.get(fmt, fmt)
    if fmt not in ("txt", "json", "md", "csv", "all"):
        raise ValueError(f"{source}: unsupported format: {fmt}")
    options = row.get("options") or ""
    if not isinstance(options, str):
        raise ValueError(f"{source}: options must be a string of supported flags")
    tokens = shlex.split(options)
    unknown = set(tokens) - ALLOWED_OPTIONS
    if unknown:
        raise ValueError(f"{source}: unsupported options: {', '.join(sorted(unknown))}")
    return dict(paths, format=fmt, source=source,
                addresses="--addresses" in tokens, flip_rpm="--flip-rpm" in tokens,
                flip_load="--flip-load" in tokens, no_stats="--no-stats" in tokens)


def load_manifest_csv(csv_path):
    path = Path(csv_path).resolve()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        lines = [line for line in stream if line.strip() and not line.lstrip().startswith("#")]
    reader = csv.DictReader(lines, delimiter="\t" if path.suffix.lower() == ".tsv" else ",")
    if not reader.fieldnames:
        raise ValueError("CSV manifest is empty or lacks a header")
    reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("CSV manifest contains duplicate headers")
    if not {"xdf", "bin", "output"}.issubset(reader.fieldnames):
        raise ValueError("CSV manifest requires xdf, bin and output headers")
    return [_normalise_row(row, f"{path.name}:{number}", path.parent)
            for number, row in enumerate(reader, start=2)]


def load_manifest_json(json_path):
    path = Path(json_path).resolve()
    with path.open(encoding="utf-8-sig") as stream:
        data = json.load(stream)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON manifest must be an object or array of objects")
    return [_normalise_row(row, f"{path.name}[{index}]", path.parent)
            for index, row in enumerate(data)]


def output_plan(job):
    base = Path(job["output"])
    formats = ("txt", "json", "md", "csv") if job["format"] == "all" else (job["format"],)
    return [(fmt, str(base.parent / f"{base.stem}.{fmt}") if job["format"] == "all" else str(base))
            for fmt in formats]


def validate_batch_plan(jobs, manifest_path=None):
    outputs = [path for job in jobs for _, path in output_plan(job)]
    protected = [path for job in jobs for path in (job["xdf"], job["bin"])]
    if manifest_path:
        protected.append(manifest_path)
    assert_safe_output_plan(outputs, protected)


def run_single_export(job):
    result = {"ok": False, "xdf": job["xdf"], "bin": job["bin"], "outputs": [], "errors": []}
    try:
        validate_batch_plan([job])
        exporter = UniversalXDFExporter(job["xdf"], job["bin"])
        for flag in ("addresses", "flip_rpm", "flip_load", "no_stats"):
            setattr(exporter, "show_addresses" if flag == "addresses" else flag, job[flag])
        if not exporter.validate_bin_file():
            raise ValueError("BIN validation failed")
        if not exporter.parse_xdf():
            raise ValueError("XDF parsing failed")
        writers = {"txt": exporter.export_to_text, "json": exporter.export_to_json,
                   "md": exporter.export_to_markdown, "csv": exporter.export_to_csv}
        for fmt, path in output_plan(job):
            if not writers[fmt](path):
                raise RuntimeError(f"{fmt.upper()} export failed: {path}")
            result["outputs"].append((fmt.upper(), path))
        result["ok"] = True
    except Exception as exc:
        result["errors"].append(str(exc))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="CSV, TSV or JSON manifest")
    args = parser.parse_args(argv)
    try:
        if not args.manifest.is_file():
            raise ValueError(f"Manifest file not found: {args.manifest}")
        jobs = load_manifest_json(args.manifest) if args.manifest.suffix.lower() == ".json" else load_manifest_csv(args.manifest)
        if not jobs:
            raise ValueError("Manifest contains no jobs")
        validate_batch_plan(jobs, args.manifest)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    results = []
    for index, job in enumerate(jobs, start=1):
        safe_print(f"[{index}/{len(jobs)}] {Path(job['xdf']).name} + {Path(job['bin']).name}")
        result = run_single_export(job)
        results.append(result)
        for error in result["errors"]:
            safe_print(f"[FAIL] {error}")
    failed = sum(not result["ok"] for result in results)
    safe_print(f"Exporter {__version__}: jobs={len(results)} passed={len(results)-failed} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
