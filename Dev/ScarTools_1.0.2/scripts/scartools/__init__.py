"""Public ScarTools menu API for XSQUADS Maya tools."""

from .menu import (
    DEPARTMENTS,
    DEPARTMENT_ICONS,
    MENU_NAME,
    clear_tools,
    icon_path,
    register_manifest,
    register_menu,
    register_tool,
    set_brand_icon,
    unregister_menu,
    unregister_tool,
)
from .compat import MIN_MAYA_VERSION, ensure_supported, maya_major_version
from .builtin import (
    BUILTIN_TOOL_MANIFESTS,
    BUILTIN_TOOL_MODULES,
    register_builtin_services,
    register_builtin_tools,
)
from .framework import (
    OperationCallbacks,
    OperationResult,
    SERVICES,
    SceneTransaction,
    ToolController,
    ToolManifest,
    ValidationReport,
    get_logger,
)
from .catalog import find_capability, find_service, find_tool, manifest_data, manifests
from . import settings
from .shelf import build_shelf, delete_shelf
from .version import VERSION, __version__
from .licensing import (
    generate_license_key,
    validate_license_key,
    get_installed_license,
    is_activated,
    save_license,
    revoke_license,
    sync_cloud_license,
    find_cloud_record,
    get_machine_hardware_id,
)


def reload_suite():
    """Hot-reload all ScarTools modules in Maya without restarting Maya."""
    import sys
    # 1. Close active windows
    try:
        from .ui.lifecycle import close_all_windows
        close_all_windows()
    except Exception:
        pass

    # 2. Remove all cached scartools submodules from sys.modules
    to_delete = [mod for mod in sys.modules if mod.startswith("scartools")]
    for mod in to_delete:
        del sys.modules[mod]

    # 3. Re-import scartools and rebuild menu/shelf
    import scartools
    try:
        import maya.cmds as cmds
        if not cmds.about(batch=True):
            scartools.unregister_menu()
            scartools.register_menu()
            from scartools.framework.logging import emit_log
            emit_log("Successfully reloaded ScarTools suite.", level="success", source="ScarTools")
    except Exception as e:
        try:
            from scartools.framework.logging import emit_log
            emit_log("Reloaded modules (Maya UI update error: {})".format(e), level="warning", source="ScarTools")
        except Exception:
            pass
    return scartools


__all__ = [
    "VERSION",
    "__version__",
    "DEPARTMENTS",
    "DEPARTMENT_ICONS",
    "MENU_NAME",
    "MIN_MAYA_VERSION",
    "maya_major_version",
    "ensure_supported",
    "BUILTIN_TOOL_MODULES",
    "BUILTIN_TOOL_MANIFESTS",
    "register_builtin_tools",
    "register_builtin_services",
    "ToolManifest",
    "OperationCallbacks",
    "OperationResult",
    "SceneTransaction",
    "ToolController",
    "ValidationReport",
    "SERVICES",
    "get_logger",
    "manifests",
    "manifest_data",
    "find_tool",
    "find_capability",
    "find_service",
    "settings",
    "icon_path",
    "register_menu",
    "unregister_menu",
    "register_tool",
    "register_manifest",
    "unregister_tool",
    "clear_tools",
    "set_brand_icon",
    "build_shelf",
    "delete_shelf",
    "reload_suite",
    "generate_license_key",
    "validate_license_key",
    "get_installed_license",
    "is_activated",
    "save_license",
    "revoke_license",
    "sync_cloud_license",
    "find_cloud_record",
    "get_machine_hardware_id",
]
