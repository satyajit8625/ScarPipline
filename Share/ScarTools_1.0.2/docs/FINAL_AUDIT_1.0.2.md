# ScarTools 1.0.2 — Final Bug Fix and Optimization Audit

Date: 2026-09-09

## Fixed in this build

1. **Headless unit tests could not start**
   - Cause: tests under `tests/unit` imported `test_release` from `tests/maya`, which was not on their import path.
   - Fix: added a shared test shim at `tests/test_release.py`.
   - Result: all 17 pure-Python unit tests pass.

2. **Updater reported the wrong installed version**
   - Cause: `framework/updater.py` hard-coded `CURRENT_VERSION = "1.0.1"`.
   - Fix: the updater now imports the canonical value from `scartools.version`.
   - Result: version checks identify this build as 1.0.2.

3. **Updater could not be validated in headless/batch contexts**
   - Cause: it imported PySide/Qt classes that it never used.
   - Fix: removed the unused Qt dependency and made returned cache data defensive copies.
   - Result: updater tests pass without a Qt installation.

4. **Settings replacement was not fully atomic on Windows**
   - Cause: the old settings file was deleted before the temporary file was renamed.
   - Fix: use `os.replace` after flushing/syncing the temporary file, and clean up abandoned temporary files.
   - Result: a failure during replacement is much less likely to destroy the previous settings file.

5. **Stale 1.0.1 paths and labels remained in 1.0.2**
   - Fix: updated the installer docstring, README, audit heading, and local registry fallback to 1.0.2/canonical version data.

6. **Test isolation defect**
   - Cause: updater and non-Qt extension tests relied on other tests running first.
   - Fix: updater tests install their own stubs; Qt-only cases skip cleanly when Qt is unavailable.

7. **Release debris**
   - Fix: removed nested Git metadata and generated `__pycache__`/`.pyc` files from the repaired archive.

## Validation performed

- Python compilation: passed for all Python source files.
- Pure-Python unit suite: **17 passed**.
- Maya regression suite under available stubs: **85 passed, 20 correctly skipped**.
- Three Maya integration modules require Autodesk `mayapy`/Maya and could not run in this environment:
  - animation export settings
  - animation I/O scene integration
  - movable pivot scene integration

These three must be run in Maya 2023–2026 before studio release. The archive's statement that all Maya tests passed cannot be independently confirmed here.

## Highest-priority improvements still recommended

### P0 — Licensing architecture

- The client contains material used to generate/verify licenses. Any secret shipped in Python or a `.pyd` should be treated as recoverable by a determined attacker.
- Make the server the authority: use short-lived, server-signed leases and embed only a public verification key in the client.
- Separate entitlement/revocation from deletion. Remote zero-fill/wipe behavior is high risk and can destroy files after a registry, network, identity, or configuration mistake. Use safe disable/uninstall with explicit local confirmation and an audit trail.
- Do not ship `admin_tools`, the license registry, Git history, or key-generation utilities in artist builds.

### P1 — Release engineering

- Add a single deterministic packager that creates an artist build containing only runtime folders, installer, icons, documentation, and required launchers.
- Add CI gates for Python 3.9 syntax, unit tests, mayapy tests for each supported Maya version, archive-content allowlists, and secret scanning.
- Stop claiming a test count/pass result in documentation unless the current package generated that report automatically.

### P1 — Maintainability and defect isolation

- Split `skin/operations.py` (3,515 lines) by copy, mirror, import/export, cleanup, and validation while preserving public imports.
- Split `skin/ui/windows.py` (2,453 lines) into per-tool windows.
- Reduce eager imports in `scartools/__init__.py`; headless code currently loads Maya-facing menu/shelf modules.
- Move `PresetManager` out of the Qt workspace module so preset persistence can be tested independently.

### P2 — Performance and reliability

- Cache settings in memory and invalidate by file modification time instead of reading/parsing JSON on every getter.
- Serialize settings writes with a process/thread lock to prevent two Maya tools overwriting each other's updates.
- Replace silent broad exception handlers in critical export, licensing, transaction, and persistence paths with structured logs and typed failures.
- Add measured benchmarks for large skin operations and animation exports; do not use unverified speed multipliers in release notes.

### P2 — Package size

- The supplied tree was about 61 MB; the UI reference PDF alone is about 54 MB.
- Keep design-source PDFs in developer documentation, not the artist runtime package, unless artists need them.
- Excluding bytecode caches and nested Git metadata removes roughly 5 MB of avoidable debris from this source build.

## Required final Maya checks

1. Install by dragging `drag_drop_install.py` into Maya 2023, 2024, 2025, and 2026.
2. Open every department window and verify icons, theme, close/reopen, and shelf/menu cleanup.
3. Run `tests/run_maya_tests.py` with the target Maya version's `mayapy.exe`.
4. Test updater discovery from the real `Share` folder using both an older build and 1.0.2.
5. Test settings recovery by interrupting a write and confirming the previous JSON remains valid.
6. Test licensing against a staging server/registry before using production seats.
