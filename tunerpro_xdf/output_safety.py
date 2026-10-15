"""Preflight destination paths before file export."""

import os
from contextlib import contextmanager
from pathlib import Path


def _same_file(left, right):
    """Compare resolved paths and, if files exist, underlying file identity."""
    left = os.fspath(left)
    right = os.fspath(right)
    if os.path.normcase(os.path.realpath(os.path.abspath(left))) == os.path.normcase(
        os.path.realpath(os.path.abspath(right))
    ):
        return True
    try:
        return os.path.samefile(left, right)
    except (OSError, ValueError):
        return False


def assert_safe_output_plan(outputs, protected_inputs):
    """Reject output collisions with sources or other planned outputs.

    Filesystem preflight is not a defence against concurrent path replacement.
    """
    planned = [Path(p) for p in outputs]
    protected = [Path(p) for p in protected_inputs]
    if not planned:
        raise ValueError("No output paths requested")
    for index, output in enumerate(planned):
        if output.is_symlink():
            raise ValueError(f"Refusing symlink output: {output}")
        if output.is_dir():
            raise ValueError(f"Output is a directory: {output}")
        for source in protected:
            if _same_file(output, source):
                raise ValueError(f"Output aliases an input: {output}")
        for previous in planned[:index]:
            if _same_file(output, previous):
                raise ValueError(f"Two outputs alias one file: {previous} / {output}")
    preflight_output_paths(planned, protected)


def preflight_output_paths(output_paths, input_paths=()):
    """Reject aliases/existing destinations; exclusive creation closes file races."""
    protected = {os.path.normcase(str(Path(p).resolve())) for p in input_paths}
    seen = set()
    for path in output_paths:
        path = Path(path)
        resolved = os.path.normcase(str(path.resolve()))
        if resolved in protected:
            raise ValueError(f"Output must not alias an input file: {path}")
        if resolved in seen:
            raise ValueError(f"Output paths must be distinct: {path}")
        seen.add(resolved)
        if os.path.lexists(path):
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")


@contextmanager
def open_new_output(path, input_paths=(), **kwargs):
    """Create a new text output without truncating existing files."""
    path = Path(path)
    assert_safe_output_plan([path], input_paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', **kwargs) as handle:
        yield handle
