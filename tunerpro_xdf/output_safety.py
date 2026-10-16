"""Preflight destination paths before file export."""

import os
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
