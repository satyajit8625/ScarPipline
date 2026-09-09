"""Shared access to the headless Maya stubs used by unit tests.

The release test module lives under ``tests/maya`` so Maya's test runner can
discover it.  Pure-Python tests add only ``tests`` to ``sys.path``; this small
shim loads that module without requiring Maya or duplicating the stub code.
"""

from __future__ import absolute_import, division, print_function

import importlib.util
from pathlib import Path


_RELEASE_TEST = Path(__file__).resolve().parent / "maya" / "test_release.py"
_SPEC = importlib.util.spec_from_file_location(
    "_scartools_maya_release_tests", str(_RELEASE_TEST)
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("Unable to load Maya release-test helpers: {}".format(_RELEASE_TEST))

_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

install_maya_stubs = _MODULE.install_maya_stubs

__all__ = ["install_maya_stubs"]
