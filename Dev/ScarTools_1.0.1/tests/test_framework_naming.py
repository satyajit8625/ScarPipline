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
    parse_shot_scene_identity,
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

    def test_parse_shot_scene_identity(self):
        # Test 5-token studio pattern: PRT_SH_010_ANM_V001.ma
        path_a = "//desktop-6hj08se/Cinematic_1/01_SF Trailers/35_Pirates_Trailer/05_Animation/Shot_010/maya/PRT_SH_010_ANM_V001.ma"
        res_a = parse_shot_scene_identity(path_a)
        self.assertEqual(res_a["project"], "PRT")
        self.assertEqual(res_a["sequence"], "SH")
        self.assertEqual(res_a["shot_num"], "010")
        self.assertEqual(res_a["shot_name"], "PRT_SH_010")
        self.assertEqual(res_a["department"], "ANM")
        self.assertEqual(res_a["version_str"], "V001")
        self.assertEqual(res_a["version_num"], 1)
        self.assertEqual(res_a["shot_root"], "//desktop-6hj08se/Cinematic_1/01_SF Trailers/35_Pirates_Trailer/05_Animation/Shot_010")
        self.assertEqual(res_a["alembic_dir"], "//desktop-6hj08se/Cinematic_1/01_SF Trailers/35_Pirates_Trailer/05_Animation/Shot_010/alembic")
        self.assertEqual(res_a["fbx_dir"], "//desktop-6hj08se/Cinematic_1/01_SF Trailers/35_Pirates_Trailer/05_Animation/Shot_010/fbx")

        # Test 4-token pattern: PRT_SH010_ANM_V002.mb
        path_b = "O:/Projects/PRT/Shots/SH010/ANM/scenes/PRT_SH010_ANM_V002.mb"
        res_b = parse_shot_scene_identity(path_b)
        self.assertEqual(res_b["project"], "PRT")
        self.assertEqual(res_b["shot_name"], "PRT_SH010")
        self.assertEqual(res_b["department"], "ANM")
        self.assertEqual(res_b["version_str"], "V002")
        self.assertEqual(res_b["version_num"], 2)


if __name__ == "__main__":
    unittest.main()
