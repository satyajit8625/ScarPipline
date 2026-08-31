# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scartools.framework.updater import (
    parse_version_tuple,
    is_newer_version,
    check_for_updates,
    CURRENT_VERSION,
)


class TestUpdater(unittest.TestCase):
    def test_parse_version_tuple(self):
        self.assertEqual(parse_version_tuple("1.0.1"), (1, 0, 1))
        self.assertEqual(parse_version_tuple("v2.1.0"), (2, 1, 0))
        self.assertEqual(parse_version_tuple("1.2"), (1, 2, 0))

    def test_is_newer_version(self):
        self.assertTrue(is_newer_version("1.0.2", "1.0.1"))
        self.assertTrue(is_newer_version("1.1.0", "1.0.9"))
        self.assertTrue(is_newer_version("2.0.0", "1.9.9"))
        self.assertFalse(is_newer_version("1.0.1", "1.0.1"))
        self.assertFalse(is_newer_version("1.0.0", "1.0.1"))

    def test_check_for_updates(self):
        info = check_for_updates(force=True)
        self.assertIn("current_version", info)
        self.assertEqual(info["current_version"], CURRENT_VERSION)
        self.assertIn("has_update", info)


if __name__ == "__main__":
    unittest.main()
