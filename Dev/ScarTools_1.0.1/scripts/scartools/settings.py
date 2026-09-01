# -*- coding: utf-8 -*-
"""
Centralized Persistent Settings Engine for ScarTools Studio Suite.

Stores user preferences and tool states in both:
1. Local studio directory: ~/.scartools/settings.json (resilient to Maya prefs resets)
2. Maya optionVar: ScarTools_<key> (fast in-memory Maya query cache)
"""

from __future__ import absolute_import, division, print_function

import os
import json
import tempfile
import maya.cmds as cmds


PREFIX = "ScarTools_"
SETTINGS_DIR = os.path.join(os.path.expanduser("~"), ".scartools")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
_FALLBACK_STORE = {}


def _name(key):
    return PREFIX + str(key)


def _has_maya_option_var():
    return hasattr(cmds, "optionVar") and callable(getattr(cmds, "optionVar", None))


def _ensure_dir():
    try:
        if not os.path.exists(SETTINGS_DIR):
            os.makedirs(SETTINGS_DIR)
    except Exception:
        pass


def _load_disk_store():
    """Load settings dictionary from ~/.scartools/settings.json."""
    if not os.path.isfile(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_disk_store(data):
    """Atomically write settings dictionary to ~/.scartools/settings.json."""
    _ensure_dir()
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(prefix=".settings_", suffix=".tmp", dir=SETTINGS_DIR)
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if os.path.exists(SETTINGS_FILE):
            try:
                os.remove(SETTINGS_FILE)
            except Exception:
                pass
        os.rename(tmp_path, SETTINGS_FILE)
    except Exception:
        pass


def get_string(key, default=""):
    name = _name(key)
    # 1. Try Maya optionVar
    if _has_maya_option_var():
        try:
            if cmds.optionVar(exists=name):
                value = cmds.optionVar(query=name)
                if value is not None:
                    return str(value)
        except Exception:
            pass

    # 2. Try disk store ~/.scartools/settings.json
    disk = _load_disk_store()
    if key in disk:
        val = str(disk[key])
        # Resync to optionVar for fast access
        if _has_maya_option_var():
            try:
                cmds.optionVar(stringValue=(name, val))
            except Exception:
                pass
        return val

    # 3. Fallback memory store
    return str(_FALLBACK_STORE.get(name, default))


def set_string(key, value):
    name = _name(key)
    str_val = str(value)
    _FALLBACK_STORE[name] = str_val

    # 1. Update Maya optionVar
    if _has_maya_option_var():
        try:
            cmds.optionVar(stringValue=(name, str_val))
        except Exception:
            pass

    # 2. Persist into ~/.scartools/settings.json
    disk = _load_disk_store()
    disk[str(key)] = str_val
    _save_disk_store(disk)

    return name


def get_bool(key, default=False):
    name = _name(key)
    if _has_maya_option_var():
        try:
            if cmds.optionVar(exists=name):
                return bool(cmds.optionVar(query=name))
        except Exception:
            pass

    disk = _load_disk_store()
    if key in disk:
        val = bool(disk[key])
        if _has_maya_option_var():
            try:
                cmds.optionVar(intValue=(name, 1 if val else 0))
            except Exception:
                pass
        return val

    return bool(_FALLBACK_STORE.get(name, default))


def set_bool(key, value):
    name = _name(key)
    bool_val = bool(value)
    _FALLBACK_STORE[name] = bool_val

    if _has_maya_option_var():
        try:
            cmds.optionVar(intValue=(name, 1 if bool_val else 0))
        except Exception:
            pass

    disk = _load_disk_store()
    disk[str(key)] = bool_val
    _save_disk_store(disk)

    return name


def get_int(key, default=0):
    name = _name(key)
    if _has_maya_option_var():
        try:
            if cmds.optionVar(exists=name):
                return int(cmds.optionVar(query=name))
        except Exception:
            pass

    disk = _load_disk_store()
    if key in disk:
        try:
            val = int(disk[key])
            if _has_maya_option_var():
                try:
                    cmds.optionVar(intValue=(name, val))
                except Exception:
                    pass
            return val
        except Exception:
            pass

    return int(_FALLBACK_STORE.get(name, default))


def set_int(key, value):
    name = _name(key)
    int_val = int(value)
    _FALLBACK_STORE[name] = int_val

    if _has_maya_option_var():
        try:
            cmds.optionVar(intValue=(name, int_val))
        except Exception:
            pass

    disk = _load_disk_store()
    disk[str(key)] = int_val
    _save_disk_store(disk)

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
    disk = _load_disk_store()
    if str(key) in disk:
        del disk[str(key)]
        _save_disk_store(disk)


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
    "SETTINGS_DIR",
    "SETTINGS_FILE",
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
