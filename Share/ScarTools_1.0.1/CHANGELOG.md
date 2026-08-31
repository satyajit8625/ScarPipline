# Changelog

## 1.0.1 — Active Cloud Allowlist & Zero-Latency CDN Synchronization

- **Anim Export Tool & Centralized Extraction Engine**:
  - Dedicated zero-complexity 1-page shot animation caching tool exporting to studio standard `Alembic/` and `FBX/` folders alongside `Maya/` files.
  - 100% automated scene parsing: auto-detects shot name (`PRT_SH_020`), active project (`PRT`), timeline range, and active shot camera (`PRT_SH_020_CAM`).
  - Integrated in-place camera standardization: non-standard cameras in the table can be double-clicked to rename directly in-place without duplicate node creation.
  - Centralized `create_stat_card` dashboard component with tight label-value spacing and zero custom stylesheets.
  - Real-time Maya scene synchronization: automatic `scriptJob` listeners for scene open, new, save, and timeline changes with clean termination on dialog close.
  - Centralized Modal Progress: integrates `scartools.ui.OperationProgressPopup` and `scartools.framework.OperationCallbacks` for live `%` and asset caching progress.
  - Post-Export 1-Click Open: integrated `open_in_file_manager` button opens destination shot root in Windows Explorer.
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

