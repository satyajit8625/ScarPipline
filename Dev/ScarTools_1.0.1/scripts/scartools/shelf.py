# -*- coding: utf-8 -*-
"""ScarTools dedicated Maya shelf builder and tab manager."""

from __future__ import print_function

import os
import sys
import maya.cmds as cmds
try:
    import maya.mel as mel
except ImportError:
    mel = None

from .framework.paths import resolve_icon as icon_path
from .version import VERSION

SHELF_NAME = "ScarTools"

SHELF_TOOLS = [
    {
        "label": "Skin Tools",
        "overlay_label": "Skin",
        "command": "import scartools.tools.skin\nscartools.tools.skin.show()",
        "icon": "tool_skin_tools.png",
        "annotation": "Multi-mesh skin weight package export, import, copy, and symmetry inspector.",
    },
    {
        "label": "Model Sanitizer",
        "overlay_label": "Model",
        "command": "import scartools.tools.modeling\nscartools.tools.modeling.show()",
        "icon": "department_modeling.png",
        "annotation": "Preflight QA, topology integrity, transforms, suffixes, and layer sanitization.",
    },
    {
        "label": "Shader Tools",
        "overlay_label": "Shader",
        "command": "import scartools.tools.shader\nscartools.tools.shader.show()",
        "icon": "tool_shader_tools.png",
        "annotation": "Shader network export, inspection, variant management, and UDIM repathing.",
    },
    {
        "label": "Character Finalizer",
        "overlay_label": "Rig",
        "command": "import scartools.tools.character_finalizer\nscartools.tools.character_finalizer.show()",
        "icon": "tool_character_finalizer.png",
        "annotation": "Single-character preflight, build, repair, and rigging validation.",
    },
    {
        "label": "Generate UDIM",
        "overlay_label": "UDIM",
        "command": "import scartools.tools.udim\nscartools.tools.udim.run_generate_udim()",
        "icon": "department_texturing.png",
        "annotation": "1-Click: Automatically format <UDIM> paths, generate hardware tile previews, and reload Viewport 2.0.",
    },
    {
        "label": "Anim Export",
        "overlay_label": "Anim",
        "command": "import scartools.tools.anim_io\nscartools.tools.anim_io.show()",
        "icon": "department_animation.png",
        "annotation": "Shot animation packaging, Alembic & FBX cache extraction to studio pipeline folders.",
    },
    {
        "label": "Pipeline Renamer",
        "overlay_label": "Rename",
        "command": "import scartools.tools.renamer\nscartools.tools.renamer.show_ui()",
        "icon": "department_pipeline.png",
        "annotation": "Fast batch node renaming with search/replace, numbering, and department suffix presets.",
    },
    {
        "label": "Log Viewer",
        "overlay_label": "Logs",
        "command": "import scartools.ui.logs\nscartools.ui.logs.show_global_log()",
        "icon": "department_pipeline.png",
        "annotation": "Open the centralized ScarTools Log Viewer with live filter chips and search.",
    },
    {
        "label": "About ScarTools",
        "overlay_label": "About",
        "command": "import scartools.ui.window\nscartools.ui.window.show_about_dialog()",
        "icon": "scarfall_app_icon.png",
        "annotation": "ScarTools version, active Python runtime, and diagnostics.",
    },

]




def _get_top_shelf():
    if not cmds.about(batch=True):
        try:
            return mel.eval("$tmp = $gShelfTopLevel")
        except Exception:
            pass
    return "Shelf"


def build_shelf(rebuild=True):
    """Create or rebuild the dedicated ScarTools shelf tab in Maya."""
    if cmds.about(batch=True):
        return None

    top_shelf = _get_top_shelf()
    if not top_shelf or not cmds.shelfTabLayout(top_shelf, exists=True):
        return None

    shelf_tab_path = top_shelf + "|" + SHELF_NAME
    exists = cmds.shelfLayout(shelf_tab_path, exists=True)

    if exists:
        if not rebuild:
            return shelf_tab_path
        buttons = cmds.shelfLayout(shelf_tab_path, query=True, childArray=True) or []
        for btn in buttons:
            try:
                cmds.deleteUI(btn)
            except Exception:
                pass
    else:
        try:
            cmds.setParent(top_shelf)
            cmds.shelfLayout(SHELF_NAME, parent=top_shelf)
        except Exception:
            pass

    for tool in SHELF_TOOLS:
        resolved_icon = icon_path(tool["icon"]) or "pythonFamily.png"
        kwargs = {
            "label": tool["label"],
            "annotation": tool.get("annotation", tool["label"]),
            "command": tool["command"],
            "image": resolved_icon,
            "style": "iconOnly",
            "width": 35,
            "height": 34,
            "parent": shelf_tab_path,
            "sourceType": "python",
        }
        if "overlay_label" in tool and tool["overlay_label"]:
            kwargs["imageOverlayLabel"] = tool["overlay_label"]
            kwargs["overlayLabelColor"] = (0.95, 0.95, 0.95)
            kwargs["overlayLabelBackColor"] = (0.1, 0.1, 0.1, 0.65)

        try:
            cmds.shelfButton(**kwargs)
        except Exception:
            pass

    try:
        tabs = cmds.shelfTabLayout(top_shelf, query=True, tabLabelArray=True) or []
        if SHELF_NAME in tabs:
            idx = tabs.index(SHELF_NAME) + 1
            cmds.shelfTabLayout(top_shelf, edit=True, selectTabIndex=idx)
    except Exception:
        pass

    return shelf_tab_path


def delete_shelf():
    """Remove the ScarTools shelf tab and preference files cleanly upon uninstall."""
    if cmds.about(batch=True):
        return True

    top_shelf = _get_top_shelf()
    shelf_tab_path = top_shelf + "|" + SHELF_NAME if top_shelf else SHELF_NAME

    try:
        mel.eval('if (`exists deleteShelfTab`) { catchQuiet(deleteShelfTab("' + SHELF_NAME + '")); }')
    except Exception:
        pass

    try:
        if cmds.shelfLayout(shelf_tab_path, exists=True):
            cmds.deleteUI(shelf_tab_path, layout=True)
    except Exception:
        pass

    try:
        shelf_dir = cmds.internalVar(userShelfDir=True)
        if shelf_dir and os.path.isdir(shelf_dir):
            for fname in os.listdir(shelf_dir):
                if fname.startswith("shelf_" + SHELF_NAME):
                    fpath = os.path.join(shelf_dir, fname)
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
    except Exception:
        pass

    return True
