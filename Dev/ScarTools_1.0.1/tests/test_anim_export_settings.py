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
    DEFAULT_ALEMBIC_SETTINGS,
    DEFAULT_FBX_SETTINGS,
)


class TestAnimExportSettings(unittest.TestCase):
    def setUp(self):
        reset_anim_export_settings()

    def test_default_settings(self):
        cfg = get_anim_export_settings()
        abc = cfg["alembic"]
        fbx = cfg["fbx"]

        # Alembic defaults
        self.assertEqual(abc.get("step"), 1.0)
        self.assertTrue(abc.get("uvs"))
        self.assertTrue(abc.get("all_uv_sets"))
        self.assertTrue(abc.get("normals"))
        self.assertTrue(abc.get("visibility"))
        self.assertTrue(abc.get("face_sets"))
        self.assertFalse(abc.get("color_sets"))
        self.assertFalse(abc.get("auto_subd"))
        self.assertFalse(abc.get("renderable_only"))
        self.assertTrue(abc.get("world_space"))
        self.assertFalse(abc.get("euler_filter"))
        self.assertFalse(abc.get("user_attributes"))
        self.assertEqual(abc.get("attribute_prefix"), "ABC_")
        self.assertTrue(abc.get("strip_namespaces"))
        self.assertEqual(abc.get("data_format"), "Ogawa")

        # FBX defaults
        self.assertTrue(fbx.get("bake_animation"))
        self.assertEqual(fbx.get("step"), 1)
        self.assertTrue(fbx.get("resample"))
        self.assertFalse(fbx.get("euler_filter"))
        self.assertFalse(fbx.get("constant_key_reducer"))
        self.assertEqual(fbx.get("quaternion_mode"), "Resample")
        self.assertTrue(fbx.get("skin"))
        self.assertTrue(fbx.get("blend_shapes"))
        self.assertTrue(fbx.get("smoothing_groups"))
        self.assertTrue(fbx.get("tangents_binormals"))
        self.assertFalse(fbx.get("smooth_mesh"))
        self.assertFalse(fbx.get("triangulate"))
        self.assertTrue(fbx.get("cameras"))
        self.assertFalse(fbx.get("lights"))
        self.assertFalse(fbx.get("constraints"))
        self.assertFalse(fbx.get("input_connections"))
        self.assertFalse(fbx.get("preserve_instances"))
        self.assertEqual(fbx.get("units"), "Centimeters")
        self.assertEqual(fbx.get("up_axis"), "Y")
        self.assertEqual(fbx.get("file_type"), "Binary")
        self.assertEqual(fbx.get("fbx_version"), "FBX 2020")
        self.assertFalse(fbx.get("embed_media"))
        self.assertTrue(fbx.get("strip_namespaces"))

    def test_save_custom_settings(self):
        custom = {
            "alembic": {
                "step": 0.5,
                "color_sets": True,
                "auto_subd": True,
                "data_format": "HDF5",
                "attribute_prefix": "CUSTOM_",
            },
            "fbx": {
                "up_axis": "Z",
                "fbx_version": "FBX 2018",
                "triangulate": True,
                "lights": True,
                "file_type": "ASCII",
            },
        }
        save_anim_export_settings(custom)
        loaded = get_anim_export_settings()
        self.assertEqual(loaded["alembic"]["step"], 0.5)
        self.assertTrue(loaded["alembic"]["color_sets"])
        self.assertTrue(loaded["alembic"]["auto_subd"])
        self.assertEqual(loaded["alembic"]["data_format"], "HDF5")
        self.assertEqual(loaded["alembic"]["attribute_prefix"], "CUSTOM_")

        self.assertEqual(loaded["fbx"]["up_axis"], "Z")
        self.assertEqual(loaded["fbx"]["fbx_version"], "FBX 2018")
        self.assertTrue(loaded["fbx"]["triangulate"])
        self.assertTrue(loaded["fbx"]["lights"])
        self.assertEqual(loaded["fbx"]["file_type"], "ASCII")

    def test_reset_settings(self):
        save_anim_export_settings({
            "fbx": {"up_axis": "Z"},
            "alembic": {"step": 0.25},
        })
        reset_anim_export_settings()
        loaded = get_anim_export_settings()
        self.assertEqual(loaded["fbx"]["up_axis"], "Y")
        self.assertEqual(loaded["alembic"]["step"], 1.0)

    def test_scoped_reset_settings(self):
        save_anim_export_settings({
            "fbx": {"step": 4},
            "alembic": {"step": 0.25},
        })
        reset_anim_export_settings(scope="alembic")
        loaded = get_anim_export_settings()
        self.assertEqual(loaded["alembic"]["step"], 1.0)
        self.assertEqual(loaded["fbx"]["step"], 4)

        reset_anim_export_settings(scope="fbx")
        loaded = get_anim_export_settings()
        self.assertEqual(loaded["fbx"]["step"], 1)


if __name__ == "__main__":
    unittest.main()
