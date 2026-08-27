"""Namespaced Maya optionVar settings store for all ScarTools tools and UI state."""

from __future__ import absolute_import, division, print_function

import json
import maya.cmds as cmds


PREFIX = "ScarTools_"
_FALLBACK_STORE = {}


def _name(key):
    return PREFIX + str(key)


def _has_maya_option_var():
    return hasattr(cmds, "optionVar") and callable(getattr(cmds, "optionVar", None))


def get_string(key, default=""):
    name = _name(key)
    if _has_maya_option_var():
        try:
            if not cmds.optionVar(exists=name):
                return default
            value = cmds.optionVar(query=name)
            return str(value) if value is not None else default
        except Exception:
            pass
    return str(_FALLBACK_STORE.get(name, default))


def set_string(key, value):
    name = _name(key)
    _FALLBACK_STORE[name] = str(value)
    if _has_maya_option_var():
        try:
            cmds.optionVar(stringValue=(name, str(value)))
        except Exception:
            pass
    return name


def get_bool(key, default=False):
    name = _name(key)
    if _has_maya_option_var():
        try:
            if not cmds.optionVar(exists=name):
                return bool(default)
            return bool(cmds.optionVar(query=name))
        except Exception:
            pass
    return bool(_FALLBACK_STORE.get(name, default))


def set_bool(key, value):
    name = _name(key)
    _FALLBACK_STORE[name] = bool(value)
    if _has_maya_option_var():
        try:
            cmds.optionVar(intValue=(name, 1 if value else 0))
        except Exception:
            pass
    return name


def get_int(key, default=0):
    name = _name(key)
    if _has_maya_option_var():
        try:
            if not cmds.optionVar(exists=name):
                return int(default)
            return int(cmds.optionVar(query=name))
        except Exception:
            pass
    return int(_FALLBACK_STORE.get(name, default))


def set_int(key, value):
    name = _name(key)
    _FALLBACK_STORE[name] = int(value)
    if _has_maya_option_var():
        try:
            cmds.optionVar(intValue=(name, int(value)))
        except Exception:
            pass
    return name


def get_json(key, default=None):
    raw = get_string(key, "")
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def set_json(key, value):
    raw = json.dumps(value)
    return set_string(key, raw)


def remove(key):
    name = _name(key)
    if name in _FALLBACK_STORE:
        del _FALLBACK_STORE[name]
    if _has_maya_option_var():
        try:
            if cmds.optionVar(exists=name):
                cmds.optionVar(remove=name)
        except Exception:
            pass


class ToolSettings(object):
    """Scoped settings manager bound to a specific tool_id."""

    def __init__(self, tool_id):
        self.tool_id = str(tool_id)

    def _k(self, key):
        return "{}_{}".format(self.tool_id, key)

    def get_string(self, key, default=""):
        return get_string(self._k(key), default)

    def set_string(self, key, value):
        return set_string(self._k(key), value)

    def get_bool(self, key, default=False):
        return get_bool(self._k(key), default)

    def set_bool(self, key, value):
        return set_bool(self._k(key), value)

    def get_int(self, key, default=0):
        return get_int(self._k(key), default)

    def set_int(self, key, value):
        return set_int(self._k(key), value)

    def get_json(self, key, default=None):
        return get_json(self._k(key), default)

    def set_json(self, key, value):
        return set_json(self._k(key), value)

    def remove(self, key):
        remove(self._k(key))


__all__ = [
    "PREFIX",
    "get_string",
    "set_string",
    "get_bool",
    "set_bool",
    "get_int",
    "set_int",
    "get_json",
    "set_json",
    "remove",
    "ToolSettings",
]
