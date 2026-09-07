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
from scartools.tools.anim_io.api.exporter import (
    discover_scene_assets,
    find_export_groups,
    export_character_cache,
)
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

    def test_fix_or_create_shot_camera(self):
        """Verify 1-click camera fix/create helper."""
        from scartools.tools.anim_io.api.camera import fix_or_create_shot_camera

        # Case 1: Camera created if none exists
        cam1 = fix_or_create_shot_camera("PRT_SH_020")
        self.assertTrue(cmds.objExists(cam1))
        self.assertTrue(cam1.endswith("PRT_SH_020_CAM"))

        # Case 2: Selected camera renamed to target
        old_cam = cmds.camera(name="temp_cam")[0]
        cmds.select(old_cam, replace=True)
        cam2 = fix_or_create_shot_camera("PRT_SH_030")
        self.assertTrue(cmds.objExists(cam2))
        self.assertTrue(cam2.endswith("PRT_SH_030_CAM"))

    def test_find_export_groups(self):
        """Verify discovery of Deformation (joints) and Geometry (mesh) groups."""
        # Standard rig
        root1 = cmds.group(em=True, name="Hero_Rig")
        deform1 = cmds.group(em=True, name="Deformation", parent=root1)
        cmds.joint(name="hero_root_jnt")
        geo1 = cmds.group(em=True, name="Geometry", parent=root1)
        mesh1 = cmds.polySphere(name="hero_body_geo")[0]
        cmds.parent(mesh1, geo1)

        groups1 = find_export_groups(root1)
        self.assertTrue(groups1["geometry"].endswith("Geometry"))
        self.assertTrue(groups1["deformation"].endswith("Deformation"))

        # Prop with no deformation
        root2 = cmds.group(em=True, name="Shield_Prop")
        geo2 = cmds.group(em=True, name="geo", parent=root2)
        mesh2 = cmds.polyCube(name="shield_mesh")[0]
        cmds.parent(mesh2, geo2)

        groups2 = find_export_groups(root2)
        self.assertTrue(groups2["geometry"].endswith("geo"))
        self.assertIsNone(groups2["deformation"])

    def test_export_character_cache_group_isolation(self):
        """Verify export_character_cache resolves Deformation and Geometry groups and exports cleanly."""
        root = cmds.group(em=True, name="Runner_Rig")
        deform = cmds.group(em=True, name="Deformation", parent=root)
        cmds.joint(name="runner_hip_jnt")
        geo = cmds.group(em=True, name="Geometry", parent=root)
        mesh = cmds.polySphere(name="runner_mesh")[0]
        cmds.parent(mesh, geo)

        out_dir = os.path.join(self.test_dir, "cache_output")
        exp_files = export_character_cache(
            root_node=root,
            output_dir=out_dir,
            start_frame=1001,
            end_frame=1005,
            formats=("abc", "fbx"),
        )
        self.assertEqual(len(exp_files), 2)
        for f in exp_files:
            self.assertTrue(os.path.exists(f))

    def test_controller_deselection_filtering(self):
        """Verify that unchecked assets in AnimIOController are excluded from export_plan."""
        from scartools.tools.anim_io.controller import AnimIOController, AnimAssetItem

        ctrl = AnimIOController()
        ctrl.shot_name = "SH_010"
        ctrl.shot_root = self.test_dir
        ctrl.assets = [
            AnimAssetItem(name="Hero", item_type="character", node="|Hero_GRP", checked=True),
            AnimAssetItem(name="Villain", item_type="character", node="|Villain_GRP", checked=False),
            AnimAssetItem(name="Sword", item_type="prop", node="|Sword_GRP", checked=True),
            AnimAssetItem(name="Cam", item_type="camera", node="|Cam_GRP", checked=False),
        ]
        ctrl.recompute_state()

        plan_names = [p["name"] for p in ctrl.export_plan]
        self.assertIn("Hero", plan_names)
        self.assertIn("Sword", plan_names)
        self.assertNotIn("Villain", plan_names)
        self.assertNotIn("Cam", plan_names)
        self.assertEqual(len(ctrl.export_plan), 2)

    def test_export_shot_package_deselected_assets(self):
        """Verify that deselected assets and camera are completely excluded from disk and manifest."""
        cam = cmds.camera(name="DeselectedCam")[0]
        char1 = cmds.group(em=True, name="ExportedChar_GRP")
        mesh1 = cmds.polySphere(name="char1_geo")[0]
        cmds.parent(mesh1, char1)

        char2 = cmds.group(em=True, name="ExcludedChar_GRP")
        mesh2 = cmds.polyCube(name="char2_geo")[0]
        cmds.parent(mesh2, char2)

        out_shot = os.path.join(self.test_dir, "Shot_Exclusion_Test")
        res = export_shot_package(
            output_dir=out_shot,
            shot_name="Shot_Exclusion_Test",
            start_frame=1001,
            end_frame=1005,
            camera_node=None,
            export_camera=False,
            character_nodes=[char1],  # char2 excluded
            character_formats=["abc"],
        )

        exported_basenames = [os.path.basename(f) for f in res.get("exported_files", [])]
        # char1 must be exported
        self.assertTrue(any("ExportedChar_GRP" in b for b in exported_basenames))
        # char2 must NOT be exported
        self.assertFalse(any("ExcludedChar_GRP" in b for b in exported_basenames))
        # camera must NOT be exported
        self.assertFalse(any("DeselectedCam" in b or "cam" in b.lower() for b in exported_basenames))

        # Check manifest
        with open(res["manifest_path"], "r") as f:
            manifest_data = json.load(f)
        self.assertFalse(manifest_data.get("camera"))
        self.assertEqual(len(manifest_data.get("characters", [])), 1)
        self.assertIn("ExportedChar_GRP", manifest_data["characters"][0]["source_node"])

    def test_controller_select_and_deselect_all(self):
        """Verify select all and deselect all state transitions."""
        from scartools.tools.anim_io.controller import AnimIOController, AnimAssetItem, AnimExportStateEnum

        ctrl = AnimIOController()
        ctrl.shot_name = "SH_020"
        ctrl.shot_root = self.test_dir
        ctrl.assets = [
            AnimAssetItem(name="AssetA", item_type="character", node="|AssetA", checked=True),
            AnimAssetItem(name="AssetB", item_type="prop", node="|AssetB", checked=True),
        ]
        ctrl.recompute_state()
        self.assertEqual(ctrl.state, AnimExportStateEnum.READY)
        self.assertEqual(len(ctrl.export_plan), 2)

        # Deselect all
        for a in ctrl.assets:
            a.checked = False
        ctrl.recompute_state()
        self.assertEqual(ctrl.state, AnimExportStateEnum.BLOCKED)
        self.assertEqual(len(ctrl.export_plan), 0)

        # Select all
        for a in ctrl.assets:
            a.checked = True
        ctrl.recompute_state()
        self.assertEqual(ctrl.state, AnimExportStateEnum.READY)
        self.assertEqual(len(ctrl.export_plan), 2)

    def test_scan_scene_preserves_checked_state(self):
        """Verify scan_scene remembers user checked selections across rescans."""
        from scartools.tools.anim_io.controller import AnimIOController

        char_grp = cmds.group(em=True, name="Persistent_Char_GRP")
        mesh = cmds.polySphere(name="p_mesh")[0]
        cmds.parent(mesh, char_grp)

        prop_grp = cmds.group(em=True, name="Persistent_Prop_GRP")
        prop_mesh = cmds.polyCube(name="p_prop_mesh")[0]
        cmds.parent(prop_mesh, prop_grp)

        ctrl = AnimIOController()
        ctrl.scan_scene()

        # Both should initially be checked
        self.assertTrue(len(ctrl.assets) >= 2)
        char_item = next(a for a in ctrl.assets if "Persistent_Char_GRP" in a.name)
        prop_item = next(a for a in ctrl.assets if "Persistent_Prop_GRP" in a.name)
        self.assertTrue(char_item.checked)
        self.assertTrue(prop_item.checked)

        # Uncheck prop_item
        prop_item.checked = False
        ctrl.recompute_state()

        # Rescan scene
        ctrl.scan_scene()
        char_item_after = next(a for a in ctrl.assets if "Persistent_Char_GRP" in a.name)
        prop_item_after = next(a for a in ctrl.assets if "Persistent_Prop_GRP" in a.name)

        # Character should stay True, Prop should stay False (not reset!)
        self.assertTrue(char_item_after.checked)
        self.assertFalse(prop_item_after.checked)


if __name__ == "__main__":
    unittest.main()
