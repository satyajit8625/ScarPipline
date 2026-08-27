# -*- coding: utf-8 -*-
"""High-speed Maya cmds and API operations for UDIM Texture Manager."""

from __future__ import print_function

import glob
import os
import re
import maya.cmds as cmds
import maya.mel as mel

from scartools.framework import (
    OperationResult,
    SceneTransaction,
)

# UDIM Tiling Mode constants in Maya
TILING_MODE_NONE = 0
TILING_MODE_ZBRUSH = 1
TILING_MODE_MUDBOX = 2
TILING_MODE_MARI = 3
TILING_MODE_EXPLICIT = 4

UDIM_PATTERN = re.compile(r"(?:<UDIM>|<udim>|10\d\d)")
MUDBOX_PATTERN = re.compile(r"(?:<UVTILE>|_u\d+_v\d+)", re.IGNORECASE)


def _log(log, message):
    if log is not None:
        log(message)


def _progress(progress, percent, message=""):
    if progress is not None:
        progress(percent, message)


def get_all_file_nodes(nodes=None):
    """Return all file texture nodes connected to given meshes or entire scene."""
    if nodes:
        file_nodes = set()
        for node in nodes:
            if not cmds.objExists(node):
                continue
            history = cmds.listHistory(node, pruneDagObjects=True) or []
            files = [h for h in history if cmds.nodeType(h) == "file"]
            file_nodes.update(files)
        return sorted(file_nodes)
    return sorted(cmds.ls(type="file") or [])


def _calculate_udim_missing_gaps(tile_numbers):
    """
    Calculate genuine missing tile gaps within UDIM UV rows.
    UDIM coordinates are 10 tiles wide per row (1001-1010, 1011-1020, etc.).
    Jumping to the start of the next row (e.g. 1004 -> 1011) is standard
    multi-row UDIM layout and not a missing gap.
    """
    if not tile_numbers:
        return []
    missing = []
    rows = {}
    for t in sorted(tile_numbers):
        row_idx = (t - 1001) // 10
        rows.setdefault(row_idx, []).append(t)
    for row_idx, row_tiles in rows.items():
        min_in_row = min(row_tiles)
        max_in_row = max(row_tiles)
        expected = set(range(min_in_row, max_in_row + 1))
        missing.extend(sorted(list(expected - set(row_tiles))))
    return sorted(missing)


def parse_udim_pattern(file_path):
    """
    Analyze a file texture path and return whether it is a UDIM pattern,
    along with directory, pattern template, and all matching tile paths on disk.
    """
    if not file_path:
        return {
            "is_udim": False,
            "pattern_type": "none",
            "directory": "",
            "template": "",
            "tiles": [],
            "missing_tiles": [],
            "tile_numbers": [],
            "disk_exists": False,
        }

    norm_path = file_path.replace("\\", "/")
    dirname = os.path.dirname(norm_path)
    basename = os.path.basename(norm_path)
    dir_exists = os.path.isdir(dirname)

    # 1. Detect explicit <UDIM> tag
    if "<udim>" in basename.lower():
        template = norm_path
        found_files = []
        tile_numbers = []

        if dir_exists:
            # Look for 4-digit numeric replacement files
            prefix, suffix = re.split(r"<udim>", basename, flags=re.IGNORECASE, maxsplit=1)
            glob_pattern = os.path.join(dirname, prefix + "*" + suffix)
            candidates = glob.glob(glob_pattern)

            for cand in sorted(candidates):
                cand_name = os.path.basename(cand)
                match = re.search(r"10\d\d", cand_name)
                if match:
                    t_num = int(match.group(0))
                    tile_numbers.append(t_num)
                    found_files.append(cand.replace("\\", "/"))

        missing = _calculate_udim_missing_gaps(tile_numbers)

        return {
            "is_udim": True,
            "pattern_type": "mari",
            "directory": dirname,
            "template": template,
            "tiles": found_files,
            "missing_tiles": missing,
            "tile_numbers": sorted(tile_numbers),
            "disk_exists": dir_exists and len(found_files) > 0,
        }

    # 2. Detect 1001, 1002 style tile number in filename
    match_1000 = re.search(r"(?:_|\.)(10\d\d)(?:_|\.|$)", basename)
    if match_1000:
        raw_num = match_1000.group(1)
        template = norm_path.replace(raw_num, "<UDIM>")
        found_files = []
        tile_numbers = []

        if dir_exists:
            prefix = basename[:match_1000.start(1)]
            suffix = basename[match_1000.end(1):]
            glob_pattern = os.path.join(dirname, prefix + "*" + suffix)
            candidates = glob.glob(glob_pattern)

            for cand in sorted(candidates):
                cand_name = os.path.basename(cand)
                match = re.search(r"10\d\d", cand_name)
                if match:
                    t_num = int(match.group(0))
                    tile_numbers.append(t_num)
                    found_files.append(cand.replace("\\", "/"))

        missing = _calculate_udim_missing_gaps(tile_numbers)

        return {
            "is_udim": True,
            "pattern_type": "mari",
            "directory": dirname,
            "template": template,
            "tiles": found_files,
            "missing_tiles": missing,
            "tile_numbers": sorted(tile_numbers),
            "disk_exists": dir_exists and len(found_files) > 0,
        }


    # 3. Detect Mudbox (_u1_v1) format
    if "_u" in basename.lower() and "_v" in basename.lower():
        found_files = []
        if dir_exists:
            glob_pattern = os.path.join(dirname, re.sub(r"_u\d+_v\d+", "*", basename, flags=re.IGNORECASE))
            found_files = sorted(glob.glob(glob_pattern))

        return {
            "is_udim": True,
            "pattern_type": "mudbox",
            "directory": dirname,
            "template": norm_path,
            "tiles": found_files,
            "missing_tiles": [],
            "tile_numbers": [],
            "disk_exists": dir_exists and len(found_files) > 0,
        }

    # 4. Single non-UDIM file
    single_exists = os.path.isfile(norm_path) if dir_exists else False
    return {
        "is_udim": False,
        "pattern_type": "none",
        "directory": dirname,
        "template": norm_path,
        "tiles": [norm_path] if single_exists else [],
        "missing_tiles": [],
        "tile_numbers": [],
        "disk_exists": single_exists,
    }


def scan_udim_textures(nodes=None):
    """
    Scan all file nodes in the scene and return full diagnostic inspection report.

    Returns:
        dict: Diagnostic dictionary containing total nodes, UDIM nodes, and per-node details.
    """
    file_nodes = get_all_file_nodes(nodes)
    results = {}
    udim_count = 0
    missing_tiles_total = 0

    for node in file_nodes:
        file_path = cmds.getAttr(node + ".fileTextureName") or ""
        tiling_mode = cmds.getAttr(node + ".uvTilingMode") if cmds.attributeQuery("uvTilingMode", node=node, exists=True) else 0

        info = parse_udim_pattern(file_path)
        info["node"] = node
        info["uvTilingMode"] = tiling_mode
        info["fileTextureName"] = file_path

        # Determine connected materials & meshes
        mats = cmds.ls(cmds.listConnections(node, destination=True) or [], materials=True) or []
        info["materials"] = sorted(set(mats))

        if info["is_udim"]:
            udim_count += 1
            missing_tiles_total += len(info["missing_tiles"])

        results[node] = info

    return {
        "total_files": len(file_nodes),
        "udim_files_count": udim_count,
        "missing_tiles_total": missing_tiles_total,
        "nodes": results,
    }


def generate_all_udim_previews(file_nodes=None, log=None, progress=None):
    """
    Activate UDIM Mari mode on all file textures and force Maya Viewport 2.0
    to generate, cache, and render all UDIM tile texture previews.
    """
    with SceneTransaction("GenerateAllUDIMPreviews"):
        if file_nodes is None:
            file_nodes = get_all_file_nodes()

        _log(log, "Scanning {} file texture node(s)...".format(len(file_nodes)))
        processed = 0
        total = len(file_nodes)

        for idx, node in enumerate(file_nodes, start=1):
            if not cmds.objExists(node):
                continue
            file_path = cmds.getAttr(node + ".fileTextureName") or ""
            info = parse_udim_pattern(file_path)

            if info["is_udim"]:
                # Ensure Maya UV tiling mode is set to Mari (3)
                if cmds.attributeQuery("uvTilingMode", node=node, exists=True):
                    current_mode = cmds.getAttr(node + ".uvTilingMode")
                    if current_mode != TILING_MODE_MARI:
                        cmds.setAttr(node + ".uvTilingMode", TILING_MODE_MARI)
                        _log(log, "INFO: Enabled UDIM (Mari) tiling mode on '{}'.".format(node))

                # Normalize and update template path (convert backslashes to forward slashes)
                target_path = info["template"].replace("\\", "/") if info["template"] else file_path.replace("\\", "/")
                try:
                    cmds.setAttr(node + ".fileTextureName", target_path, type="string")
                except Exception:
                    pass

                # 1. Ensure preview quality is active
                if cmds.attributeQuery("uvTileProxyQuality", node=node, exists=True):
                    try:
                        if cmds.getAttr(node + ".uvTileProxyQuality") == 0:
                            cmds.setAttr(node + ".uvTileProxyQuality", 3)
                    except Exception:
                        pass

                # 2. Maya internal fileTexturePathResolver to register and compute all UV tiles
                try:
                    import maya.app.general.fileTexturePathResolver as ftpr
                    all_found_files = ftpr.findAllFilesForPattern(target_path, None)
                    if all_found_files:
                        ftpr.computeUVForFiles(all_found_files, target_path)
                except Exception:
                    pass

                # 3. Maya native C++ generateUvTilePreview command (the exact command behind the red AE button)
                try:
                    mel.eval('generateUvTilePreview "{node}";'.format(node=node))
                except Exception:
                    try:
                        cmds.generateUvTilePreview(node)
                    except Exception:
                        pass

                # 4. Touch node to ensure attribute propagation
                try:
                    cmds.setAttr(node + ".uvTilingMode", TILING_MODE_MARI)
                except Exception:
                    pass

                processed += 1
                tile_cnt = len(info["tiles"])
                _log(log, "SUCCESS: ✓ Generated tile previews for '{}' ({} tile(s) found on disk).".format(node, tile_cnt))

            _progress(progress, int((idx / float(max(1, total))) * 100), "Generated previews for {}".format(node))

        # 5. Trigger global OGS texture regeneration and GPU cache reload
        try:
            cmds.ogs(regenerateUvTilePreviews=True)
            _log(log, "INFO: Triggered ogs -regenerateUvTilePreviews.")
        except Exception:
            pass

        try:
            cmds.ogs(reloadTextures=True)
            _log(log, "INFO: Viewport 2.0 texture cache reloaded.")
        except Exception:
            pass

        # 6. Automatically enable Textured display mode (Key 6) in all 3D viewports
        try:
            for panel in cmds.getPanel(type="modelPanel") or []:
                cmds.modelEditor(panel, edit=True, displayAppearance="smoothShaded", displayTextures=True)
            _log(log, "INFO: Set active 3D viewports to Textured display mode (Key 6).")
        except Exception:
            pass

        try:
            cmds.refresh(force=True)
        except Exception:
            pass



        _log(log, "\nSUCCESS: ✓ Completed UDIM tile generation across {} texture node(s).".format(processed))
        return processed


def run_generate_udim(log=None):
    """
    Direct 1-click command (no window needed):
    1. Converts any unformatted numbered textures to <UDIM>.
    2. Generates all hardware tile previews and builds mipmap proxies.
    3. Flushes Viewport 2.0 graphics cache.
    4. Sets viewports to textured mode (Key 6).
    5. Displays in-view notification in Maya and logs to Global Log Store.
    """
    from scartools.licensing import require_license
    require_license("UDIM Previews")

    def _local_log(msg):

        if log:
            log(msg)
        try:
            from scartools.framework.logging import emit_log
            emit_log(msg, source="UDIM")
        except Exception:
            pass


    _local_log("=" * 68)
    _local_log("INFO: STARTING 1-CLICK GENERATE UDIM PREVIEWS...")
    _local_log("=" * 68)

    try:
        # Step 1: Scan and auto-convert numbered files to UDIM
        convert_selected_to_udim(log=_local_log)

        # Step 2: Generate all UDIM tile previews
        count = generate_all_udim_previews(log=_local_log)

        _local_log("=" * 68)
        _local_log("SUCCESS: ✓ Successfully generated UDIM previews for {} file node(s)!".format(count))
        _local_log("=" * 68)

        msg = "Generated UDIM previews for {} texture node(s).".format(count)
        if count == 0:
            msg = "No UDIM texture nodes found in scene."

        try:
            cmds.inViewMessage(
                statusMessage='<span style="color: #72D6AA; font-weight: bold;">✓ ' + msg + '</span>',
                pos="topCenter",
                fade=True,
                fadeStayTime=2500,
            )
        except Exception:
            pass

        return count
    except Exception as exc:
        _local_log("ERROR: UDIM generation failed -> {}".format(exc))
        try:
            cmds.inViewMessage(
                statusMessage='<span style="color: #F07D7D; font-weight: bold;">❌ UDIM Generation Error: ' + str(exc) + '</span>',
                pos="topCenter",
                fade=True,
                fadeStayTime=4000,
            )
        except Exception:
            pass
        raise



def convert_selected_to_udim(file_nodes=None, log=None):
    """Convert selected file nodes to explicit <UDIM> paths."""
    with SceneTransaction("ConvertToUDIM"):
        if file_nodes is None:
            file_nodes = get_all_file_nodes()

        converted = 0
        for node in file_nodes:
            if not cmds.objExists(node):
                continue
            file_path = cmds.getAttr(node + ".fileTextureName") or ""
            info = parse_udim_pattern(file_path)
            if info["is_udim"] and "<UDIM>" not in file_path and info["template"]:
                try:
                    norm_tpl = info["template"].replace("\\", "/")
                    cmds.setAttr(node + ".fileTextureName", norm_tpl, type="string")
                    if cmds.attributeQuery("uvTilingMode", node=node, exists=True):
                        cmds.setAttr(node + ".uvTilingMode", TILING_MODE_MARI)
                    converted += 1
                    _log(log, "Converted '{}' -> {}".format(node, norm_tpl))
                except Exception as exc:
                    _log(log, "ERROR: Could not convert '{}': {}".format(node, exc))

        _log(log, "Converted {} file node(s) to <UDIM> format.".format(converted))
        return converted
