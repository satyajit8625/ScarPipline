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


__all__ = [
    "SuffixRegistry",
    "sanitize_maya_name",
    "apply_affixes",
    "split_version_string",
    "format_version",
]
