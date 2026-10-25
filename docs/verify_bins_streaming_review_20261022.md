# Offline review: streaming firmware-string scanner (22 October 2026)

Targeted audit of verify_bins.py, which previously called an unrestricted read() for every file in every selected directory. That operation scales memory linearly with source file size, making very large BIN collections or mistakenly selected disk images risky.

The revised check_strings() reads at most 64 KiB at a time and maintains a bounded overlap. It preserves the previous scanner's **first matching software string**, absolute offset, four bytes of left context and up to 20 bytes of right context, including when a marker crosses a chunk boundary. It checks file size and metadata before and after scanning, and refuses direct links/reparse points. No original firmware or definition is changed, decoded, written or flashed.

Executed Python 3.13.5 synthetic tests: **14/14 PASS**, including nine boundary offsets, mixed-case source IDs, multiple occurrences, empty/short files, a bounded-read spy that disallows unbounded read(), and symlink refusal.

Local focused test code was committed exactly as executed (test Git blob SHA: 6cbac1054a7caa6642a322679194da067df2faf6). The source-scanner logic was developed/tested in an isolated module and transplanted into verify_bins.py while preserving its CLI classification/reporting path; the **complete existing exporter regression suite and installed-package smoke were not run** here. No GitHub Actions. Leave draft pending a full local checkout/installed test.

Run:

    python -m pytest -q test_verify_bins_streaming.py test_portable_validators.py

Large original corpora and ECU identity claims remain outside this synthetic regression.

## Integrated qualification — 25 October 2026

The candidate retains PR9's 64 KiB reads, overlap, link/reparse refusal and
before/after metadata checks. It reconstructs the final dictionary in the
legacy signature order, retaining PR10's ordered-output property without
replacing the safer streaming implementation. Only the result assembly changes;
the marker list, offsets, contexts and CLI classification remain unchanged.

Pinned inputs: main `b79704782adc4b0782046dc42dcc8c6f78573942`, PR9
`48f94c4b981dadac593b236f29c8845adcf35085`, PR10
`47cc96d55fac45f696a29f8f261adb53f27166f6`. Both original branches remain
preserved. PR10's source is not an ancestor merge; its ordered-output behavior
is covered by the combined candidate's explicit item-order and CLI regressions.

Actual Windows / Python 3.13.5 qualification:

- Eleven new contract cases initially gave **7 failed / 4 passed**, exit 1,
  reproducing dictionary/CLI ordering differences. After the narrow repair,
  original PR9 tests plus the contract and portable-validator tests gave
  **38 passed**, exit 0.
- The unchanged original suites replayed against their own preserved source:
  PR9 **14 passed**, PR10 **9 passed**, both exit 0. The PR10 tests patch its
  `SCAN_BLOCK_SIZE`; they were not mislabeled as candidate chunk-boundary tests.
- Independent replay of the same **672 synthetic input cases** passed mapping,
  exact item order and unchanged-input checks, exit 0. These are the earlier
  oracle inputs with stronger order assertions, not 672 new independent inputs.
- Full source suite: **734 passed, 4 skipped, 18 subtests passed**, exit 0.
  The four skips concern absent exact local SP-Daten/native/MS41 fixtures; no
  new skips or weaker assertions were introduced.
- Built the wheel/sdist without isolation or downloads, installed the wheel in
  a fresh venv, and ran the copied suite away from checkout:
  **734 passed, 4 skipped**, exit 0. All eight wheel Python payloads matched
  both source and installed bytes. Core imports resolved inside that venv;
  installed `tunerpro-xdf-export --help` exited 0.
- `verify_bins.py` remains a source-only standalone utility, NOT a wheel
  payload. The outside-checkout suite separately included a hash-matched copy
  of it and exercised its actual CLI ordering/warning and failure exits.

The source and installed runs overlap; their counts must not be added as unique
coverage. Metadata-only mutation refusal and short reads are now explicit
regressions. Path `lstat` checks do not establish descriptor identity or complete
TOCTOU resistance. Linux/Python 3.10 and native editor/real-firmware qualification
were not run in this batch. Existing GitHub jobs were billing-locked before any
test steps; local results are not a replacement claim for that CI matrix.

Portable machine summary:
[verify_bins_streaming_qualification_20261025.json](verify_bins_streaming_qualification_20261025.json).
