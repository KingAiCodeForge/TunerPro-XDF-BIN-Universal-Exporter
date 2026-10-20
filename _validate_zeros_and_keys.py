#!/usr/bin/env python3
"""Compare zero/range/axis signals for two explicitly selected XDF/BIN pairs.

Uses the same bounded parser and equation engine as the exporter. Exact table
name matches are comparison candidates, not evidence of semantic equivalence.
No private calibration names, known-address lists, or workstation defaults are
embedded in this reusable utility.
"""
from _validate_xdf_bin import main


if __name__ == "__main__":
    raise SystemExit(main())
