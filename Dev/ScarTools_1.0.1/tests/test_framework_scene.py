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

from scartools.framework.scene import (
    get_short_name,
    split_namespace,
)


class TestFrameworkScene(unittest.TestCase):
    def test_get_short_name(self):
        self.assertEqual(get_short_name("|group1|character:body_GEO"), "body_GEO")
        self.assertEqual(get_short_name("pCube1"), "pCube1")
        self.assertEqual(get_short_name(""), "")

    def test_split_namespace(self):
        self.assertEqual(split_namespace("character:body_GEO"), ("character", "body_GEO"))
        self.assertEqual(split_namespace("|group|rig:arm:hand_JNT"), ("rig:arm", "hand_JNT"))
        self.assertEqual(split_namespace("pCube1"), ("", "pCube1"))


if __name__ == "__main__":
    unittest.main()
