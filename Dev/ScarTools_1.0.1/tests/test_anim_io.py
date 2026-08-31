# -*- coding: utf-8 -*-
"""Headless unit tests for ScarTools Animation Export and Import Suite."""

from __future__ import absolute_import, division, print_function

import json
import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    import maya.standalone
    maya.standalone.initialize(name="python")
except Exception:
    pass

import maya.cmds as cmds

from scartools.tools.anim_io.manifest import MANIFEST
from scartools.tools.anim_io.api.manifest_builder import (
    build_shot_manifest,
    save_shot_manifest,
    load_shot_manifest,
)
from scartools.tools.anim_io.api.camera import (
    discover_shot_cameras,
    bake_camera_world_space,
)
from scartools.tools.anim_io.api.exporter import discover_scene_assets
from scartools.tools.anim_io.api.importer import apply_shot_time_settings
from scartools.tools.anim_io.operations import (
    export_shot_package,
    import_shot_package,
)
from scartools.licensing import save_license, generate_license_key, get_machine_hardware_id


class TestAnimIO(unittest.TestCase):
    """Test suite for Anim I/O operations and manifest building."""

    def setUp(self):
        cmds.file(new=True, force=True)
        self.test_dir = tempfile.mkdtemp(prefix="scartools_anim_test_")
        os.environ["SCARTOOLS_USER_DIR"] = self.test_dir

        # Setup valid license for tests
        user = "anim_tester"
        hwid = get_machine_hardware_id()
        key = generate_license_key(user, hwid)
        save_license(user, key)

    def tearDown(self):
        cmds.file(new=True, force=True)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        os.environ.pop("SCARTOOLS_USER_DIR", None)

    def test_manifest_contract(self):
        """Verify tool manifest compliance with ScarTools standards."""
        self.assertEqual(MANIFEST.tool_id, "scartools_anim_io")
        self.assertEqual(MANIFEST.department, "animation")
        self.assertEqual(MANIFEST.version, "1.0.1")
        self.assertTrue(MANIFEST.controller_entry_point)
        self.assertTrue(MANIFEST.ui_spec_entry_point)
        self.assertIn("anim.export_shot", [s[0] for s in MANIFEST.services])
        self.assertIn("anim.import_shot", [s[0] for s in MANIFEST.services])

    def test_manifest_builder_and_loader(self):
        """Verify JSON manifest construction, serialization, and deserialization."""
        manifest_dict = build_shot_manifest(
            shot_name="SQ01_SH020",
            start_frame=1001,
            end_frame=1050,
            fps=24.0,
            camera_info={"name": "shot_cam", "file": "shot_cam.fbx", "format": "fbx"},
            characters=[{"name": "Hero", "file": "Hero.abc", "format": "abc"}],
            props=[{"name": "Sword", "file": "Sword.abc", "format": "abc"}],
            handles=5,
            notes="Test export manifest",
        )

        out_path = save_shot_manifest(manifest_dict, self.test_dir)
        self.assertTrue(os.path.isfile(out_path))

        loaded = load_shot_manifest(self.test_dir)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["shot_name"], "SQ01_SH020")
        self.assertEqual(loaded["fps"], 24.0)
        self.assertEqual(loaded["frame_range"]["start"], 1001)
        self.assertEqual(loaded["frame_range"]["end"], 1050)
        self.assertEqual(loaded["frame_range"]["eval_start"], 996)
        self.assertEqual(loaded["frame_range"]["eval_end"], 1055)
        self.assertEqual(len(loaded["characters"]), 1)
        self.assertEqual(len(loaded["props"]), 1)

    def test_camera_discovery_and_baking(self):
        """Verify discovery of custom cameras and world-space baking."""
        raw_cam = cmds.camera()[0]
        cam_tf = cmds.rename(raw_cam, "ShotCam_010")
        cmds.setKeyframe(cam_tf, attribute="translateX", t=1001, v=0.0)
        cmds.setKeyframe(cam_tf, attribute="translateX", t=1010, v=50.0)

        cams = discover_shot_cameras()
        short_names = [c.split("|")[-1] for c in cams]
        self.assertIn("ShotCam_010", short_names)

        baked_cam = bake_camera_world_space(cam_tf, 1001, 1010)
        self.assertTrue(cmds.objExists(baked_cam))
        keys = cmds.keyframe(baked_cam, attribute="translateX", query=True)
        self.assertTrue(len(keys) >= 10)
        cmds.delete(baked_cam)

    def test_scene_asset_discovery(self):
        """Verify asset discovery for characters, props, and cameras."""
        cmds.camera(name="main_shot_cam")
        char_grp = cmds.group(em=True, name="char_hero_GRP")
        mesh_a = cmds.polySphere(name="hero_body_GEO")[0]
        cmds.parent(mesh_a, char_grp)

        prop_grp = cmds.group(em=True, name="prop_sword_GRP")
        mesh_b = cmds.polyCube(name="sword_blade_GEO")[0]
        cmds.parent(mesh_b, prop_grp)

        assets = discover_scene_assets()
        chars = [c.split("|")[-1] for c in assets["characters"]]
        props = [p.split("|")[-1] for p in assets["props"]]

        self.assertIn("char_hero_GRP", chars)
        self.assertIn("prop_sword_GRP", props)

    def test_apply_shot_time_settings(self):
        """Verify time settings and playback range application."""
        manifest = {
            "fps": 24.0,
            "frame_range": {"start": 1050, "end": 1120},
        }
        apply_shot_time_settings(manifest)
        self.assertEqual(int(cmds.playbackOptions(q=True, minTime=True)), 1050)
        self.assertEqual(int(cmds.playbackOptions(q=True, maxTime=True)), 1120)

    def test_export_shot_package_subfolders(self):
        """Verify export_shot_package creates Alembic/ and FBX/ subfolders."""
        cam = cmds.camera(name="ShotCam")[0]
        char_grp = cmds.group(em=True, name="char_runner_GRP")
        mesh = cmds.polySphere(name="runner_GEO")[0]
        cmds.parent(mesh, char_grp)

        out_shot = os.path.join(self.test_dir, "Shot_010")
        res = export_shot_package(
            output_dir=out_shot,
            shot_name="Shot_010",
            start_frame=1001,
            end_frame=1010,
            camera_node=cam,
            camera_format="fbx",
            character_nodes=[char_grp],
            character_formats=["abc", "fbx"],
        )

        self.assertTrue(res["success"])
        target_dir = res["target_dir"]
        self.assertTrue(os.path.isdir(os.path.join(target_dir, "Alembic")))
        self.assertTrue(os.path.isdir(os.path.join(target_dir, "FBX")))
        self.assertTrue(os.path.isfile(res["manifest_file"]))


if __name__ == "__main__":
    unittest.main()
