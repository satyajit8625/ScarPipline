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
