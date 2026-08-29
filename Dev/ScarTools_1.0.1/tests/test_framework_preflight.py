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

from scartools.framework.preflight import (
    PreflightSeverity,
    PreflightStatus,
    PreflightIssue,
    PreflightCheck,
    PreflightReport,
)


class DummyPassCheck(PreflightCheck):
    CHECK_ID = "dummy_pass"
    LABEL = "Dummy Pass"

    def inspect(self, nodes=None):
        return []


class DummyFailCheck(PreflightCheck):
    CHECK_ID = "dummy_fail"
    LABEL = "Dummy Fail"

    def inspect(self, nodes=None):
        return [
            PreflightIssue("pCube1", "Unfrozen transform", self.CHECK_ID, PreflightSeverity.WARNING, can_fix=True)
        ]

    def fix(self, issues=None):
        return len(issues or [])


class TestFrameworkPreflight(unittest.TestCase):
    def test_preflight_report_clean(self):
        report = PreflightReport("modeling")
        check = DummyPassCheck()
        issues = check.inspect()
        report.add_result(check.CHECK_ID, check.LABEL, check.CATEGORY, check.SEVERITY, PreflightStatus.OK, issues)

        self.assertTrue(report.is_clean)
        self.assertEqual(report.total_checks, 1)
        self.assertEqual(report.summary_counts["OK"], 1)

    def test_preflight_report_with_issues(self):
        report = PreflightReport("modeling")
        check = DummyFailCheck()
        issues = check.inspect()
        report.add_result(
            check.CHECK_ID, check.LABEL, check.CATEGORY, check.SEVERITY,
            PreflightStatus.WARNING, issues, fix_fn=check.fix
        )

        self.assertFalse(report.is_clean)
        self.assertEqual(len(report.failed_checks), 1)
        self.assertEqual(len(report.issues), 1)
        self.assertEqual(report.issues[0].node, "pCube1")

        # Test fix execution
        fixed = check.fix(issues)
        self.assertEqual(fixed, 1)


if __name__ == "__main__":
    unittest.main()
