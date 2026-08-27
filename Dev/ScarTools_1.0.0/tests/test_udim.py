# -*- coding: utf-8 -*-
"""Unit tests for UDIM Texture Manager."""

from __future__ import absolute_import, division, print_function

import os
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

from scartools.tools.udim.operations import (
    parse_udim_pattern,
    scan_udim_textures,
    get_all_file_nodes,
)


class TestUDIMManager(unittest.TestCase):

    def test_parse_mari_udim_pattern(self):
        info = parse_udim_pattern("D:/textures/character_head.<UDIM>.png")
        self.assertTrue(info["is_udim"])
        self.assertEqual(info["pattern_type"], "mari")

    def test_parse_numbered_udim_pattern(self):
        info = parse_udim_pattern("D:/textures/barrels_diffuse_1001.png")
        self.assertTrue(info["is_udim"])
        self.assertEqual(info["pattern_type"], "mari")
        self.assertIn("<UDIM>", info["template"])

    def test_parse_single_file(self):
        info = parse_udim_pattern("D:/textures/wood_albedo.png")
        self.assertFalse(info["is_udim"])
        self.assertEqual(info["pattern_type"], "none")

    def test_scan_empty_scene(self):
        report = scan_udim_textures()
        self.assertIn("total_files", report)
        self.assertIn("udim_files_count", report)
        self.assertIn("nodes", report)


if __name__ == "__main__":
    unittest.main()
