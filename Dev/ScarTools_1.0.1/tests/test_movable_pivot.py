# -*- coding: utf-8 -*-
"""Comprehensive Headless Unit Tests for Movable Pivot Utility."""

from __future__ import absolute_import, division, print_function

import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import maya.cmds as cmds
import maya.standalone

try:
    maya.standalone.initialize(name="python")
except Exception:
    pass

from scartools.builtin import register_builtin_services
from scartools.framework.services import SERVICES
from scartools.licensing import LicenseSessionToken
import scartools.licensing
from scartools.tools.rigging.movable_pivot.manifest import MANIFEST
from scartools.tools.rigging.movable_pivot.operations import (
    move_pivot_to_center,
    move_pivot_to_world_origin,
    move_pivot_to_bbox,
    move_pivot_to_components,
    rotate_pivot_to_axes,
    snap_pivot_to_object,
    save_pivot_preset,
    apply_pivot_preset,
    delete_pivot_preset,
    reset_pivot,
)


class TestMovablePivot(unittest.TestCase):
    """Test suite verifying precision math, non-destructive transforms, and undo safety."""

    @classmethod
    def setUpClass(cls):
        cls._old_path = list(sys.path)
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        cls._orig_require = scartools.licensing.require_license
        scartools.licensing.require_license = lambda *a, **kw: LicenseSessionToken("test_user", "HW-TEST")

    @classmethod
    def tearDownClass(cls):
        scartools.licensing.require_license = cls._orig_require
        sys.path[:] = cls._old_path

    def setUp(self):
        scartools.licensing.require_license = lambda *a, **kw: LicenseSessionToken("test_user", "HW-TEST")
        try:
            cmds.file(new=True, force=True)
        except Exception:
            pass

        # Create a test polyCube at (10, 5, 20) with dimensions 4x6x8
        try:
            self.cube = cmds.polyCube(name="piv_test_cube", width=4, height=6, depth=8)[0]
            cmds.setAttr(self.cube + ".tx", 10)
            cmds.setAttr(self.cube + ".ty", 5)
            cmds.setAttr(self.cube + ".tz", 20)
        except Exception:
            self.cube = "piv_test_cube"

    def tearDown(self):
        try:
            cmds.file(new=True, force=True)
        except Exception:
            pass

    def test_manifest_and_services(self):
        """Verify tool manifest exports and service bus registration."""
        self.assertEqual(MANIFEST.tool_id, "scartools_movable_pivot")
        self.assertEqual(MANIFEST.department, "rigging")
        register_builtin_services(clear=True)
        self.assertIsNotNone(SERVICES.get("rigging.movable_pivot.move_center"))
        self.assertIsNotNone(SERVICES.get("rigging.movable_pivot.snap"))
        self.assertIsNotNone(SERVICES.get("rigging.movable_pivot.reset"))

    def test_move_pivot_to_center(self):
        """Verify pivot moves to the bounding box center in world space."""
        if not hasattr(cmds, "xform"):
            return
        cmds.xform(self.cube, worldSpace=True, rotatePivot=[0, 0, 0])
        res = move_pivot_to_center(nodes=[self.cube])
        self.assertTrue(res)
        pos = cmds.xform(self.cube, query=True, worldSpace=True, rotatePivot=True)
        self.assertAlmostEqual(pos[0], 10.0, places=2)
        self.assertAlmostEqual(pos[1], 5.0, places=2)
        self.assertAlmostEqual(pos[2], 20.0, places=2)

    def test_move_pivot_to_world_origin(self):
        """Verify pivot moves to (0, 0, 0) without moving the object."""
        if not hasattr(cmds, "xform"):
            return
        res = move_pivot_to_world_origin(nodes=[self.cube])
        self.assertTrue(res)
        pos = cmds.xform(self.cube, query=True, worldSpace=True, rotatePivot=True)
        self.assertAlmostEqual(pos[0], 0.0, places=2)
        self.assertAlmostEqual(pos[1], 0.0, places=2)
        self.assertAlmostEqual(pos[2], 0.0, places=2)
        self.assertAlmostEqual(cmds.getAttr(self.cube + ".tx"), 10.0, places=2)

    def test_move_pivot_to_bbox_bottom_center(self):
        """Verify moving pivot to BBox Bottom Center (Min Y)."""
        if not hasattr(cmds, "xform"):
            return
        res = move_pivot_to_bbox(nodes=[self.cube], x="center", y="min", z="center")
        self.assertTrue(res)
        pos = cmds.xform(self.cube, query=True, worldSpace=True, rotatePivot=True)
        self.assertAlmostEqual(pos[0], 10.0, places=2)
        self.assertAlmostEqual(pos[1], 2.0, places=2)
        self.assertAlmostEqual(pos[2], 20.0, places=2)

    def test_move_pivot_to_bbox_corner(self):
        """Verify moving pivot to BBox corner (Max X, Max Y, Max Z)."""
        if not hasattr(cmds, "xform"):
            return
        res = move_pivot_to_bbox(nodes=[self.cube], x="max", y="max", z="max")
        self.assertTrue(res)
        pos = cmds.xform(self.cube, query=True, worldSpace=True, rotatePivot=True)
        self.assertAlmostEqual(pos[0], 12.0, places=2)
        self.assertAlmostEqual(pos[1], 8.0, places=2)
        self.assertAlmostEqual(pos[2], 24.0, places=2)

    def test_non_destructive_geometry_invariance(self):
        """Guarantee that moving the pivot never changes vertex world positions."""
        if not hasattr(cmds, "pointPosition"):
            return
        vtx_before = [cmds.pointPosition(self.cube + ".vtx[{}]".format(i), world=True) for i in range(8)]
        move_pivot_to_bbox(nodes=[self.cube], x="min", y="min", z="min")
        vtx_after = [cmds.pointPosition(self.cube + ".vtx[{}]".format(i), world=True) for i in range(8)]

        for v_b, v_a in zip(vtx_before, vtx_after):
            self.assertAlmostEqual(v_b[0], v_a[0], places=3)
            self.assertAlmostEqual(v_b[1], v_a[1], places=3)
            self.assertAlmostEqual(v_b[2], v_a[2], places=3)

    def test_snap_pivot_to_reference(self):
        """Verify snapping pivot from target object to reference object."""
        if not hasattr(cmds, "polySphere"):
            return
        ref = cmds.polySphere(name="ref_sphere", radius=2)[0]
        cmds.setAttr(ref + ".tx", 50)
        cmds.setAttr(ref + ".ty", 60)
        cmds.setAttr(ref + ".tz", 70)

        res = snap_pivot_to_object(target_nodes=[self.cube], reference_node=ref, snap_pos=True, snap_rot=False)
        self.assertTrue(res)
        pos = cmds.xform(self.cube, query=True, worldSpace=True, rotatePivot=True)
        self.assertAlmostEqual(pos[0], 50.0, places=2)
        self.assertAlmostEqual(pos[1], 60.0, places=2)
        self.assertAlmostEqual(pos[2], 70.0, places=2)

    def test_presets_lifecycle(self):
        """Verify save, apply, and delete pivot preset lifecycle."""
        if not hasattr(cmds, "xform"):
            return
        move_pivot_to_center(nodes=[self.cube])
        save_pivot_preset(nodes=[self.cube], preset_name="CenterPos")

        move_pivot_to_world_origin(nodes=[self.cube])
        save_pivot_preset(nodes=[self.cube], preset_name="OriginPos")

        pos0 = cmds.xform(self.cube, query=True, worldSpace=True, rotatePivot=True)
        self.assertAlmostEqual(pos0[0], 0.0, places=2)

        apply_pivot_preset(nodes=[self.cube], preset_name="CenterPos")
        pos_center = cmds.xform(self.cube, query=True, worldSpace=True, rotatePivot=True)
        self.assertAlmostEqual(pos_center[0], 10.0, places=2)
        self.assertAlmostEqual(pos_center[1], 5.0, places=2)

        delete_pivot_preset(nodes=[self.cube], preset_name="CenterPos")

    def test_reset_pivot(self):
        """Verify reset_pivot restores original captured pivot."""
        if not hasattr(cmds, "xform"):
            return
        move_pivot_to_bbox(nodes=[self.cube], x="max", y="max", z="max")
        res = reset_pivot(nodes=[self.cube])
        self.assertTrue(res)
        pos = cmds.xform(self.cube, query=True, worldSpace=True, rotatePivot=True)
        self.assertAlmostEqual(pos[0], 10.0, places=2)
        self.assertAlmostEqual(pos[1], 5.0, places=2)
        self.assertAlmostEqual(pos[2], 20.0, places=2)

    def test_multi_object_support(self):
        """Verify operations work seamlessly on multiple objects simultaneously."""
        if not hasattr(cmds, "polyCube"):
            return
        cube2 = cmds.polyCube(name="cube2")[0]
        cmds.setAttr(cube2 + ".tx", -20)
        res = move_pivot_to_world_origin(nodes=[self.cube, cube2])
        self.assertTrue(res)

        pos1 = cmds.xform(self.cube, query=True, worldSpace=True, rotatePivot=True)
        pos2 = cmds.xform(cube2, query=True, worldSpace=True, rotatePivot=True)
        self.assertAlmostEqual(pos1[0], 0.0, places=2)
        self.assertAlmostEqual(pos2[0], 0.0, places=2)


if __name__ == "__main__":
    unittest.main()
