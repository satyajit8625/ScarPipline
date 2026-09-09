"""Headless suite diagnostics suitable for support reports and mayapy."""

from __future__ import print_function

import os
import sys

from .builtin import BUILTIN_TOOL_MANIFESTS
from .catalog import manifest_data
from .compat import maya_major_version
from .framework.paths import package_root, scripts_root
from .version import VERSION


def collect():
    """Return a JSON-safe snapshot without importing any tool UI."""
    root = package_root()
    return {
        "suite": "ScarTools",
        "version": VERSION,
        "maya_version": maya_major_version(),
        "python_version": "{}.{}.{}".format(*sys.version_info[:3]),
        "package_root": root,
        "scripts_root": scripts_root(),
        "package_exists": os.path.isdir(root),
        "tools": list(manifest_data()),
        "manifest_entry_points": list(BUILTIN_TOOL_MANIFESTS),
        "qt_loaded": any(
            name == "PySide2" or name.startswith("PySide2.")
            or name == "PySide6" or name.startswith("PySide6.")
            for name in sys.modules
        ),
    }


def format_report(data=None):
    data = data or collect()
    lines = [
        "ScarTools Diagnostics",
        "Version: {}".format(data["version"]),
        "Maya: {}".format(data["maya_version"]),
        "Python: {}".format(data["python_version"]),
        "Root: {}".format(data["package_root"]),
        "Tools: {}".format(len(data["tools"])),
        "Qt loaded: {}".format(data["qt_loaded"]),
    ]
    for tool in data["tools"]:
        lines.append(
            "- {label} [{tool_id}] v{version}".format(**tool)
        )
    return "\n".join(lines)


def run_self_test():
    """
    Execute comprehensive suite health checks and return diagnostics report.

    Returns:
        dict: {
            "all_passed": bool,
            "tests": list[dict],
            "report_text": str
        }
    """
    tests = []
    
    # 1. Package Root Exists
    root = package_root()
    root_ok = os.path.isdir(root)
    tests.append({
        "name": "Package Root Directory",
        "status": "PASS" if root_ok else "FAIL",
        "details": root,
    })

    # 2. Scripts Directory Exists
    s_root = scripts_root()
    s_ok = os.path.isdir(s_root)
    tests.append({
        "name": "Scripts Directory",
        "status": "PASS" if s_ok else "FAIL",
        "details": s_root,
    })

    # 3. Tool Manifests Loaded
    manifests_list = list(manifest_data())
    manifest_ok = len(manifests_list) > 0
    tests.append({
        "name": "Registered Tool Manifests",
        "status": "PASS" if manifest_ok else "FAIL",
        "details": "{} tools discovered".format(len(manifests_list)),
    })

    # 4. Icon Resolution
    from .framework.paths import resolve_icon
    missing_icons = []
    for tool in manifests_list:
        icon_name = tool.get("icon", "")
        if icon_name:
            path = resolve_icon(icon_name)
            if not path or not os.path.isfile(path):
                missing_icons.append(icon_name)
    tests.append({
        "name": "Icon Assets Integrity",
        "status": "PASS" if not missing_icons else "WARN",
        "details": "All icons resolved" if not missing_icons else "Missing: " + ", ".join(missing_icons),
    })

    # 5. Licensing System
    try:
        from .licensing import is_activated
        lic_ok = is_activated()
        tests.append({
            "name": "License Activation",
            "status": "PASS" if lic_ok else "INFO",
            "details": "Activated" if lic_ok else "Demo / Unlicensed mode",
        })
    except Exception as e:
        tests.append({
            "name": "License System",
            "status": "FAIL",
            "details": str(e),
        })

    # 6. Temp Write Permission
    import tempfile
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"scartools_test")
        tmp.close()
        os.remove(tmp.name)
        write_ok = True
    except Exception:
        write_ok = False
    tests.append({
        "name": "Filesystem Write Permission",
        "status": "PASS" if write_ok else "FAIL",
        "details": "OK" if write_ok else "Temp directory not writable",
    })

    all_passed = all(t["status"] in ("PASS", "INFO") for t in tests)

    lines = [
        "=" * 60,
        "SCARTOOLS SUITE HEALTH & DIAGNOSTICS SELF-TEST",
        "=" * 60,
        "Suite Version: {}".format(VERSION),
        "Maya Version : {}".format(maya_major_version()),
        "Status       : {}".format("HEALTHY (All Passed)" if all_passed else "ATTENTION NEEDED"),
        "-" * 60,
    ]
    for t in tests:
        lines.append("[{:4s}] {:<30s} : {}".format(t["status"], t["name"], t["details"]))
    lines.append("=" * 60)

    report_text = "\n".join(lines)
    return {
        "all_passed": all_passed,
        "tests": tests,
        "report_text": report_text,
    }


__all__ = ["collect", "format_report", "run_self_test"]
