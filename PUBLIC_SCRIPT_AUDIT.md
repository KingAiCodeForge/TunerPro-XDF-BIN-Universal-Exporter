# Public auxiliary script review — 20 October 2026

Scope: the 16 existing auxiliary Python/batch scripts below and one new shared helper were inspected individually in a fresh clone of the public exporter. Existing branch refs and original source remain identifiable in the preserved repository ref manifest/bundle. No dirty working copy or private repository was used as an import source.

This ledger concerns source-distributed tools. The core wheel contains the exporter, shared parser, native parity helper and BMW converter. Copying utility tests into an isolated test directory also requires copying their source utility modules and the new `public_collection_cli.py`; their tests do not establish that utilities are inside the core wheel.

## Per-script ledger

Every row is **inspected, changed, tested** unless specifically qualified below. Test names refer to the committed synthetic modules, with no customer definitions or firmware included.

| Script | Reviewed behavior and resulting change | Executed evidence / limit |
| --- | --- | --- |
| `_compare_xml_xdf_addresses.py` | Explicit `--xml` and repeated `--xdf OSID_SIZE=PATH` mappings; no fixed machine path; main guard. Uses the actual Z storage address and base-offset subtract flag; incomplete evidence fails. Reports overlap rather than semantic parity. | `test_portable_validators.py`: explicit mapping with spaces, missing evidence, Z ownership/base subtract and missing-argument cases. No native GUI equivalence established. |
| `_validate_xdf_bin.py` | Explicit XDF/BIN inputs, shared parser and bounded equation evaluation. Range/axis/zero diagnostics require readable complete data; empty ranges cannot establish zero. No automatic import-time scans. | Validator generated-pair/source preservation, bounded equation/no-empty-zero, missing-input tests. Signals are heuristic; no tune or ECU compatibility claim. |
| `_validate_zeros_and_keys.py` | Generic entry point for the explicit pair diagnostics/comparison above. Removed fixed private-layout sample paths, sample-specific address lists and direct `eval`. | Validator generated-pair and missing-argument tests. Historical sample-specific implementation remains in original Git history. Exact-name matches are comparison candidates only. |
| `check_axis_quality.py` | Explicit JSON file/directory input and main guard. Distinguishes missing, literal and finite numeric coordinates; does not equate monotonicity with mapping correctness. | Validator numeric/literal/missing axis test and import/missing-input tests. No native semantic validation. |
| `verify_bins.py` | Explicit read-only collection folders; import-safe CLI; read failures are errors. Embedded strings and filenames are explicitly heuristic signals. | Validator explicit-folder/read-error, missing-argument and import tests. Strings do not establish exact ECU identity. |
| `clean_and_dedup_bins.py` | Explicit source/destination. Default preview; `--apply` copies all originals into selected, duplicate-content or filename-review lanes. No deletion/move; complete SHA-256; source-relative identity preserved. | `test_portable_organizers.py`: preview/apply/rerun, duplicate and filename-review preservation, missing/inside-source destination, import safety. Filename review is not a license to discard files. |
| `organize_bins.py` | Explicit source/destination, default preview and copy-only `--apply`. Common deterministic copy-plan helpers, full hashes, exclusive destination creation and manifest; unknown files retained. Removed unsupported correct-XDF assertions. | Organizer existing-output preflight, duplicate-basename identity, source preservation, missing/inside-source destination and import tests. Not an atomic transaction; new partial outputs can remain after I/O failure. |
| `sort_tuning_db_to_bins.py` | Explicit source/destination and copy-only application. Deterministic normalized names preserve distinct variants and normalization collisions; no workstation roots. | Organizer normalization-variant, preview/apply/rerun, source preservation and missing-input tests. Classifier remains a documented filename heuristic. |
| `hash_dedup_dualmode.py` | Explicit source and one or more existing `--collection` folders (legacy `--ms42`/`--ms43` accepted only with explicit paths). Full SHA-256; read-only; optional exclusive report. Unknown names remain unclassified. | `test_portable_collection_tools.py`: full-hash/source-duplicate/no-copy/unknown-identity test; import safety. Content equality does not establish provenance or licensing. |
| `quick_scan.py` | Explicit read-only folders; stdout report by default, optional new `--output`; no machine map or import side effect. Clear missing-directory/error handling. | Collection-tool parameterized space-path/source preservation/report overwrite/missing-input test and import test. Reports suspected placements from string heuristics only. |
| `scan_bin_cal_ids.py` | Explicit folders and optional exclusive JSON report; deterministic hints; no fixed machine folder/output. No automatic scan or stdout reconfiguration during import. | Same collection-tool scan tests and import test. Filename/region strings are incomplete heuristic evidence. |
| `csv_json_input_batch_exporter.py` | Manifest-relative input/output paths, independent of cwd. CSV/TSV/JSON input validation fails on malformed rows, duplicate headers, excess fields, unsupported options or missing inputs. Whole-batch destination preflight protects every source and manifest; existing destinations refused. Success requires every requested writer to succeed. | Collection-tool unrelated-cwd/space-path export, repeated-report preservation, cross-job input/output collision, invalid row, malformed JSON and ambiguous CSV tests. Validation is not an atomic multi-file transaction; a later parse/write failure can leave earlier newly-created outputs. |
| `run_regression_suite.py` | Existing source-relative/env configuration inspected; added explicit `--guides-root` and `--repos-root`. Missing corpus remains `FAIL`; existing `--keep-output` directories refused before generated fixtures can overwrite content. Cleanup targets only the runner-created temporary subtree after path checks. | Collection-tool missing-corpus test verifies `PASSED: 0 FAILED: 1`; existing-output preservation test. Four generated regression cases also executed. Private MS42/MS43/MS45/VY corpus absent; no native parity/hardware qualification inferred. |
| `install.bat` | Python 3.10+; optional `KINGAI_PYTHON`; creates a new project `.venv`, refuses an existing environment and preserves pip error exits. No elevation, registry, user PATH, global package modification or generated absolute wrappers. GUI dependencies require explicit `--gui`; `--help` has no install side effects. | Windows launcher test from path containing spaces checks installer `--help` and no `.venv` creation. Installation itself not run by this focused launcher test; core clean-install evidence belongs in the release receipt. Network/package availability can still block installation. |
| `launch_cli.bat` | Uses explicit `KINGAI_PYTHON`, local `.venv` or PATH Python; version check, quoted script location, actual CLI `--help`, no pause and exit-code propagation. | Windows launcher test checks a script path containing spaces, argument forwarding and exit code 7. Core CLI checks recorded separately by release qualification. |
| `launch_gui.bat` | Same interpreter selection/version handling; clear missing PySide6 error; no automatic dependency installation; quoted source location and process exit propagation. | Windows launcher test checks missing explicit interpreter returns 1 clearly. GUI widgets were not driven by this utility suite; restored GUI worker safety tests belong to core qualification. |
| `public_collection_cli.py` (new) | Shared explicit-folder validation and optional exclusive UTF-8 report creation for source utilities; no private roots. | Collection-tool import safety and scanner/hash execution. Exclusive report creation refuses prior files; concurrent hostile directory replacement is outside the filesystem threat model. |

## Executed checks

Windows, Python 3.13, isolated qualification environment; `TEMP` and `TMP` were set to a task-local test directory and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.

```powershell
& '../qualification env/Scripts/python.exe' -m pytest test_portable_collection_tools.py test_portable_organizers.py test_portable_validators.py -q --basetemp='../utility final qualification'
```

Result: **44 passed** (20 collection/batch/runner/launcher, 11 organizer, 13 validator cases). Syntax compilation and `git diff --check` passed. These are synthetic source-tool tests, not missing real-corpus evidence.

```powershell
& '../qualification env/Scripts/python.exe' run_regression_suite.py --case Synthetic_Positive_Major_Stride --case Synthetic_Overlapping_Axis_Stride --case Synthetic_Native_Text_Limit_Warning --case Synthetic_Native_Axis_Semantics --keep-output '../utility runner synthetic artifacts'
```

Result: **4 generated cases passed**. This does not include the four unavailable real-definition corpus cases.

## Ignore/source audit

- `.gitignore`, default `.git/info/exclude`, tracked file status and `git ls-files --others --ignored --exclude-standard` were inspected. The fresh clone's local exclude file contains only Git's default commented examples.
- Ignored untracked files present during qualification were generated caches, build metadata and release package outputs. No ignored reusable source candidate was present to promote. No private/local original clone was swept or copied into the public tree.
- `batch_ms4x_manifest.csv` was already tracked despite its ignore pattern. Root integration replaced its workstation paths with a generic relative-path template; the revised batch parser tests verify those relative-path semantics. It contains no binary/XDF payload.
- Keep secrets, local configuration, customer/firmware inputs, private notes, generated outputs and caches excluded. No blanket unignore was performed. The new public audit/release documents live at the repository root so broad historical `docs/` exclusions do not hide them.
- Legacy sample-specific/destructive utility implementations remain identifiable in the preserved source refs. They were refactored in-place on this isolated integration branch; no original branch or historical artifact was deleted.

The original source variants, column-major prototype, packaged core review, branch integration provenance and final artifact hashes are covered by the separate release/provenance receipt. Nothing in this ledger qualifies ECU flashing or physical tuning.
