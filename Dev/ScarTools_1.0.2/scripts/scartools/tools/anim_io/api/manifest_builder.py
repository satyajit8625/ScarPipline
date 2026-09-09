# -*- coding: utf-8 -*-
"""Shot Manifest Builder, Serializer, and Parser for Anim I/O.

Supports Schema 2.0.0 multi-version manifests, capturing version history,
user metadata, timeline settings, and asset cache registries in shot_manifest.json.
"""

from __future__ import absolute_import, division, print_function

import json
import os
import platform
import re
import socket
import time

MANIFEST_FILENAME = "shot_manifest.json"
SCHEMA_VERSION = "2.0.0"
_VERSION_DIR_RE = re.compile(r"^v(\d+)$", re.IGNORECASE)


def build_version_record(
    version_name,
    start_frame,
    end_frame,
    fps,
    camera_info=None,
    characters=None,
    props=None,
    handles=0,
    step=1.0,
    exported_by=None,
    workstation=None,
    notes="",
):
    """
    Construct a structured version record dictionary for inclusion in shot_manifest.json.
    """
    eval_start = int(start_frame) - int(handles)
    eval_end = int(end_frame) + int(handles)
    total_frames = max(0, eval_end - eval_start + 1)

    # Extract version integer
    v_match = _VERSION_DIR_RE.match(str(version_name or "").strip())
    version_num = int(v_match.group(1)) if v_match else 1

    user_name = str(
        exported_by
        or os.environ.get("USERNAME")
        or os.environ.get("USER")
        or "studio_artist"
    ).strip()

    host_name = str(
        workstation
        or os.environ.get("COMPUTERNAME")
        or socket.gethostname()
        or "workstation"
    ).strip()

    return {
        "version": str(version_name).strip(),
        "version_number": version_num,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "exported_by": user_name,
        "workstation": host_name,
        "os": "{} {}".format(platform.system(), platform.release()),
        "fps": float(fps or 24.0),
        "frame_range": {
            "start": int(start_frame),
            "end": int(end_frame),
            "handles": int(handles),
            "step": float(step or 1.0),
            "eval_start": eval_start,
            "eval_end": eval_end,
            "total_frames": total_frames,
        },
        "camera": camera_info or {},
        "characters": list(characters or []),
        "props": list(props or []),
        "metadata": {
            "generator": "ScarTools Anim Export",
            "notes": str(notes or ""),
        },
    }


def build_shot_manifest(
    shot_name,
    start_frame,
    end_frame,
    fps,
    camera_info=None,
    characters=None,
    props=None,
    handles=0,
    step=1.0,
    exported_by=None,
    notes="",
    version_name="v001",
):
    """
    Construct a multi-version root shot manifest dictionary (Schema 2.0.0).
    Maintains backward compatibility with callers expecting build_shot_manifest.
    """
    ver_record = build_version_record(
        version_name=version_name,
        start_frame=start_frame,
        end_frame=end_frame,
        fps=fps,
        camera_info=camera_info,
        characters=characters,
        props=props,
        handles=handles,
        step=step,
        exported_by=exported_by,
        notes=notes,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "shot_name": str(shot_name or "untitled_shot").strip(),
        "latest_version": str(version_name).strip(),
        "total_versions": 1,
        "exported_by": ver_record.get("exported_by", ""),
        "fps": ver_record.get("fps", 24.0),
        "frame_range": ver_record.get("frame_range", {}),
        "camera": ver_record.get("camera", {}),
        "characters": ver_record.get("characters", []),
        "props": ver_record.get("props", []),
        "metadata": ver_record.get("metadata", {}),
        "versions": {
            str(version_name).strip(): ver_record,
        },
    }


def load_shot_manifest(manifest_or_dir):
    """
    Load shot_manifest.json from a file path or containing directory.
    Returns parsed dictionary or None if invalid.
    Handles both Schema 2.0.0 and legacy Schema 1.0.0 formats seamlessly.
    """
    if not manifest_or_dir:
        return None

    path = str(manifest_or_dir).strip()
    if os.path.isdir(path):
        path = os.path.join(path, MANIFEST_FILENAME)

    if not os.path.isfile(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return None

        data["_manifest_path"] = os.path.normpath(path)
        data["_package_dir"] = os.path.dirname(os.path.normpath(path))

        # Backward compatibility: Upgrade legacy 1.0.0 single-version manifests to 2.0.0 in-memory
        if "versions" not in data and "frame_range" in data:
            v_name = "v001"
            data["schema_version"] = SCHEMA_VERSION
            data["latest_version"] = v_name
            data["total_versions"] = 1
            data["versions"] = {
                v_name: {
                    "version": v_name,
                    "version_number": 1,
                    "timestamp": data.get("metadata", {}).get("timestamp", ""),
                    "exported_by": data.get("metadata", {}).get("exported_by", ""),
                    "fps": data.get("fps", 24.0),
                    "frame_range": data.get("frame_range", {}),
                    "camera": data.get("camera", {}),
                    "characters": data.get("characters", []),
                    "props": data.get("props", []),
                    "metadata": data.get("metadata", {}),
                }
            }
        elif "versions" in data and data["versions"]:
            latest_k = data.get("latest_version")
            if not latest_k or latest_k not in data["versions"]:
                def _v_k(vn):
                    m = _VERSION_DIR_RE.match(vn)
                    return int(m.group(1)) if m else 0
                latest_k = sorted(data["versions"].keys(), key=_v_k)[-1]
            latest_rec = data["versions"][latest_k]
            data.setdefault("fps", latest_rec.get("fps", 24.0))
            data.setdefault("frame_range", latest_rec.get("frame_range", {}))
            data.setdefault("camera", latest_rec.get("camera", {}))
            data.setdefault("characters", latest_rec.get("characters", []))
            data.setdefault("props", latest_rec.get("props", []))
            data.setdefault("metadata", latest_rec.get("metadata", {}))

        return data
    except Exception as e:
        try:
            from scartools.framework.logging import emit_log
            emit_log("Failed to read manifest '{}': {}".format(path, e), level="warning", source="AnimIO")
        except Exception:
            pass
        return None


def save_shot_manifest(manifest_data, output_dir):
    """Save the manifest dictionary as shot_manifest.json in the output directory."""
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, MANIFEST_FILENAME)
    temp_path = manifest_path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=False)
    if os.path.isfile(manifest_path):
        os.replace(temp_path, manifest_path)
    else:
        os.rename(temp_path, manifest_path)
    return manifest_path


def update_shot_manifest(shot_dir, version_name, version_record, shot_name=None):
    """
    Append or update a version record in the master shot_manifest.json at shot_dir.
    Maintains chronological and numeric order of versions and updates latest_version.
    """
    if not os.path.isdir(shot_dir):
        os.makedirs(shot_dir, exist_ok=True)

    manifest = load_shot_manifest(shot_dir)
    if not manifest:
        s_name = shot_name or os.path.basename(os.path.normpath(shot_dir)) or "untitled_shot"
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "shot_name": s_name,
            "latest_version": version_name,
            "total_versions": 0,
            "versions": {},
        }

    if shot_name and (manifest.get("shot_name") in (None, "", "untitled_shot")):
        manifest["shot_name"] = shot_name

    versions = manifest.setdefault("versions", {})
    versions[version_name] = version_record

    # Re-calculate highest version number and latest_version
    def _v_key(vn):
        m = _VERSION_DIR_RE.match(vn)
        return int(m.group(1)) if m else 0

    sorted_versions = sorted(versions.keys(), key=_v_key)
    manifest["latest_version"] = sorted_versions[-1] if sorted_versions else version_name
    manifest["total_versions"] = len(versions)

    # Mirror latest version attributes at root level for backward compatibility
    latest_rec = versions[manifest["latest_version"]]
    manifest["exported_by"] = latest_rec.get("exported_by", "")
    manifest["fps"] = latest_rec.get("fps", 24.0)
    manifest["frame_range"] = latest_rec.get("frame_range", {})
    manifest["camera"] = latest_rec.get("camera", {})
    manifest["characters"] = latest_rec.get("characters", [])
    manifest["props"] = latest_rec.get("props", [])
    manifest["metadata"] = latest_rec.get("metadata", {})

    save_shot_manifest(manifest, shot_dir)
    return manifest


def resolve_next_version(shot_dir):
    """
    Determine the next available version string (e.g. 'v001', 'v002') for shot_dir
    by inspecting Alembic/ subfolders, FBX/ subfolders, and shot_manifest.json.
    Returns tuple: (version_str, version_num).
    """
    seen_numbers = set()

    # 1. Inspect shot_manifest.json
    manifest = load_shot_manifest(shot_dir)
    if manifest and "versions" in manifest:
        for v_str in manifest["versions"].keys():
            m = _VERSION_DIR_RE.match(str(v_str).strip())
            if m:
                seen_numbers.add(int(m.group(1)))

    # 2. Inspect Alembic/ and FBX/ directories on disk
    for sub in ("Alembic", "FBX"):
        sub_path = os.path.join(shot_dir, sub)
        if os.path.isdir(sub_path):
            for entry in os.listdir(sub_path):
                entry_full = os.path.join(sub_path, entry)
                if os.path.isdir(entry_full):
                    m = _VERSION_DIR_RE.match(entry)
                    if m:
                        seen_numbers.add(int(m.group(1)))

    next_num = (max(seen_numbers) + 1) if seen_numbers else 1
    next_ver = "v{:03d}".format(next_num)
    return next_ver, next_num


def get_all_shot_versions(shot_dir):
    """
    Return a sorted list of all available version records for shot_dir.
    Combines data from shot_manifest.json with physical disk folders under Alembic/ and FBX/.
    Each item is a dict with full version metadata, file flags, and asset counts.
    """
    versions_map = {}

    # 1. Read manifest versions
    manifest = load_shot_manifest(shot_dir)
    if manifest and "versions" in manifest:
        for v_name, v_data in manifest["versions"].items():
            versions_map[v_name] = dict(v_data)

    # 2. Check disk for any unmanifested version folders under Alembic/ and FBX/
    for sub in ("Alembic", "FBX"):
        sub_path = os.path.join(shot_dir, sub)
        if os.path.isdir(sub_path):
            for entry in os.listdir(sub_path):
                if not os.path.isdir(os.path.join(sub_path, entry)):
                    continue
                m = _VERSION_DIR_RE.match(entry)
                if not m:
                    continue
                v_name = entry.lower()
                if v_name not in versions_map:
                    v_num = int(m.group(1))
                    mtime = os.path.getmtime(os.path.join(sub_path, entry))
                    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
                    versions_map[v_name] = {
                        "version": v_name,
                        "version_number": v_num,
                        "timestamp": time_str,
                        "exported_by": "unknown",
                        "workstation": "unknown",
                        "fps": 24.0,
                        "frame_range": {"start": 0, "end": 0},
                        "camera": {},
                        "characters": [],
                        "props": [],
                        "metadata": {"notes": "Discovered on disk"},
                    }

    # 3. Enrich with disk file presence and sort by version number
    result = []
    for v_name, rec in versions_map.items():
        v_rec = dict(rec)
        abc_dir = os.path.join(shot_dir, "Alembic", v_name)
        fbx_dir = os.path.join(shot_dir, "FBX", v_name)
        v_rec["has_alembic"] = os.path.isdir(abc_dir) and bool(os.listdir(abc_dir))
        v_rec["has_fbx"] = os.path.isdir(fbx_dir) and bool(os.listdir(fbx_dir))
        v_rec["abc_dir"] = abc_dir if v_rec["has_alembic"] else ""
        v_rec["fbx_dir"] = fbx_dir if v_rec["has_fbx"] else ""
        result.append(v_rec)

    def _v_num(item):
        return item.get("version_number", 0)

    result.sort(key=_v_num)
    return result


__all__ = [
    "MANIFEST_FILENAME",
    "SCHEMA_VERSION",
    "build_version_record",
    "build_shot_manifest",
    "load_shot_manifest",
    "save_shot_manifest",
    "update_shot_manifest",
    "resolve_next_version",
    "get_all_shot_versions",
]
