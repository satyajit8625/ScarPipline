from __future__ import absolute_import, division, print_function

import os, sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / 'scripts'
_TESTS = _ROOT / 'tests'
if str(_SCRIPTS) not in sys.path: sys.path.insert(0, str(_SCRIPTS))
if str(_TESTS) not in sys.path: sys.path.insert(0, str(_TESTS))

# -*- coding: utf-8 -*-
"""Headless unit tests for ScarTools Animation Export and Import Suite."""


import json
import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
try:
    import maya.standalone
    maya.standalone.initialize(name="python")
except Exception:
    pass

if _SCRIPTS in sys.path:
    sys.path.remove(_SCRIPTS)
sys.path.insert(0, _SCRIPTS)
for _m in list(sys.modules.keys()):
    if _m.startswith("scartools"):
        sys.modules.pop(_m, None)

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
    extract_asset_export_name,
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
        os.environ["SCARTOOLS_TEST_MODE"] = "1"

        # Setup isolated mock registry for tests
        user = "anim_tester"
        hwid = get_machine_hardware_id()
        key = generate_license_key(user, hwid)
        mock_reg_file = os.path.join(self.test_dir, "mock_registry.json")
        with open(mock_reg_file, "w") as fp:
            json.dump([{"user_id": user, "hardware_id": hwid, "license_key": key, "status": "Active"}], fp)
        os.environ["SCARTOOLS_LICENSE_REGISTRY"] = mock_reg_file

        save_license(user, key)

        if hasattr(cmds, "loadPlugin"):
            for plug in ("AbcExport", "AbcImport", "fbxmaya"):
                try:
                    if not cmds.pluginInfo(plug, query=True, loaded=True):
                        cmds.loadPlugin(plug, quiet=True)
                except Exception:
                    pass

    def tearDown(self):
        cmds.file(new=True, force=True)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        os.environ.pop("SCARTOOLS_USER_DIR", None)
        os.environ.pop("SCARTOOLS_TEST_MODE", None)
        os.environ.pop("SCARTOOLS_LICENSE_REGISTRY", None)

    def test_manifest_contract(self):
        """Verify tool manifest compliance with ScarTools standards."""
        self.assertEqual(MANIFEST.tool_id, "scartools_anim_io")
        self.assertEqual(MANIFEST.department, "animation")
        self.assertEqual(MANIFEST.version, "1.0.2")
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

    def test_batched_alembic_export_multi_asset(self):
        """Verify export_shot_package batches multiple assets into Alembic and FBX cleanly."""
        char1 = cmds.group(em=True, name="BatchChar1_GRP")
        mesh1 = cmds.polySphere(name="bmesh1")[0]
        cmds.parent(mesh1, char1)

        char2 = cmds.group(em=True, name="BatchChar2_GRP")
        mesh2 = cmds.polyCube(name="bmesh2")[0]
        cmds.parent(mesh2, char2)

        out_shot = os.path.join(self.test_dir, "Batch_Export_Test")
        res = export_shot_package(
            output_dir=out_shot,
            shot_name="Batch_Export_Test",
            start_frame=1001,
            end_frame=1005,
            camera_node=None,
            export_camera=False,
            character_nodes=[char1, char2],
            character_formats=["abc", "fbx"],
        )

        self.assertEqual(res["characters_exported"], 4)  # 2 abc + 2 fbx
        for f in res["exported_files"]:
            self.assertTrue(os.path.exists(f))
            self.assertTrue(os.path.getsize(f) > 0)


    def test_export_progress_smoothness(self):
        """Verify export progress begins at low percentage (never 95% at start) and scales cleanly."""
        from scartools.framework.operations import OperationCallbacks

        char1 = cmds.group(em=True, name="ProgressTest_GRP")
        mesh1 = cmds.polySphere(name="pt_mesh")[0]
        cmds.parent(mesh1, char1)

        recorded_progress = []
        def _prog(pct, msg="", **kwargs):
            recorded_progress.append((pct, msg, kwargs))

        callbacks = OperationCallbacks(progress_callback=_prog)
        out_shot = os.path.join(self.test_dir, "Progress_Smoothness_Test")

        res = export_shot_package(
            output_dir=out_shot,
            shot_name="Progress_Smoothness_Test",
            start_frame=1001,
            end_frame=1002,
            camera_node=None,
            export_camera=False,
            character_nodes=[char1],
            character_formats=["fbx"],
            callbacks=callbacks,
        )

        self.assertGreater(len(recorded_progress), 2)
        # Verify initial progress is small (e.g. 5% or 10%), NOT 95%!
        self.assertLessEqual(recorded_progress[0][0], 10)
        # Verify final progress is 100%
        self.assertEqual(recorded_progress[-1][0], 100)

        # Verify percentages are non-decreasing
        pct_values = [p[0] for p in recorded_progress]
        for i in range(len(pct_values) - 1):
            self.assertLessEqual(pct_values[i], pct_values[i + 1])

        # Verify kwargs contain current, total, and current_item
        has_current = any("current" in p[2] for p in recorded_progress)
        self.assertTrue(has_current)

    def test_alembic_per_frame_progress(self):
        """Verify Alembic export fires per-frame progress callbacks for each frame."""
        from scartools.framework.operations import OperationCallbacks

        char1 = cmds.group(em=True, name="AbcProgressChar_GRP")
        mesh1 = cmds.polySphere(name="abc_prog_mesh")[0]
        cmds.parent(mesh1, char1)

        recorded = []
        def _prog(pct, msg="", **kwargs):
            recorded.append((pct, msg, kwargs))

        callbacks = OperationCallbacks(progress_callback=_prog)
        out_shot = os.path.join(self.test_dir, "Abc_PerFrame_Test")

        res = export_shot_package(
            output_dir=out_shot,
            shot_name="Abc_PerFrame_Test",
            start_frame=1001,
            end_frame=1005,
            camera_node=None,
            export_camera=False,
            character_nodes=[char1],
            character_formats=["abc"],
            callbacks=callbacks,
        )

        frame_messages = [p[1] for p in recorded if "Frame" in p[1]]
        # In Maya with AbcExport loaded, each frame triggers a per-frame update
        if hasattr(cmds, "AbcExport"):
            self.assertGreaterEqual(len(frame_messages), 4)
            self.assertTrue(any("1001" in m for m in frame_messages))
            self.assertTrue(any("1005" in m for m in frame_messages))

    def test_import_shot_package_preferred_format(self):
        """Verify import_shot_package only imports preferred format when both exist."""
        char1 = cmds.group(em=True, name="MultiFmtChar_GRP")
        mesh1 = cmds.polySphere(name="mfc_mesh")[0]
        cmds.parent(mesh1, char1)

        out_shot = os.path.join(self.test_dir, "MultiFmt_Import_Test")
        res = export_shot_package(
            output_dir=out_shot,
            shot_name="MultiFmt_Import_Test",
            start_frame=1001,
            end_frame=1002,
            camera_node=None,
            export_camera=False,
            character_nodes=[char1],
            character_formats=["abc", "fbx"],
        )

        # Clear scene before importing
        cmds.file(new=True, force=True)

        # Import with default preferred_format="abc"
        imp_res = import_shot_package(res["target_dir"], preferred_format="abc")
        self.assertTrue(imp_res["success"])
        # Should only import 1 cache (the .abc) instead of duplicating both .abc and .fbx
        self.assertEqual(imp_res["characters_imported"], 1)

    def test_camera_shape_baking_focal_length(self):
        """Verify camera focal length and lens attributes are baked into shape keyframes."""
        cam_node, cam_shape = cmds.camera(name="Animated_Lens_CAM")
        # Keyframe focal length
        cmds.setKeyframe(cam_shape, attribute="focalLength", time=1001, value=35.0)
        cmds.setKeyframe(cam_shape, attribute="focalLength", time=1005, value=70.0)
        # Set custom rotation order (ZXY = 2) and scale
        cmds.setAttr(cam_node + ".rotateOrder", 2)
        cmds.setAttr(cam_node + ".scale", 2.0, 2.0, 2.0)

        baked_cam = bake_camera_world_space(cam_node, start_frame=1001, end_frame=1005)
        self.assertTrue(cmds.objExists(baked_cam))

        # Verify rotation order and scale are preserved
        self.assertEqual(cmds.getAttr(baked_cam + ".rotateOrder"), 2)
        self.assertAlmostEqual(cmds.getAttr(baked_cam + ".scaleX"), 2.0, places=1)

        baked_shapes = cmds.listRelatives(baked_cam, shapes=True, fullPath=True) or []
        self.assertTrue(bool(baked_shapes))
        baked_shape = baked_shapes[0]

        # Verify focalLength has keys and values evaluated
        fl_1001 = cmds.getAttr(baked_shape + ".focalLength", time=1001)
        fl_1005 = cmds.getAttr(baked_shape + ".focalLength", time=1005)
        self.assertAlmostEqual(fl_1001, 35.0, places=1)
        self.assertAlmostEqual(fl_1005, 70.0, places=1)

    def test_import_camera_locking_isolation(self):
        """Verify importing a shot camera does NOT lock preexisting scene cameras."""
        # Create an existing artist camera
        artist_cam, _ = cmds.camera(name="Existing_Artist_CAM")
        self.assertFalse(cmds.getAttr(artist_cam + ".tx", lock=True))

        # Build a package with a camera
        shot_cam, _ = cmds.camera(name="Export_Shot_CAM")
        out_shot = os.path.join(self.test_dir, "Cam_Lock_Isolation_Test")
        res = export_shot_package(
            output_dir=out_shot,
            shot_name="Cam_Lock_Isolation_Test",
            start_frame=1001,
            end_frame=1002,
            camera_node=shot_cam,
            export_camera=True,
            camera_format="fbx",
            character_nodes=[],
        )

        # Import shot camera with lock_camera=True
        imp_res = import_shot_package(res["target_dir"], lock_camera=True, import_characters=False, import_props=False)
        self.assertTrue(imp_res["success"])

        # Verify existing artist camera was NOT locked
        self.assertFalse(cmds.getAttr(artist_cam + ".tx", lock=True))
        self.assertFalse(cmds.getAttr(artist_cam + ".rx", lock=True))

    def test_suspend_viewport_refresh_undo_and_selection(self):
        """Verify suspend_viewport_refresh preserves undo queue state and restores selection."""
        from scartools.framework.scene import suspend_viewport_refresh

        node_a = cmds.polyCube(name="sel_node_a")[0]
        cmds.select(node_a, replace=True)

        undo_before = cmds.undoInfo(query=True, stateWithoutFlush=True)
        with suspend_viewport_refresh():
            # Undo should be suspended inside
            undo_inside = cmds.undoInfo(query=True, stateWithoutFlush=True)
            self.assertFalse(undo_inside)
            # Deselect inside
            cmds.select(clear=True)

        # On exit, undo state and selection must be restored
        undo_after = cmds.undoInfo(query=True, stateWithoutFlush=True)
        current_sel = cmds.ls(selection=True, long=True) or []
        self.assertTrue(any(node_a in s for s in current_sel))

    def test_shot_multi_version_export_and_import(self):
        """Verify Alembic/v### and FBX/v### hierarchy, manifest history, and version-specific import."""
        from scartools.tools.anim_io.operations import export_shot_package, import_shot_package
        from scartools.tools.anim_io.api.manifest_builder import get_all_shot_versions, load_shot_manifest

        cube_char = cmds.polyCube(name="char_version_test")[0]
        shot_dir = os.path.join(self.test_dir, "Shot_Version_Suite_Test")

        # Pass 1: Export first version (auto v001)
        res1 = export_shot_package(
            output_dir=shot_dir,
            shot_name="Shot_Version_Suite_Test",
            start_frame=1001,
            end_frame=1005,
            character_nodes=[cube_char],
            character_formats=("abc", "fbx"),
            export_camera=False,
            notes="First pass blocking",
        )
        self.assertEqual(res1["version"], "v001")
        target_dir = res1["target_dir"]

        v1_abc = os.path.join(target_dir, "Alembic", "v001")
        v1_fbx = os.path.join(target_dir, "FBX", "v001")
        self.assertTrue(os.path.isdir(v1_abc))
        self.assertTrue(os.path.isdir(v1_fbx))
        self.assertTrue(any("char_version_test" in f for f in os.listdir(v1_abc)))
        self.assertTrue(any("char_version_test" in f for f in os.listdir(v1_fbx)))

        # Verify manifest v001
        m1 = load_shot_manifest(target_dir)
        self.assertEqual(m1["latest_version"], "v001")
        self.assertEqual(m1["total_versions"], 1)
        self.assertIn("v001", m1["versions"])
        self.assertEqual(m1["versions"]["v001"]["exported_by"], m1.get("exported_by"))
        self.assertTrue(bool(m1.get("exported_by")))

        # Pass 2: Export second version (auto v002)
        res2 = export_shot_package(
            output_dir=shot_dir,
            shot_name="Shot_Version_Suite_Test",
            start_frame=1001,
            end_frame=1010,
            character_nodes=[cube_char],
            character_formats=("abc", "fbx"),
            export_camera=False,
            notes="Second pass polish",
        )
        self.assertEqual(res2["version"], "v002")

        v2_abc = os.path.join(target_dir, "Alembic", "v002")
        v2_fbx = os.path.join(target_dir, "FBX", "v002")
        self.assertTrue(os.path.isdir(v2_abc))
        self.assertTrue(os.path.isdir(v2_fbx))
        # Verify v001 was NOT overwritten
        self.assertTrue(os.path.isdir(v1_abc))
        self.assertTrue(os.path.isdir(v1_fbx))

        # Verify multi-version manifest
        m2 = load_shot_manifest(target_dir)
        self.assertEqual(m2["latest_version"], "v002")
        self.assertEqual(m2["total_versions"], 2)
        self.assertIn("v001", m2["versions"])
        self.assertIn("v002", m2["versions"])
        self.assertEqual(m2["versions"]["v001"]["frame_range"]["end"], 1005)
        self.assertEqual(m2["versions"]["v002"]["frame_range"]["end"], 1010)

        # Test get_all_shot_versions
        all_vers = get_all_shot_versions(target_dir)
        self.assertEqual(len(all_vers), 2)
        self.assertEqual(all_vers[0]["version"], "v001")
        self.assertEqual(all_vers[1]["version"], "v002")
        self.assertTrue(all_vers[0]["has_alembic"])
        self.assertTrue(all_vers[0]["has_fbx"])

        # Test import specific version v001
        imp_v1 = import_shot_package(target_dir, version="v001", preferred_format="abc")
        self.assertTrue(imp_v1["success"])
        self.assertEqual(imp_v1["version"], "v001")

        # Test import specific version v002
        imp_v2 = import_shot_package(target_dir, version="v002", preferred_format="fbx")
        self.assertTrue(imp_v2["success"])
        self.assertEqual(imp_v2["version"], "v002")

    def test_resolve_shot_root_dir(self):
        """Verify resolve_shot_root_dir sanitizes UNC paths and prevents department nesting."""
        from scartools.framework import resolve_shot_root_dir

        unc_nested = r"\\DESKTOP-6HJ08SE\Cinematic_1\01_SF Trailers\35_Pirates_Trailer\05_Animation\Shot_000\Alembic\PRT_SH_000"
        expected_shot_root = "//DESKTOP-6HJ08SE/Cinematic_1/01_SF Trailers/35_Pirates_Trailer/05_Animation/Shot_000"

        # 1. Trailing errant Alembic/PRT_SH_000
        self.assertEqual(resolve_shot_root_dir(unc_nested, "PRT_SH_000"), expected_shot_root)

        # 2. Trailing Alembic
        unc_abc = r"\\DESKTOP-6HJ08SE\Cinematic_1\01_SF Trailers\35_Pirates_Trailer\05_Animation\Shot_000\Alembic"
        self.assertEqual(resolve_shot_root_dir(unc_abc, "PRT_SH_000"), expected_shot_root)

        # 3. Trailing FBX
        unc_fbx = r"\\DESKTOP-6HJ08SE\Cinematic_1\01_SF Trailers\35_Pirates_Trailer\05_Animation\Shot_000\FBX"
        self.assertEqual(resolve_shot_root_dir(unc_fbx, "PRT_SH_000"), expected_shot_root)

        # 4. Trailing scenes / maya
        unc_scenes = r"\\DESKTOP-6HJ08SE\Cinematic_1\01_SF Trailers\35_Pirates_Trailer\05_Animation\Shot_000\maya\scenes"
        self.assertEqual(resolve_shot_root_dir(unc_scenes, "PRT_SH_000"), expected_shot_root)

        # 5. Clean shot root
        unc_clean = r"\\DESKTOP-6HJ08SE\Cinematic_1\01_SF Trailers\35_Pirates_Trailer\05_Animation\Shot_000"
        self.assertEqual(resolve_shot_root_dir(unc_clean, "PRT_SH_000"), expected_shot_root)

        # 6. Department folder -> appends shot
        dept_path = "D:/Projects/PRT/05_Animation"
        self.assertEqual(resolve_shot_root_dir(dept_path, "PRT_SH_000"), "D:/Projects/PRT/05_Animation/PRT_SH_000")

    def test_export_shot_package_no_double_nesting(self):
        """Verify exporting to a path ending in Alembic/PRT_SH_000 does NOT create nested folders."""
        cam = cmds.camera(name="PRT_SH_000_CAM")[0]
        char_grp = cmds.group(em=True, name="char_hero_GRP")
        mesh = cmds.polyCube(name="hero_GEO")[0]
        cmds.parent(mesh, char_grp)

        # Intentionally provide bad/nested output_dir
        bad_output_dir = os.path.join(self.test_dir, "Shot_000", "Alembic", "PRT_SH_000").replace("\\", "/")

        res = export_shot_package(
            output_dir=bad_output_dir,
            shot_name="PRT_SH_000",
            start_frame=1001,
            end_frame=1005,
            camera_node=cam,
            camera_format="fbx",
            character_nodes=[char_grp],
            character_formats=["abc", "fbx"],
            version="v001",
        )

        expected_root = os.path.join(self.test_dir, "Shot_000").replace("\\", "/")
        self.assertEqual(res["output_dir"], expected_root)

        # Must exist at root:
        abc_v1 = os.path.join(expected_root, "Alembic", "v001")
        fbx_v1 = os.path.join(expected_root, "FBX", "v001")
        manifest_file = os.path.join(expected_root, "shot_manifest.json")
        self.assertTrue(os.path.isdir(abc_v1))
        self.assertTrue(os.path.isdir(fbx_v1))
        self.assertTrue(os.path.isfile(manifest_file))

        # Must NEVER create nested Alembic inside Alembic:
        nested_bad = os.path.join(self.test_dir, "Shot_000", "Alembic", "PRT_SH_000")
        self.assertFalse(os.path.exists(nested_bad))

    def test_extract_asset_export_name_with_namespace(self):
        """Verify extract_asset_export_name uses namespace prefix when available to prevent collisions."""
        self.assertEqual(extract_asset_export_name("hero:rig_GRP"), "hero")
        self.assertEqual(extract_asset_export_name("|seq:shot_hero:rig_GRP"), "seq_shot_hero")
        self.assertEqual(extract_asset_export_name("villain:character"), "villain")
        self.assertEqual(extract_asset_export_name("unnamespaced_GRP"), "unnamespaced_GRP")
        self.assertEqual(extract_asset_export_name("|world|char_prop"), "char_prop")

    def test_namespace_export_cache_naming_and_geo_group(self):
        """Verify an asset with namespace exports to <namespace>.abc and <namespace>.fbx and finds namespaced geo."""
        # Create namespace
        cmds.namespace(add="hero_pirate")
        cmds.namespace(set="hero_pirate")
        char_grp = cmds.group(em=True, name="rig_GRP")
        geo_grp = cmds.group(em=True, name="Geometry", parent=char_grp)
        mesh = cmds.polySphere(name="body_GEO")[0]
        cmds.parent(mesh, geo_grp)
        cmds.namespace(set=":")

        full_char = "|hero_pirate:rig_GRP"
        self.assertTrue(cmds.objExists(full_char))

        # Test find_export_groups with namespace
        groups = find_export_groups(full_char)
        self.assertIsNotNone(groups["geometry"])
        self.assertTrue(groups["geometry"].endswith("Geometry"))

        # Test export
        out_shot = os.path.join(self.test_dir, "Shot_Namespace_Test")
        res = export_shot_package(
            output_dir=out_shot,
            shot_name="Shot_Namespace_Test",
            start_frame=1001,
            end_frame=1005,
            character_nodes=[full_char],
            character_formats=["abc", "fbx"],
            export_camera=False,
            version="v001",
        )

        expected_root = res["output_dir"]
        abc_file = os.path.join(expected_root, "Alembic", "v001", "hero_pirate.abc")
        fbx_file = os.path.join(expected_root, "FBX", "v001", "hero_pirate.fbx")

        self.assertTrue(os.path.isfile(abc_file))
        self.assertTrue(os.path.isfile(fbx_file))


if __name__ == "__main__":
    unittest.main()

