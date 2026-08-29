# -*- coding: utf-8 -*-
"""Unit tests for Modeling and Scene Sanitizer operations."""

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_release import install_maya_stubs

class ModelingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_path = list(sys.path)
        sys.path.insert(0, str(SCRIPTS))
        cls.maya_state = install_maya_stubs()

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls._old_path

    def test_inspect_model_and_scene_headless(self):
        from scartools.tools.modeling.api import inspect_model_and_scene
        report = inspect_model_and_scene()
        self.assertIn("overall_status", report)
        self.assertIn("critical_count", report)
        self.assertIn("warning_count", report)
        self.assertIn("checks", report)
        self.assertIn("duplicate_names", report["checks"])
        self.assertIn("mesh_suffixes", report["checks"])
        self.assertIn("group_suffixes", report["checks"])
        self.assertIn("material_suffixes", report["checks"])
        self.assertIn("shading_group_suffixes", report["checks"])
        self.assertIn("unfrozen_transforms", report["checks"])
        self.assertIn("non_manifold", report["checks"])
        self.assertIn("lamina_faces", report["checks"])
        self.assertIn("zero_area_faces", report["checks"])
        self.assertIn("zero_length_edges", report["checks"])
        self.assertIn("display_layers", report["checks"])
        self.assertIn("anim_layers", report["checks"])
        self.assertIn("unknown_nodes", report["checks"])

    def test_fix_functions_callable(self):
        from scartools.tools.modeling.api import (
            fix_make_names_unique,
            fix_add_geo_suffixes,
            fix_add_grp_suffixes,
            fix_shader_suffixes,
            fix_freeze_transforms,
            fix_center_pivots,
            fix_delete_construction_history,
            fix_delete_intermediate_shapes,
            fix_unlock_normals,
            fix_clean_scene_clutter,
            fix_all_safe_issues,
        )
        self.assertEqual(fix_make_names_unique(), 0)
        self.assertEqual(fix_add_geo_suffixes(), 0)
        self.assertEqual(fix_add_grp_suffixes(), 0)
        self.assertEqual(fix_shader_suffixes(), 0)
        self.assertEqual(fix_freeze_transforms(), 0)
        self.assertEqual(fix_center_pivots(), 0)
        self.assertEqual(fix_delete_construction_history(), 0)
        self.assertEqual(fix_delete_intermediate_shapes(), 0)
        self.assertEqual(fix_unlock_normals(), 0)
        self.assertEqual(fix_clean_scene_clutter(), 0)
        self.assertTrue(fix_all_safe_issues())


if __name__ == "__main__":
    unittest.main()
