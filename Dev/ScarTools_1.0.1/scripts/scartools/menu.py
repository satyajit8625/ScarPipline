"""Shared, reusable ScarTools Maya menu registry."""

from __future__ import print_function

import builtins
import os

import maya.cmds as cmds

from .framework import resolve_icon
from .version import VERSION


MENU_NAME = "ScarToolsMainMenu"
REGISTRY_ATTR = "_SCARTOOLS_MENU_REGISTRY"
ICON_ATTR = "_SCARTOOLS_MENU_ICON"
DIRTY_ATTR = "_SCARTOOLS_MENU_DIRTY"

DEPARTMENTS = (
    ("modeling", "Modeling"),
    ("rigging", "Rigging"),
    ("texturing", "Texturing"),
    ("animation", "Animation"),
    ("pipeline_utilities", "Pipeline Utilities"),
)

DEPARTMENT_ICONS = {
    "rigging": "department_rigging.png",
    "modeling": "department_modeling.png",
    "texturing": "department_texturing.png",
    "animation": "department_animation.png",
    "pipeline_utilities": "department_pipeline.png",
}

DEPARTMENT_ALIASES = {
    "pipeline": "pipeline_utilities",
    "rig": "rigging",
    "model": "modeling",
    "texture": "texturing",
    "anim": "animation",
}


def _registry():
    registry = getattr(builtins, REGISTRY_ATTR, None)
    if registry is None:
        registry = {}
        setattr(builtins, REGISTRY_ATTR, registry)
    return registry


def _valid_icon(path):
    return os.path.normpath(path) if path and os.path.isfile(path) else None


def icon_path(filename):
    """Return an absolute packaged icon path, or None when unavailable."""
    return resolve_icon(filename)


def _mark_dirty():
    setattr(builtins, DIRTY_ATTR, True)


def _is_dirty():
    return bool(getattr(builtins, DIRTY_ATTR, True))


def set_brand_icon(path):
    """Set the icon inherited by the ScarTools menu and registered tools."""
    icon = _valid_icon(path)
    if getattr(builtins, ICON_ATTR, None) != icon:
        setattr(builtins, ICON_ATTR, icon)
        _mark_dirty()
    return icon


def brand_icon():
    # Validation happens once in set_brand_icon/register_tool. Avoid repeated
    # network/disk checks when a studio icon lives on a mapped drive.
    return getattr(builtins, ICON_ATTR, None)


def register_tool(
    department,
    tool_id,
    label,
    command,
    annotation="",
    icon=None,
    order=100,
    rebuild=True,
):
    """Register one callable tool beneath a stable ScarTools department."""
    department = DEPARTMENT_ALIASES.get(str(department).lower(), str(department).lower())
    valid_departments = {key for key, _ in DEPARTMENTS}
    if department not in valid_departments:
        raise ValueError("Unknown ScarTools department: {}".format(department))
    if not tool_id:
        raise ValueError("ScarTools tool_id cannot be empty.")
    if not callable(command):
        raise TypeError("ScarTools command must be callable.")

    descriptor = {
        "department": department,
        "label": label,
        "command": command,
        "annotation": annotation or "",
        "icon": _valid_icon(icon),
        "order": int(order),
    }
    registry = _registry()
    if registry.get(tool_id) != descriptor:
        registry[tool_id] = descriptor
        _mark_dirty()
    if rebuild:
        return register_menu()
    return tool_id


def register_manifest(manifest, icon=None, rebuild=True):
    """Register any suite tool through the shared declarative contract."""
    from .framework import ToolManifest

    if not isinstance(manifest, ToolManifest):
        raise TypeError("register_manifest requires a ToolManifest instance.")
    return register_tool(
        department=manifest.department,
        tool_id=manifest.tool_id,
        label=manifest.label,
        command=manifest.menu_command,
        annotation=manifest.annotation,
        icon=icon or icon_path(manifest.icon_name),
        order=manifest.order,
        rebuild=rebuild,
    )


def unregister_tool(tool_id, rebuild=True):
    """Remove a tool registration without affecting other departments/tools."""
    if _registry().pop(tool_id, None) is not None:
        _mark_dirty()
    if rebuild:
        return register_menu()
    return None


def clear_tools():
    registry = _registry()
    if registry:
        registry.clear()
        _mark_dirty()


def _menu_kwargs(icon):
    kwargs = {
        "label": "ScarTools",
        "parent": "MayaWindow",
        "tearOff": True,
    }
    if icon:
        kwargs["familyImage"] = icon
    return kwargs


def _show_about(*_):
    try:
        from .ui.window import show_about_dialog
        return show_about_dialog()
    except Exception as exc:
        cmds.warning("Could not open ScarTools About dialog: {}".format(exc))


def _show_global_console(*_):
    try:
        from .ui.logs import show_global_log
        return show_global_log()
    except Exception as exc:
        cmds.warning("Could not open ScarTools Global Console: {}".format(exc))


def _show_showcase(*_):
    try:
        from .ui.showcase import show_showcase
        return show_showcase()
    except Exception as exc:
        cmds.warning("Could not open Design System Showcase: {}".format(exc))



def _show_license_activation_dialog(*_):
    try:
        from .ui.license_dialog import show_license_dialog
        return show_license_dialog()
    except Exception as exc:
        cmds.warning("Could not open ScarTools License Dialog: {}".format(exc))


def _run_topology_qa(*_):
    try:
        from .framework.validation import inspect_mesh_topology, select_mesh_topology_issues
        sel = cmds.ls(selection=True, long=True) or []
        if not sel:
            cmds.warning("Please select one or more polygon meshes to inspect.")
            return
        results = inspect_mesh_topology(sel)
        issues_found = 0
        for node, data in results.items():
            short = node.split("|")[-1]
            if data["clean"]:
                print("[ScarTools Topology QA] {}: Clean (No topology issues)".format(short))
            else:
                nm_v = len(data["non_manifold_vertices"])
                nm_e = len(data["non_manifold_edges"])
                lam = len(data["lamina_faces"])
                inter = len(data["intermediate_shapes"])
                issues_found += (nm_v + nm_e + lam + inter)
                print("[ScarTools Topology QA] {}: ISSUES -> {} non-manifold verts, {} non-manifold edges, {} lamina faces, {} intermediate shapes".format(short, nm_v, nm_e, lam, inter))
                select_mesh_topology_issues(node, "all")

        if issues_found:
            cmds.inViewMessage(
                statusMessage="Topology QA: {} issue component(s) found and selected in viewport.".format(issues_found),
                pos="topCenter",
                fade=True,
            )
        else:
            cmds.inViewMessage(
                statusMessage="Topology QA: Selected mesh(es) are 100% clean!",
                pos="topCenter",
                fade=True,
            )
    except Exception as exc:
        cmds.warning("Could not run Topology QA: {}".format(exc))


def register_menu(icon=None):
    """Build the root menu and every department from the current registry."""
    if icon:
        set_brand_icon(icon)
    icon = brand_icon()

    # Registration is often called repeatedly while several department tools
    # initialize. If neither the registry nor branding changed, keep Maya's
    # existing controls instead of deleting and recreating the complete menu.
    if not _is_dirty() and cmds.menu(MENU_NAME, exists=True):
        return MENU_NAME

    unregister_menu()

    from .licensing import is_activated, get_installed_license

    has_license, lic_msg, lic_details = get_installed_license()
    if not has_license:
        # Build locked menu with activation prompt
        root_menu = cmds.menu(MENU_NAME, **_menu_kwargs(icon))
        cmds.menuItem(
            label="⚠️ License Not Activated",
            enable=False,
            parent=root_menu,
        )
        cmds.menuItem(
            label="Activate Studio License...",
            annotation="Activate ScarTools with your Artist User ID and License Key.",
            command=lambda *_: _show_license_activation_dialog(),
            parent=root_menu,
        )
        cmds.menuItem(divider=True, parent=root_menu)
        cmds.menuItem(
            label="About ScarTools",
            command=_show_about,
            parent=root_menu,
        )
        setattr(builtins, DIRTY_ATTR, False)
        return root_menu

    root_menu = cmds.menu(MENU_NAME, **_menu_kwargs(icon))

    registry = _registry()
    for department_id, department_label in DEPARTMENTS:
        submenu_kwargs = {
            "label": department_label,
            "subMenu": True,
            "tearOff": True,
            "parent": root_menu,
        }
        department_icon = icon_path(DEPARTMENT_ICONS[department_id])
        if department_icon:
            submenu_kwargs["image"] = department_icon
        submenu = cmds.menuItem(
            **submenu_kwargs
        )
        tools = [
            (tool_id, tool)
            for tool_id, tool in registry.items()
            if tool["department"] == department_id
        ]
        tools.sort(key=lambda item: (item[1]["order"], item[1]["label"].lower()))

        if not tools:
            if department_id == "modeling":
                cmds.menuItem(
                    label="Topology QA Inspector",
                    annotation="Scan selected meshes for non-manifold edges/vertices and lamina faces.",
                    command=_run_topology_qa,
                    parent=submenu,
                )
            else:
                cmds.menuItem(
                    label="No tools installed",
                    enable=False,
                    parent=submenu,
                )
            continue

        for _, tool in tools:
            item_kwargs = {
                "label": tool["label"],
                "annotation": tool["annotation"],
                "command": tool["command"],
                "parent": submenu,
            }
            tool_icon = tool["icon"] or icon
            if tool_icon:
                item_kwargs["image"] = tool_icon
            cmds.menuItem(**item_kwargs)

    cmds.menuItem(divider=True, parent=root_menu)
    cmds.menuItem(
        label="Log Viewer...",
        annotation="Open the centralized ScarTools Log Viewer and live log stream.",
        command=lambda *_: _show_global_console(),
        parent=root_menu,
    )
    cmds.menuItem(
        label="About ScarTools",
        command=_show_about,
        parent=root_menu,
    )


    version_kwargs = {
        "label": "ScarTools v{}".format(VERSION),
        "enable": False,
        "parent": root_menu,
    }
    cmds.menuItem(**version_kwargs)

    setattr(builtins, DIRTY_ATTR, False)
    return root_menu


def unregister_menu():
    """Remove only the ScarTools Maya menu; registrations remain available."""
    try:
        if cmds.menu(MENU_NAME, exists=True):
            cmds.deleteUI(MENU_NAME, menu=True)
            _mark_dirty()
    except Exception:
        pass
