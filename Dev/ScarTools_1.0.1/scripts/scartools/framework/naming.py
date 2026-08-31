# -*- coding: utf-8 -*-
"""Centralized Maya Naming & Studio Suffix Registry.

Provides studio naming standards, illegal character sanitization,
clean prefix/suffix attachment, and version string parsing.
"""

from __future__ import absolute_import, division, print_function

import re


class SuffixRegistry(object):
    """Standard studio suffixes for Maya pipeline nodes."""
    GEOMETRY = "_GEO"
    GROUP = "_GRP"
    JOINT = "_JNT"
    CONTROL = "_CTRL"
    MATERIAL = "_MAT"
    SHADING_GROUP = "_SG"
    TEXTURE = "_TEX"
    LOCATOR = "_LOC"
    IK_HANDLE = "_IKH"
    BLENDSHAPE = "_BS"

    ALL_SUFFIXES = (
        GEOMETRY, GROUP, JOINT, CONTROL, MATERIAL,
        SHADING_GROUP, TEXTURE, LOCATOR, IK_HANDLE, BLENDSHAPE
    )


def sanitize_maya_name(name, replacement="_"):
    """
    Replace illegal Maya naming characters (spaces, hyphens, symbols) with replacement.

    Args:
        name (str): Original string.
        replacement (str): Character to replace illegal characters with.

    Returns:
        str: Valid Maya node name string.
    """
    if not name:
        return ""
    # Strip leading/trailing whitespace
    clean = str(name).strip()
    # Replace non-alphanumeric and non-underscore with replacement
    clean = re.sub(r"[^a-zA-Z0-9_]", replacement, clean)
    # Ensure it doesn't start with a number
    if clean and clean[0].isdigit():
        clean = "_" + clean
    # Collapse multiple consecutive underscores
    clean = re.sub(r"_+", "_", clean)
    return clean


def apply_affixes(name, prefix="", suffix="", separator="_"):
    """
    Apply prefix and/or suffix to a base name cleanly without double-separators.

    Args:
        name (str): Base name.
        prefix (str): Optional prefix to prepend.
        suffix (str): Optional suffix to append.
        separator (str): Separator to normalize.

    Returns:
        str: Assembled name.
    """
    if not name:
        return ""

    result = str(name)
    if prefix:
        p = str(prefix)
        if not p.endswith(separator) and not result.startswith(separator):
            result = p + separator + result
        else:
            result = p + result

    if suffix:
        s = str(suffix)
        if not s.startswith(separator) and not result.endswith(separator):
            result = result + separator + s
        else:
            result = result + s

    # Normalize double separators
    if separator:
        result = re.sub(re.escape(separator) + r"+", separator, result)

    return result


def split_version_string(text):
    """
    Parse a version string (e.g. 'v001', 'asset_v02', '3') into prefix, number, and padding.

    Returns:
        tuple[str, int, int]: (base_prefix, version_int, padding_digits)
    """
    if not text:
        return ("", 1, 3)

    match = re.search(r"(.*?)v?(\d+)$", str(text), re.IGNORECASE)
    if match:
        prefix = match.group(1)
        num_str = match.group(2)
        return (prefix, int(num_str), len(num_str))
    return (str(text), 1, 3)


def format_version(version_num, padding=3, prefix="v"):
    """Format an integer as a standard version string (e.g., v001, v012)."""
    fmt = "{}{:0" + str(max(1, int(padding))) + "d}"
    return fmt.format(prefix, int(version_num))


def parse_shot_scene_identity(scene_path=None):
    """
    Parse studio shot scene file naming:
    Pattern: <PROJECT>_<SEQ>_<SHOT>_<DEPT>_<VERSION>
    Example: 'PRT_SH_010_ANM_V001.ma'
      - project: 'PRT'
      - sequence: 'SH'
      - shot_num: '010'
      - shot_name: 'PRT_SH_010'
      - department: 'ANM'
      - version_str: 'V001'
      - version_num: 1
      - scene_dir: Directory containing the scene file
      - export_dir: Resolved export destination folder

    Args:
        scene_path (str, optional): Full path to scene file. If None, queries active Maya scene.

    Returns:
        dict: Standardized shot scene identity dictionary.
    """
    import os
    if scene_path is None:
        try:
            import maya.cmds as cmds
            scene_path = cmds.file(query=True, sceneName=True) or ""
        except Exception:
            scene_path = ""

    clean_path = str(scene_path or "").replace("\\", "/")
    if clean_path:
        filename = clean_path.rsplit("/", 1)[-1]
        scene_dir = clean_path.rsplit("/", 1)[0]
    else:
        filename = ""
        scene_dir = ""

    stem = os.path.splitext(filename)[0] if filename else ""
    if not stem:
        stem = "untitled_scene"

    tokens = stem.split("_")
    project = ""
    sequence = ""
    shot_num = ""
    shot_name = ""
    department = ""
    version_str = "V001"
    version_num = 1

    # 1. Check for trailing version token (e.g. V001, v002, 001)
    if tokens and re.match(r"^v?\d+$", tokens[-1], re.IGNORECASE):
        v_token = tokens[-1]
        version_str = v_token.upper() if v_token.lower().startswith("v") else "V" + v_token
        v_match = re.search(r"\d+", v_token)
        version_num = int(v_match.group(0)) if v_match else 1
        core_tokens = tokens[:-1]
    else:
        core_tokens = tokens

    # 2. Check if second to last token is department (e.g. ANM, MOD, RIG, TXT, LGT, CMP, FX, LAY)
    KNOWN_DEPTS = {"ANM", "ANIM", "MOD", "MODEL", "RIG", "RIGGING", "TXT", "TEX", "LGT", "LIGHT", "CMP", "COMP", "FX", "CFX", "LAY", "LAYOUT"}
    if core_tokens and core_tokens[-1].upper() in KNOWN_DEPTS:
        department = core_tokens[-1].upper()
        core_tokens = core_tokens[:-1]

    # 3. Resolve Project and Shot Name
    if len(core_tokens) >= 3:
        project = core_tokens[0]
        sequence = core_tokens[1]
        shot_num = core_tokens[2]
        shot_name = "_".join(core_tokens)
    elif len(core_tokens) == 2:
        project = core_tokens[0]
        shot_name = "_".join(core_tokens)
    elif len(core_tokens) == 1:
        shot_name = core_tokens[0]
    else:
        shot_name = stem

    # 4. Resolve default Shot Root & Export Directory
    export_dir = ""
    alembic_dir = ""
    fbx_dir = ""
    if scene_dir:
        norm_dir = os.path.normpath(scene_dir)
        dir_name = os.path.basename(norm_dir).lower()
        parent_dir = os.path.dirname(norm_dir)
        if dir_name in ("maya", "scenes", "scene", "work", "wip", "wips", "scripts"):
            shot_root = parent_dir.replace("\\", "/")
        else:
            shot_root = norm_dir.replace("\\", "/")

        export_dir = shot_root
        alembic_dir = os.path.join(shot_root, "Alembic").replace("\\", "/")
        fbx_dir = os.path.join(shot_root, "FBX").replace("\\", "/")

    return {
        "file_name": filename,
        "stem": stem,
        "scene_dir": scene_dir,
        "shot_root": export_dir,
        "export_dir": export_dir,
        "alembic_dir": alembic_dir,
        "fbx_dir": fbx_dir,
        "project": project,
        "sequence": sequence,
        "shot_num": shot_num,
        "shot_name": shot_name,
        "department": department,
        "version_str": version_str,
        "version_num": version_num,
    }


__all__ = [
    "SuffixRegistry",
    "sanitize_maya_name",
    "apply_affixes",
    "split_version_string",
    "format_version",
    "parse_shot_scene_identity",
]
