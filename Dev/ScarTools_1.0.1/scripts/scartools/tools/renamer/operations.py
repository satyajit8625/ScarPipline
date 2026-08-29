# -*- coding: utf-8 -*-
"""High-speed Maya cmds and Python operations for Pipeline Renamer."""

from __future__ import print_function

import re
import maya.cmds as cmds

from scartools.framework import (
    OperationResult,
    SceneTransaction,
)

# Standard Department Suffix Presets
DEPARTMENT_SUFFIXES = {
    "Geometry (_GEO)": "_GEO",
    "Group (_GRP)": "_GRP",
    "Joint (_JNT)": "_JNT",
    "Controller (_CTRL)": "_CTRL",
    "Locator (_LOC)": "_LOC",
    "Shader (_SHD)": "_SHD",
    "Shading Group (_SG)": "_SG",
    "Material (_MAT)": "_MAT",
    "Camera (_CAM)": "_CAM",
}

ALL_KNOWN_SUFFIXES = (
    "_GEO", "_GRP", "_JNT", "_CTRL", "_LOC", "_SHD", "_SG", "_MAT", "_CAM",
    "_geo", "_grp", "_jnt", "_ctrl", "_loc", "_shd", "_sg", "_mat", "_cam"
)


def _log(log, message):
    if log is not None:
        log(message)


def get_selected_or_hierarchy(hierarchy=False):
    """
    Return selected DAG nodes or full hierarchy ordered for renaming.

    - When hierarchy=False: Preserves the user's exact selection order (top-to-bottom).
    - When hierarchy=True: Orders hierarchy top-down (parents first, then children).
    """
    selected = cmds.ls(selection=True, long=True) or []
    if not selected:
        return []

    if hierarchy:
        all_nodes = []
        seen = set()
        for s in selected:
            if s not in seen:
                all_nodes.append(s)
                seen.add(s)
            children = cmds.listRelatives(s, allDescendents=True, fullPath=True) or []
            # In Maya, listRelatives with allDescendents returns children bottom-up; reverse for top-down
            for child in reversed(children):
                if child not in seen:
                    all_nodes.append(child)
                    seen.add(child)
        # Order top-down (root/parents first, then children, then grandchildren)
        return sorted(all_nodes, key=lambda x: x.count("|"))

    # Preserve exact user selection order (e.g. top-to-bottom selection)
    return list(selected)


def _int_to_letters(n):
    """Convert a positive integer (1-indexed) to alphabetic sequence (1->A, 2->B, 27->AA)."""
    result = ""
    while n > 0:
        n -= 1
        result = chr(65 + (n % 26)) + result
        n //= 26
    return result or "A"


def compute_new_name(short_name, mode_or_options="unified", options=None, index=1):
    """
    Compute new short name based on unified options or a legacy single-operation mode.

    Args:
        short_name (str): Original short node name.
        mode_or_options (str or dict): Mode name or options dict if unified.
        options (dict, optional): Mode-specific parameters if mode name passed.
        index (int): Index in sequence (for numbering mode, 1-indexed).

    Returns:
        str: Transformed new node name.
    """
    if isinstance(mode_or_options, dict):
        options = mode_or_options
        mode = "unified"
    else:
        mode = mode_or_options or "unified"
        options = options or {}

    name = short_name

    # -------------------------------------------------------------
    # 1. Legacy Single Modes
    # -------------------------------------------------------------
    if mode == "search_replace":
        search = options.get("search", "")
        replace = options.get("replace", "")
        use_regex = options.get("use_regex", False)
        case_sensitive = options.get("case_sensitive", True)

        if search:
            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                try:
                    name = re.sub(search, replace, name, flags=flags)
                except Exception:
                    pass
            else:
                if case_sensitive:
                    name = name.replace(search, replace)
                else:
                    pattern = re.compile(re.escape(search), re.IGNORECASE)
                    name = pattern.sub(replace, name)

    elif mode == "prefix_suffix":
        prefix = options.get("prefix", "")
        suffix = options.get("suffix", "")
        name = "{}{}{}".format(prefix, name, suffix)

    elif mode == "numbering":
        base_name = options.get("base_name", "")
        start_idx = int(options.get("start_idx", 1))
        padding = int(options.get("padding", 2))
        suffix = options.get("suffix", "")

        curr_num = start_idx + (index - 1)
        fmt = "{:0" + str(padding) + "d}" if padding > 0 else "{:d}"
        num_str = fmt.format(curr_num)

        if base_name:
            name = "{}_{}{}".format(base_name, num_str, suffix)
        else:
            name = "{}_{}{}".format(name, num_str, suffix)

    elif mode == "preset":
        target_suffix = options.get("suffix", "_GEO")
        # Strip known existing suffixes first
        clean = name
        for s in ALL_KNOWN_SUFFIXES:
            if clean.endswith(s):
                clean = clean[:-len(s)]
                break
        name = clean + target_suffix

    elif mode == "trim":
        trim_start = int(options.get("trim_start", 0))
        trim_end = int(options.get("trim_end", 0))
        if trim_start > 0:
            name = name[trim_start:]
        if trim_end > 0 and len(name) > trim_end:
            name = name[:-trim_end]

    # -------------------------------------------------------------
    # 2. Unified Master Renaming Pipeline
    # -------------------------------------------------------------
    elif mode == "unified":
        # Step A: Rename from Scratch
        rename_from_scratch = options.get("rename_from_scratch", False)
        base_name = options.get("base_name", "").strip()

        if rename_from_scratch and base_name:
            name = base_name

        # Step B: Search and Replace
        search = options.get("search", "")
        replace = options.get("replace", "")
        if search:
            use_regex = options.get("use_regex", False)
            case_sensitive = options.get("case_sensitive", True)
            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                try:
                    name = re.sub(search, replace, name, flags=flags)
                except Exception:
                    pass
            else:
                if case_sensitive:
                    name = name.replace(search, replace)
                else:
                    pattern = re.compile(re.escape(search), re.IGNORECASE)
                    name = pattern.sub(replace, name)

        # Step C: Numbering
        is_scratch = bool(options.get("rename_from_scratch")) and bool(base_name)
        has_search_replace = bool(search) or bool(replace)

        if "apply_numbering" in options:
            apply_num = bool(options["apply_numbering"])
        else:
            apply_num = is_scratch or int(options.get("padding", 0)) > 0 or options.get("mode") in ("Letter", "Prefix Number", "Suffix Number")

        # Search & Replace on existing names must preserve the replaced string without appending auto-numbering
        if has_search_replace and not is_scratch:
            apply_num = False

        if apply_num:
            num_mode = options.get("mode", "Numbering")
            start_idx = int(options.get("start_idx", 1))
            padding = int(options.get("padding", 2))

            curr_val = start_idx + (index - 1)
            if num_mode == "Letter":
                num_str = _int_to_letters(curr_val)
            else:
                if padding > 0:
                    fmt = "{:0" + str(padding) + "d}"
                    num_str = fmt.format(curr_val)
                else:
                    num_str = str(curr_val)

            # If renumbering existing names without scratch base name, clean trailing number
            if not is_scratch:
                base_cleaned = re.sub(r"(_\d+|\d+)$", "", name)
                if base_cleaned:
                    name = base_cleaned

            if num_mode == "Prefix Number":
                name = "{}_{}".format(num_str, name)
            else:
                name = "{}_{}".format(name, num_str)

        # Step D: Prefix & Suffix
        prefix = options.get("prefix", "")
        suffix = options.get("suffix", "")
        name = "{}{}{}".format(prefix, name, suffix)

    # Sanitize invalid Maya characters (spaces to underscores)
    name = re.sub(r"[\s#$@!%^&*+=~`]+", "_", name)
    return name


def preview_rename(nodes, mode_or_options="unified", options=None):
    """
    Generate an interactive dry-run preview of the proposed rename operation.

    Returns:
        list of dict: [{'full_path', 'short_name', 'new_name', 'changed', 'status', 'color'}]
    """
    if isinstance(mode_or_options, dict):
        options = mode_or_options
        mode = "unified"
    else:
        mode = mode_or_options or "unified"
        options = options or {}

    preview = []
    seen_names = {}
    total_nodes = len(nodes)

    opts = dict(options)
    opts["total_nodes"] = total_nodes

    for idx, path in enumerate(nodes, start=1):
        if not cmds.objExists(path):
            continue
        short = path.split("|")[-1]
        new_name = compute_new_name(short, mode, opts, index=idx)
        changed = (short != new_name)

        status = "No Change" if not changed else "Will Rename"
        color = "#A0A0A0" if not changed else "#72D6AA"

        # Check collisions
        if new_name in seen_names:
            status = "Collision (Duplicate)"
            color = "#F07D7D"
        elif not new_name or new_name == "_":
            status = "Invalid Name"
            color = "#F07D7D"

        seen_names[new_name] = path

        preview.append({
            "full_path": path,
            "short_name": short,
            "new_name": new_name,
            "changed": changed,
            "status": status,
            "color": color,
        })

    return preview


def execute_batch_rename(nodes, mode_or_options="unified", options=None, log=None):
    """
    Execute batch renaming inside an atomic Maya undo transaction.

    Returns:
        int: Total number of nodes successfully renamed.
    """
    if isinstance(mode_or_options, dict):
        options = mode_or_options
        mode = "unified"
    else:
        mode = mode_or_options or "unified"
        options = options or {}

    with SceneTransaction("PipelineBatchRename"):
        preview_list = preview_rename(nodes, mode, options)
        renamed_count = 0

        # Sort deepest child first so renaming children does not invalidate parent paths
        preview_list.sort(key=lambda x: x["full_path"].count("|"), reverse=True)

        for item in preview_list:
            if not item["changed"] or "Collision" in item["status"] or "Invalid" in item["status"]:
                continue
            path = item["full_path"]
            new_name = item["new_name"]

            if not cmds.objExists(path):
                continue
            try:
                cmds.rename(path, new_name)
                renamed_count += 1
                _log(log, "INFO: Renamed '{}' -> '{}'".format(item["short_name"], new_name))
            except Exception as exc:
                _log(log, "ERROR: Could not rename '{}': {}".format(path, exc))

        _log(log, "\nSUCCESS: ✓ Batch renamed {} node(s) in 1 unified Maya undo step.".format(renamed_count))
        return renamed_count
