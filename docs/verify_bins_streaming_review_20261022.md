# Offline review: streaming firmware-string scanner (22 October 2026)

Targeted audit of verify_bins.py, which previously called an unrestricted read() for every file in every selected directory. That operation scales memory linearly with source file size, making very large BIN collections or mistakenly selected disk images risky.

The revised check_strings() reads at most 64 KiB at a time and maintains a bounded overlap. It preserves the previous scanner's **first matching software string**, absolute offset, four bytes of left context and up to 20 bytes of right context, including when a marker crosses a chunk boundary. It checks file size and metadata before and after scanning, and refuses direct links/reparse points. No original firmware or definition is changed, decoded, written or flashed.

Executed Python 3.13.5 synthetic tests: **14/14 PASS**, including nine boundary offsets, mixed-case source IDs, multiple occurrences, empty/short files, a bounded-read spy that disallows unbounded read(), and symlink refusal.

Local focused test code was committed exactly as executed (test Git blob SHA: 6cbac1054a7caa6642a322679194da067df2faf6). The source-scanner logic was developed/tested in an isolated module and transplanted into verify_bins.py while preserving its CLI classification/reporting path; the **complete existing exporter regression suite and installed-package smoke were not run** here. No GitHub Actions. Leave draft pending a full local checkout/installed test.

Run:

    python -m pytest -q test_verify_bins_streaming.py test_portable_validators.py

Large original corpora and ECU identity claims remain outside this synthetic regression.
