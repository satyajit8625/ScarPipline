# -*- coding: utf-8 -*-
"""
ScarTools In-App Update Engine & Hot-Reload System.

Provides non-blocking background update checks against studio network Share/
and remote Git repositories with 1-click in-place Maya hot-reloading.
"""

from __future__ import absolute_import, division, print_function

import importlib
import json
import os
import re
import shutil
import sys
import threading
import time

from scartools.framework.logging import emit_log
from scartools.ui.qt import QtCore, QtWidgets, QtGui

CURRENT_VERSION = "1.0.1"
_UPDATE_CACHE = {"latest_version": None, "share_path": None, "has_update": False, "last_checked": 0}


def parse_version_tuple(v_str):
    """Convert version string '1.0.2' into comparable integer tuple (1, 0, 2)."""
    clean = re.sub(r"[^0-9.]", "", str(v_str or "0.0.0"))
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer_version(candidate_ver, current_ver=CURRENT_VERSION):
    """Return True if candidate version is strictly newer than current version."""
    return parse_version_tuple(candidate_ver) > parse_version_tuple(current_ver)


def find_share_directory():
    """Discover studio network Share/ directory relative to workspace or standard locations."""
    # 1. Environment variable override
    env_share = os.environ.get("SCARTOOLS_SHARE_DIR")
    if env_share and os.path.isdir(env_share):
        return os.path.normpath(env_share)

    # 2. Relative to active scripts folder
    here = os.path.abspath(os.path.dirname(__file__))
    parts = here.split(os.sep)
    try:
        idx = parts.index("ScarTools_" + CURRENT_VERSION)
        root = os.sep.join(parts[:idx])
        parent = os.path.dirname(root)
        share_candidate = os.path.join(parent, "Share")
        if os.path.isdir(share_candidate):
            return os.path.normpath(share_candidate)
    except Exception:
        pass

    # 3. Standard workspace search
    for drive in ["O:", "D:", "C:"]:
        candidate = os.path.join(drive, os.sep, "Rnd", "Scripts", "ScarPipline", "Share")
        if os.path.isdir(candidate):
            return os.path.normpath(candidate)

    return None


def get_available_share_versions(share_dir=None):
    """Scan Share/ directory for released version packages."""
    s_dir = share_dir or find_share_directory()
    if not s_dir or not os.path.isdir(s_dir):
        return []

    versions = []
    for item in os.listdir(s_dir):
        m = re.match(r"^ScarTools_([0-9]+\.[0-9]+\.[0-9]+)$", item, re.IGNORECASE)
        if m:
            v_str = m.group(1)
            pkg_path = os.path.join(s_dir, item)
            if os.path.isdir(pkg_path):
                versions.append({
                    "version": v_str,
                    "path": pkg_path,
                    "tuple": parse_version_tuple(v_str),
                })

    versions.sort(key=lambda x: x["tuple"], reverse=True)
    return versions


def check_for_updates(force=False, async_callback=None):
    """
    Check for available updates. Returns dict with status and version info.
    If async_callback is provided, executes non-blocking on a background thread.
    """
    global _UPDATE_CACHE
    now = time.time()

    # Cache for 60 seconds unless forced
    if not force and _UPDATE_CACHE["last_checked"] > 0 and (now - _UPDATE_CACHE["last_checked"] < 60):
        if async_callback:
            async_callback(_UPDATE_CACHE)
        return _UPDATE_CACHE

    def _do_check():
        available = get_available_share_versions()
        latest = available[0] if available else None

        has_newer = False
        if latest and is_newer_version(latest["version"], CURRENT_VERSION):
            has_newer = True

        res = {
            "current_version": CURRENT_VERSION,
            "latest_version": latest["version"] if latest else CURRENT_VERSION,
            "share_path": latest["path"] if latest else None,
            "has_update": has_newer,
            "last_checked": time.time(),
        }
        _UPDATE_CACHE.update(res)

        if async_callback:
            async_callback(res)
        return res

    if async_callback:
        t = threading.Thread(target=_do_check)
        t.daemon = True
        t.start()
        return _UPDATE_CACHE
    else:
        return _do_check()


def apply_hot_update(target_share_path=None, target_version=None):
    """
    1-Click Hot-Reload in Maya:
    Updates sys.path, reloads scartools modules, and refreshes Maya menus.
    """
    share_dir = find_share_directory()
    if not target_share_path and share_dir:
        available = get_available_share_versions(share_dir)
        if available:
            target_share_path = available[0]["path"]
            target_version = available[0]["version"]

    if not target_share_path or not os.path.isdir(target_share_path):
        raise RuntimeError("Target update release directory not found: {}".format(target_share_path))

    scripts_dir = os.path.join(target_share_path, "scripts")
    if not os.path.isdir(scripts_dir):
        scripts_dir = target_share_path

    emit_log("Applying ScarTools hot-update to v{}...".format(target_version or "latest"), level="INFO", source="updater")

    # Update sys.path
    norm_scripts = os.path.normpath(scripts_dir)
    to_remove = [p for p in sys.path if "ScarTools_" in p and "scripts" in p]
    for p in to_remove:
        try:
            sys.path.remove(p)
        except Exception:
            pass

    if norm_scripts not in sys.path:
        sys.path.insert(0, norm_scripts)

    # Invalidate and reload scartools modules
    reloaded_count = 0
    scartools_modules = [m for m in list(sys.modules.keys()) if m == "scartools" or m.startswith("scartools.")]
    
    # Sort modules so parents reload after children
    scartools_modules.sort(key=lambda m: m.count("."), reverse=True)

    for mod_name in scartools_modules:
        mod = sys.modules.get(mod_name)
        if mod:
            try:
                importlib.reload(mod)
                reloaded_count += 1
            except Exception:
                pass

    # Refresh Maya menu if available
    try:
        import maya.cmds as cmds
        if hasattr(cmds, "evalDeferred"):
            cmds.evalDeferred("import scartools.bootstrap; scartools.bootstrap.install_menu()")
    except Exception:
        pass

    emit_log("ScarTools updated successfully to v{} ({} modules reloaded).".format(target_version or "latest", reloaded_count), level="SUCCESS", source="updater")
    return {
        "success": True,
        "version": target_version or "latest",
        "modules_reloaded": reloaded_count,
    }
