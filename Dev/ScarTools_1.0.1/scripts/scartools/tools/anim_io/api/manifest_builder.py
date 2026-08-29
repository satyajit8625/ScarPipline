# -*- coding: utf-8 -*-
"""Shot Manifest Builder, Serializer, and Parser for Anim I/O."""

from __future__ import absolute_import, division, print_function

import json
import os
import time

MANIFEST_FILENAME = "shot_manifest.json"


def build_shot_manifest(
    shot_name,
    start_frame,
    end_frame,
    fps,
    camera_info=None,
    characters=None,
    props=None,
    handles=0,
    exported_by=None,
    notes="",
):
    """
    Construct a structured shot manifest dictionary.
    """
    return {
        "schema_version": "1.0.0",
        "shot_name": str(shot_name or "untitled_shot").strip(),
        "fps": float(fps or 24.0),
        "frame_range": {
            "start": int(start_frame),
            "end": int(end_frame),
            "handles": int(handles),
            "eval_start": int(start_frame) - int(handles),
            "eval_end": int(end_frame) + int(handles),
        },
        "camera": camera_info or {},
        "characters": list(characters or []),
        "props": list(props or []),
        "metadata": {
            "exported_by": str(exported_by or os.environ.get("USERNAME", "studio_animator")),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "generator": "ScarTools Anim I/O Suite",
            "notes": str(notes or ""),
        },
    }


def save_shot_manifest(manifest_data, output_dir):
    """Save the manifest dictionary as shot_manifest.json in the output directory."""
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, MANIFEST_FILENAME)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=False)
    return manifest_path


def load_shot_manifest(manifest_or_dir):
    """
    Load a shot_manifest.json from a file path or containing directory.
    Returns parsed dict or None if invalid.
    """
    if not manifest_or_dir:
        return None

    path = manifest_or_dir
    if os.path.isdir(path):
        path = os.path.join(path, MANIFEST_FILENAME)

    if not os.path.isfile(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "frame_range" in data:
            data["_manifest_path"] = os.path.normpath(path)
            data["_package_dir"] = os.path.dirname(os.path.normpath(path))
            return data
    except Exception as e:
        print("[ScarTools Anim I/O] Failed to read manifest '{}': {}".format(path, e))
    return None
