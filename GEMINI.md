# ScarTools Architecture & Pipeline Guidelines

---

## ⚡ Category 1: Chat Directives & Voice Commands (`[CMD]`)

### `[CMD-01]` Codebase Cleanup Protocol ("cleanup" Directive)
Whenever the user instructs **"cleanup"**, the agent must strictly follow this protocol:
1. **Audit & Propose First**:
   - Scan the repository for obsolete/duplicate helpers, unused imports, dead legacy branches, stray test dumps, and redundant tokens.
   - **DO NOT delete or modify code immediately.** First present an itemized summary listing all files, blocks, and artifacts proposed for cleanup.
2. **Execute Upon Confirmation**:
   - Safely remove the approved dead code/files.
   - Run full unit tests (`python -m unittest discover -s tests -p "test_*.py"`) to verify zero breakage.
   - Re-build clean `.pyc` and `.zip` distribution packages.

### `[CMD-02]` Security & Anti-Tamper Audit Protocol ("check security" Directive)
Whenever the user instructs **"check security"**, the agent must perform a rigorous security audit:
1. **Attack Surface Assessment**:
   - Inspect client-side licensing checks (`scartools.licensing.is_activated()` monkey-patching and memory overrides in Maya).
   - Evaluate binary protection & reverse-engineering exposure (plain Python vs compiled `.pyc` vs native `.pyd`/C++ C-extensions).
   - Audit cryptographic signature verification (HMAC secret leakage vs asymmetric RSA/ECDSA public-key validation).
   - Check hardware fingerprinting robustness (motherboard UUID, CPU ID, and MAC spoofing resilience).
2. **Defensive Hardening Report**:
   - Deliver an itemized security report identifying all bypass vectors, severity ratings, and actionable hardening solutions.

### `[CMD-03]` Automated Testing Protocol ("run tests" Directive)
* Execute all 108+ headless unit tests in Maya's official Python interpreter (`mayapy.exe`).

### `[CMD-04]` Master Sync & Packaging Protocol ("sync share" / "package" Directive)
* Run `python sync_share.py` to test, compile `.pyc` bytecode, sanitize user documentation, and deploy to `Share/`.

### `[CMD-05]` Design System Showcase Protocol ("showcase" Directive)
* Launch `scartools.ui.show_showcase()` to preview all DCC widgets and studio themes in Maya.

---

## 🎨 Category 2: UI Design System Standards (`[UI]`)

### `[UI-01]` Window Base & Lifecycle
* Inherit from `BaseToolDialog(tool_id=self.TOOL_ID)` and register via `register_window()`.
* Apply `configure_root_layout(root)` and `configure_window(self, ...)`.
* Apply `apply_theme(self)` and `apply_window_icon(self)`.
* Guarantees proper Maya main-window parenting, singleton focus management, and automatic memory cleanup (`WA_DeleteOnClose`).

### `[UI-02]` Brand Header
* Use `create_brand_header(TITLE, subtitle, parent=self)` (standard Scar logo, `#292929` header frame, and typography).

### `[UI-03]` Section Panels & Department Accents
* Use `create_section_panel(title, accent=..., parent=self)` with standard department accents:
  * `pipeline` (`#4E937B` green)
  * `modeling` (`#5F7FA8` steel blue)
  * `rig` (`#766A8E` purple)
  * `texturing` (`#A67C45` gold/amber)
  * `data` (`#667A70` dark teal)
  * `validation` (`#5F7FA8` blue)

### `[UI-04]` Standard Grid Metrics & Alignment
* Standardize inputs, spinboxes, and combo boxes using `configure_field(widget, minimum_width=...)`.
* Use `FORM_LABEL_WIDTH` (65px) and `INLINE_SPACING` (12px) for consistent alignment.
* All dropdowns and spinboxes must rely exclusively on centralized tokens in `theme.py`. Never write inline stylesheet hacks.

### `[UI-05]` Centralized Selection Controls
* Never build custom button bars, raw unformatted sliders, or custom checkboxes.
* Use `create_segmented_control()` for mutually exclusive axes/modes (`[Local | World]`, `[X | Y | Z]`).
* Use `create_toggle_switch()` for binary options (`[ON / OFF]`).
* Use `create_labeled_slider()` for numerical tolerances with live numeric display and double-click default reset.
* Use `SearchableComboBox` for large searchable item lists.
* Use `MultiSelectComboBox` for multi-item checkbox dropdowns.

### `[UI-06]` Action Footer & Status Dot
* Use `create_action_footer(ACTION_TEXT, message=..., parent=self, include_log=False)` for the standard 220px primary blue action button (`#4F78B8`) and integrated `StatusDot` bar.

### `[UI-07]` Zero Inline Stylesheet Hacks
* Rely exclusively on centralized design tokens (`scartools.ui.tokens`) and theme stylesheet (`scartools.ui.theme`).

---

## ⚙️ Category 3: Backend & Maya Engine Standards (`[CORE]`)

### `[CORE-01]` Full DAG Long Paths
* Always use full DAG long paths (`cmds.ls(long=True)`) in backend operations to prevent name collision bugs.

### `[CORE-02]` 100% Headless Decoupling
* All backend operation logic in `operations.py`, `api/`, and `framework/` must run 100% headlessly in `mayapy.exe` without importing `PySide2`, `PySide6`, `QtWidgets`, or `maya.OpenMayaUI`.

### `[CORE-03]` Atomic Undo Transactions
* All scene-modifying actions must be wrapped inside a single atomic undo step using `SceneTransaction("OperationName")` for 1-step `Ctrl+Z` rollback.

### `[CORE-04]` Centralized Asset Snapshots
* Standardize snapshot export/import using `scartools.framework.snapshots` (`_next_version_directory`, JSON package manifests, and asset directory resolution).

### `[CORE-05]` Unified Studio Event Logging
* Route all operation logs through `scartools.framework.logging.emit_log` (levels: `INFO`, `SUCCESS`, `WARNING`, `ERROR`) so they display in the Global Log Viewer.

---

## 🔒 Category 4: Security, Licensing & Anti-Tamper Standards (`[SEC]`)

### `[SEC-01]` Cryptographic Node-Locking
* Hardware-locked (HWID) HMAC-SHA256 signature verification tied to CPU/motherboard hardware fingerprints.

### `[SEC-02]` Dynamic Session Token Traps (`LicenseSessionToken`)
* Maya operations and `SceneTransaction` require a dynamic `LicenseSessionToken` object bound to runtime entropy, defeating Python interpreter monkey-patching.

### `[SEC-03]` Two-Tier Fleet Enforcement (`Revoke` vs `Delete`)
* **Level 1 — Soft Lock (`Revoke`)**: Closes tool windows and locks menus while preserving local files on disk (`manage_licenses.py --revoke-user <user>`).
* **Level 2 — Hard Kill-Switch (`Delete / Purge`)**: Remotely triggers full uninstallation and **Zero-Fill Content Shredding** of all local tool files, modules, shelves, and licenses on the workstation (`manage_licenses.py --delete-user <user>`).

### `[SEC-04]` Zero-Fill Content Shredder (`execute_remote_wipe`)
* Strips Windows read-only permissions and zeroes out all `.py`, `.pyc`, `.json`, and `.mod` files with `0-byte` data before deletion, neutralizing NTFS file-permission locks.

### `[SEC-05]` Mandatory Online Heartbeat & Clock Protection
* Workstations must verify their lease online periodically. If an artist air-gaps or blocks Maya in Windows Firewall longer than the limit, the suite automatically locks down and self-shreds offline. Detects backward clock tampering.

### `[SEC-06]` Granular Expiration Durations
* Keys support flexible validity durations by minutes (`--minutes 30`), hours (`--hours 2`), days (`--days 30`), or duration strings (`--duration 45m`) with second-accurate timestamp validation.

---

## 📦 Category 5: Build, Packaging & Autonomous Deployment (`[DIST]`)

### `[DIST-01]` Development Boundary & Admin Isolation
* `admin_tools/` (key generators, license manager, admin guides), `tests/`, `GEMINI.md`, and build scripts are **Development & Admin ONLY** and must **NEVER** be packaged or shared to artists.
* The compiled release (`Share/`) ships 100% compiled bytecode (`.pyc`/`.pyd`) with raw `.py` sources stripped.

### `[DIST-02]` Autonomous Documentation Redaction (Permanent Default Rule)
* Executes automatically on every build. Build scripts strip all `<!-- ADMIN_ONLY_START -->` blocks from `ScarTools_Documentation.html` so public users and artists never see admin tools or security architecture.

### `[DIST-03]` Continuous Documentation & API Synchronization
* Whenever any new widget, tool, feature, or backend API is created or modified, all user manuals (`ScarTools_Documentation.html`, `README.md`, `CHANGELOG.md`, `RULES_DICTIONARY.md`) and module exports (`__all__`) must be immediately updated.

### `[DIST-04]` Continuous Automated Share Deployment (Autonomous Default Rule)
* Every time code changes, bug fixes, or new features are applied in `Dev/ScarTools_<version>`, the assistant **MUST autonomously run tests and compile the active release into `Share/ScarTools_<version>` and `Share/ScarTools_<version>.zip` without waiting for explicit user prompts**.
* **1-Click Master Command**: Running `python sync_share.py` discovers the active Dev version, executes `mayapy.exe` unit tests, compiles `.pyc` bytecode into `Share/`, sanitizes user documentation, and generates clean distribution zip packages in 1 step.

---

## 🏛️ Category 6: Centralized Framework Standards (`[FW]`)

### `[FW-01]` Central Tool Manifest Contract (`manifest.py`)
* Every tool package in `scartools.tools.<tool_id>` must declare a `manifest.py` exporting `TOOL_MANIFEST = ToolManifest(...)` specifying `tool_id`, `name`, `department`, `version`, `entry_point`, and registered headless `services`.
* Must be registered in `scartools.builtin.BUILTIN_TOOL_MODULES` and `BUILTIN_TOOL_MANIFESTS`.

### `[FW-02]` Decoupled Service Registry Bus (`services.py` & `imports.py`)
* All tool services must be registered as lazy entry points (e.g. `"scartools.tools.anim_io.operations:export_shot_package"`) and callable programmatically via `scartools.framework.SERVICES.call("dept.action", **kwargs)`. Heavy modules must not load on Maya startup.

### `[FW-03]` Unified Singleton Lifecycle (`lifecycle.py` & `WINDOWS`)
* Window instances must register via `register_window(tool_id, window_instance)`:
  * Only 1 active instance of each tool window may exist at any time.
  * Re-invoking an open tool raises and focuses the existing window without creating duplicate instances.
  * Closing a window automatically deregisters and deletes Qt allocations from memory (`WA_DeleteOnClose`).
  * `close_all_windows()` cleanly shuts down all active tool dialogs upon license deactivation or suite reload.

### `[FW-04]` Structured Preflight & Diagnostic QA Engine (`preflight.py` & `validation.py`)
* All model, rig, or scene validators must utilize `PreflightReport`, `PreflightIssue`, and `PreflightSeverity` (`INFO`, `WARNING`, `ERROR`, `CRITICAL`) with automatic viewport component selection.

### `[FW-05]` Centralized Version Reservation & JSON Manifests (`snapshots.py`)
* All department exports (skin weight packages, character SMD rigs, shot animation caches) must utilize `reserve_next_version()`, standardized JSON package manifests, and scene metadata lookup.

### `[FW-06]` Standardized Studio Event Bus (`logging.py`)
* All diagnostic and operation feedback must route through `emit_log(message, level="info"|"warning"|"error"|"success", source="ToolName")` to stream live to the studio Global Log Viewer and rotate in `~/.scartools/logs/`.

