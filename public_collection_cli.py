"""Shared CLI validation for the optional, source-distributed collection tools.

These tools report filename/string heuristics, never ECU compatibility or tuning
safety. Caller-supplied directories are read-only; reports use exclusive creation.
"""

import argparse
from pathlib import Path


def collection_arguments(parser: argparse.ArgumentParser, argv=None):
    parser.add_argument("folders", nargs="+", type=Path,
                        help="Explicit collection directories to inspect (read-only)")
    parser.add_argument("-o", "--output", type=Path,
                        help="Optional new report path; existing files are refused")
    args = parser.parse_args(argv)
    for folder in args.folders:
        if not folder.is_dir():
            parser.error(f"Collection directory not found: {folder}")
    if args.output and (args.output.exists() or args.output.is_symlink()):
        parser.error(f"Refusing to overwrite report: {args.output}")
    return args


def write_report(path, text):
    """Write a new report without overwriting source files or prior reports."""
    if path is None:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)
