"""Canonical suite paths; avoids every tool calculating its own roots."""

import os


def package_root():
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )


def scripts_root():
    return os.path.join(package_root(), "scripts")


def icons_root():
    return os.path.join(package_root(), "icons")


def resolve_icon(filename):
    if not filename:
        return None
    path = os.path.normpath(os.path.join(icons_root(), str(filename)))
    return path if os.path.isfile(path) else None


def open_in_file_manager(path):
    """
    Open the given directory or containing folder of a file in native OS file manager
    (Windows Explorer, macOS Finder, Linux file manager).
    """
    import sys
    import subprocess

    if not path:
        return False
    norm_path = os.path.normpath(str(path))
    if not os.path.exists(norm_path):
        parent = os.path.dirname(norm_path)
        if os.path.exists(parent):
            norm_path = parent
        else:
            return False

    if os.path.isfile(norm_path):
        target_dir = os.path.dirname(norm_path)
    else:
        target_dir = norm_path

    try:
        if sys.platform.startswith("win"):
            os.startfile(target_dir)
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target_dir])
            return True
        else:
            subprocess.Popen(["xdg-open", target_dir])
            return True
    except Exception:
        return False
