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
        abc = cfg["alembic"]
        fbx = cfg["fbx"]
        self.assertTrue(abc.get("write_velocities"))
        self.assertEqual(abc.get("step"), 1.0)
        self.assertEqual(abc.get("handles"), 0)
        self.assertTrue(abc.get("uvs"))
        self.assertTrue(abc.get("normals"))
        self.assertEqual(fbx.get("up_axis"), "Y-Up")
        self.assertEqual(fbx.get("fbx_version"), "FBX 2020")
        self.assertTrue(fbx.get("smoothing_groups"))

    def test_save_custom_settings(self):
        custom = {
            "alembic": {
                "write_velocities": False,
                "step": 0.5,
                "handles": 5,
            },
            "fbx": {
                "up_axis": "Z-Up",
                "fbx_version": "FBX 2018",
                "triangulate": True,
            },
        }
        save_anim_export_settings(custom)
        loaded = get_anim_export_settings()
        self.assertFalse(loaded["alembic"]["write_velocities"])
        self.assertEqual(loaded["alembic"]["step"], 0.5)
        self.assertEqual(loaded["alembic"]["handles"], 5)
        self.assertEqual(loaded["fbx"]["up_axis"], "Z-Up")
        self.assertEqual(loaded["fbx"]["fbx_version"], "FBX 2018")
        self.assertTrue(loaded["fbx"]["triangulate"])

    def test_reset_settings(self):
        save_anim_export_settings({
            "fbx": {"up_axis": "Z-Up"},
            "alembic": {"step": 0.25},
        })
        reset_anim_export_settings()
        loaded = get_anim_export_settings()
        self.assertEqual(loaded["fbx"]["up_axis"], "Y-Up")
        self.assertEqual(loaded["alembic"]["step"], 1.0)


if __name__ == "__main__":
    unittest.main()
