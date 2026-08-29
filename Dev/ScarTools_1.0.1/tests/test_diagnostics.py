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

from scartools.diagnostics import collect, format_report, run_self_test


class TestDiagnostics(unittest.TestCase):
    def test_collect(self):
        data = collect()
        self.assertEqual(data["suite"], "ScarTools")
        self.assertIn("tools", data)
        self.assertTrue(len(data["tools"]) >= 6)

    def test_format_report(self):
        report = format_report()
        self.assertIn("ScarTools Diagnostics", report)

    def test_run_self_test(self):
        res = run_self_test()
        self.assertIn("all_passed", res)
        self.assertIn("report_text", res)
        self.assertIn("SCARTOOLS SUITE HEALTH", res["report_text"])


if __name__ == "__main__":
    unittest.main()
