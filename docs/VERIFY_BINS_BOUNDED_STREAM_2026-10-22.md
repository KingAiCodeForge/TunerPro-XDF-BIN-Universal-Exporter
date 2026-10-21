# Bounded-memory BIN string inventory — v0.1.0

**Date:** 2026-10-22 06:54 ACDT · **Status:** isolated read-only optimization, not merged.

The original `verify_bins.py` called `f.read()` for every firmware file, allocating the **entire BIN** before searching for known Siemens/BMW string hints. This increases memory usage when scanning many large dumps. It also made no bounded-memory guarantee for accidentally supplied oversized files.

## Implementation

- Stream one 1 MiB input block at a time, with a `max(marker length) - 1` overlap to detect signatures crossing block boundaries.
- Preserve the **first occurrence byte offset** of every marker, original ASCII printable context (`-4` to `+20`), case sensitivity and existing output format.
- Preserve the exact total file size via seek/tell; do not infer file identity from a label.
- Seek back only to format context for markers actually found, instead of keeping the firmware in RAM.
- Entirely read-only: no calibration edits, checksum rewriting, reflashing or auto-identification claims.

## Executed test evidence

A local Python prototype of the updated scanner was checked against an oracle for the original whole-buffer implementation.

- **7/7** synthetic cases passed: beginning-of-file hits, split-across-block hits, multiple first-match hits, case-sensitive overlapping markers, absent markers, small files and read failures.
- The committed `test_verify_bins_streaming.py` contains **9** parameterized tests. A local mirror of the production function plus that test file passed **9/9** with Pytest 9; the full private repo was not checked out/executed, so **the exact complete committed package still requires a real checkout run**.

Synthetic 64 MiB fixture benchmark (Python 3.13, one run, not a sustained speed claim):

| Method | Elapsed | Peak Python-tracked allocations |
| --- | ---: | ---: |
| Prior `read()` whole BIN | 878 ms | 64 MiB |
| Streaming scanner | 714 ms | 3 MiB |

The peak-memory reduction is the primary objective. Timing is workload/OS-cache dependent and does not imply every 512 KB ECU BIN will run faster.

Original file blob: `df179f1802c68f8f135511b59179741d30f75f4f`. New file blob: `09065f5c39e52c427f4276575d1bb77e66daf7fe`.

## Reproduction

```sh
python -m pytest -q test_verify_bins_streaming.py
python -m pytest -q test_portable_validators.py
python verify_bins.py <your-read-only-folder>
```

Before merge, run the full regression collection and compare the exact string/size inventories of known local firmware samples. These results establish source/tool behaviour **only**, not ECU software identity or readiness for vehicle programming. Preserve all original BINs and XDFs.
