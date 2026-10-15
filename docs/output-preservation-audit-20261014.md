# Output preservation audit

## Integration Review, 15 October 2026

Maintained with OpenAI ChatGPT/Codex. This is a local review, not a release,
fresh native TunerPro validation, tune approval or hardware test.

The starting review commit is `aeae4d3591a9a74f48c16a7cdabea794cc04f9cb`,
on `chatgpt/exporter-three-fix-integration-20261015`. Its three intended fixes
were inspected in code and tests: complete output-plan alias checks,
INCONCLUSIVE/units-aware native-text parity, and one-based CATEGORYMEM zero
sentinels. The existing direct-ID category tie break is preserved, including
legacy direct category zero; the format is not guessed from zero counts.

The separate dirty checkout was preserved in a verified archive, including
untracked source/tests, before work in `codex/exporter-reconcile-20261015`.
No reset, clean, force push, original-definition edit or main merge was used.

### Reconciliation Decisions

- Retain the review branch's scoped-MATH zero-based default, explicit one-based
  opt-in and failure on uncovered cells without a global equation. Do not
  restore the older local one-based inference.
- Carry forward local declared raw-variable aliases, coordinate evidence and
  omitted-definition accounting. Text labels remain distinct from physical
  numeric coordinates; unsupported virtual tables cannot disappear behind a
  clean subset export.
- Combine the review's whole-plan checks with exclusive new-file creation.
  Every format and derived report refuses existing destinations, input aliases
  and duplicate outputs. Direct library writers share the same protection.
  This is not an all-or-nothing multi-file transaction or protection against
  hostile concurrent replacement of parent directories.
- Apply the existing strict-storage regressions: reject malformed integers,
  duplicate nonzero object identifiers, unresolved required axes and partial
  patch-status matches. Unknown storage flags, including `0x04`, remain held
  rather than being accepted as a guessed no-op.
- Native parity cannot PASS empty object/cell comparisons. Incomplete scalar
  evidence produces a useful CLI error; non-finite/negative tolerances are
  rejected. Existing half-display-unit precision is unchanged. Unit checks
  concern the units represented in the saved scalar/table-cell text, not an
  independent proof of axis units or physical meaning.
- Keep converter code unchanged: the preserved local and selected review
  versions are normalized-text identical. No reciprocal-write integration.

Some historical tests contradicted the selected contract. Their replacements
preserve the regression: exact positive-stride read offsets plus rejected
writes; explicit global identity for a sparse-math fixture; zero-based selectors
for an alias-only fixture; and INCONCLUSIVE rather than FAIL for empty evidence.
The optional saved-MS42-label test now extracts two unchanged source objects
onto a disposable zero image. It tests labels, not the unrelated broken links
in the full legacy definition. No numeric tolerances were increased.

### Validation Results

All results below were run locally in this review. Complete logs, commands,
input SHA-256 receipts and dependency listings are retained outside Git in the
target-specific `exporter_reconcile_20261015_r1` audit directory. Private
firmware and saved native captures are not included in this commit.

| Check | Result |
| --- | --- |
| Untouched starting review, portable pytest | 352 passed, 67 failed, 4 fixture skips, 6 subtests; exit 1 |
| Reconciled portable pytest before fixture setup | 477 passed, 4 fixture skips, 6 subtests; exit 0 |
| Final source pytest with exact optional fixtures | 491 passed, 0 skipped, 6 subtests; exit 0 |
| Wheel-installed copied suite outside repository | 491 passed, 0 skipped, 6 subtests; exit 0 |
| Wheel + sdist build; clean runtime installation | Passed; no editable/source-tree installation |
| Installed entry point, helper imports, help/version | Passed; imports resolve under isolated site-packages |
| Source versus installed synthetic export | Equal except export timestamp; independently checked U16, signed, float and 2x2 data |
| Direct/relative/parent-component input aliases | Rejected; input hash assertions pass |
| Hardlink and symlink aliases on this Windows host | Both exercised and rejected; input hash assertions pass |
| Exclusive-create race and whole-plan sidecar collisions | Regression tests pass |
| Empty/matching/unit-mismatch/missing-evidence/tolerance parity | Synthetic regressions pass; no new native editor run |
| Existing CLI corpus runner | 4 synthetic passed, 4 full-definition failures; exit 1 |

Build/test environment: Python 3.13.5, pytest 9.1.1, build 1.6.1,
setuptools 84.0.0, wheel 0.48.0. Commands used include:

```console
python -m pytest -q -p no:cacheprovider --junitxml=<local-audit>/full_final.xml
python -m build --no-isolation --outdir <local-audit>/dist
python -m pip install --no-index --no-deps <built-wheel>
python -I -m pytest <copied-tests> --import-mode=importlib -q -p no:cacheprovider
python run_regression_suite.py --keep-output <local-audit>/fixture_checks_r1/regression
```

`python` refers to the appropriate isolated A-drive environment, not the global
installation. The outside-source smoke harness initially expected exit 2 for
an unknown exporter option; the exporter correctly uses exit 1. That harness
failure is retained alongside a rerun asserting the existing nonzero contract.
It was not repaired by changing production exit codes or suppressing a test.

### Real-Definition Holds

The existing fixture identities, hashes, sizes, storage declarations and
specific offending XML were inspected. Filename/size agreement alone is not
treated as new OSID proof. Original files have matching before/after hashes.

| Existing case | Actual result and boundary |
| --- | --- |
| MS42 0110C6 | Full parse fails at a required linked axis without linkobjid; no whole-definition export approval. Saved-label regression is a narrow separate check. |
| MS43 430069 | Full parse fails on duplicate nonzero uniqueid `0xDC`; selecting an arbitrary link target would be unsafe. |
| MS45 4560BN00 v3 | 1,244 bodies can be graded, but 84 declared views are omitted/unsupported. Complete export fails. Diagnostics grade INCOMPLETE, not a clean full definition. |
| VY $060A legacy Enhanced | Malformed `*2**14` conversion fails export. Diagnostics retain eight decode errors and grade INCOMPLETE. No replacement equation was invented. |

The two generated diagnostic reports retain zero/uniform findings (MS45: 16
zero-context and 541 uniform; VY: 33 zero-context and 68 uniform). Those are
review signals, not proof of corrupt definitions or absent features. No bounds
violations were found in the bodies these reports graded; omitted/failed
objects remain outside that claim. `--diagnostics` exit 0 means the report was
written: inspect `validation_complete`, grade and findings, not exit alone.

The current regression runner's historical expected counts are not silently
updated to hide these failures. No BIN modifications or write/readback tests
were needed for this read-only integration.

### Packaging And Follow-Up

Package metadata, module version and README now agree on
`3.7.3+reconcile.20261015`, a distinct local-review build. The workflow already
discovers the actual wheel filename rather than a stale version pin. The wheel
includes the converter/parity modules its exporter imports. GUI runtime,
Python 3.10, other operating systems, fresh TunerPro parity and hardware safety
were not tested. No GitHub Actions were run and no release was published.

Next separate task: reconcile the CLI editor reciprocal-write branch and verify
its README, version and exporter pin together. Do not equate this exporter
review with validation of reciprocal writes or merge that branch here.
