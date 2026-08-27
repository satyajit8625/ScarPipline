# 📖 ScarTools Pipeline & Architecture Rules Dictionary

A standardized, unambiguous reference catalog of all development rules, architectural standards, security protocols, and CLI directives across the **ScarTools** ecosystem.

---

## ⚡ Category 1: Chat Directives & Voice Commands (`[CMD]`)

| Rule ID | Directive (What You Type) | Protocol & Execution | Expected Output |
| :--- | :--- | :--- | :--- |
| **`[CMD-01]`** | **`cleanup`** | Scans repo for obsolete helpers, dead code, stray test dumps, and unused imports. **Audits & proposes first**; waits for user confirmation before deleting. | Pristine codebase, 100% test pass, updated builds. |
| **`[CMD-02]`** | **`check security`** | Performs a full 360° audit of licensing bypasses, memory monkey-patching, decompilation risks, and hardware spoofing. | Itemized Threat Report + Hardening Architecture. |
| **`[CMD-03]`** | **`run tests`** | Executes all 108+ headless unit tests in Maya's official Python interpreter (`mayapy.exe`). | Real-time test results and regression verification. |
| **`[CMD-04]`** | **`sync share`** / **`package`** | Runs `sync_share.py`: tests, compiles `.pyc` bytecode, sanitizes user docs, and updates `Share/` and `.zip`. | Production-ready shareable release packages. |
| **`[CMD-05]`** | **`showcase`** | Launches the live interactive Maya UI Design System Showcase window. | Live interactive gallery of all DCC widgets & themes. |

---

## 🎨 Category 2: UI Design System & Window Architecture (`[UI]`)

### `[UI-01]` Window Lifecycle & Base Dialog
* **Rule**: Every window **must** inherit from `BaseToolDialog(tool_id=self.TOOL_ID)` and register via `register_window()`.
* **Standard Pattern**:
  ```python
  from scartools.ui import BaseToolDialog, configure_window, configure_root_layout, apply_theme

  class MyToolDialog(BaseToolDialog):
      TOOL_ID = "my_tool"
      def __init__(self, parent=None):
          super(MyToolDialog, self).__init__(parent, tool_id=self.TOOL_ID)
          configure_window(self, (520, 480), (700, 650))
          root = QtWidgets.QVBoxLayout(self)
          configure_root_layout(root)
          apply_theme(self)
  ```
* **Guarantees**: Maya main-window parenting, singleton focus management, and automatic memory cleanup (`WA_DeleteOnClose`).

### `[UI-02]` Standard Brand Header
* **Rule**: Use `create_brand_header(TITLE, subtitle, parent=self)`. Never create custom title bars or unbranded frames.

### `[UI-03]` Section Panels & Department Color Accents
* **Rule**: Use `create_section_panel(title, accent=..., parent=self)`.
* **Standard Department Accents**:
  * `pipeline` $\rightarrow$ `#4E937B` (Teal Green)
  * `modeling` $\rightarrow$ `#5F7FA8` (Steel Blue)
  * `rig` $\rightarrow$ `#766A8E` (Studio Purple)
  * `texturing` $\rightarrow$ `#A67C45` (Gold / Amber)
  * `data` $\rightarrow$ `#667A70` (Dark Teal)
  * `validation` $\rightarrow$ `#5F7FA8` (Blue)

### `[UI-04]` Standard Grid Metrics & Alignment
* **Rule**: Standardize inputs, spinboxes, and combo boxes using `configure_field(widget, minimum_width=...)`.
* **Standard Metric Tokens**:
  * `FORM_LABEL_WIDTH` = **65px**
  * `INLINE_SPACING` = **12px**
  * `FIELD_HEIGHT` = **30px**
  * `PRIMARY_BUTTON_WIDTH` = **220px**

### `[UI-05]` Centralized DCC Selection Controls
* **Rule**: Never build custom button bars or raw sliders. Always reuse centralized widget helpers:
  * `create_segmented_control(["Local", "World"])` $\rightarrow$ Pill segmented buttons.
  * `create_toggle_switch("Normalize", checked=True)` $\rightarrow$ Binary iOS/Studio toggle switch.
  * `create_labeled_slider("Tolerance", min=0.0, max=1.0)` $\rightarrow$ Slider with numeric live display & double-click reset.
  * `create_vector3_input(0.0, 0.0, 0.0)` $\rightarrow$ 3-Axis coordinate pad (X/Y/Z color badges).
  * `create_path_picker(placeholder=...)` $\rightarrow$ File/Directory browser with drag-and-drop.
  * `create_uv_tile_grid(u=10, v=4)` $\rightarrow$ $10 \times 10$ interactive matrix for UDIMs.
  * `create_curve_editor()` $\rightarrow$ 2D Bézier curve graph for falloffs.
  * `create_palette_grid()` $\rightarrow$ 16-color studio swatch picker.
  * `create_token_input()` $\rightarrow$ Dynamic tag chip input (`#hero`, `#lod0`).
  * `create_step_wizard(["Select", "Fix", "Export"])` $\rightarrow$ Visual pipeline stage tracker.
  * `create_preset_bar(tool_id)` $\rightarrow$ Save/Load JSON preset toolbar.

### `[UI-06]` Action Footer & Status Dot
* **Rule**: Every dialog must finish with `create_action_footer(ACTION_TEXT, message=..., parent=self)`.

### `[UI-07]` Zero Inline Stylesheet Hacks
* **Rule**: Never write `widget.setStyleSheet("...")` with custom hardcoded colors. All colors, borders, and margins must reside centrally in `scartools.ui.tokens` and `scartools.ui.theme`.

---

## ⚙️ Category 3: Backend & Maya Engine Standards (`[CORE]`)

### `[CORE-01]` Full DAG Long Paths
* **Rule**: Always use `cmds.ls(long=True)` in backend operations to prevent name collision bugs across deep hierarchies.

### `[CORE-02]` 100% Headless Decoupling
* **Rule**: All backend logic in `operations.py`, `api/`, and `framework/` must run 100% headlessly in `mayapy.exe` without importing `PySide2`, `PySide6`, `QtWidgets`, or `maya.OpenMayaUI`.

### `[CORE-03]` Atomic Undo Transactions
* **Rule**: All scene modifications must be wrapped inside a single atomic undo transaction for 1-step `Ctrl+Z` rollback:
  ```python
  from scartools.framework.transactions import SceneTransaction

  with SceneTransaction("Batch Rename Nodes"):
      # Maya modifications here
  ```

### `[CORE-04]` Centralized Asset Snapshots
* **Rule**: Standardize snapshot export/import using `scartools.framework.snapshots` (`_next_version_directory`, JSON package manifests, and asset directory resolution).

### `[CORE-05]` Unified Studio Event Logging
* **Rule**: Route all logs through `scartools.framework.logging.emit_log(message, level="info"|"warning"|"error"|"success", source="ToolName")` to feed the centralized Global Log Viewer.

---

## 🔒 Category 4: Security, Licensing & Anti-Tamper Standards (`[SEC]`)

### `[SEC-01]` Cryptographic Node-Locking
* **Rule**: Every key is cryptographically signed using HMAC-SHA256 tied to physical hardware (`HWID` calculated from CPU UUID, motherboard GUID, and volume serial).

### `[SEC-02]` Dynamic Session Token Traps (`LicenseSessionToken`)
* **Rule**: Maya operations and `SceneTransaction` require a dynamic `LicenseSessionToken` object bound to runtime entropy. Boolean monkey-patching (`require_license = lambda: True`) fails validation and prevents scene mutations.

### `[SEC-03]` Two-Tier Fleet Enforcement (`Revoke` vs `Delete`)
* **Level 1 — Soft Lock (`Revoke`)**: `python manage_licenses.py --revoke-user <user>` deactivates the license token, closes windows, and locks menus while preserving local files.
* **Level 2 — Hard Kill-Switch (`Delete / Purge`)**: `python manage_licenses.py --delete-user <user>` remotely uninstalls and triggers **Zero-Fill Content Shredding** across all local tool files, modules, shelves, and licenses on the workstation.

### `[SEC-04]` Zero-Fill Content Shredder (`execute_remote_wipe`)
* **Rule**: Strips Windows read-only permissions and overwrites all `.py`, `.pyc`, `.json`, and `.mod` files with `0-byte` data before deletion, neutralizing any local NTFS permission locks.

### `[SEC-05]` Mandatory Online Heartbeat & Clock Protection
* **Heartbeat & Anti-Airgap Defense**: Workstations must verify their lease online periodically. If an artist air-gaps or blocks Maya in Windows Firewall longer than the heartbeat limit, the suite automatically locks down and self-shreds offline.
* **Anti-Clock Rollback**: Verifies system time against both activation and last-verified online timestamps to detect backdated system clocks.

### `[SEC-06]` Granular Expiration Durations
* **Rule**: Keys support flexible validity durations by minutes (`--minutes 30`), hours (`--hours 2`), days (`--days 30`), or duration strings (`--duration 45m`) with second-accurate timestamp validation.

---

## 📦 Category 5: Build, Packaging & Autonomous Deployment (`[DIST]`)

### `[DIST-01]` Strict Development Boundary & Admin Isolation
* **Rule**: `admin_tools/` (key generators, license manager, admin guides), `tests/`, `GEMINI.md`, and build scripts are **Development & Admin ONLY** and must **NEVER** be packaged or shared to artists.
* **Bytecode Compilation**: The compiled release (`Share/`) ships 100% compiled bytecode (`.pyc`/`.pyd`) with raw `.py` sources stripped.

### `[DIST-02]` Autonomous Documentation Redaction
* **Rule**: Executes automatically on every build. Build scripts strip all `<!-- ADMIN_ONLY_START -->` blocks from `ScarTools_Documentation.html` so public users and artists never see admin tools or security architecture.

### `[DIST-03]` Continuous Documentation & API Synchronization
* **Rule**: Whenever any tool, widget, or API is created or modified, all user manuals (`ScarTools_Documentation.html`, `README.md`, `CHANGELOG.md`, `RULES_DICTIONARY.md`) and module exports (`__all__`) must be immediately synchronized.

### `[DIST-04]` Continuous Automated Share Deployment (Autonomous Default Rule)
* **Rule**: Every time code changes or new features are applied in `Dev/ScarTools_<version>`, the assistant **must autonomously run tests and compile the active release into `Share/ScarTools_<version>` and `Share/ScarTools_<version>.zip` without waiting for explicit user prompts**.
* **1-Click Master Command**: Running `python sync_share.py` executes Maya unit tests, compiles `.pyc` bytecode, sanitizes documentation, and updates `.zip` distribution packages in 1 step.
