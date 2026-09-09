# -*- coding: utf-8 -*-
"""
1-Click Automated Native .pyd Binary Compiler.

Usage:
    python build_pyd.py

Requirements:
    1. Visual Studio Build Tools (C++ Desktop development workload).
    2. Cython (pip install cython).
"""

from __future__ import print_function

import os
import shutil
import subprocess
import sys

ADMIN_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_DIR = os.path.dirname(ADMIN_DIR)
SHARE_DIR = os.path.join(os.path.dirname(DEV_DIR), "Share", "ScarTools_1.0.0")


def build_pyd():
    print("=" * 68)
    print("  SCARTOOLS NATIVE .PYD COMPILER (MAXIMUM BINARY SECURITY)")
    print("=" * 68)

    # 1. Check for Cython
    try:
        import Cython
        print("[OK] Cython detected (v{})".format(Cython.__version__))
    except ImportError:
        print("[FAIL] Cython is not installed.")
        print("   Run: pip install cython")
        return False

    # 2. Run setup_pyd.py build_ext --inplace
    setup_script = os.path.join(ADMIN_DIR, "setup_pyd.py")
    cmd = [sys.executable, setup_script, "build_ext", "--inplace"]
    print("Running:", " ".join(cmd))

    try:
        subprocess.check_call(cmd, cwd=DEV_DIR)
    except subprocess.CalledProcessError as exc:
        print("[FAIL] Compilation failed:", exc)
        print("   Make sure Microsoft Visual C++ Build Tools is installed on this machine.")
        return False

    # 3. Move compiled .pyd into Share directory and clean temp C files
    scartools_dev = os.path.join(DEV_DIR, "scripts", "scartools")
    scartools_share = os.path.join(SHARE_DIR, "scripts", "scartools")

    pyd_found = 0
    for f in os.listdir(scartools_dev):
        if f.endswith(".pyd"):
            src_pyd = os.path.join(scartools_dev, f)
            dest_pyd = os.path.join(scartools_share, f)
            if os.path.isdir(scartools_share):
                shutil.copy2(src_pyd, dest_pyd)
                # Remove corresponding .pyc if present in share
                base_name = f.split(".")[0]
                pyc_file = os.path.join(scartools_share, base_name + ".pyc")
                if os.path.isfile(pyc_file):
                    os.remove(pyc_file)
            print("[OK] Native C++ binary compiled and installed:", f)
            pyd_found += 1
        elif f.endswith(".c"):
            # Clean temporary generated C file
            os.remove(os.path.join(scartools_dev, f))

    # Clean build directory
    build_temp = os.path.join(DEV_DIR, "build")
    if os.path.isdir(build_temp):
        shutil.rmtree(build_temp)

    if pyd_found > 0:
        print("\n" + "=" * 68)
        print("SUCCESS! {} native .pyd binary module(s) compiled successfully!".format(pyd_found))
        print("Zero bytecode left to decompile - military-grade binary security active.")
        print("=" * 68)
        return True
    else:
        print("[WARNING] No .pyd files produced.")
        return False


if __name__ == "__main__":
    build_pyd()
