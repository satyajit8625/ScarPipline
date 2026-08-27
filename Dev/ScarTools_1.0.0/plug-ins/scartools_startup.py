"""Maya auto-load plug-in that owns the shared ScarTools menu."""

import builtins
import os
import sys

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.utils


_STARTUP_TOKEN_ATTR = "_SCARTOOLS_STARTUP_TOKEN"


def _source_path():
    """Resolve this plug-in path even when Maya does not define ``__file__``."""
    candidates = [
        globals().get("__file__"),
        _source_path.__code__.co_filename,
    ]
    for candidate in candidates:
        if candidate:
            candidate = os.path.abspath(candidate)
            if os.path.isfile(candidate):
                return candidate
    raise RuntimeError("Could not resolve the ScarTools startup plug-in path.")


def _module_root():
    return os.path.dirname(os.path.dirname(_source_path()))


def _bootstrap_package_path():
    """Make the package importable even before Maya processes the .mod paths."""
    scripts_path = os.path.join(_module_root(), "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return scripts_path


_bootstrap_package_path()


maya_useNewAPI = True


def _next_startup_token():
    token = int(getattr(builtins, _STARTUP_TOKEN_ATTR, 0)) + 1
    setattr(builtins, _STARTUP_TOKEN_ATTR, token)
    return token


_heartbeat_timer = None


def _start_heartbeat_monitor():
    """Lightweight background lease monitor that checks revocation/heartbeat every 30s."""
    global _heartbeat_timer
    try:
        from PySide2 import QtCore
    except ImportError:
        try:
            from PySide6 import QtCore
        except ImportError:
            return

    try:
        if _heartbeat_timer is not None:
            _heartbeat_timer.stop()
    except Exception:
        pass

    def _tick():
        try:
            from scartools.licensing import is_activated
            is_activated(force_check=True)
        except Exception:
            pass

    _heartbeat_timer = QtCore.QTimer()
    _heartbeat_timer.setInterval(30000)  # Check every 30 seconds
    _heartbeat_timer.timeout.connect(_tick)
    _heartbeat_timer.start()


def _stop_heartbeat_monitor():
    global _heartbeat_timer
    try:
        if _heartbeat_timer is not None:
            _heartbeat_timer.stop()
    except Exception:
        pass
    _heartbeat_timer = None


def _register_menu(token):
    # A plug-in can be unloaded before its deferred callback executes during
    # install/update. Ignore stale callbacks instead of rebuilding twice.
    if token != getattr(builtins, _STARTUP_TOKEN_ATTR, None):
        return

    from scartools import (
        build_shelf,
        clear_tools,
        ensure_supported,
        set_brand_icon,
    )
    from scartools.builtin import register_builtin_tools

    ensure_supported()
    clear_tools()
    set_brand_icon(None)
    register_builtin_tools(rebuild=True)
    try:
        build_shelf(rebuild=False)
    except Exception:
        pass
    _start_heartbeat_monitor()


def initializePlugin(plugin_object):
    from scartools.version import VERSION
    om.MFnPlugin(plugin_object, "XSQUADS", VERSION, "Any")
    token = _next_startup_token()
    # maya.standalone and mayapy need the reusable API, not GUI controls.
    if not cmds.about(batch=True):
        maya.utils.executeDeferred(lambda: _register_menu(token))


def uninitializePlugin(plugin_object):
    _next_startup_token()  # Invalidate a callback still waiting in Maya's queue.
    _stop_heartbeat_monitor()
    from scartools import clear_tools, unregister_menu
    from scartools.builtin import close_builtin_windows
    close_builtin_windows()
    unregister_menu()
    clear_tools()
