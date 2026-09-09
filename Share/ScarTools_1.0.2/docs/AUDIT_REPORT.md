# ScarTools Codebase Audit Report (v1.0.2)

**Prepared by:** Agent 1 — Codebase Audit Agent  
**Date:** 2026-09-09  
**Target Release:** ScarTools v1.0.2  

---

## Executive Summary
An exhaustive audit of the ScarTools repository was conducted to inspect folder structure, architectural decoupling, exception handling, code duplication, and runtime performance. The suite demonstrates solid DCC patterns (undo transactions, DAG long names, hardware node-locking), but exhibits areas for significant architectural refinement in modularity, error logging, test separation, and UI centralization.

---

## 1. Identified Architecture & Maintainability Issues

### Issue 1.1: Monolithic Skin Operations Monolith
- **Location:** scripts/scartools/tools/skin/operations.py (114.9 KB, 2,800+ lines).
- **Severity:** High
- **Analysis:** Contains copy, mirror, weights export/import, transfer, vertex unbinding, cluster inspection, and topology checking all in a single massive file. Highly difficult to debug or extend without regression risks.
- **Recommended Solution:** Modularize into dedicated sub-packages:
  - 	ools/skin/operations/copy.py
  - 	ools/skin/operations/mirror.py
  - 	ools/skin/operations/transfer.py
  - 	ools/skin/operations/cleanup.py
  - 	ools/skin/operations/validation.py
  - 	ools/skin/operations/weights.py
  - Maintain backwards-compatible exports in 	ools/skin/operations/__init__.py.
- **Expected Impact:** 100% API compatibility, improved maintainability, and isolated unit testing.

### Issue 1.2: Bare Exception Trapping (except Exception: return False)
- **Location:** 338 instances across scripts/scartools/ (e.g. 	ransactions.py, importer.py, lifecycle.py).
- **Severity:** High
- **Analysis:** Suppresses critical underlying syntax errors, missing attributes, or Maya API exceptions, rendering headless failures silent and impossible to diagnose remotely.
- **Recommended Solution:**
  - Create a structured exception hierarchy in ramework/errors/: ScarToolsError, ValidationError, SkinOperationError, ExportError, LicenseError, ToolExecutionError.
  - Replace silent catches with structured logging and explicit error raising.
- **Expected Impact:** Immediate diagnostic visibility, no silent failures, informative user alerts.

### Issue 1.3: UI System Duplication & Monolithic Widgets
- **Location:** ui/components.py, ui/refactored_components.py, ui/controls.py, ui/__init__.py (44.1 KB).
- **Severity:** Medium
- **Analysis:** UI controls are scattered across legacy and refactored components with duplicate definitions for badges, buttons, and panels.
- **Recommended Solution:**
  - Establish a single cohesive ui/core/ package: utton.py, checkbox.py, dropdown.py, panel.py, window.py.
  - Re-export centralized controls cleanly from ui/core/__init__.py.
- **Expected Impact:** Single source of truth for all DCC dialogs, eliminates visual inconsistencies.

---

## 2. Test Architecture & DCC Decoupling

### Issue 2.1: Coupled Maya & Pure Python Tests
- **Location:** 	ests/ root directory (all test files mixed together).
- **Severity:** Medium
- **Analysis:** Standalone CI/CD or developers without Maya installed cannot run headless unit tests (pytest) because tests are co-mingled with Maya C++ dependent test files.
- **Recommended Solution:**
  - Partition into:
    - 	ests/unit/: Pure Python tests runnable with standard pytest (	est_settings.py, 	est_validation.py, 	est_naming.py, 	est_manifest.py).
    - 	ests/maya/: Maya DCC tests executed in mayapy.exe (	est_skin.py, 	est_anim_io.py, 	est_movable_pivot.py, 	est_licensing.py).
- **Expected Impact:** Fast unit test cycles on developer machines and isolated Maya DCC validation.

---

## 3. Diagnostic & Error Reporting Systems

### Issue 3.1: Lack of Crash Package Generation
- **Location:** ramework/
- **Severity:** Medium
- **Analysis:** When an unhandled exception or crash occurs on an artist workstation, TDs have no easy way to inspect scene context, Maya version, Python version, or stack trace without manually digging through user temp directories.
- **Recommended Solution:**
  - Implement ramework/crash_reporter/ to intercept critical failures and generate ScarTools_Crash_Report.zip containing logs, system diagnostics, active tool ID, and stack trace.
- **Expected Impact:** 1-click bug reporting for artists; instant triage for pipeline engineers.

### Issue 3.2: Missing Centralized Health Check Diagnostic
- **Location:** ramework/
- **Severity:** Low to Medium
- **Analysis:** Difficult to verify if a remote artist has required plugins loaded (bxmaya, AbcExport), correct Qt bindings, valid filesystem permissions, or active license status before launching heavy operations.
- **Recommended Solution:**
  - Add ramework/diagnostics/health_check.py with UI inspector in Maya menu (ScarTools -> Diagnostics -> Health Check...).
- **Expected Impact:** Proactive prevention of tool crashes before artists start work.

---

## Summary of Action Plan for v1.0.2
1. **Agent 2**: Restructure 	ests/ into unit/ and maya/.
2. **Agent 3**: Implement ramework/errors/, ramework/logging/, and ramework/crash_reporter/.
3. **Agent 4**: Modularize 	ools/skin/operations.py into dedicated submodules.
4. **Agent 5**: Consolidate UI controls into ui/core/.
5. **Agent 6**: Enforce lazy loading during Maya startup.
6. **Agent 7**: Implement the Suite Health Check tool.
7. **Agent 8**: Verify security and session token seals.
8. **Agent 9**: Validate, package, and generate v1.0.2 distribution.
