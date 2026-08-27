# -*- coding: utf-8 -*-
"""Unit tests for Pipeline Renamer."""

from __future__ import absolute_import, division, print_function

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_release import install_maya_stubs
install_maya_stubs()

from scartools.tools.renamer.operations import (
    compute_new_name,
    preview_rename,
)


class TestPipelineRenamer(unittest.TestCase):

    def test_search_replace(self):
        new_name = compute_new_name("prop_barrel_mesh", "search_replace", {"search": "mesh", "replace": "geo"})
        self.assertEqual(new_name, "prop_barrel_geo")

    def test_prefix_suffix(self):
        new_name = compute_new_name("arm_FK", "prefix_suffix", {"prefix": "L_", "suffix": "_CTRL"})
        self.assertEqual(new_name, "L_arm_FK_CTRL")

    def test_numbering(self):
        new_name = compute_new_name("barrel", "numbering", {"base_name": "barrel", "start_idx": 1, "padding": 2}, index=3)
        self.assertEqual(new_name, "barrel_03")

    def test_preset_suffix(self):
        new_name = compute_new_name("hero_body_mesh_old", "preset", {"suffix": "_GEO"})
        self.assertEqual(new_name, "hero_body_mesh_old_GEO")

        # Test stripping existing _GRP before appending _GEO
        new_name2 = compute_new_name("character_GRP", "preset", {"suffix": "_GEO"})
        self.assertEqual(new_name2, "character_GEO")

    def test_sanitize_spaces(self):
        new_name = compute_new_name("my bad name#01", "prefix_suffix", {"prefix": "", "suffix": ""})
        self.assertEqual(new_name, "my_bad_name_01")

    def test_unified_scratch_rename(self):
        opts = {
            "rename_from_scratch": True,
            "base_name": "hero_armor",
            "prefix": "L_",
            "suffix": "_GEO",
            "mode": "Numbering",
            "start_idx": 1,
            "padding": 2,
        }
        new_name = compute_new_name("pCube1", "unified", opts, index=1)
        self.assertEqual(new_name, "L_hero_armor_01_GEO")

        new_name_2 = compute_new_name("pCube2", "unified", opts, index=2)
        self.assertEqual(new_name_2, "L_hero_armor_02_GEO")

    def test_unified_combined_operations(self):
        opts = {
            "search": "poly",
            "replace": "mesh",
            "prefix": "chr_",
            "suffix": "_GRP",
        }
        new_name = compute_new_name("polySurface1", "unified", opts, index=1)
        self.assertEqual(new_name, "chr_meshSurface1_GRP")

    def test_unified_letter_mode(self):
        opts = {
            "rename_from_scratch": True,
            "base_name": "finger",
            "prefix": "L_",
            "suffix": "_JNT",
            "mode": "Letter",
            "start_idx": 1,
        }
        self.assertEqual(compute_new_name("joint1", "unified", opts, index=1), "L_finger_A_JNT")
        self.assertEqual(compute_new_name("joint2", "unified", opts, index=2), "L_finger_B_JNT")
        self.assertEqual(compute_new_name("joint3", "unified", opts, index=3), "L_finger_C_JNT")

    def test_top_to_bottom_numbering_order(self):
        # When user selects joint hierarchy top to bottom with numbering enabled
        opts = {
            "rename_from_scratch": True,
            "base_name": "Hair",
            "padding": 2,
            "start_idx": 1,
            "apply_numbering": True,
        }
        # Verify index calculation in selection order:
        self.assertEqual(compute_new_name("joint1", "unified", opts, index=1), "Hair_01")
        self.assertEqual(compute_new_name("joint2", "unified", opts, index=2), "Hair_02")
        self.assertEqual(compute_new_name("joint3", "unified", opts, index=3), "Hair_03")
        self.assertEqual(compute_new_name("joint4", "unified", opts, index=4), "Hair_04")

    def test_rename_without_numbering(self):
        # When numbering is disabled (apply_numbering=False)
        opts = {
            "rename_from_scratch": True,
            "base_name": "hero_weapon",
            "prefix": "chr_",
            "suffix": "_GEO",
            "apply_numbering": False,
        }
        self.assertEqual(compute_new_name("pCube1", "unified", opts, index=1), "chr_hero_weapon_GEO")
        self.assertEqual(compute_new_name("pCube2", "unified", opts, index=2), "chr_hero_weapon_GEO")

    def test_search_replace_does_not_append_numbering(self):
        # When Search & Replace is run even if apply_numbering is True in options
        opts = {
            "search": "a",
            "replace": "b",
            "apply_numbering": True,
            "start_idx": 1,
            "padding": 2,
        }
        self.assertEqual(compute_new_name("a_01", "unified", opts, index=1), "b_01")
        self.assertEqual(compute_new_name("a_02", "unified", opts, index=2), "b_02")


if __name__ == "__main__":
    unittest.main()
