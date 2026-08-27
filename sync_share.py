# -*- coding: utf-8 -*-
"""
ScarTools 1-Click Master Sync and Auto-Packaging Tool.

Discovers the active Dev/ScarTools_<version>, runs all unit tests in mayapy,
compiles protected .pyc bytecode into Share/ScarTools_<version>, strips Admin docs,
and builds clean release zip packages.
"""

from __future__ import print_function

import compileall
import os
import re
import shutil
import subprocess
import sys
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCARPIPELINE_ROOT = SCRIPT_DIR if os.path.isdir(os.path.join(SCRIPT_DIR, "Dev")) else os.path.dirname(SCRIPT_DIR)
DEV_ROOT = os.path.join(SCARPIPELINE_ROOT, "Dev")
SHARE_ROOT = os.path.join(SCARPIPELINE_ROOT, "Share")
MAYAPY_PATH = r"C:\Program Files\Autodesk\Maya2023\bin\mayapy.exe"

EXCLUDE_DIRS = {"admin_tools", "tests", "__pycache__", ".git", ".idea", ".vscode", ".user_uploaded"}
EXCLUDE_FILES = {
    "GEMINI.md",
    "RULES_DICTIONARY.md",
    "design_system_showcase.html",
    "showcase.py",
}
EXCLUDE_EXTS = {".pyc", ".pyo", ".tmp"}


def find_active_dev_version():
    """Find the highest active version folder inside Dev/."""
    candidates = []
    for item in os.listdir(DEV_ROOT):
        full = os.path.join(DEV_ROOT, item)
        if os.path.isdir(full) and item.startswith("ScarTools_"):
            version_str = item.replace("ScarTools_", "")
            parts = [int(p) if p.isdigit() else p for p in version_str.split(".")]
            candidates.append((parts, item, full))

    if not candidates:
        raise RuntimeError("No ScarTools_<version> folders found in: {}".format(DEV_ROOT))

    candidates.sort()
    latest_parts, latest_folder_name, latest_full_path = candidates[-1]
    return latest_folder_name, latest_full_path


def sanitize_documentation_html(doc_path):
    """Strip all admin sections marked with <!-- ADMIN_ONLY_START --> ... <!-- ADMIN_ONLY_END -->."""
    if not os.path.isfile(doc_path):
        return
    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"<!--\s*ADMIN_ONLY_START\s*-->.*?<!--\s*ADMIN_ONLY_END\s*-->"
    sanitized = re.sub(pattern, "", content, flags=re.DOTALL)

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(sanitized)


def compile_share_package(source_dir, target_dir):
    """Compile raw .py sources into .pyc bytecode and stage to Share/."""
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)
    os.makedirs(target_dir, exist_ok=True)

    # 1. Copy files
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        rel_path = os.path.relpath(root, source_dir)
        dest_dir = os.path.join(target_dir, rel_path) if rel_path != "." else target_dir
        os.makedirs(dest_dir, exist_ok=True)

        for f in files:
            if any(f.endswith(ext) for ext in EXCLUDE_EXTS):
                continue
            if f in EXCLUDE_FILES:
                continue

            src_file = os.path.join(root, f)
            dst_file = os.path.join(dest_dir, f)
            shutil.copy2(src_file, dst_file)

    # 2. Redact documentation in Share
    doc_path = os.path.join(target_dir, "ScarTools_Documentation.html")
    sanitize_documentation_html(doc_path)

    # 3. Compile bytecode (.py -> .pyc)
    python_exe = MAYAPY_PATH if os.path.exists(MAYAPY_PATH) else sys.executable
    compile_cmd = [
        python_exe,
        "-m",
        "compileall",
        "-b",
        "-q",
        target_dir
    ]
    subprocess.call(compile_cmd)

    # 4. Remove raw .py sources inside scripts/ (preserve drag_drop_install.py and plug-ins/scartools_startup.py)
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            if f.endswith(".py") and f not in ["drag_drop_install.py", "scartools_startup.py"]:
                os.remove(os.path.join(root, f))
            elif f.endswith(".cpython-39.pyc") or f.endswith(".cpython-310.pyc"):
                # Normalize bytecode names
                clean_name = re.sub(r"\.cpython-\d+", "", f)
                clean_path = os.path.join(root, clean_name)
                if not os.path.exists(clean_path):
                    shutil.move(os.path.join(root, f), clean_path)

    # 5. Clean up any leftover __pycache__ folders in target
    for root, dirs, files in os.walk(target_dir, topdown=False):
        if os.path.basename(root) == "__pycache__":
            shutil.rmtree(root, ignore_errors=True)


def build_zip_package(target_dir, zip_path):
    """Build clean distribution .zip from compiled Share folder."""
    if os.path.exists(zip_path):
        os.remove(zip_path)

    base_name = os.path.basename(target_dir)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(target_dir):
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, target_dir)
                archive_name = os.path.join(base_name, rel_path)
                zipf.write(full_path, archive_name)


def run_sync(target_version_dir=None):
    if not target_version_dir:
        folder_name, target_version_dir = find_active_dev_version()
    else:
        folder_name = os.path.basename(target_version_dir)

    share_version_dir = os.path.join(SHARE_ROOT, folder_name)
    share_zip_path = os.path.join(SHARE_ROOT, "{}.zip".format(folder_name))

    print("=" * 68)
    print("  SCARTOOLS MASTER AUTO-SYNC TO SHARE")
    print("=" * 68)
    print("Active Dev Version : {}".format(folder_name))
    print("Dev Directory      : {}".format(target_version_dir))
    print("Share Directory    : {}".format(share_version_dir))
    print("Share Archive      : {}".format(share_zip_path))
    print("-" * 68)

    # 1. Run unit tests
    test_dir = os.path.join(target_version_dir, "tests")
    if os.path.isdir(test_dir) and os.path.exists(MAYAPY_PATH):
        print("\n[1/3] Running Maya Unit Tests (mayapy)...")
        cmd = [MAYAPY_PATH, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
        res = subprocess.call(cmd, cwd=target_version_dir)
        if res != 0:
            print("\n[ERROR] Tests failed! Aborting sync to Share.")
            sys.exit(1)
        print("  OK: All unit tests passed!")
    else:
        print("\n[1/3] Skipping tests (no mayapy or tests directory).")

    # 2. Compile .pyc Bytecode to Share
    print("\n[2/3] Compiling .pyc Bytecode to Share/...")
    compile_share_package(target_version_dir, share_version_dir)
    print("  OK: Bytecode compiled and documentation sanitized in Share/.")

    # 3. Build Distribution Zip Archive
    print("\n[3/3] Building Distribution Zip Archive...")
    build_zip_package(share_version_dir, share_zip_path)
    print("  OK: Release archive created at {}".format(share_zip_path))

    print("\n" + "=" * 68)
    print("  OK: SYNC COMPLETE - {} DEPLOYED TO SHARE/".format(folder_name))
    print("=" * 68)


if __name__ == "__main__":
    custom_dir = sys.argv[1] if len(sys.argv) > 1 else None
    run_sync(custom_dir)
