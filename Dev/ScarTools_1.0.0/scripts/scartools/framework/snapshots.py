"""Shared scene identity and atomic snapshot-folder services.

This module intentionally has no Qt dependency.  It can be reused by Maya UI
tools, shelf commands, batch jobs, and maya.standalone processes.
"""

from __future__ import print_function

import os
import re

import maya.cmds as cmds


_INVALID_FILENAME_CHARS = '<>:"/\\|?*'
_SCENE_VERSION_SUFFIX_RE = re.compile(
    r"(?:[_.\- ]+(?:(?:version|ver|v)[_.\- ]*)?\d+)$",
    re.IGNORECASE,
)
_VERSION_FOLDER_RE = re.compile(r"^v(\d+)$", re.IGNORECASE)


class SnapshotError(RuntimeError):
    """Raised when a scene snapshot location cannot be resolved safely."""


def current_scene_path():
    """Return the normalized current Maya scene path, or an empty string."""
    scene_path = cmds.file(query=True, sceneName=True) or ""
    return os.path.normpath(scene_path) if scene_path else ""


def require_saved_scene():
    """Return the current scene path, rejecting unsaved scenes."""
    scene_path = current_scene_path()
    if not scene_path:
        raise SnapshotError(
            "Save the Maya scene first. Pipeline snapshots require a stable "
            "asset name derived from the scene file."
        )
    return scene_path


def asset_key(value):
    """Normalize a versioned scene/file/folder name to one stable asset key."""
    portable_value = str(value or "").replace("\\", "/")
    name = os.path.splitext(portable_value.rsplit("/", 1)[-1])[0]
    name = _SCENE_VERSION_SUFFIX_RE.sub("", name).strip("_.- ")
    for character in _INVALID_FILENAME_CHARS:
        name = name.replace(character, "_")
    return name or "untitled_scene"


def current_asset_key():
    """Return the stable key for the current Maya scene."""
    path = current_scene_path()
    return asset_key(path) if path else "untitled_scene"


def current_scene_metadata():
    """Return portable source-scene identity for package manifests."""
    path = current_scene_path()
    file_name = path.replace("\\", "/").rsplit("/", 1)[-1] if path else ""
    key = current_asset_key()
    return {"fileName": file_name, "folderName": key, "assetKey": key}


def version_number(folder_name):
    """Return the integer in a v### folder name, otherwise ``None``."""
    match = _VERSION_FOLDER_RE.match(str(folder_name or ""))
    return int(match.group(1)) if match else None


def version_directories(asset_directory):
    """Return existing ``(number, path)`` version folders in numeric order."""
    if not os.path.isdir(asset_directory):
        return []
    versions = []
    for name in os.listdir(asset_directory):
        number = version_number(name)
        path = os.path.join(asset_directory, name)
        if number is not None and os.path.isdir(path):
            versions.append((number, path))
    versions.sort(key=lambda item: item[0])
    return versions


def asset_directory(root_directory, create=False):
    """Resolve <root>/<stable asset> from a root, asset, or v### choice."""
    root_directory = os.path.normpath(root_directory)
    key = current_asset_key()
    base = os.path.basename(root_directory)
    parent = os.path.dirname(root_directory)

    # 1. If root_directory already has v### subdirectories, it IS an asset directory!
    if os.path.isdir(root_directory) and len(version_directories(root_directory)) > 0:
        return root_directory

    # 2. If root_directory itself is a v### folder
    if version_number(base) is not None:
        return parent

    # 3. If base name matches current asset key
    if asset_key(base).lower() == key.lower():
        return root_directory

    # 4. Standard path: <root_directory>/<current_asset_key>
    candidate = os.path.join(root_directory, key)
    if os.path.isdir(candidate) or create:
        if create and not os.path.isdir(candidate):
            os.makedirs(candidate)
        return candidate

    # 5. Look for any existing asset directory inside root_directory
    if os.path.isdir(root_directory):
        for name in os.listdir(root_directory):
            sub_path = os.path.join(root_directory, name)
            if os.path.isdir(sub_path) and len(version_directories(sub_path)) > 0:
                return sub_path

    return candidate


def reserve_next_version(asset_directory_path):
    """Atomically reserve and return the next ``(directory, v###)`` snapshot."""
    if not os.path.isdir(asset_directory_path):
        os.makedirs(asset_directory_path)
    versions = version_directories(asset_directory_path)
    next_number = (versions[-1][0] + 1) if versions else 1
    while True:
        name = "v{:03d}".format(next_number)
        path = os.path.join(asset_directory_path, name)
        try:
            os.mkdir(path)
            return path, name
        except OSError:
            if not os.path.isdir(path):
                raise
            next_number += 1


def latest_version(asset_directory_path):
    """Return the newest ``(directory, v###)`` or ``(None, None)``."""
    versions = version_directories(asset_directory_path)
    if not versions:
        return None, None
    _number, path = versions[-1]
    return path, os.path.basename(path)


def resolve_import_version(asset_directory_path, requested_directory=None):
    """Use an explicitly selected v###, otherwise use the latest snapshot."""
    asset_directory_path = os.path.normpath(asset_directory_path)
    if requested_directory:
        requested_directory = os.path.normpath(requested_directory)
        name = os.path.basename(requested_directory)
        parent = os.path.dirname(requested_directory)
        if (
            version_number(name) is not None
            and os.path.normcase(parent) == os.path.normcase(asset_directory_path)
            and os.path.isdir(requested_directory)
        ):
            return requested_directory, name
    return latest_version(asset_directory_path)


def validate_scene_identity(source_scene, error_type=SnapshotError):
    """Allow cross-department transfers (e.g. Model -> Rig -> Anim)."""
    return True



__all__ = [
    "SnapshotError",
    "asset_directory",
    "asset_key",
    "current_asset_key",
    "current_scene_metadata",
    "current_scene_path",
    "latest_version",
    "require_saved_scene",
    "reserve_next_version",
    "resolve_import_version",
    "validate_scene_identity",
    "version_directories",
    "version_number",
]
