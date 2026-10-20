# Exporter 3.7.5rc1 public integration

This is an experimental, Python-based prerelease. It retains the precision engine from public main, restores omitted GUI output-preservation/CI repairs, fixes exact numeric declaration parsing and incomplete native-export verdicts, and refactors public utilities for explicit portable paths and source preservation. Editor 1.2.0rc1 is qualified against an exact exporter commit; its package metadata records that pin.

No native TunerPro, vehicle, controller, checksum/signature or flash-readiness qualification is claimed. Missing fixtures remain missing evidence. The wheel is platform-independent Python source, not a standalone executable.

## Preserved variants and feature matrix

Baseline main was `3cc8c64a9970a448fdb18711475b0f6b21e20050`. Its tree exactly matched the precision candidate `31851b52c12bb55cd3ee98d6093c66c74d1f943a`; PR #6 was squash-merged. Original public refs and per-ref source blob identities are recorded in [PUBLIC_SOURCE_MANIFEST.json](PUBLIC_SOURCE_MANIFEST.json). A complete original Git bundle is retained in the isolated task evidence. Every original remote branch remains available; none is deleted, reset, rebased or force-pushed.

| Original variant/tip | Content accounting and integration decision | Evidence |
| --- | --- | --- |
| Output preservation `c72e660` / PR #3 | Core safeguards already present and strengthened in main. Restore omitted GUI whole-plan preflight, checked writer results and shared CSV writer; restore checked single-wheel CI discovery. | Output, release-safety and headless GUI-worker tests |
| Category zero `ee9737b` / PR #4 | Main already retains uncategorized-zero voting correction, one-based sentinel and legacy direct-ID tie break; retains additional malformed-category tests. | `test_category_resolution.py` |
| Native verdict `b73899c` | Main retains empty-evidence refusal and stricter case-sensitive units. Also reject unreadable native body rows, overflowing numbers and imprecise hexadecimal display evidence. | Native parity, shape, unit, scientific precision and unreadable-row modules |
| Integrated review `4a73a13` | Output/native features accounted above; keep newer precision parser. | Full suite and source diff |
| Three-fix `aeae4d3` | Category/output/native work accounted. Its relaxed `0x04` no-op policy is superseded by the current stricter unsupported-storage refusal. | Unsupported flag and write-gate tests |
| Reciprocal inverse `ec1315b` | Main retains narrow K/X inverse and adds raw-zero refusal/signed-domain tests. No general nonlinear inverse is enabled. | Shared equation tests and editor contract suite |
| Release finalize `679d76e` | Retain main's newer diagnostics, completeness, precision and write gates; restore only omitted GUI/CI fixes. | Full source/wheel suites |
| Column-major `a0ee7e9` | Preserved historical prototype, excluded from runtime integration. It contains literal newline syntax corruption and incomplete field/flag plumbing; native layout evidence is absent. | Read audit; current unsupported layout refusal remains active |
| Local parser `cf4785d` | Already merged in main ancestry; current parser retained and exact numeric decoding repaired. | Storage/address/scoped-math suites |
| README `b4c5450` | Version wording already accounted by main; updated for explicit prerelease. | Documentation/code comparison |
| Precision `31851b5` | Exact baseline tree match; all main-only precision/diagnostic tests retained. | Tree comparison, full suite |

Main-only safeguards retained include scientific display quantum/ULP checks, zero default absolute tolerance, ragged matrix validation, blocked-input diagnostics, singleton-stride write gates, reciprocal raw-zero rejection, strict required links/axes, omitted-definition completeness, MIT metadata and console entry points. Earlier source trees were not copied wholesale over these changes.

## Script review and distribution scope

[PUBLIC_CORE_AUDIT.md](PUBLIC_CORE_AUDIT.md) records the nine core/GUI modules and each test module, including inspected portions and limits. [PUBLIC_SCRIPT_AUDIT.md](PUBLIC_SCRIPT_AUDIT.md) records each auxiliary script/launcher, tests, removed workstation defaults and historical behavior. Review does not mean every possible input or code path was proved correct.

The core wheel contains `tunerpro_exporter.py`, `tunerpro_native_export_parity.py`, `bmw_0pa_0da_to_bin.py` and every `tunerpro_xdf` module. The source distribution/portable source ZIP additionally includes the GUI, cleaned auxiliary tools, Windows launchers, tests and public ledgers. GUI dependencies are optional; no interactive GUI qualification was performed. Its worker now always invokes normal input validation, preflights all outputs and checks writer results; folder opening follows its checkbox.

Organizers default to preview and copy on explicit `--apply`; sources and distinct variants are retained. Batch paths resolve beside the selected manifest and all job destinations are checked before writes. The tracked manifest was sanitized to a relative-path template. Reusable validators use the shared bounded parser instead of evaluating XDF text as Python. No private repository source, firmware or proprietary definition was imported.

Ignore rules and local excludes were inspected. This fresh public clone had no ignored reusable source candidate; generated caches/build outputs remained excluded. Case-insensitive BIN/XDF and secret/local-configuration rules remain; only the sanitized tracked template is explicitly allowed. No blanket unignore occurred.

## Reproducible qualification

Use Python 3.10+ in a new environment with `setuptools>=77`, `build` and `pytest>=8,<10`. Set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, clear unrelated `PYTHONPATH`, and use a writable temporary directory.

```console
python -m pytest -p no:cacheprovider -q -ra --basetemp="../source test temp"
python -m build --no-isolation
python -m pip install --no-index dist/kingai_tunerpro_xdf-3.7.5rc1-py3-none-any.whl
```

For installed validation, copy the public tests and source-only utility/GUI/launcher files into a separate directory with spaces. Do not copy the three core runtime modules or `tunerpro_xdf` there. From that directory:

```console
python -I -m pytest --import-mode=importlib -p no:cacheprovider -q -ra --basetemp="../installed test temp"
tunerpro-xdf-export --help
tunerpro-native-parity --help
python -m pip check
```

Windows Python 3.13 final source suite: **709 passed, 4 skipped, 18 subtests passed**. The four unavailable fixtures are the exact SP-Daten single/pair inputs, MS42 native TunerPro export and legacy MS41 definition. The source-tool runner also executed four generated corpus cases successfully. Native/real corpus files were not invented or copied into the public tree.

Ubuntu 24.04 under WSL, Python 3.12 final source suite: **708 passed, 5 skipped, 18 subtests passed**. The additional skip is the Windows batch-launcher check. Linux used the task's pure-Python test dependencies explicitly; no system package or Docker daemon was changed.

Final installed-wheel, portable source, Linux execution, exact source commit, artifact SHA-256 and hosted-check observations are recorded in the release's verification receipt. Hosted GitHub Actions billing/runner failures before checkout are infrastructure failures, not passing test evidence. The configured Windows/Linux Python 3.10/3.13 hosted matrix is distinct from local results and must not be described as passing unless its actual steps complete.

Stable release remains blocked on permissioned replay of the known MS42 linked-axis, MS43 duplicate-ID, MS45 virtual/Z-less and VY malformed-equation cases, independent native comparisons and the remaining platform matrix. These are software qualification limits; no hardware operation is part of this release.
