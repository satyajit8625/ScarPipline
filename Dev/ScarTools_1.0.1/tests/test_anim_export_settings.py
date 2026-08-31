# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
try:
    import maya.standalone
    maya.standalone.initialize(name="python")
except Exception:
    pass

import maya.cmds as cmds

from scartools.tools.anim_io.ui.settings_dialog import (
    get_anim_export_settings,
    save_anim_export_settings,
    reset_anim_export_settings,
    DEFAULT_SETTINGS,
)


class TestAnimExportSettings(unittest.TestCase):
    def setUp(self):
        reset_anim_export_settings()

    def test_default_settings(self):
        cfg = get_anim_export_settings()
        self.assertTrue(cfg.get("abc_write_velocities"))
        self.assertEqual(cfg.get("abc_step"), 1.0)
        self.assertEqual(cfg.get("abc_handles"), 0)
        self.assertEqual(cfg.get("fbx_up_axis"), "Y-Up")
        self.assertEqual(cfg.get("fbx_version"), "FBX 2020")
        self.assertTrue(cfg.get("fbx_smoothing_groups"))

    def test_save_custom_settings(self):
        custom = {
            "abc_write_velocities": False,
            "abc_step": 0.5,
            "abc_handles": 5,
            "fbx_up_axis": "Z-Up",
            "fbx_version": "FBX 2018",
            "fbx_triangulate": True,
        }
        save_anim_export_settings(custom)
        loaded = get_anim_export_settings()
        self.assertFalse(loaded["abc_write_velocities"])
        self.assertEqual(loaded["abc_step"], 0.5)
        self.assertEqual(loaded["abc_handles"], 5)
        self.assertEqual(loaded["fbx_up_axis"], "Z-Up")
        self.assertEqual(loaded["fbx_version"], "FBX 2018")
        self.assertTrue(loaded["fbx_triangulate"])

    def test_reset_settings(self):
        save_anim_export_settings({"fbx_up_axis": "Z-Up", "abc_step": 0.25})
        reset_anim_export_settings()
        loaded = get_anim_export_settings()
        self.assertEqual(loaded["fbx_up_axis"], "Y-Up")
        self.assertEqual(loaded["abc_step"], 1.0)


if __name__ == "__main__":
    unittest.main()
