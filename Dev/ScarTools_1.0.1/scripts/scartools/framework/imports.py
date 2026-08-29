"""Small lazy-import helpers shared by manifests and pipeline integrations."""

from __future__ import print_function

import importlib


def _parts(entry_point):
    value = str(entry_point or "").strip()
    module_name, separator, attribute_name = value.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError(
            "Entry point must use 'python.module:callable_name' syntax."
        )
    return module_name, attribute_name


def entry_point_module(entry_point):
    """Return only the module portion without importing it."""
    return _parts(entry_point)[0]


def load_entry_point(entry_point):
    """Import and return a callable declared as ``module:attribute``."""
    module_name, attribute_name = _parts(entry_point)
    module = importlib.import_module(module_name)
    value = getattr(module, attribute_name, None)
    if not callable(value):
        raise TypeError("Entry point is not callable: {}".format(entry_point))
    return value
