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

from scartools.settings import ToolSettings, get_string, set_string, get_bool, set_bool


class TestSettings(unittest.TestCase):
    def test_tool_settings_scope(self):
        ts = ToolSettings("test_tool")
        ts.set_string("last_path", "O:/Rnd/Assets")
        self.assertEqual(ts.get_string("last_path"), "O:/Rnd/Assets")

        ts.set_bool("auto_fix", True)
        self.assertTrue(ts.get_bool("auto_fix"))

        ts.set_int("count", 42)
        self.assertEqual(ts.get_int("count"), 42)

        ts.set_json("config", {"mode": "export", "step": 1})
        self.assertEqual(ts.get_json("config")["mode"], "export")

        ts.remove("last_path")
        self.assertEqual(ts.get_string("last_path", "default"), "default")


if __name__ == "__main__":
    unittest.main()
