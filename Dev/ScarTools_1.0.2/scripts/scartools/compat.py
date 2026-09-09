"""Runtime compatibility checks shared by ScarTools components."""

from __future__ import print_function

import re

import maya.cmds as cmds


MIN_MAYA_VERSION = 2023


def maya_major_version():
    """Return Maya's four-digit major version without assuming text format."""
    version_text = str(cmds.about(version=True) or "")
    match = re.search(r"(?:^|\D)(20\d{2})(?:\D|$)", version_text)
    if match:
        return int(match.group(1))

    try:
        api_version = int(cmds.about(apiVersion=True))
    except Exception:
        api_version = 0
    if api_version >= 20000000:
        return api_version // 10000

    raise RuntimeError("Could not determine the running Maya version.")


def ensure_supported():
    """Reject Maya releases older than the production support baseline."""
    version = maya_major_version()
    if version < MIN_MAYA_VERSION:
        raise RuntimeError(
            "ScarTools requires Maya {} or newer. Running Maya {}.".format(
                MIN_MAYA_VERSION, version
            )
        )
    return version
