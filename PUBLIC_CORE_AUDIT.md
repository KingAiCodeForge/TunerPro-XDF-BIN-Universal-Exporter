# Public core and test review ledger

Review date: 20 October 2026. Release candidate: `3.7.5rc1`.

This records code inspection and the boundaries of the public integration. It is
not an exhaustive correctness proof, a native TunerPro certification, or ECU,
checksum, signature, tuning or flashing qualification. Exact final platform,
source/wheel test counts and artifact hashes belong in `PUBLIC_RELEASE.md` and
`PUBLIC_SOURCE_MANIFEST.json`; this ledger does not turn optional skips into
passes. Only public repository source and generated test inputs were used for
the integration. No private fixture was imported or made public.

## Runtime files

Every file below was inspected as actual code. The inspection covered the
listed paths; it was not limited to PR descriptions or filenames. All nine are
syntactically valid. No `eval`, `exec`, `compile`, or dynamic-import call sites
were found in these runtime modules. The equation implementation interprets a
bounded, allowed AST rather than executing equation text.

| File | Inspection and integration status | Test evidence / limits |
|---|---|---|
| `tunerpro_exporter.py` | Inspected input dispatch, XML/legacy normalization, numeric storage, linked variables and axes, scoped equations, diagnostics, output guards and CLI. Changed explicit integer parsing so accepted decimal/hex metadata reaches readers unchanged; malformed declarations fail instead of using defaults. Existing omitted-metadata defaults remain. | Synthetic tests exercise actual values, paths, errors and preserved input bytes. Rendering/export formatting loops were sampled, not exhaustively checked for every label/layout. Native mappings and resource-exhaustion fuzzing remain unqualified. |
| `tunerpro_native_export_parity.py` | Entire module inspected: native scalar/fixed-width table parsing, display precision, shape/orientation, units, JSON validation, report writers and CLI. Changed unreadable-row accounting, oversized numeric handling and hexadecimal precision refusal. A malformed row cannot disappear into the demonstrated smaller-subset PASS. | Generated parity API/CLI tests cover the reported defects. Real native capture replay and every ambiguous fixed-width interpretation remain unqualified. JSON/CSV publication is not an atomic pair transaction. |
| `bmw_0pa_0da_to_bin.py` | Inspected headers, Intel HEX grammar/checksums, source spaces, address maps, overlapping bytes, single conversion, combination, scanning and CLI. Changed writes to exclusive binary creation, scan configuration to explicit roots, missing-input errors, fill forwarding and refusal of `--info --combine`. | Synthetic HEX/mapping/collision/output tests. Controller identity/profile selection still includes heuristics. BMW directive checks, controller checksums/signatures, programming and recovery behavior are not established. |
| `exporter_gui.py` | Inspected worker, input/format selection, paths/settings, recent files, validation, result handling and folder opening. Changed whole-output preflight, core CSV use, error results and portable defaults. Removed the bypass control and stale feature descriptions; legacy worker argument still validates. Completion obeys the folder checkbox. | Worker logic is exercised with generated data and Qt stand-ins. No interactive Qt window, drag/drop, native file dialog, accessibility or visual layout qualification was performed. Styling and rendering were sampled. Source-only GUI, outside the wheel. |
| `tunerpro_xdf/__init__.py` | Entire file inspected; package documentation only. Retained. | Import/package presence; no runtime algorithm. |
| `tunerpro_xdf/output_safety.py` | Entire file inspected: normalized/resolved paths, file identity, symlinks, duplicate outputs, existing destinations and exclusive creation. Retained strengthened implementation. | Synthetic input/output aliases, creation races and link tests. Link availability is platform dependent. Directory replacement races and multi-file rollback are outside this helper's contract. |
| `tunerpro_xdf/xdf_addressing.py` | Entire file inspected: widths, bounds, positive strides, address spans and independent write admission. Retained singleton-stride safeguard. | Exact-offset and small-layout footprint assertions. Non-contiguous reads do not establish native semantics; negative strides and column-major interpretation remain held. |
| `tunerpro_xdf/xdf_equations.py` | Entire file inspected: token/AST/depth/size limits, numeric protocols, lazy conditionals, bounded arithmetic and affine/reciprocal inverses. Retained stricter raw-zero rejection. | Generated accepted/rejected expressions and round trips, including signed reciprocal ranges. Unsupported syntax and general nonlinear inverse remain outside the contract. |
| `tunerpro_xdf/xdf_values.py` | Entire file inspected: integer/float widths, endian/sign handling, bounds and integer writes. Retained. | Exercised by addressing, float, release-safety and editor compatibility tests. Numeric decoding alone does not establish the physical meaning of an ECU value. |

The historical column-major branch remains identifiable at its original ref.
Its literal newline syntax defect, missing model field/plumbing and unproven
flag interpretation were not promoted into runtime. Older variants were not
used to replace newer precision, completeness, diagnostics or write gates.

## Test-module inspection

All 35 `test_*.py` modules were inspected through their fixture construction,
test bodies/assertions and skip conditions. The parity modules also received a
separate complete review. This is a review inventory, not a claim that every
possible input is tested or that an optional real-fixture case executed.
Generated XDF/BIN/HEX/native-text files are created in temporary directories;
they are not redistributed real firmware or definition files. Historical
comments describing earlier corpus observations are provenance context, not
freshly executed evidence.

| Test module | Fixture/assertion subjects | Evidence boundary |
|---|---|---|
| `test_address_type_var.py` | Generated BIN/XDF config bytes; address-backed VAR selects the correct branch; out-of-bounds source raises. | No external corpus loaded; default byte-width behavior only for modeled cases. |
| `test_addressing_and_scoped_math.py` | Exact positive-stride offsets/spans, read/write separation, explicit index base, scoped precedence and duplicate/invalid selectors. | In-memory layouts/XML; no native storage witness. |
| `test_axis_coordinate_evidence.py` | Prose versus numeric coordinates, missing/nonfinite labels, embedded/linked sources, JSON evidence and axis flips without source mutation. | Generated XML/BIN; display labels are not physical breakpoint proof. |
| `test_binary_size_validation.py` | Common image sizes and arbitrary-size warning classification. | Tests a size helper; does not identify controllers or matching definitions. |
| `test_blocked_diagnostics.py` | Failed/missing inputs produce INCOMPLETE identity evidence, no subset grade; report preservation, handler cleanup and write errors. | Generated malformed definitions; hashes identify test bytes only. |
| `test_bmw_0pa_0da_to_bin.py` | Strict HEX grammar/checksums/EOF, source conflicts, explicit MS45 spaces, loss accounting and defined-byte-only combination. | Synthetic cases plus **two optional real SP-Daten cases** under `KINGAI_SPDATEN_ROOT`; absent inputs skip and do not qualify the real cases. |
| `test_category_resolution.py` | Direct/one-based category IDs, zero sentinels, tie behavior and malformed category data. | Generated XML; mixed conventions retain the documented heuristic/tie policy. |
| `test_converter_output_preservation.py` | Repeated/hash-fallback conversion preserves existing output; explicit scans, missing paths, incompatible info/combine and fill forwarding. | Added generated CLI/API regressions; no real conversion corpus. |
| `test_declared_raw_variable_aliases.py` | Declared raw aliases, absent aliases, address/link sources, per-cell scope and authoritative context. | Generated scalar/table bytes; no implicit-variable inference. |
| `test_diagnostics_zero_tables.py` | Zero/raw/uniform patterns are contextual observations; missing neighbors do not refute; reports omit workstation directory names. | Generated bytes; historical bucket names/comments do not prove feature absence or write history. |
| `test_float_cells_and_literal_labels.py` | Float/endian/width flags, interleaved strides, literal labels, linked/per-row math and dangling links. | Generated cases plus **one optional MS42 definition/native-text case** under `KINGAI_MS42_FIXTURE_ROOT`; absence is missing native evidence. |
| `test_gui_worker_preservation.py` | Whole-plan worker collision refusal, CSV failure propagation and legacy skip argument still validating. | Added test extracts trusted repository worker code with AST and executes it with Qt stand-ins; not an interactive GUI test. |
| `test_legacy_xdf_support.py` | Generated TunerPro 1.11 normalization, table/axis/scalar/flag values and dispatch. | **One optional real MS41 definition case** under `KINGAI_BMW_DEFINITION_ROOT`; synthetic BINs/counts do not establish real calibration meaning. |
| `test_multibit_flag_state.py` | All masked bits required; zero mask does not report Set. | Small pure-function cases. |
| `test_native_binary_xdf_detection.py` | Generated protected-container magic refuses XML fallback with an explicit unsupported error; plain XML control. | Does not decrypt or bypass protected XDFs. |
| `test_native_parity_cli_precision.py` | Subprocess CLI scientific precision/defaults/overrides, exit codes, JSON/CSV and preserved input bytes. | Generated scalar cases. |
| `test_native_parity_matrix_shape.py` | Ragged/unequal/missing cells fail; rectangular matrix control. | Direct matrix API; no native text parsing. |
| `test_native_parity_scientific_display_precision.py` | Exponent-adjusted quantum, ULP/subnormal/finite limits, tolerances and boundary comparisons. | Numerical unit tests; no native capture replay. |
| `test_native_parity_shape.py` | Malformed JSON data/axes/numbers and bounded CLI refusal without output. | Small generated table. |
| `test_native_parity_unit_verdicts.py` | Case-sensitive units, whitespace/aliases/missing declarations, orientation, missing evidence, CSV/report fields and alias/existing-output protection. | Generated comparisons/CLI files; optional hardlink skip is filesystem capability, not corpus evidence. |
| `test_native_parity_unreadable_rows.py` | Unreadable/truncated native body cannot vanish; smaller subset fails; oversized/imprecise decimal/hex inputs fail without success reports. | Added generated text/JSON cases; general fixed-width interpretation is still unproven. |
| `test_native_parity_verdict.py` | Empty/unrecognized INCONCLUSIVE; matches/mismatches; missing objects/units; malformed scalar, CSV and tolerance behavior. | Mostly direct generated comparison objects. |
| `test_omitted_definition_completeness.py` | Generated virtual/Z-less views remain named in INCOMPLETE diagnostics; API/CLI refuses silent subset export; addressed control works. | No implementation or validation of unsupported virtual views. |
| `test_output_preservation.py` | Every export format preserves inputs/existing files; exclusive creation, hard/symlinks, all-format/sidecar plan, diagnostics and parity report safety. | Generated files; symlink creation may skip when unavailable. No hostile-directory-race or transactional guarantee. |
| `test_output_safety.py` | Relative aliases, complete-plan refusal, duplicate outputs, hard/symlink identity and export refusal. | Generated files; link cases may skip for filesystem restrictions. |
| `test_portable_collection_tools.py` | Import side effects, explicit scanning/report preservation, full hashes, manifest-relative batches/cross-job collisions, malformed manifests and missing regression corpus. | Added generated subprocess cases. Windows batch launcher forwarding/help/missing interpreter case is Windows-only; it skips on Linux. |
| `test_portable_organizers.py` | Preview/apply, copy hashes, source preservation, output preflight, relative-name variants and normalization collisions. | Added generated collection trees; classifier labels remain heuristics; I/O publication is not transactional. |
| `test_portable_validators.py` | Explicit arguments/missing inputs, no import side effects, paths with spaces, source preservation, safe equations, unresolved coordinates and XML/XDF address ownership. | Added generated pairs/reports; no real-definition correctness claim. |
| `test_release_safety.py` | Malformed storage/base offsets, defaults, duplicate/unassigned IDs, scoped math, required axes, unsafe outputs, CLI errors and patch status completeness. | Generated fixtures; optional hardlink skip reflects filesystem capability. Broad cases are not exhaustive parser fuzzing. |
| `test_scalar_export_errors.py` | Malformed equation returns explicit error; omitted equation versus explicit blank MATH remains distinguishable. | Direct helper tests, not full native conversion evidence. |
| `test_shared_xdf_addressing.py` | Width-dependent packed offsets/spans, explicit positive-stride reads, held writes and BASEOFFSET arithmetic. | Generated layouts; no controller/native proof. |
| `test_shared_xdf_equations.py` | Allowed operations, lazy branches, domain/protocol/resource failures, exact affine/reciprocal inverses and absence of code execution. | Generated numerical/XML cases; version assertion compares source metadata or installed package metadata, not a hardcoded historical version. |
| `test_singleton_stride_write_gate.py` | Singleton stride refusal; packed controls; enumeration checks every admitted small layout has contiguous cell footprint. | Bounded small-layout enumeration, not all integer dimensions. |
| `test_storage_numeric_precision.py` | Exact hex address/width/sign/endian reads, strided cells/axis labels, masks, malformed declarations, preserved inputs/defaults and unknown-flag refusal. | Added generated parser/value regressions; no native format qualification. |
| `test_tunerpro_native_export_parity.py` | Decimal/HEX scalar parse and retention of literal-label table rows/breakpoints. | Synthetic strings patterned after native layout, not an actual GUI execution. |

Exactly four test cases in this inventory depend on optional external real
fixtures: two BMW SP-Daten cases, one MS42 native-text case and one MS41
definition case. They are not supplied by this public release. Link-capability
skips and the Linux skip of Windows launchers are separate platform limitations.
Tests that deliberately inspect/compile trusted repository source (the GUI
worker harness and equation-source guard) do not authorize execution of input
equation or manifest text.

## Package, licence and workflow scope

- `LICENSE` and package metadata declare MIT for this project's code. No third
  party BIN/XDF/native executable or private report is needed for the generated
  suite. This review does not grant redistribution rights to external inputs.
- The wheel includes the exporter, native-parity and BMW converter modules plus
  `tunerpro_xdf`. It does not install the GUI, source-only utilities or PySide6.
  Source-distribution/portable contents are recorded separately; utilities used
  alongside installed-wheel tests must not shadow the three installed modules.
- `MANIFEST.in` retains test modules and listed public source utilities.
  `pyproject.toml` declares Python 3.10+ and a pytest test extra. Supported-version
  metadata is not evidence that every interpreter/OS was executed.
- `.github/workflows/exporter-tests.yml` now runs source tests, builds and checks
  for exactly one wheel, then runs copied tests away from core source. Its
  Ubuntu/Windows Python 3.10/3.13 matrix must be reported from actual run results;
  reviewing the workflow is not a passing hosted run.
- No reviewed core file is marked completely unreviewed. Material partial
  areas remain exporter formatting combinations, GUI interaction/visual layout,
  exhaustive malformed-input/resource testing and unavailable real/native
  corpus cases. Those limits remain visible for this experimental release.
