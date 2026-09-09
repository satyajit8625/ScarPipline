# -*- coding: utf-8 -*-
"""Centralized Diagnostics and Crash Reporter for ScarTools."""

from __future__ import absolute_import, division, print_function

import os
import sys
import time
import zipfile
import traceback
from datetime import datetime

from scartools.version import VERSION
from scartools.compat import maya_major_version
from scartools.framework.paths import package_root, scripts_root


def get_environment_info(active_tool=None):
    """Collect runtime environment diagnostic dictionary."""
    return {
        "suite_version": VERSION,
        "maya_version": maya_major_version(),
        "python_version": "{}.{}.{}".format(*sys.version_info[:3]),
        "platform": sys.platform,
        "package_root": package_root(),
        "scripts_root": scripts_root(),
        "active_tool": str(active_tool or "General"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def generate_crash_report(active_tool="General", error=None, extra_info=None, output_dir=None):
    """
    Bundle diagnostic logs, system state, and exception traceback into a zip package.

    Returns:
        str: Path to the generated ScarTools_Crash_Report.zip
    """
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or os.path.expanduser("~")
    if not output_dir:
        output_dir = os.path.join(home, ".scartools", "crashes")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = "ScarTools_Crash_Report_{}.zip".format(timestamp_str)
    zip_path = os.path.join(output_dir, zip_filename)

    env_info = get_environment_info(active_tool=active_tool)

    # Format traceback
    if error is not None:
        if isinstance(error, BaseException):
            tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
            tb_str = "".join(tb_lines)
        else:
            tb_str = str(error)
    else:
        tb_str = traceback.format_exc()
        if not tb_str or "NoneType: None" in tb_str:
            tb_str = "No active traceback recorded."

    log_file_path = os.path.join(home, ".scartools", "logs", "scarTools.log")
    log_content = ""
    if os.path.isfile(log_file_path):
        try:
            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                # Read last 500 lines
                lines = f.readlines()
                log_content = "".join(lines[-500:])
        except Exception:
            log_content = "Failed to read scarTools.log"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # 1. maya_version.txt
        zipf.writestr("maya_version.txt", "Maya {}\nPlatform: {}".format(env_info["maya_version"], sys.platform))

        # 2. python_version.txt
        zipf.writestr("python_version.txt", "Python {}\nExecutable: {}".format(env_info["python_version"], sys.executable))

        # 3. active_tool.txt
        zipf.writestr("active_tool.txt", "Active Tool: {}\nSuite Version: {}\nTimestamp: {}".format(
            env_info["active_tool"], env_info["suite_version"], env_info["timestamp"]
        ))

        # 4. traceback.txt
        zipf.writestr("traceback.txt", tb_str)

        # 5. logs.txt
        zipf.writestr("logs.txt", log_content)

        # 6. extra_info.txt (if provided)
        if extra_info:
            zipf.writestr("extra_info.txt", str(extra_info))

    return zip_path


__all__ = ["generate_crash_report", "get_environment_info"]
