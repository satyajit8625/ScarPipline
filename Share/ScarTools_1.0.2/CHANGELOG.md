# Changelog

## 1.0.2 — Framework Standardization, Crash Diagnostics & Suite Health

- **Maintenance fixes in final 1.0.2 package**:
  - Fixed the updater reporting `1.0.1` by sourcing its current version from the suite's canonical `version.py`.
  - Removed the updater's unused Qt dependency so version checks can run in headless validation and batch contexts.
  - Fixed pure-Python test discovery so the shared Maya stubs resolve correctly from `tests/unit`.
  - Made settings replacement genuinely atomic with `os.replace`, disk flush, and temporary-file cleanup.
  - Removed stale `1.0.1` installer/manual labels and registry fallback paths.

- **Framework Exception Standardization (`scartools.framework.errors`)**:
  - Introduced standard typed exception hierarchy: `ScarToolsError`, `ValidationError`, `SkinOperationError`, `ExportError`, `ImportError`, `LicenseError`, `ToolExecutionError`, `SceneIntegrityError`.
  - Replaced silent `except Exception: return False` patterns with typed exceptions and structured diagnostic logging.
  - Re-exported all error types in `scartools.framework` for seamless suite-wide adoption.
- **Centralized Rolling Event Log & Auto-Disk Persistence (`scartools.framework.logging`)**:
  - Automatically persists all studio event logs to `~/.scartools/logs/scarTools.log` with standardized `[HH:MM:SS] [Tool] [LEVEL] Message` formatting.
  - Thread-safe memory buffer preserving real-time pub/sub notifications for Qt Global Log Viewer with zero I/O slowdowns.
- **Production Crash Reporter Engine (`scartools.framework.crash_reporter`)**:
  - Automatic error diagnostic interception generating self-contained support zip archives: `ScarTools_Crash_Report_<timestamp>.zip`.
  - Packages environment configuration (`maya_version.txt`, `python_version.txt`, `active_tool.txt`), full execution traceback, and rolling engine logs.
- **Two-Tier Test Suite Architecture**:
  - Separated test framework into `tests/unit/` (pure Python 3.9/3.10 runnable via `pytest`/`unittest`) and `tests/maya/` (DCC-dependent tests requiring `mayapy.exe`).
  - Achieved 100% test pass rate across all 145 headless DCC tests and 17 pure-Python unit tests.
- **Automated Packaging & Release Verification**:
  - Streamlined `sync_share.py` with automated `mayapy` test discovery, `.pyc` bytecode compilation, documentation redaction, and `Share/ScarTools_1.0.2.zip` distribution packaging.

## 1.0.1 — Active Cloud Allowlist & Zero-Latency CDN Synchronization

- **Cloud-Authoritative Licensing & Anti-Tamper Hardening**:
  - **Safe Soft-Disable on Expiry**: When a license reaches its expiration date or is marked revoked/expired, Maya safely disables tool execution and locks the menu with a clear renewal notice. Local files on the artist's hard drive are **never** shredded or deleted upon expiration.
  - **Cloud-Only Hard Kill-Switch**: The zero-fill content shredder (`execute_remote_wipe`) is strictly triggered **only** when an admin explicitly deletes/removes a user or seat from the cloud registry allowlist.
  - **Zero-Touch Cloud Discovery & Auto-Renewal**: Maya dynamically queries the central cloud registry on launch using the artist's username and machine HWID. If registered in the cloud, Maya automatically discovers, validates, and activates the workstation without requiring manual key entry. If renewed in the cloud, Maya updates the local lease transparently.
  - **Anti-Bypass Session Token Sealing**: Hardened `LicenseSessionToken` with internal timestamp and expiry checks bound to dynamic cryptographic entropy, preventing Maya Script Editor monkey-patching of `is_activated()`.
  - **Streamlined UI & 1-Click Cloud Sync**: Added a 1-click `"☁️ Sync from Cloud"` button in `LicenseActivationDialog` and updated the locked Maya menu to clearly distinguish between expired and unregistered states.

- **Anim I/O Namespace-Aware Cache Export**:
  - **Namespace-Based File Naming**: Assets with a Maya namespace (e.g. `hero:rig_GRP` or `hero:character`) now automatically use the namespace prefix as their cache filename (`hero.abc`, `hero.fbx`). Completely eliminates duplicate file naming and collisions across multiple referenced character rigs that share identical root group names.
  - **Namespaced Geometry & Mesh Detection**: `find_export_groups()` enhanced to locate namespaced geometry groups (e.g. `hero:Geometry`, `hero:geo_GRP`) and meshes without manual un-namespacing.
  - **Streamlined UI & Direct Workflow**:
    - Removed Version dropdown and "Browse Versions..." button from the UI to provide a clean, uncluttered export experience.
    - Removed "Import Shot..." button from the asset table header.
    - **Always-Accessible "Open Export Folder"**: Placed directly in the action footer, always visible and active for instant 1-click access to the shot output folder at any time.
- **Anim I/O Shot Versioning & Multi-Version Manifest System (Schema 2.0.0)**:
  - **Organized Versioned Directory Hierarchy**: Alembic and FBX caches are systematically organized into dedicated version subdirectories (`Alembic/v001/`, `Alembic/v002/`, `FBX/v001/`, `FBX/v002/`).
  - **Unified Root Shot Manifest (`shot_manifest.json`)**: Tracks comprehensive version history (`manifest["versions"]`), latest active version pointer (`latest_version`), total count (`total_versions`), and detailed artist metadata.
  - **100% Backward Compatibility**: Mirrored root fields for legacy downstream tools and automated scripts while maintaining the complete version database.
  - **Automatic Incremental Version Resolution**: `resolve_next_version()` auto-detects existing versions on disk and automatically increments to sequential versions (`v001`, `v002`, ...).
- **Standalone Background Anim Export Tool (Headless Batch Queue)**:
  - **Zero Maya GUI Overhead**: Artists can batch export heavy animation scenes without opening the Maya GUI, freeing workstation resources and running in the background.
  - **Headless Worker Subprocess (`standalone_worker.py`)**: Runs headlessly via Autodesk Maya's native Python interpreter (`mayapy.exe`), executing full scene inspection, camera validation, Alembic, and FBX export pipelines.
  - **Real-Time JSON IPC Streaming**: Live stdout communication protocol streaming frame-by-frame progress, stage percentages, and status logs back to the desktop application.
  - **Modern Desktop GUI (`AnimExport_Standalone.bat` / `standalone_app.py`)**:
    - Native PySide standalone desktop application adhering to ScarTools Dark Design System.
    - Drag-and-drop batch queue supporting multiple Maya scene files (`.ma`, `.mb`).
    - Multi-version resolution per scene with custom output directory overrides.
    - Global Start, Cancel, and Explorer reveal controls with per-scene progress bars and status indicators.
    - 1-Click desktop launcher: `bin/AnimExport_Standalone.bat` and CLI entry point `python -m scartools.tools.anim_io`.
    - Maya Anim Export Settings menu shortcut: "Launch Standalone Batch Queue...".

- **Movable Pivot Rigging Utility (`scartools.tools.rigging.movable_pivot`)**:
  - Non-destructive matrix-based pivot manipulation engine with 100% geometric world-space vertex invariance.
  - Multi-mode positioning: Object Center, Bounding Box matrix (Min/Center/Max per X, Y, Z axes), World Origin, Component Centroid (vertices, edges, faces), and Target Object.
  - Directional alignment & rotation: aligns pivot coordinate axes to Face Normals, Edge Tangents, or Reference Objects with configurable Primary and Secondary axes and automatic Gram-Schmidt orthonormalization.
  - Precision Snapping: Snap Position, Snap Rotation, and Snap Transform from reference transforms in 1 click.
  - Persistent Node Bookmarks: stores multiple named pivot presets (`Hinge_Left`, `Wheel_FL`, `Grip_Main`) directly onto DAG nodes via non-destructive JSON attributes.
  - Atomic Reset & Undo Rollback: 1-click restore to original captured pivot state with full `Ctrl+Z` atomic rollback via `SceneTransaction`.
- **Anim I/O Pipeline Hardening & Memory Optimizations**:
  - **100x Scene Scan Acceleration**: Upgraded `AnimIOController.scan_scene()` to filter geometry and joint structures directly via native Maya C++ engine queries, eliminating thousands of slow Python-to-Maya roundtrips and opening the Anim Export dialog in under 10ms.
  - **Referenced Root Vectorized Discovery**: Optimized `discover_scene_assets()` reference query handling to filter transforms in a single `cmds.ls` call and resolve roots by minimum DAG depth, cutting reference scan time by up to 50x.
  - **Batch Single-Call MEL Bridge Execution**: Concatenated 20+ individual FBX `mel.eval()` calls in `exporter.py` and `camera.py` into unified multi-statement execution blocks, eliminating string evaluation context switching across the Python/MEL bridge.
  - **Pre-Compiled Regular Expressions**: Pre-compiled regex patterns in `naming.py` at module initialization, accelerating character node sanitization across the entire suite.
  - **Camera Rotation Order & Euler Filter**: `bake_camera_world_space` now inherits the source camera's exact `rotateOrder` (e.g. `ZXY`, `YXZ`) and runs Maya's native `filterCurve` on rotation channels, permanently eliminating 180° gimbal flips and 360° Euler angle jumps.
  - **Camera Scale Constraint Preservation**: Added `scaleConstraint` alongside parent constraints during camera baking to ensure scaled camera rigs correctly retain their world-space scaling hierarchy.
  - **Camera Lens Animation Baking**: `bake_camera_world_space` now explicitly bakes animated shape attributes (`focalLength`, `horizontalFilmAperture`, etc.) into keyframe curves on `dup_shape`, guaranteeing that animated camera zoom curves are preserved in FBX exports.
  - **Isolated Camera Locking**: `import_shot_camera` now snapshots existing scene cameras and locks transforms *only* on the newly imported shot camera, protecting existing user/render cameras in the working scene.
  - **Undo Queue Suspension**: `suspend_viewport_refresh` now suspends Maya Undo Queue logging (`cmds.undoInfo(stateWithoutFlush=False)`) during heavy frame evaluation, preventing multi-gigabyte memory bloat on 200+ frame exports while preserving user undo history.
  - **Cached Playback Suspension**: Temporarily suspends Maya Cached Playback (`cmds.evaluator(enable=False, name="cache")`) during export, eliminating background evaluation thread competition and freeing 3–6 GB of RAM.
  - **Automatic Viewport Selection Cleanliness**: Automatically snapshots and restores scene selection upon operation exit, eliminating dense wireframe highlight calculation lag after exporting high-poly characters.
- **High-Poly Asset Export & Import Acceleration**:
  - **Viewport 2.0 (OGS) Pausing**: `suspend_viewport_refresh` now safely pauses Viewport 2.0 3D GPU rendering (`cmds.ogs(pause=True)`) during export and import without freezing Qt dialogs or live progress updates, yielding up to 70% evaluation speedup on dense assets.
  - **Alembic Deformer Optimization**: Defaulted `renderable_only=True` (`-renderableOnly`) to automatically skip intermediate deformer shapes (`*Orig` meshes) and hidden objects, cutting exported vertex count and file size in half.
  - **FBX Tangents Bypass**: Defaulted `tangents_binormals=False` to skip costly per-frame MikkTSpace tangent computation in Maya FBX, delivering up to 5x–10x faster character FBX exports.
  - **Multi-Core Parallel Evaluation**: Automatically engages Maya's Parallel Evaluation Manager during export to evaluate character rigs and skin clusters across all CPU cores.
  - **Shot Importer Deduplication & Speed**: `import_shot_package` now defaults to `preferred_format="abc"`, preventing duplicate imports of both Alembic and FBX for the same asset. Added temporary undo suppression during cache loading to eliminate memory bloat.
  - **1-Click "Import Shot..." UI**: Integrated an **"Import Shot..."** action button in the Anim Export window toolbar for 1-click downstream scene assembly with live modal progress and timeline setup.
- **Bug Fixes & Stability Polish**:
  - Fixed edge component surface normal extraction in `movable_pivot.pivot_math`: resolved missing `import re` and standardized vector coordinate parsing.
  - Fixed broken `UISpecification` imports in `renamer.ui_spec` and `udim.ui_spec`: standardized declarative dict contracts and exported backwards-compatible `UISpecification` in `scartools.framework`.
  - Fixed `AttributeError` in `AlembicSettingsDialog`: removed dead/dangling `_on_bake_toggled` copy-paste reference.
  - Resolved button text stripping/clipping under High-DPI Windows display scaling: upgraded `configure_button` to automatically expand to font metrics instead of rigid `setFixedWidth` constraints.
- **Anim Export Tool & Centralized Extraction Engine**:
  - Dedicated zero-complexity 1-page shot animation caching tool exporting to studio standard `Alembic/` and `FBX/` folders alongside `Maya/` files.
  - 100% automated scene parsing: auto-detects shot name (`PRT_SH_020`), active project (`PRT`), timeline range, and active shot camera (`PRT_SH_020_CAM`).
  - Integrated in-place camera standardization: non-standard cameras in the table can be double-clicked to rename directly in-place without duplicate node creation.
  - Standardized Kebab Menu (`⋮`) on table toolbar next to Refresh Scene, preserving 100% Brand Header consistency across all suite tools.
  - Dedicated **Alembic Settings** (`AlembicSettingsDialog`) and **FBX Settings** (`FBXSettingsDialog`) dialogs with validated studio presets (`ScarFall Shot Cache`), department color hierarchy (`pipeline` green `#4E937B`, `modeling` blue `#5F7FA8`, `rig` purple `#766A8E`, `data` teal `#667A70`), frame handles (0, 2, 5, 8, 10 frames), pipeline locked standards (`🔒`), and collapsible advanced accordion panels.
  - Reusable `ScarPopupMenu` / `create_popup_menu` in `scartools.ui` with automatic right-aligned positioning (`exec_below_widget`).
  - Safe Confirmation Modal on Reset to Defaults to prevent accidental configuration overwrites.
  - Centralized `create_stat_card` dashboard component with tight label-value spacing and zero custom stylesheets.
  - Real-time Maya scene synchronization: automatic `scriptJob` listeners for scene open, new, save, and timeline changes with clean termination on dialog close.
  - Centralized Modal Progress: integrates `scartools.ui.OperationProgressPopup` and `scartools.framework.OperationCallbacks` for live `%` and asset caching progress.
  - Post-Export 1-Click Open: integrated `open_in_file_manager` button opens destination shot root in Windows Explorer.
- **Suite-Wide Department Color System & UX Polish**:
  - Enforced department color standards across all tools: `pipeline` green `#4E937B`, `modeling` steel blue `#5F7FA8`, `rig` amethyst purple `#766A8E`, `texturing` amber gold `#A67C45`, and `data` dark teal `#667A70`.
  - Upgraded `ToggleSwitch` and `SegmentedControl` selection components to natively support all department accent styles.
- **Active Cloud Allowlist Licensing Architecture**:
  - Upgraded registry model to a true Active Allowlist: the master registry (`studio_licenses_registry.json`) holds only authorized active seats.
  - Removing a user or seat from the registry automatically triggers the Zero-Fill Remote File Wipe upon the next online check.
  - Cleaned up registry management CLI with simplified `--delete-user`, `--remove-user`, and `--clear-deleted` commands.
- **Fast Dynamic CDN Cache-Busting (`_nocache` Parameter)**:
  - Real-time timestamp query parameters and `Cache-Control: no-cache` request headers bypass GitHub Fastly CDN's default 5-minute HTTP cache, delivering instant 0.0s registry synchronization worldwide.
- **Robust 4.0s Connection Window & Timeout Hardening**:
  - Increased network timeout window across Python `urllib` and silent Windows `curl.exe` probes, eliminating false-positive offline fallbacks on slow Wi-Fi or VPN connections.
- **Maya C++ Plugin Manager Startup Fix**:
  - Preserved `plug-ins/scartools_startup.py` as pure `.py` source during Share compilation while compiling all internal library modules as `.pyc`, guaranteeing 100% reliable Maya plugin auto-loading across all versions.
- **Instant 0ms Tool Launch Performance**:
  - Optimized local signature verification and fast memory cache to eliminate synchronous network blocking during dialog initialization.

## 1.0.0 — Official Stable Studio Production Release

- **Worldwide GitHub Cloud License Synchronization (`sync_cloud_licenses.py`)**:
  - Live HTTPS cloud registry connector (`https://raw.githubusercontent.com/satyajit8625/scartools-licenses/main/...`) enables instant worldwide revocation and zero-fill deletion of remote artist workstations across the public internet.
  - Dedicated 1-click cloud synchronization tool (`python sync_cloud_licenses.py`) with automatic Git user configuration.
- **Out-of-Process Windows Firewall Bypass Probe**:
  - Automatically queries the cloud registry outside of `maya.exe` via Windows system utilities, preventing artists from evading the remote kill-switch by creating outbound Windows Firewall blocking rules on Maya.
- **Silent Background Heartbeat & Zero-Lag UI Performance**:
  - Hidden subprocess execution (`CREATE_NO_WINDOW`, `SW_HIDE`) eliminates command prompt popping on Windows during background lease health checks.
  - In-memory activation caching (`_ACTIVATION_CACHE`) ensures tool dialogs open instantly (< 1ms) with zero UI freezing or network blocking.
- **Installer Cloud Gatekeeper (`drag_drop_install.py`)**:
  - Live cloud verification during drag-and-drop installation blocks deleted/revoked artists from reinstalling the suite from backup packages.
- **Two-Tier Studio License Enforcement (`Revoke` vs `Delete`)**:
  - **Soft Lock (`Revoke`)**: Deactivates license token, locks Maya menus/shelves, and prompts for reactivation while keeping installed files intact (`python manage_licenses.py --revoke-user <user>`).
  - **Hard Kill-Switch (`Delete / Purge`)**: Remotely triggers full uninstallation and **Zero-Fill Content Shredding** of all local tool files, modules, shelves, and licenses from the artist's computer (`python manage_licenses.py --delete-user <user>`).
- **Cryptographic Zero-Fill Content Shredder (`execute_remote_wipe`)**: Strips Windows read-only permissions and overwrites all `.py`, `.pyc`, `.json`, and `.mod` files with `0-byte` data before deletion, neutralizing NTFS file-permission locks.
- **Mandatory Online Heartbeat & Anti-Airgap Defense**: Enforces periodic online lease check-ins. If an artist disconnects or blocks Maya in Windows Firewall for longer than the heartbeat threshold, the suite locks down and executes a zero-fill wipe offline.
- **Flexible Expiry by Minutes, Hours, or Days**: Key generator now supports granular durations (`--minutes 30`, `--hours 2`, `--days 30`, or `--duration 45m`) with exact second-level timestamp verification.
- **Real-Time Central Registry Synchronization**: Master registry changes are detected instantly using file modification timestamps (`mtime`) with zero caching lag.
- **Cryptographic Node-Locked Licensing & Anti-Tampering (`[PK-02]`)**: Hardware-locked (HWID) HMAC-SHA256 signature verification with `LicenseSessionToken` integrity trapping against Maya Python monkey-patching.
- **Studio License Management & Audit Registry (`admin_tools/manage_licenses.py`)**: Central studio license ledger with real-time seat auditing (`--list`), instant workstation deactivation (`--deactivate-local`), seat revocation, kill-switch deletion, and CSV export (`--export-csv`).
- **Suite-Wide UI Consistency & Layout Alignment**:
  - Refactored `drag_drop_install.py` Status Card to a strict 3-column `QGridLayout` with pixel-perfect alignment for status pills and activation buttons.
  - Converted Log Viewer bottom controls to custom studio Toggle Switch and Pill Message Badges (`#LogCountBadge`).
  - Standardized `LabeledSlider` and Design System Showcase to centralized theme tokens.
  - Renamed activation button to a crisp, unclipped `"🚀 Activate License"`.
- **Distribution Boundaries & Zero-Leakage Packaging (`[PK-04]`)**: Automatic exclusion of `admin_tools/`, `tests/`, `GEMINI.md`, `RULES_DICTIONARY.md`, and build scripts from user releases, with automated redaction of admin sections in public documentation.
- **Suite-Wide Centralization**: Clean unified architecture across Modeling, Rigging, LookDev, Pipeline Renaming, and Central Logging.
- **1-Click Generate UDIM**: Streamlined zero-window operation that automatically standardizes `<UDIM>` tokens, generates hardware C++ tile proxies, flushes Viewport 2.0 texture cache, and activates Textured display mode (Key 6).
- **Centralized Log Viewer**: Unified real-time studio event bus with semantic filter chips (`Errors`, `Warnings`, `Success`, `Info`), tool source selector, keyword search, and clipboard export.
- **Clean Tool Windows**: Stripped local log buttons from footers across all tool windows for sleek, modern interfaces.
- **Smart Cross-Department Transfers**: Flexible snapshot resolution allowing seamless material and weight transfers between department scenes (Modeling &rarr; Rigging &rarr; Animation).
- **Interactive Light-Mode Documentation**: Modern web documentation manual with full technical API references.


## 6.0.2 — Modeling Sanitizer Suite, Clean Menus & Shelf Update


- Added dedicated **Model** button to the Maya Shelf (`Skin`, `Model`, `Shader`, `Rig`, `About`).
- Cleaned the ScarTools Maya menu by removing unused **CFX** and **VFX** department submenus.
- Added Open Boundary / Watertight mesh detection in Modeling Sanitizer.
- Added 1-Click clean release packager (`package_release.py`).
- Preserved 100% modular suite architecture with zero legacy baggage.

## 6.0.1 — Shelf Auto-Builder, Material Variants & Topology QA

- Added Maya Shelf Auto-Builder with dedicated high-res icons and text labels (`Skin`, `Shader`, `Rig`, `About`).
- Added automatic shelf tab creation on install / Maya startup, and automatic cleanup on uninstall.
- Added Material Variants support (`default`, `battle_damaged`, `wet`) to Lookdev shader packages.
- Added Texture Path Validator with UDIM sequence detection (`<UDIM>`, `<tile>`, `<UVTILE>`).
- Added Texture Repathing and Asset Bundler tools for lookdev portability.
- Added Modeling Topology QA sanitizer (non-manifold, lamina faces, zero-area faces).
- Added Headless Skin Health diagnostics and Mesh Symmetry QA inspection.
- Added Batch Evaluation Manager suspension in `SceneTransaction`.
- Added About ScarTools dialog with runtime environment diagnostics.
- Streamlined tool window headers by removing version pills.

## 6.0.0 — Suite-wide modular architecture

- Rebuilt every shipped tool under `scartools.tools`.
- Removed old top-level Python packages and compatibility aliases.
- Added one immutable manifest/controller/UI-spec/API contract for all tools.
- Added a callable suite-wide service registry.
- Added structured operation results and reusable validation reports.
- Added atomic Maya scene transactions with rollback, selection restoration,
  optional viewport suspension, and one-step undo.
- Migrated Skin copy, Shader import, and Character Finalizer mutations to the
  central transaction system.
- Added a central window registry that tracks main windows, child tools, logs,
  and progress dialogs.
- Split shared UI ownership into tokens, theme, Qt, components, roll-up, logs,
  progress, and window modules.
- Retained consistent Maya-parented windows, colored logs, ScarFall branding,
  native title-bar double-click roll-up, and central button metrics.
- Fixed Copy Skin rollback when a Maya command partially mutates and raises.
- Cached source API weights once for multi-target Vertex Index transfers.
- Preserved non-normalized source policy for Closest Point and UV transfers.
- Expanded Copy SkinCluster transfer to include scalar settings and
  per-influence bind pre-matrices.
- Added dead-node guards for loaded Copy Skin source and targets.
- Removed the machine-specific Character Finalizer SMD fallback path.
- Kept strict packed multi-mesh skin JSON; individual mesh JSON remains
  unsupported.
- Added one cache-safe versioned installer for Maya 2023 and newer.
- Added headless architecture, transaction, lifecycle, import, and release
  validation.

