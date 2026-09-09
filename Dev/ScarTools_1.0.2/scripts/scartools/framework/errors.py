# -*- coding: utf-8 -*-
"""Centralized exception hierarchy for ScarTools pipeline and framework."""

from __future__ import absolute_import, division, print_function


class ScarToolsError(Exception):
    """Base exception for all ScarTools errors."""
    pass


class ValidationError(ScarToolsError):
    """Raised when topology, preflight, or scene validation checks fail."""
    pass


class SkinOperationError(ScarToolsError):
    """Raised during skin binding, mirror, transfer, copy, or weight I/O failures."""
    pass


class ExportError(ScarToolsError):
    """Raised when asset, animation, cache, or camera export fails."""
    pass


class ImportError(ScarToolsError):
    """Raised when asset, animation, cache, or camera import fails."""
    pass


class LicenseError(ScarToolsError):
    """Raised when licensing, lease, or activation validation fails."""
    pass


class ToolExecutionError(ScarToolsError):
    """Raised when a DCC tool operation cannot be completed safely."""
    pass


class SceneIntegrityError(ScarToolsError):
    """Raised when scene naming, namespace, or hierarchy violates pipeline rules."""
    pass


__all__ = [
    "ScarToolsError",
    "ValidationError",
    "SkinOperationError",
    "ExportError",
    "ImportError",
    "LicenseError",
    "ToolExecutionError",
    "SceneIntegrityError",
]
