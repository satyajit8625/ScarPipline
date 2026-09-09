# -*- coding: utf-8 -*-
"""
Cython Build Script for ScarTools Native C++ .pyd Binary Compilation.

Compiles critical security modules (e.g. licensing, core controllers)
into raw x86_64 Machine Code Windows DLLs (.pyd), leaving zero bytecode to decompile.
"""

import os
import sys
from setuptools import setup, Extension

try:
    from Cython.Build import cythonize
except ImportError:
    print("ERROR: Cython is required. Run 'pip install cython'.")
    sys.exit(1)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

# Target modules to compile into native C++ .pyd binaries
extensions = [
    Extension(
        "scartools.licensing",
        [os.path.join(SCRIPTS_DIR, "scartools", "licensing.py")],
        extra_compile_args=["/O2", "/fp:fast"],
    ),
    Extension(
        "scartools.framework.transactions",
        [os.path.join(SCRIPTS_DIR, "scartools", "framework", "transactions.py")],
        extra_compile_args=["/O2", "/fp:fast"],
    ),
    Extension(
        "scartools.framework.controller",
        [os.path.join(SCRIPTS_DIR, "scartools", "framework", "controller.py")],
        extra_compile_args=["/O2", "/fp:fast"],
    ),
    Extension(
        "scartools.framework.operations",
        [os.path.join(SCRIPTS_DIR, "scartools", "framework", "operations.py")],
        extra_compile_args=["/O2", "/fp:fast"],
    ),
]

setup(
    name="scartools_native",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "always_allow_keywords": True,
            "embedsignature": False,
        },
    ),
)
