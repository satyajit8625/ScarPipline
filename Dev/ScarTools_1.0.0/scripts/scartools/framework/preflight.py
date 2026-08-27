# -*- coding: utf-8 -*-
"""Centralized Preflight & Scene QA Check Framework.

Provides base classes for creating standardized scene hygiene checks,
severity categorization, issue reporting, and atomic batch fixers.
"""

from __future__ import absolute_import, division, print_function

import json


class PreflightSeverity(object):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class PreflightStatus(object):
    OK = "OK"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


class PreflightIssue(object):
    """Encapsulates a single issue identified by a preflight check."""

    def __init__(self, node, message, check_id="", severity=PreflightSeverity.WARNING, can_fix=False):
        self.node = str(node)
        self.message = str(message)
        self.check_id = str(check_id)
        self.severity = str(severity)
        self.can_fix = bool(can_fix)

    def as_dict(self):
        return {
            "node": self.node,
            "message": self.message,
            "check_id": self.check_id,
            "severity": self.severity,
            "can_fix": self.can_fix,
        }


class PreflightCheck(object):
    """Abstract base class for all ScarTools QA and inspection checks."""

    CHECK_ID = "generic_check"
    LABEL = "Generic Check"
    CATEGORY = "General"
    SEVERITY = PreflightSeverity.WARNING
    DESCRIPTION = ""

    def __init__(self):
        pass

    def inspect(self, nodes=None):
        """
        Run the check against given or all scene nodes.

        Args:
            nodes (list[str], optional): Nodes to inspect. If None, inspects active scene.

        Returns:
            list[PreflightIssue]: List of issues discovered. Empty list if passing.
        """
        raise NotImplementedError

    def fix(self, issues=None):
        """
        Execute automatic, safe fixes for detected issues.

        Args:
            issues (list[PreflightIssue], optional): Specific issues to fix.

        Returns:
            int: Count of issues resolved.
        """
        return 0


class PreflightReport(object):
    """Aggregates results across multiple preflight checks."""

    def __init__(self, department="general"):
        self.department = str(department)
        self.results = {}
        self.issues = []

    def add_result(self, check_id, label, category, severity, status, issues=None, fix_fn=None):
        issues = issues or []
        self.results[check_id] = {
            "check_id": check_id,
            "label": label,
            "category": category,
            "severity": severity,
            "status": status,
            "issue_count": len(issues),
            "issues": [i.as_dict() if hasattr(i, "as_dict") else dict(i) for i in issues],
            "has_fix": fix_fn is not None,
        }
        self.issues.extend(issues)

    @property
    def total_checks(self):
        return len(self.results)

    @property
    def failed_checks(self):
        return [r for r in self.results.values() if r["status"] in (PreflightStatus.FAIL, PreflightStatus.WARNING)]

    @property
    def is_clean(self):
        return len(self.failed_checks) == 0

    @property
    def summary_counts(self):
        counts = {"OK": 0, "WARNING": 0, "FAIL": 0, "SKIPPED": 0}
        for r in self.results.values():
            st = r["status"]
            counts[st] = counts.get(st, 0) + 1
        return counts

    def as_dict(self):
        return {
            "department": self.department,
            "summary": self.summary_counts,
            "is_clean": self.is_clean,
            "checks": self.results,
        }

    def to_json(self, indent=2):
        return json.dumps(self.as_dict(), indent=indent)


__all__ = [
    "PreflightSeverity",
    "PreflightStatus",
    "PreflightIssue",
    "PreflightCheck",
    "PreflightReport",
]
