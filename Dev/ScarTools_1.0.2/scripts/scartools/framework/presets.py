# -*- coding: utf-8 -*-
"""Centralized headless JSON Preset Manager for ScarTools suite."""

from __future__ import absolute_import, division, print_function

import json
import os


class PresetManager(object):
    """Handles persistent JSON user presets for tools in ~/.scartools/presets/<tool_id>/."""

    def __init__(self, tool_id):
        self.tool_id = str(tool_id or "general")
        self.dir_path = os.path.join(os.path.expanduser("~"), ".scartools", "presets", self.tool_id)
        os.makedirs(self.dir_path, exist_ok=True)

    def list_presets(self):
        if not os.path.exists(self.dir_path):
            return []
        files = [f[:-5] for f in os.listdir(self.dir_path) if f.endswith(".json")]
        return sorted(files)

    def save_preset(self, name, data):
        clean_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")).strip()
        if not clean_name:
            return False
        p = os.path.join(self.dir_path, clean_name + ".json")
        with open(p, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)
        return True

    def load_preset(self, name):
        p = os.path.join(self.dir_path, name + ".json")
        if not os.path.exists(p):
            return None
        with open(p, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def delete_preset(self, name):
        p = os.path.join(self.dir_path, name + ".json")
        if os.path.exists(p):
            os.remove(p)
            return True
        return False


__all__ = ["PresetManager"]
