# ScarTools Engineering Rulebook

**Version:** 3.0.0  
**Status:** Active engineering standard  
**Scope:** ScarTools for Autodesk Maya, its shared framework, individual tools, tests, installers, build scripts, licensing services, documentation, and release packages.

This document defines the mandatory engineering rules for ScarTools. It is the source of truth for architecture and release decisions. Assistant commands are convenience aliases only and cannot override these rules.

---

## 0. Rulebook Governance (`[GOV]`)

### Requirement Levels

- **MUST / MUST NOT** — mandatory. A failed check blocks release.
- **SHOULD / SHOULD NOT** — expected unless a documented exception is approved.
- **MAY** — optional guidance.

### Rule Status

- **Active** — approved and currently enforced.
- **Proposed** — not enforced until approved.
- **Deprecated** — retained temporarily for migration and scheduled for removal.

### `[GOV-01]` Rule Precedence

**Requirement:** Safety and data-protection rules take precedence over security, automation, packaging, and convenience rules. Release rules take precedence over chat commands.

**Verification:** Any conflict must be resolved using this priority:

1. User data and workstation safety
2. Security and privacy
3. Release integrity
4. Architecture and maintainability
5. UI consistency and convenience

### `[GOV-02]` One Rule, One Owner

**Requirement:** A behaviour MUST have one authoritative rule. Other sections MUST reference its Rule ID instead of repeating it.

**Verification:** The rule audit reports duplicate requirements and conflicting wording.

### `[GOV-03]` Measurable Language

**Requirement:** Rules MUST describe testable behaviour. Avoid claims such as “100% secure,” “unbreakable,” “full 360° audit,” or “pristine codebase.”

**Verification:** Every MUST rule identifies a test, lint check, package check, or review step.

### `[GOV-04]` Exceptions

**Requirement:** A rule exception MUST record the affected rule, reason, owner, scope, risk, approval, and expiry date in an Architecture Decision Record (`docs/adr/`). Silent exceptions are prohibited.

**Verification:** CI and review notes link to the ADR when an exception is active.

### `[GOV-05]` Implementation Status

**Requirement:** Rules define the required standard, not proof that the repository already complies. Compliance MUST be tracked as `Implemented`, `Partial`, `Missing`, or `Not Applicable` in a separate audit report.

### `[GOV-06]` Definition of Done

**Requirement:** A feature, tool, migration, or fix is complete only when its applicable architecture, lifecycle, scene-safety, undo, cleanup, testing, UI, documentation, packaging, and security rules pass. Unused code exposed by the change MUST be handled under `[ARCH-07]`.

### `[GOV-07]` Major-Release Compliance Audit

**Requirement:** Before every major release, each active rule MUST be classified as `Implemented`, `Partial`, `Missing`, `Not Applicable`, or `Approved Exception`. A `Missing` release-blocking rule prevents approval.

---

## 1. Supported Runtime (`[RUNTIME]`)

### `[RUNTIME-01]` Supported Maya Matrix

**Requirement:** ScarTools supports Maya 2023 and any later Maya versions explicitly listed in `docs/SUPPORT_MATRIX.md`. “Maya 2023+” MUST NOT be interpreted as automatic support for every future Maya release.

**Verification:** Each listed Maya version has an installation test, startup smoke test, and tool-launch smoke test.

### `[RUNTIME-02]` Python and Qt Compatibility

**Requirement:** Maya’s bundled Python and Qt binding are authoritative. Compatibility adapters MAY isolate PySide2/PySide6 differences, but tool modules MUST NOT contain scattered version checks.

**Verification:** A centralized compatibility module owns supported Qt imports; repository checks reject direct compatibility branches in individual tools.

### `[RUNTIME-03]` Windows Support

**Requirement:** Supported Windows versions, Maya versions, Python versions, and package variants MUST be recorded together in the support matrix.

**Verification:** The release manifest declares the tested environment.

---

## 2. Repository and Architecture (`[ARCH]`)

### `[ARCH-01]` Dependency Direction

**Requirement:** Dependencies MUST flow in this direction:

```text
UI -> Services -> Operations -> Framework Adapters -> Maya API
```

Backend layers MUST NOT import UI modules. Framework modules MUST NOT import individual tool packages.

**Verification:** Import-boundary tests scan package imports and fail on reverse dependencies.

### `[ARCH-02]` Standard Tool Package

**Requirement:** Every tool package in `scartools.tools.<tool_id>` MUST use the standard structure appropriate to its size:

```text
<tool_id>/
  __init__.py
  manifest.py
  operations.py
  validation.py       # when validation is required
  ui.py               # when the tool has a UI
  resources/          # tool-specific non-code resources
  tests/
```

Empty placeholder modules are not required.

### `[ARCH-03]` Centralized-First Design

**Requirement:** Existing components in `scartools.ui` and `scartools.framework` MUST be audited before new shared behaviour is created. Duplicate implementations of lifecycle, logging, progress, validation, paths, snapshots, transactions, or styling are prohibited.

**Promotion Rule:** A component SHOULD move into the central system when it is used by two or more tools, controls studio-wide behaviour, or establishes a design-system pattern.

**Exception:** Truly tool-specific logic MAY remain inside its tool package, but it MUST NOT duplicate central behaviour or introduce private design tokens.

### `[ARCH-04]` No Legacy Compatibility Shims

**Requirement:** ScarTools does not preserve obsolete internal script APIs, deprecated module paths, duplicate launchers, or compatibility wrappers for retired tool versions unless explicitly approved.

**Data Protection:** Removing old code compatibility does not permit silent loss of user-created data. Data migrations follow `[DATA-03]`.

### `[ARCH-05]` No Import-Time Side Effects

**Requirement:** Importing a module MUST NOT open windows, edit a Maya scene, modify environment variables, write files, create menus, or perform license network calls.

**Verification:** Headless import tests load every public module in a clean process.

### `[ARCH-06]` Public API Ownership

**Requirement:** Public exports MUST be intentional. `__all__` changes only when the supported public API changes. Tool packages MUST NOT import private names from another tool.

### `[ARCH-07]` Verified Removal of Unused Code and Files

**Requirement:** Obsolete code, unused imports, duplicate helpers, abandoned compatibility layers, temporary files, stale build outputs, and unreferenced resources MUST be removed as part of the change that makes them unnecessary.

Before removal, the developer MUST verify references through repository search, manifest and entry-point checks, import analysis where available, and the applicable test suite. A file MUST NOT be classified as unused only because it is not imported directly; dynamic imports, Maya shelves, manifests, resource loaders, installers, and build scripts MUST also be checked.

**Safety:** Cleanup MUST NOT delete artist-created files, Maya scenes, presets, exports, active release packages, production assets, or files outside ScarTools ownership. Ambiguous files MUST be reported for review instead of deleted. Material cleanup MUST remain recoverable through version control or a backup until validation passes.

**Verification:** The change review records what was removed, why it was unused, how references were checked, and which tests passed after removal.

### `[ARCH-08]` Tool Failure Isolation

**Requirement:** Failure while discovering, importing, registering, or launching one tool MUST NOT prevent the ScarTools menu or unrelated tools from loading. The failed tool MUST be disabled for that session and reported through the central log with a clear recovery action.

### `[ARCH-09]` Controlled User-Facing Deprecation

**Requirement:** A user-facing tool or documented workflow SHOULD be marked deprecated for at least one approved release before removal. Obsolete internal APIs, compatibility shims, and private module paths MAY be removed immediately under `[ARCH-04]` when no supported user data depends on them.

---

## 3. Tool Manifest and Services (`[FW]`)

### `[FW-01]` Tool Manifest Contract

**Requirement:** Every tool MUST declare `TOOL_MANIFEST = ToolManifest(...)` in `manifest.py`, containing at least:

- `tool_id`
- `name`
- `department`
- `version`
- `entry_point`
- registered headless services
- minimum supported Maya version, when tool-specific

**Verification:** Manifest schema validation runs before Maya startup and during packaging.

### `[FW-02]` Central Tool Discovery

**Requirement:** Tool discovery MUST have one authoritative registration mechanism. A tool MUST NOT require registration in multiple manually synchronized lists.

**Migration Note:** If `BUILTIN_TOOL_MODULES` and `BUILTIN_TOOL_MANIFESTS` both exist, they MUST be generated from one source or consolidated.

### `[FW-03]` Lazy Service Registry

**Requirement:** Headless services MUST be registered as lazy entry points and called through the central service registry. Heavy UI and backend modules MUST NOT load during Maya startup unless required.

**Verification:** Startup tests record imported ScarTools modules and enforce the approved startup allowlist.

### `[FW-04]` Structured Operation Results

**Requirement:** Shared operations SHOULD return a standard result containing success state, message, warnings, changed items, output paths, and error details. Expected user errors MUST NOT be communicated only through uncaught exceptions.

### `[FW-05]` Structured Validation

**Requirement:** Model, rig, scene, and export validators MUST use the centralized preflight types and severities: `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.

**Blocking Rule:** `ERROR` and `CRITICAL` issues block destructive or invalid exports unless an approved exception exists.

### `[FW-06]` Central Event Logging

**Requirement:** Diagnostic and operation feedback MUST route through the central logging API. Logs MUST include timestamp, level, source, operation, and message.

**Privacy:** Passwords, tokens, private keys, raw HWIDs, and sensitive artist paths MUST NOT be logged.

**Verification:** Logging tests validate levels, rotation, redaction, and failure fallback.

### `[FW-07]` Scene-Impact Declaration

**Requirement:** Every tool manifest MUST declare whether the tool is read-only, modifies the Maya scene, writes external files, requires undo support, requires a saved scene, supports referenced nodes, and supports cancellation. Validation and test requirements MUST be derived from these capabilities.

### `[FW-08]` Framework Capability Registry

**Requirement:** Tools MUST request shared capabilities such as lifecycle, logging, validation, progress, paths, snapshots, licensing, settings, and UI through public framework services. Tools MUST NOT import another tool's private implementation.

### `[FW-09]` No Silent Failure

**Requirement:** An operation MUST NOT fail only through a console traceback or swallowed exception. The user receives a concise actionable message, while technical context and the original exception are preserved in the central log.

---

## 4. UI Design System (`[UI]`)

### `[UI-01]` Standard Window Lifecycle

**Requirement:** Every tool window MUST inherit from `BaseToolDialog` and be opened through one centralized window launcher/lifecycle API.

The lifecycle system MUST provide:

- Maya main-window parenting
- one active instance per `tool_id`
- focus/raise when reopened
- clean deregistration on close
- `WA_DeleteOnClose` or equivalent cleanup
- safe `close_all_windows()` during suite reload or license deactivation

**Important:** Registration MUST happen in one place only. A dialog MUST NOT be registered both by its constructor and by its launcher.

### `[UI-02]` Brand Header and Roll-Up

**Requirement:** Tool windows MUST use the shared ScarTools brand header. Roll-up behaviour, when enabled, MUST be implemented centrally and triggered consistently from the approved header area.

Custom title bars or independent roll-up implementations are prohibited.

### `[UI-03]` Section Panels and Department Accents

**Requirement:** Standard section panels MUST be created through the central UI factory. Department accent colours MUST come from semantic tokens, not tool-local hexadecimal values.

Approved default accents:

| Department token | Default colour |
|---|---:|
| `pipeline` | `#4E937B` |
| `modeling` | `#5F7FA8` |
| `rigging` | `#766A8E` |
| `texturing` | `#A67C45` |
| `animation` | Defined in central tokens |
| `vfx` | Defined in central tokens |
| `cfx` | Defined in central tokens |
| `data` | `#667A70` |
| `validation` | `#5F7FA8` |

### `[UI-04]` Central Layout Metrics

**Requirement:** Spacing, margins, control heights, label widths, button sizes, corner radii, and typography MUST use central tokens.

Current baseline tokens:

| Token | Baseline |
|---|---:|
| `FORM_LABEL_WIDTH` | `65 px` |
| `INLINE_SPACING` | `12 px` |
| `FIELD_HEIGHT` | `30 px` |
| `PRIMARY_BUTTON_WIDTH` | `220 px` |

These values are defaults, not permission to clip translated text or break responsive layouts.

### `[UI-05]` Shared Controls

**Requirement:** If an equivalent shared control exists, tools MUST reuse it. This includes segmented controls, toggle switches, labeled sliders, vector inputs, path pickers, UV tile grids, curve editors, palette grids, token inputs, step wizards, and preset bars.

**Exception:** A specialized tool control MAY be local until it meets `[ARCH-03]` promotion criteria.

### `[UI-06]` Action and Status Area

**Requirement:** Action-driven dialogs MUST use the shared action footer/status component. Informational windows without a primary action MAY omit it.

Actions MUST expose clear enabled, disabled, running, success, warning, and failure states.

### `[UI-07]` No Inline Styling

**Requirement:** Tool code MUST NOT use hardcoded `setStyleSheet(...)` fragments, private colours, or duplicated theme rules. Styling belongs in central tokens and themes.

### `[UI-08]` Responsive and High-DPI Behaviour

**Requirement:** Windows MUST remain usable at supported Windows scaling levels and at the minimum supported Maya workspace size. Fixed sizes MUST NOT clip labels, controls, logs, or action buttons.

### `[UI-09]` Main-Thread Safety

**Requirement:** Maya commands and Qt widget updates MUST run on the appropriate Maya/Qt main thread. Background workers MAY perform safe computation or file preparation but MUST communicate through controlled signals and support shutdown.

### `[UI-10]` UI Cleanup

**Requirement:** Closing or reloading a tool MUST stop timers and workers, disconnect callbacks, remove script jobs, and release Maya event subscriptions owned by that tool.

**Verification:** Repeated open/close tests check for duplicate callbacks, orphan windows, and growing listener counts.

### `[UI-11]` Central Dialog System

**Requirement:** Confirmations, overwrite prompts, warnings, errors, and success messages MUST use shared ScarTools dialogs with consistent severity, wording, button order, focus, and keyboard behaviour. Native Maya dialogs MAY be used only through an approved adapter.

### `[UI-12]` Callback Ownership

**Requirement:** Every Maya callback, script job, Qt signal, timer, worker, and event subscription MUST have an identifiable owner and deterministic cleanup. Anonymous persistent callbacks and unowned script jobs are prohibited.

---

## 5. Maya Backend and Scene Safety (`[CORE]`)

### `[CORE-01]` Stable Node Identity

**Requirement:** DAG nodes MUST be resolved to full paths at operation boundaries. Operations that must survive rename or reparent actions SHOULD use Maya UUIDs and re-resolve the current DAG path before mutation.

Short names MUST NOT be treated as unique.

### `[CORE-02]` Headless Backend Separation

**Requirement:** Backend modules in `operations.py`, `api/`, and `framework/` MUST run under `mayapy` without importing Qt widgets or `maya.OpenMayaUI`.

**Verification:** Headless import and operation tests run using the Maya standalone environment.

### `[CORE-03]` Atomic Scene Undo

**Requirement:** Scene-editing operations MUST be grouped into one named undo transaction wherever Maya supports safe rollback.

The transaction MUST:

- close its undo chunk in `finally`
- preserve the original exception
- avoid leaving a half-open undo queue
- produce one meaningful `Ctrl+Z` step

**Exception:** File export, external file writes, scene open/new operations, and non-undoable plugin operations follow `[CORE-04]` instead of claiming full Maya undo support.

### `[CORE-04]` Atomic Filesystem Operations

**Requirement:** Exports and package writes MUST use a temporary destination, validate the completed output, and atomically promote it to the final path when supported. Failed operations MUST remove only their own temporary files and MUST NOT damage the previous valid version.

### `[CORE-05]` Preflight Before Mutation

**Requirement:** Tools MUST validate selection, node types, namespaces, references, writable destinations, required plugins, and scene state before beginning a multi-step mutation.

### `[CORE-06]` Progress and Cancellation

**Requirement:** Long-running operations MUST use the central progress service. Cancellation MUST occur only at defined safe checkpoints and MUST leave the scene and filesystem in a valid state. A cancelled operation MUST report what changed and what was rolled back.

### `[CORE-07]` Preserve User Context

**Requirement:** Unless the tool explicitly documents an intentional change, operations SHOULD restore the user’s selection, current frame, playback range, active camera, active tool context, auto-key state, construction-history state, evaluation mode, viewport refresh state, and other captured working context after completion or failure.

### `[CORE-08]` Namespace and Reference Safety

**Requirement:** Tools MUST support namespaced nodes where their workflow allows it and declare reference support under `[FW-07]`. Referenced nodes MUST NOT be silently unlocked, imported, duplicated, edited, or stripped of reference edits. Any supported reference mutation requires explicit user intent and preflight validation.

### `[CORE-09]` Performance Boundaries

**Requirement:** Backend operations SHOULD avoid repeated full-scene scans, per-component `cmds` loops when an API/batched approach is appropriate, unnecessary viewport refresh, and repeated dependency-graph evaluation.

Performance-sensitive tools MUST have a representative large-scene benchmark.

Potentially expensive whole-scene operations MUST estimate or report their scope before mutation. Above a centrally defined threshold, the operation MUST warn the user, use batching, or require explicit confirmation.

### `[CORE-10]` Selection Contract

**Requirement:** Every operation MUST define whether it acts on the live selection, a captured selection, explicit node arguments, or the whole scene. Selection and node identity MUST be revalidated immediately before mutation.

### `[CORE-11]` No Forced Scene Save

**Requirement:** A tool MUST NOT save, rename, or overwrite the current Maya scene unless the user explicitly initiated that action or approved a clearly identified workflow step. Auto-recovery copies MUST use a separate owned path.

### `[CORE-12]` Temporary Node Ownership

**Requirement:** Temporary Maya nodes MUST use central ownership metadata or an approved ScarTools naming prefix. They MUST be removed after success, failure, or cancellation unless the user explicitly chooses to retain them.

### `[CORE-13]` Unknown Node and Plugin Safety

**Requirement:** ScarTools MUST NOT automatically delete unknown nodes, remove unknown plugin records, or erase reference edits. Diagnostic tools MAY identify them; cleanup requires an explicit scoped action and recoverable scene protection.

### `[CORE-14]` Units and Coordinate Contract

**Requirement:** Tools handling geometry, transforms, animation, simulation, or exports MUST declare and validate applicable linear units, angular units, frame rate, up axis, coordinate space, and handedness. Conversion MUST be explicit and tested.

---

## 6. Data, Snapshots, and Exports (`[DATA]`)

### `[DATA-01]` Central Snapshot and Version Service

**Requirement:** All department exports MUST use the central snapshot/version service. Individual tools MUST NOT implement private “find next version” algorithms.

### `[DATA-02]` Atomic Version Reservation

**Requirement:** Version numbers MUST be reserved centrally to prevent two processes from publishing the same version. A version is marked complete only after validation succeeds.

### `[DATA-03]` Versioned Manifest Schema

**Requirement:** Every exported ScarTools package MUST include a versioned manifest containing, where applicable:

- `schema_version`
- `tool_id` and `tool_version`
- Maya and Python versions
- asset or shot identity
- source scene reference
- created timestamp and creator identity
- package version
- exported items
- file checksums
- warnings and validation summary
- export settings and coordinate/unit contract

Readers MUST reject unsupported schema versions clearly and without partial import.

### `[DATA-04]` Controlled Data Migration

**Requirement:** User-created data migration MUST be explicit, tested, and directional. A migration MUST preserve the original package until the new package validates successfully.

Internal legacy code APIs remain unsupported under `[ARCH-04]`.

### `[DATA-05]` Path Policy

**Requirement:** Central path utilities MUST handle normalization, invalid characters, reserved Windows names, long paths, permissions, and project-relative versus absolute paths.

Tools MUST NOT manually concatenate production paths.

### `[DATA-06]` Export Validation

**Requirement:** An export is successful only when required files exist, manifests parse, checksums match, and tool-specific structural validation passes. A publish MUST remain hidden or marked incomplete until every required artifact validates; failed or cancelled work MUST NOT appear as a completed version.

### `[DATA-07]` Central Settings Ownership

**Requirement:** Tool preferences, UI state, paths, recent items, and presets MUST use the central settings service. Tools MUST NOT create private preference roots or arbitrary JSON files outside approved locations.

### `[DATA-08]` Settings and Preset Schema

**Requirement:** Every persisted settings or preset payload MUST declare `schema_version`, `tool_id`, and `tool_version`. Unsupported or invalid data MUST fail clearly without partially applying values. Migrations follow `[DATA-04]`.

### `[DATA-09]` Publish Immutability

**Requirement:** A completed published version MUST NOT be silently overwritten or modified in place. Corrections require a new version unless an authorized, logged rollback or administrative repair procedure is used.

### `[DATA-10]` Preset Scope and Ownership

**Requirement:** Every preset MUST declare whether it is user, project, department, or studio scoped. A lower-scope preset MUST NOT silently overwrite a shared preset, and shared changes require appropriate authorization.

---

## 7. Testing and Quality Gates (`[TEST]`)

### `[TEST-01]` Test Layers

**Requirement:** ScarTools MUST maintain the following test layers where applicable:

1. Pure Python unit tests
2. `mayapy` headless tests
3. Maya integration tests
4. Qt lifecycle tests
5. Installer/update/uninstaller tests
6. Release-package smoke tests

The rulebook MUST NOT hardcode the current number of tests.

### `[TEST-02]` Regression Tests

**Requirement:** Every confirmed bug fix MUST include a regression test when the behaviour can be tested reliably.

### `[TEST-03]` Test Isolation

**Requirement:** Tests MUST use temporary scenes and directories. Tests MUST NOT write to production asset locations, the active Share release, or a user’s Maya preferences.

### `[TEST-04]` Release Gate

**Requirement:** A release is blocked when mandatory tests fail, the package allowlist fails, documentation required for that release is missing, or the artifact smoke test fails.

### `[TEST-05]` Honest Test Reporting

**Requirement:** Reports MUST distinguish passed, failed, skipped, expected-failure, and unavailable-environment tests. Skipped tests MUST NOT be presented as passed.

---

## 8. Security and Licensing (`[SEC]`)

### `[SEC-01]` Asymmetric License Signing

**Requirement:** License grants and server responses SHOULD use asymmetric digital signatures. Private signing keys MUST remain on approved admin/server systems. Distributed clients contain only public verification material.

HMAC MAY be used only when the shared secret can remain outside distributed clients.

### `[SEC-02]` Minimal Hardware Fingerprint

**Requirement:** If node locking is required, ScarTools MUST collect only the minimum approved hardware identifiers, normalize them centrally, and store/transmit only a protected fingerprint where practical.

Raw CPU, motherboard, or volume identifiers MUST NOT appear in normal logs or user documentation.

### `[SEC-03]` Safe License Revocation

**Requirement:** An authorized administrator MAY remotely revoke a ScarTools license. Revocation disables ScarTools functionality on the next successful heartbeat or lease expiry and MAY close ScarTools-owned windows, disable ScarTools menus, and block future launches.

Revocation MUST NOT alter Maya scenes, artist-created data, Maya preferences unrelated to ScarTools, or files owned by other software.

### `[SEC-04]` No Remote Wipe or Self-Shredding

**Requirement:** ScarTools MUST NOT remotely overwrite, zero-fill, shred, or delete workstation files. Network failure, firewall blocking, clock mismatch, or license expiry MUST result in a safe lock state—not data destruction.

### `[SEC-05]` Safe Uninstallation

**Requirement:** Uninstallation MUST be locally initiated or explicitly approved, remove only paths recorded as ScarTools-owned, and provide a dry-run/summary before removal. User-created exports, presets, logs required for support, and Maya scenes MUST be preserved unless the user explicitly selects them.

### `[SEC-06]` Heartbeat and Offline Grace

**Requirement:** Online lease verification MUST use authenticated encrypted transport, bounded timeouts, and a configurable offline grace period. Temporary service failure MUST NOT immediately block active production.

Clock rollback detection MUST tolerate ordinary clock corrections and MUST fail safely.

### `[SEC-07]` Session Authorization

**Requirement:** Sensitive operations MAY require a validated session capability. Failure MUST produce a clear authorization error and MUST NOT leave partial scene or file mutations.

Client-side anti-tamper checks are defence-in-depth only and MUST NOT be described as impossible to bypass.

### `[SEC-08]` Secrets Management

**Requirement:** Private keys, admin credentials, API secrets, and signing secrets MUST NOT be committed, embedded in distributed packages, written to logs, or included in documentation.

### `[SEC-09]` Admin Tool Isolation

**Requirement:** License generators, administrative commands, private security documentation, tests, and development-only build utilities MUST be excluded from artist packages through a package allowlist.

### `[SEC-10]` Security Audit Scope

**Requirement:** Security reviews SHOULD cover authorization, secret exposure, package contents, unsafe deserialization, path traversal, command execution, dependency risk, log privacy, update integrity, and failure behaviour.

---

## 9. Build, Packaging, and Release (`[DIST]`)

### `[DIST-01]` Test/Staging First

**Requirement:** Code changes MUST be applied and verified in the active development or Test/Staging environment. A normal edit MUST NOT automatically overwrite the production `Share/` package.

### `[DIST-02]` Explicit Release Approval

**Requirement:** `Share/ScarTools_<version>` and its ZIP MUST be updated only after all release gates pass and the user or designated release owner explicitly approves the release.

Failed packaging MUST leave the previous Share release unchanged.

### `[DIST-03]` Reproducible Build

**Requirement:** One canonical build command MUST produce the release from a clean input state. The build MUST record source revision, version, target Maya/Python version, timestamp, test summary, and artifact checksum.

### `[DIST-04]` Package Allowlist

**Requirement:** Release contents MUST be controlled by an allowlist. At minimum, these development items are excluded unless explicitly required at runtime:

- admin tools and private admin guides
- tests and fixtures
- AI assistant instruction files
- developer notes
- raw secrets or credentials
- temporary files and caches
- source maps and debug dumps

### `[DIST-05]` Bytecode Is Packaging, Not Security

**Requirement:** Python bytecode MAY be shipped to reduce casual source exposure, but MUST NOT be presented as strong source protection. `.pyc` files MUST match the target Maya Python version. `.pyd` files may be included only when they were deliberately compiled and tested for the target environment.

### `[DIST-06]` Documentation Redaction

**Requirement:** Artist documentation MUST be generated from approved public content. If admin-only blocks are used, the build MUST test that none remain in the final package. Package allowlisting remains the primary boundary.

### `[DIST-07]` Versioning and Changelog

**Requirement:** Releases MUST use one documented versioning policy. The changelog MUST identify additions, fixes, breaking changes, migration requirements, known issues, and supported Maya versions.

### `[DIST-08]` Backup and Rollback

**Requirement:** Before replacing an existing Share release, the build process MUST preserve a recoverable previous version. Rollback steps MUST be documented and tested.

### `[DIST-09]` Installation Integrity

**Requirement:** Installers MUST verify artifact checksums, validate target paths, avoid duplicate install entry points, and report exactly which files were installed.

### `[DIST-10]` Owned-File Installation Manifest

**Requirement:** Every installation MUST record the exact ScarTools-owned files, directories, shortcuts, shelves, and module entries it creates. Updates and uninstallers MUST modify only recorded owned paths unless the user explicitly approves an additional scoped target.

### `[DIST-11]` Update Compatibility Preflight

**Requirement:** Before updating, ScarTools MUST validate the Maya, Python, Qt, Windows, installed-suite and target-suite versions, installation path, permissions, available disk space, package checksum, and rollback availability.

### `[DIST-12]` Atomic Update and Automatic Rollback

**Requirement:** Updates MUST stage the new version separately, validate package integrity and startup, switch the active version atomically where supported, and restore the previous version if validation fails. The current working release MUST remain usable until promotion succeeds.

### `[DIST-13]` Single Approved Installer Entry Point

**Requirement:** ScarTools MUST provide one authoritative drag-and-drop or equivalent installer workflow. Duplicate, obsolete, or independently maintained installer entry points MUST be removed under `[ARCH-07]`.

---

## 10. Documentation (`[DOC]`)

### `[DOC-01]` Documentation Must Stay Synchronized

**Requirement:** Every code or workflow change MUST include the documentation updates required by its change type in the same reviewed change. A feature, fix, breaking change, public API change, installation change, supported-version change, or user-visible behaviour change is incomplete until its affected documentation is updated.

Documentation updates are based on what changed:

| Change | Required documentation |
|---|---|
| User-facing behaviour | User manual and changelog |
| Public API | API documentation and exports |
| Architecture | Rulebook or ADR |
| Internal refactor with no behaviour/API change | Code/tests only; changelog optional |
| Release | Version, changelog, support matrix, release report |

An internal refactor does not require unrelated documentation rewrites, but documentation that becomes inaccurate MUST be corrected or removed. Examples, screenshots, command names, paths, version numbers, manifests, support information, and release instructions MUST match the delivered behaviour.

**Verification:** Reviewers compare the change against the documentation matrix, and release checks fail when required documents are missing, stale, or contradictory.

### `[DOC-02]` Examples Must Execute

**Requirement:** Published code examples MUST use current imports and APIs. Examples SHOULD be covered by a syntax/import test where practical.

### `[DOC-03]` Artist and Admin Separation

**Requirement:** Artist-facing documentation MUST explain supported workflows and safe troubleshooting without exposing private keys, administrative commands, or unnecessary anti-tamper implementation details.

### `[DOC-04]` Rulebook Change Control

**Requirement:** Any rule addition, removal, or semantic change MUST update the rulebook version and include a short change note.

---

## 11. Operational Commands (`[CMD]`)

These are convenience commands for the assistant or developer. They MUST obey all governance, safety, testing, and release rules above.

| Command | Required behaviour | Output |
|---|---|---|
| `cleanup` | Audit obsolete helpers, dead code, unused imports, temporary dumps, and duplicate implementations. Propose deletions before deleting user or project files. | Cleanup report, approved changes, test results |
| `check security` | Run the security review defined by `[SEC-10]`. Do not claim absolute protection. | Findings by severity, evidence, remediation plan |
| `run tests` | Run every applicable test discovered by the configured test runner and report unavailable environments honestly. | Passed, failed, skipped, unavailable, duration |
| `package` | Build and validate a staging artifact. Do not update Share without explicit release approval. | Staging path, manifest, tests, checksum |
| `sync share` | Request/confirm release approval, run release gates, preserve the previous release, then update Share atomically. | Release report, final artifacts, rollback reference |
| `showcase` | Launch the centralized UI design-system showcase in Maya. | Interactive widget/theme gallery |
| `audit rules` | Compare the repository with this rulebook. | Implemented/Partial/Missing/N/A compliance report |

---

## 12. Mandatory Rule Execution Order

When the user requests `audit rules`, `run all rules`, a major migration, or a release-readiness pass, work MUST proceed in this order. A later phase MUST NOT be used to hide or bypass a failure from an earlier phase.

| Phase | Rule groups | Required outcome |
|---:|---|---|
| 1 | `[GOV]`, `[RUNTIME]` | Confirm scope, precedence, supported environment, exceptions, and definition of done. |
| 2 | `[ARCH]` | Validate package structure, dependency direction, isolation, public APIs, and centralized ownership. |
| 3 | `[FW]`, `[UI]` | Validate manifests, capabilities, lifecycle, dialogs, callbacks, styling, and service registration. |
| 4 | `[CORE]` | Validate selection, scene impact, references, undo, user context, temporary nodes, units, cancellation, and performance. |
| 5 | `[DATA]` | Validate paths, settings, schemas, snapshots, immutable versions, atomic exports, presets, and provenance. |
| 6 | `[TEST]` | Run applicable unit, headless, Maya, Qt, installer, regression, and package tests; report unavailable tests honestly. |
| 7 | `[SEC]` | Validate authorization, safe revocation, secrets, privacy, transport, package boundaries, and non-destructive failure. |
| 8 | `[DIST]` | Build and validate a staging package, installation manifest, compatibility preflight, update, and rollback. |
| 9 | `[DOC]` | Synchronize user, API, architecture, support, changelog, and release documentation. |
| 10 | `[ARCH-07]` | Remove verified unused code/files exposed by the completed work, then rerun affected tests. |
| 11 | Release checklist | Produce the compliance report and request explicit release approval. |
| 12 | Approved promotion | Back up the current Share release and atomically promote the validated artifact. |

**Stop Rule:** Critical safety, data-loss, architecture-boundary, test, security, or package-integrity failures block subsequent release phases. Non-release audits MAY continue collecting findings, but MUST preserve the failed status.

**Revalidation Rule:** Changes made in phases 7–10 MUST rerun every affected earlier validation before approval.

---

## 13. Release Checklist

A ScarTools release is approved only when all applicable items pass:

- [ ] Supported Maya/Python/Qt target identified
- [ ] Manifest validation passed
- [ ] Import-boundary tests passed
- [ ] Unused code/files introduced or exposed by the change were removed under `[ARCH-07]`
- [ ] Pure Python and `mayapy` tests passed
- [ ] Maya integration smoke test passed
- [ ] UI open/close lifecycle test passed
- [ ] Installer/package smoke test passed
- [ ] Package allowlist passed
- [ ] No admin tools, secrets, tests, or temporary files included
- [ ] Exported data schema and migrations validated
- [ ] Artist documentation updated for user-visible changes
- [ ] Changelog and support matrix updated
- [ ] Artifact checksum generated
- [ ] Previous release preserved for rollback
- [ ] Explicit release approval recorded

---

## Change Notes

### Version 3.0.0

- Added a mandatory 12-phase execution order for audits, migrations, and releases.
- Added suite-level rules for definition of done, compliance audits, tool isolation, deprecation, scene-impact declarations, framework capabilities, shared dialogs, and callback ownership.
- Added selection, scene-save, temporary-node, unknown-node, units, context-preservation, cancellation, and large-scene protections.
- Added central settings, settings schemas, immutable publishes, partial-publish prevention, export provenance, and preset ownership.
- Added owned-file installation manifests, compatibility preflight, atomic updates, rollback, and one approved installer entry point.
- Clarified safe authorized remote deactivation: license and UI access may be disabled, but files and artist data are never remotely wiped.

### Version 2.1.0

- Added a mandatory, verified cleanup rule for unused code, duplicate helpers, obsolete compatibility layers, stale outputs, and unreferenced files.
- Added safeguards for dynamic imports, Maya shelves, manifests, installers, resources, user data, active releases, and production assets during cleanup.
- Strengthened documentation synchronization so affected documentation is updated in the same reviewed change.
- Added cleanup verification to the release checklist.

### Version 2.0.0

- Reorganized the document into enforceable engineering categories.
- Added requirement levels, precedence, exceptions, and compliance status.
- Removed remote wipe, zero-fill deletion, and offline self-shredding behaviour.
- Changed automatic Share deployment to Test/Staging-first with explicit release approval.
- Added runtime support, dependency direction, main-thread safety, data schemas, test layers, rollback, and package integrity rules.
- Clarified that bytecode is packaging rather than strong security.
- Preserved the centralized UI/framework direction and the no-legacy-compatibility policy.
