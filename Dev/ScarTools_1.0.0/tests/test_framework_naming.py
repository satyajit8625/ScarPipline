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

from scartools.framework.naming import (
    SuffixRegistry,
    sanitize_maya_name,
    apply_affixes,
    split_version_string,
    format_version,
)


class TestFrameworkNaming(unittest.TestCase):
    def test_suffix_registry(self):
        self.assertEqual(SuffixRegistry.GEOMETRY, "_GEO")
        self.assertEqual(SuffixRegistry.GROUP, "_GRP")
        self.assertEqual(SuffixRegistry.JOINT, "_JNT")
        self.assertIn("_GEO", SuffixRegistry.ALL_SUFFIXES)

    def test_sanitize_maya_name(self):
        self.assertEqual(sanitize_maya_name("my mesh-01@cool"), "my_mesh_01_cool")
        self.assertEqual(sanitize_maya_name("123node"), "_123node")
        self.assertEqual(sanitize_maya_name("body___geo"), "body_geo")

    def test_apply_affixes(self):
        self.assertEqual(apply_affixes("body", prefix="hero", suffix="GEO"), "hero_body_GEO")
        self.assertEqual(apply_affixes("body_", suffix="_GEO"), "body_GEO")
        self.assertEqual(apply_affixes("body", prefix="hero_"), "hero_body")

    def test_version_helpers(self):
        self.assertEqual(split_version_string("v001"), ("", 1, 3))
        self.assertEqual(split_version_string("asset_v02"), ("asset_", 2, 2))
        self.assertEqual(format_version(5, padding=3), "v005")
        self.assertEqual(format_version(12, padding=4), "v0012")


if __name__ == "__main__":
    unittest.main()
