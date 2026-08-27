# -*- coding: utf-8 -*-
"""
Skin Tools
==========
Production-oriented, UI-independent Maya skin-weight core.

Designed for Maya 2023+ and usable from Maya GUI or maya.standalone.

Features
--------
- Fast Maya API 2.0 weight extraction/application
- Sparse JSON storage (only non-zero weights)
- Influence world matrices + radius
- Skinning method / normalize / max influences settings
- Already-skinned meshes are skipped automatically (with a warning), not overwritten
- Create missing joints from stored transforms
- Namespace-aware influence matching
- Exact vertex-count validation
- Topology signature validation runs automatically in the background
- Scene-classified v### snapshot folders; re-export never overwrites prior JSON
- Batch export/import for selected meshes
- Undo chunk for imports
- Headless Python API
- API mirror is registered as one native Maya undo item (Ctrl+Z / Ctrl+Y)
- Copy weights to existing skinClusters or duplicate a complete skin binding

This module contains no Qt dependency. Other Maya tools can import the stable
public adapters from ``scartools.tools.skin.api`` without loading the interface.
"""

from __future__ import print_function

import json
import os
import re
import math
import time
import tempfile
import uuid
import hashlib
import builtins
from array import array

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma

from scartools.version import VERSION

EPSILON = 1e-7
SKIN_PACKAGE_FORMAT = "ScarToolsSkinPackage"
SKIN_PACKAGE_VERSION = 1
SKIN_PACKAGE_FILENAME = "skin_weights_package.json"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SkinIOError(Exception):
    pass


# ---------------------------------------------------------------------------
# Maya helpers
# ---------------------------------------------------------------------------


def _short_name(node):
    return node.split("|")[-1]


def _strip_namespace(name):
    return name.split("|")[-1].split(":")[-1]


_INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def _safe_filename(node):
    """
    Turn a Maya node name into a name that is safe to use as a file name.

    The namespace separator ":" is the main risk: on Windows/NTFS,
    "name:stream" is Alternate Data Stream syntax, so a file name like
    "model:Pankho.json" silently creates an empty file named "model"
    instead of the file you expect. Replace ":" (and any other character
    that isn't safe across Windows/macOS/Linux file systems) rather than
    stripping the namespace outright, so meshes that share a short name
    across different namespaces still get distinct file names.
    """
    name = _short_name(node)

    for char in _INVALID_FILENAME_CHARS:
        name = name.replace(char, "_")

    return name


def _current_scene_path():
    """Return the normalized path of the currently open Maya scene."""
    scene_path = cmds.file(query=True, sceneName=True) or ""
    return os.path.normpath(scene_path) if scene_path else ""


def _require_saved_scene():
    """
    Scene-safe skin storage depends on a stable Maya file name.
    Refuse folder-classified export/import while the scene is unsaved.
    """
    scene_path = _current_scene_path()
    if not scene_path:
        raise SkinIOError(
            "Save the Maya scene first. Skin JSON files are classified "
            "inside a folder named after the current Maya file."
        )
    return scene_path


_SCENE_VERSION_SUFFIX_RE = re.compile(
    r"(?:[_.\- ]+(?:(?:version|ver|v)[_.\- ]*)?\d+)$",
    re.IGNORECASE,
)


def _scene_asset_key(value):
    """Normalize versioned scene names to one stable rig identity."""
    portable_value = str(value or "").replace("\\", "/")
    name = os.path.splitext(portable_value.rsplit("/", 1)[-1])[0]
    name = _SCENE_VERSION_SUFFIX_RE.sub("", name).strip("_.- ")
    for char in _INVALID_FILENAME_CHARS:
        name = name.replace(char, "_")
    return name or "untitled_scene"


def _current_scene_folder_name():
    """
    Return a filesystem-safe folder name derived from the current Maya file.

    Versioned Maya files share one stable folder:
        Hero_Rig_v01.ma -> Hero_Rig
        Hero_Rig_v02.ma -> Hero_Rig
        Hero_Rig.ma     -> Hero_Rig
    """
    scene_path = _current_scene_path()

    if not scene_path:
        return "untitled_scene"

    return _scene_asset_key(scene_path)


def _current_scene_metadata():
    """Small portable scene identity stored inside every exported JSON."""
    scene_path = _current_scene_path()
    scene_file = (
        scene_path.replace("\\", "/").rsplit("/", 1)[-1]
        if scene_path else ""
    )
    return {
        "fileName": scene_file,
        "folderName": _current_scene_folder_name(),
        "assetKey": _current_scene_folder_name(),
    }


_VERSION_FOLDER_RE = re.compile(r"^v(\d+)$", re.IGNORECASE)


def _version_number(folder_name):
    """Return the integer version for names such as v001, v12, V003."""
    match = _VERSION_FOLDER_RE.match(folder_name or "")
    return int(match.group(1)) if match else None


def _scene_directory(root_directory, create=False):
    """
    Resolve the scene-classified directory under a user-selected root.

    Accepted selections:
        <root>
        <root>/<scene>
        <root>/<scene>/v###

    Selecting a version folder resolves back to its owning scene folder,
    preventing accidental nesting such as ``v003/Pumpkin_Rig``.
    """
    root_directory = os.path.normpath(root_directory)
    scene_folder = _current_scene_folder_name()
    base = os.path.basename(root_directory)
    parent = os.path.dirname(root_directory)

    if _scene_asset_key(base).lower() == scene_folder.lower():
        scene_dir = root_directory
    elif (
        _version_number(base) is not None
        and _scene_asset_key(os.path.basename(parent)).lower() == scene_folder.lower()
    ):
        scene_dir = parent
    else:
        scene_dir = os.path.join(root_directory, scene_folder)

        # Existing pre-4.7 folders such as Male_Rig_v01 remain readable when
        # the artist selects their shared parent directory. New exports always
        # use the normalized Male_Rig folder.
        if not create and not os.path.isdir(scene_dir) and os.path.isdir(root_directory):
            compatible = []
            for name in os.listdir(root_directory):
                path = os.path.join(root_directory, name)
                if (
                    os.path.isdir(path)
                    and _scene_asset_key(name).lower() == scene_folder.lower()
                ):
                    versions = _version_directories(path)
                    newest = versions[-1][0] if versions else 0
                    compatible.append((newest, os.path.getmtime(path), path))
            if compatible:
                compatible.sort()
                scene_dir = compatible[-1][2]

    if create and not os.path.exists(scene_dir):
        os.makedirs(scene_dir)

    return scene_dir


def _version_directories(scene_dir):
    """Return existing scene version folders sorted by numeric version."""
    if not os.path.isdir(scene_dir):
        return []

    versions = []
    for name in os.listdir(scene_dir):
        number = _version_number(name)
        path = os.path.join(scene_dir, name)
        if number is not None and os.path.isdir(path):
            versions.append((number, path))

    versions.sort(key=lambda item: item[0])
    return versions


def _next_version_directory(scene_dir, create=True):
    """
    Create/resolve the next scene export version directory.

    Example:
        Pumpkin_Rig/v001
        Pumpkin_Rig/v002
        Pumpkin_Rig/v003
    """
    versions = _version_directories(scene_dir)
    next_number = (versions[-1][0] + 1) if versions else 1
    while True:
        version_name = "v{:03d}".format(next_number)
        version_dir = os.path.join(scene_dir, version_name)
        if not create:
            return version_dir, version_name
        try:
            # Atomic reservation prevents two artists/processes from claiming
            # the same snapshot version on a shared production location.
            os.mkdir(version_dir)
            return version_dir, version_name
        except OSError:
            if not os.path.isdir(version_dir):
                raise
            next_number += 1


def _latest_version_directory(scene_dir):
    """Return ``(path, version_name)`` for the newest numeric version."""
    versions = _version_directories(scene_dir)
    if not versions:
        return None, None

    _number, path = versions[-1]
    return path, os.path.basename(path)


def _import_directory_for_scene(scene_dir, requested_directory=None):
    """
    Resolve the import source for the current scene.

    If the user explicitly selects a v### folder belonging to this scene,
    use that exact version. Otherwise use the newest version automatically.

    Loose JSON files in the asset folder are deliberately not supported.
    """
    scene_dir = os.path.normpath(scene_dir)

    if requested_directory:
        requested_directory = os.path.normpath(requested_directory)
        requested_name = os.path.basename(requested_directory)
        requested_parent = os.path.dirname(requested_directory)

        if (
            _version_number(requested_name) is not None
            and os.path.normcase(requested_parent) == os.path.normcase(scene_dir)
            and os.path.isdir(requested_directory)
        ):
            return requested_directory, requested_name

    version_dir, version_name = _latest_version_directory(scene_dir)
    if version_dir:
        return version_dir, version_name

    return None, None


def _validate_json_scene_identity(data, file_path=None):
    """
    Reject a JSON explicitly exported from a different Maya scene.

    Packed v4.8+ packages must include sourceScene metadata.
    """
    source_scene = data.get("sourceScene") or {}
    exported_folder = (
        source_scene.get("assetKey")
        or source_scene.get("folderName")
        or source_scene.get("fileName")
    )

    if not exported_folder:
        raise SkinIOError(
            "Packed skin JSON has no source-scene identity metadata. "
            "Re-export it with ScarTools 4.8 or newer."
        )

    current_folder = _current_scene_folder_name()
    exported_asset = _scene_asset_key(exported_folder)
    if exported_asset.lower() != current_folder.lower():
        raise SkinIOError(
            "Scene mismatch. Import cancelled to prevent applying skin "
            "weights from the wrong Maya file.\n\n"
            "JSON scene: {}\n"
            "Current scene: {}\n"
            "File: {}".format(
                exported_asset,
                current_folder,
                file_path or "<unknown>"
            )
        )


def _dag_path(node):
    sel = om.MSelectionList()
    sel.add(node)
    return sel.getDagPath(0)


def _mesh_shape(node):
    if not cmds.objExists(node):
        raise SkinIOError("Node does not exist: {}".format(node))

    if cmds.nodeType(node) == "mesh":
        return node

    shapes = cmds.listRelatives(
        node, shapes=True, noIntermediate=True, fullPath=True
    ) or []

    for shape in shapes:
        if cmds.nodeType(shape) == "mesh":
            return shape

    raise SkinIOError("'{}' is not a polygon mesh.".format(node))


def _mesh_transform(node):
    shape = _mesh_shape(node)
    parent = cmds.listRelatives(shape, parent=True, fullPath=True) or []
    if not parent:
        raise SkinIOError("Could not find transform for '{}'.".format(node))
    return parent[0]


def _skin_cluster(node):
    transform = _mesh_transform(node)
    shape = _mesh_shape(transform)

    for target in (transform, shape):
        history = cmds.listHistory(target, pruneDagObjects=True) or []
        skins = cmds.ls(history, type="skinCluster") or []
        if skins:
            return skins[0]

    return None


def _progress(callback, value, message=None):
    if callback:
        try:
            callback(value, message)
        except TypeError:
            callback(value)


def _log(callback, message):
    if callback:
        callback(message)
    else:
        print(message)


# ---------------------------------------------------------------------------
# Influence matching
# ---------------------------------------------------------------------------

class _InfluenceLookup(object):
    """Pre-index influence names for fast, deterministic matching."""

    __slots__ = ("exact", "short", "base")

    def __init__(self, influences):
        self.exact = set(influences)
        self.short = self._unique_map(influences, _short_name)
        self.base = self._unique_map(influences, _strip_namespace)

    @staticmethod
    def _unique_map(influences, key_function):
        result = {}
        ambiguous = set()
        for influence in influences:
            key = key_function(influence)
            if key in result:
                ambiguous.add(key)
            else:
                result[key] = influence
        for key in ambiguous:
            result.pop(key, None)
        return result

    def resolve(self, source_name):
        if source_name in self.exact:
            return source_name
        match = self.short.get(_short_name(source_name))
        if match is not None:
            return match
        return self.base.get(_strip_namespace(source_name))


def _find_influence(source_name, scene_influences):
    """
    Resolve an exported influence against current scene influences.

    Priority:
        1. exact name
        2. exact short name
        3. namespace-free name if unique
    """
    lookup = (
        scene_influences
        if isinstance(scene_influences, _InfluenceLookup)
        else _InfluenceLookup(scene_influences)
    )
    return lookup.resolve(source_name)


# ---------------------------------------------------------------------------
# Joint transform helpers
# ---------------------------------------------------------------------------

def _world_matrix(node):
    return [
        float(x)
        for x in cmds.xform(node, q=True, ws=True, matrix=True)
    ]


def _set_world_matrix(node, matrix):
    if matrix and len(matrix) == 16:
        cmds.xform(node, ws=True, matrix=matrix)


def _joint_radius(node):
    if cmds.attributeQuery("radius", node=node, exists=True):
        try:
            return float(cmds.getAttr(node + ".radius"))
        except Exception:
            pass
    return 1.0


def _create_joint_from_data(name, info):
    """
    Create a missing joint without assuming hierarchy.
    The stored world matrix is restored after creation.
    """
    clean_name = _short_name(name)

    cmds.select(clear=True)
    try:
        joint = cmds.createNode("joint", name=clean_name)
    except Exception:
        # Maya may reject a duplicate short name because another namespace
        # resolves to the same requested name.
        joint = cmds.createNode("joint", name="SWI_" + clean_name)

    matrix = info.get("worldMatrix") if info else None
    if matrix:
        _set_world_matrix(joint, matrix)

    radius = info.get("radius") if info else None
    if radius is not None:
        try:
            cmds.setAttr(joint + ".radius", float(radius))
        except Exception:
            pass

    return joint


# ---------------------------------------------------------------------------
# Mesh metadata
# ---------------------------------------------------------------------------

def _mesh_vertex_count(shape):
    return int(cmds.polyEvaluate(shape, vertex=True))


def _mesh_face_count(shape):
    return int(cmds.polyEvaluate(shape, face=True))


def _mesh_edge_count(shape):
    return int(cmds.polyEvaluate(shape, edge=True))


def _mesh_signature(shape):
    """Return a deterministic topology signature including connectivity."""
    signature = {
        "vertexCount": _mesh_vertex_count(shape),
        "edgeCount": _mesh_edge_count(shape),
        "faceCount": _mesh_face_count(shape),
    }
    try:
        mesh = om.MSelectionList()
        mesh.add(shape)
        dag = mesh.getDagPath(0)
        fn = om.MFnMesh(dag)
        counts, connects = fn.getVertices()
        payload = "|".join(map(str, counts)) + "|" + "|".join(map(str, connects))
        signature["topologyHash"] = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    except Exception:
        signature["topologyHash"] = None
    return signature


# ---------------------------------------------------------------------------
# API weight access
# ---------------------------------------------------------------------------

def _skin_fn(skin_cluster):
    sel = om.MSelectionList()
    sel.add(skin_cluster)
    obj = sel.getDependNode(0)
    return oma.MFnSkinCluster(obj)


def _mesh_components(vertex_count):
    fn = om.MFnSingleIndexedComponent()
    comp = fn.create(om.MFn.kMeshVertComponent)
    fn.addElements(list(range(vertex_count)))
    return comp


def _api_export_weights(skin_cluster, shape):
    """
    Read all skin weights in one API call.

    Return influences and Maya's contiguous component-major weight buffer.

    Keeping the native flat buffer avoids creating a second large nested
    Python list before sparse JSON packing.
    """
    dag = _dag_path(shape)
    fn = _skin_fn(skin_cluster)
    influence_paths = fn.influenceObjects()

    influences = [
        influence_path.fullPathName()
        for influence_path in influence_paths
    ]

    vertex_count = _mesh_vertex_count(shape)
    components = _mesh_components(vertex_count)

    result = fn.getWeights(dag, components)
    weights = result[0]
    influence_count = int(result[1])

    return influences, weights, vertex_count, influence_count


def _api_import_weights(skin_cluster, shape, flat_weights, vertex_count, influence_count):
    """Apply the complete weight buffer in one typed Maya API 2.0 call."""
    expected = vertex_count * influence_count
    if len(flat_weights) != expected:
        raise SkinIOError(
            "Invalid API weight buffer: expected {} values, got {}.".format(
                expected, len(flat_weights)
            )
        )

    dag = _dag_path(shape)
    fn = _skin_fn(skin_cluster)
    components = _mesh_components(vertex_count)

    # Be explicit about the API array type. Some Maya/Python builds do not
    # reliably select the MIntArray overload when given a normal Python list.
    influence_indices = om.MIntArray()
    influence_indices.copy(list(range(influence_count)))

    fn.setWeights(
        dag,
        components,
        influence_indices,
        flat_weights,
        False
    )



# ---------------------------------------------------------------------------
# Skin utilities
# ---------------------------------------------------------------------------

def _skin_influence_paths(skin_cluster):
    """Return skinCluster influences as full DAG paths in API index order."""
    return [
        path.fullPathName()
        for path in _skin_fn(skin_cluster).influenceObjects()
    ]


def _find_unused_influences(skin_cluster, shape, threshold=EPSILON):
    """
    Return full DAG paths for influences with no meaningful vertex weight.

    All weights are read in one Maya API call. At least one influence is
    preserved because a usable skinCluster must retain an influence.
    """
    fn = _skin_fn(skin_cluster)
    influence_paths = fn.influenceObjects()
    influence_count = len(influence_paths)

    if influence_count <= 1:
        return []

    vertex_count = _mesh_vertex_count(shape)
    if vertex_count <= 0:
        return []

    dag = _dag_path(shape)
    components = _mesh_components(vertex_count)
    weights, returned_count = fn.getWeights(dag, components)
    returned_count = int(returned_count)

    if returned_count != influence_count:
        raise SkinIOError(
            "Influence count changed while checking unused influences. "
            "Expected {}, got {}.".format(influence_count, returned_count)
        )

    used = [False] * influence_count
    remaining = influence_count

    # getWeights() layout is component -> influence.
    for flat_index, value in enumerate(weights):
        if abs(float(value)) > threshold:
            influence_index = flat_index % influence_count
            if not used[influence_index]:
                used[influence_index] = True
                remaining -= 1
                if remaining == 0:
                    break

    unused = [
        influence_paths[index].fullPathName()
        for index, is_used in enumerate(used)
        if not is_used
    ]

    # Pathological all-zero cluster: keep the first influence for safety.
    if len(unused) == influence_count:
        unused = unused[1:]

    return unused


def remove_unused_influences(node=None, threshold=EPSILON, log=None):
    """
    Remove zero-weight influences from one mesh's skinCluster.

    Returns the full DAG paths of influences successfully removed.
    """
    if node is None:
        selection = cmds.ls(sl=True, long=True) or []
        if not selection:
            raise SkinIOError("Select a skinned mesh or mesh transform.")
        node = selection[0]

    transform = _mesh_transform(node)
    shape = _mesh_shape(transform)
    skin = _skin_cluster(transform)

    if not skin:
        raise SkinIOError("No skinCluster found on '{}'.".format(transform))

    unused = _find_unused_influences(skin, shape, threshold=threshold)
    if not unused:
        _log(log, "No unused influences: {}".format(_short_name(transform)))
        return []

    # add/removeInfluence are multi-use flags in Maya 2023+. One command is
    # significantly faster for production rigs with many empty influences.
    try:
        cmds.skinCluster(skin, edit=True, removeInfluence=unused)
        removed = list(unused)
    except Exception:
        removed = []
        current_lookup = _InfluenceLookup(_skin_influence_paths(skin))
        for influence in unused:
            if current_lookup.resolve(influence) is None:
                removed.append(influence)
                continue
            try:
                cmds.skinCluster(skin, edit=True, removeInfluence=influence)
                removed.append(influence)
            except Exception as exc:
                _log(
                    log,
                    "WARNING: Could not remove {}: {}".format(
                        _short_name(influence), exc
                    )
                )

    _log(
        log,
        "Removed {} unused influence(s) from {}.".format(
            len(removed), _short_name(transform)
        )
    )
    return removed


def remove_unused_influences_from_selected(
    threshold=EPSILON,
    log=None,
    progress=None,
    use_undo=True
):
    """
    Remove unused influences from all currently selected polygon meshes.

    The whole operation is one Maya Undo step. Meshes without skinClusters
    are skipped. Returns {mesh: [removed influence paths]}.
    """
    meshes = selected_meshes()
    if not meshes:
        raise SkinIOError("Select one or more polygon meshes.")

    old_selection = cmds.ls(sl=True, long=True) or []
    results = {}

    if use_undo:
        cmds.undoInfo(
            openChunk=True,
            chunkName="ScarTools_RemoveUnusedInfluences"
        )

    try:
        total = len(meshes)
        for index, mesh in enumerate(meshes):
            if not _skin_cluster(mesh):
                _log(log, "SKIP: No skinCluster on {}".format(_short_name(mesh)))
                results[mesh] = []
            else:
                results[mesh] = remove_unused_influences(
                    node=mesh,
                    threshold=threshold,
                    log=log
                )

            _progress(
                progress,
                int(((index + 1) / float(total)) * 100),
                "Removing unused influences..."
            )
    finally:
        if old_selection:
            try:
                cmds.select(old_selection, replace=True)
            except Exception:
                pass

        if use_undo:
            cmds.undoInfo(closeChunk=True)

    return results


# ---------------------------------------------------------------------------
# Skin Health Diagnostics & Symmetry QA
# ---------------------------------------------------------------------------


def inspect_skin_health(nodes=None, threshold=0.001, max_influences=None):
    """Scan skinned meshes for zero-weight, unnormalized, stray, or NaN weights."""
    from scartools.licensing import require_license
    require_license("Skin Health QA")

    targets = [nodes] if isinstance(nodes, str) else (nodes or selected_meshes())

    results = {}

    for node in targets:
        transform = _mesh_transform(node)
        shape = _mesh_shape(transform)
        skin = _skin_cluster(transform)
        if not skin:
            continue

        influences, weights, vertex_count, influence_count = _api_export_weights(
            skin, shape
        )
        unweighted = []
        unnormalized = []
        stray = []
        exceeds_max = []
        nan_inf = []

        eff_max = (
            int(max_influences)
            if max_influences is not None
            else int(_skin_setting(skin, "maxInfluences", 4))
        )

        for vertex_id in range(vertex_count):
            base = vertex_id * influence_count
            total = 0.0
            active_count = 0
            has_nan = False

            for inf_idx in range(influence_count):
                val = weights[base + inf_idx]
                if not math.isfinite(val):
                    has_nan = True
                    break
                if val > EPSILON:
                    total += val
                    active_count += 1
                    if val < threshold:
                        stray.append((vertex_id, influences[inf_idx], val))

            if has_nan:
                nan_inf.append(vertex_id)
            elif active_count == 0:
                unweighted.append(vertex_id)
            else:
                if abs(total - 1.0) > 1e-4:
                    unnormalized.append((vertex_id, total))
                if active_count > eff_max:
                    exceeds_max.append((vertex_id, active_count))

        results[transform] = {
            "transform": transform,
            "skin": skin,
            "vertex_count": vertex_count,
            "influence_count": influence_count,
            "max_influences_threshold": eff_max,
            "unweighted": unweighted,
            "unnormalized": unnormalized,
            "stray": stray,
            "exceeds_max": exceeds_max,
            "nan_inf": nan_inf,
            "healthy": not (unweighted or unnormalized or nan_inf or exceeds_max),
        }

    return results


def select_skin_issue_vertices(
    node, issue_type="unweighted", threshold=0.001, max_influences=None
):
    """Select offending mesh vertices in Maya's viewport for visual inspection."""
    report = inspect_skin_health(
        node, threshold=threshold, max_influences=max_influences
    )
    transform = _mesh_transform(node)
    data = report.get(transform)
    if not data:
        return []

    shape = _mesh_shape(transform)
    issue_type = str(issue_type).lower()

    if issue_type == "unweighted":
        vids = data["unweighted"]
    elif issue_type == "unnormalized":
        vids = [item[0] for item in data["unnormalized"]]
    elif issue_type == "stray":
        vids = list({item[0] for item in data["stray"]})
    elif issue_type == "exceeds_max":
        vids = [item[0] for item in data["exceeds_max"]]
    elif issue_type == "nan_inf":
        vids = data["nan_inf"]
    else:
        vids = list(
            set(data["unweighted"])
            | {item[0] for item in data["unnormalized"]}
            | {item[0] for item in data["stray"]}
            | {item[0] for item in data["exceeds_max"]}
            | set(data["nan_inf"])
        )

    components = ["{}.vtx[{}]".format(shape, vid) for vid in vids]
    if components:
        cmds.select(components, replace=True)
    else:
        cmds.select(clear=True)
    return components


def inspect_skin_symmetry(node, axis="X", tolerance=1e-4):
    """Find geometric mesh vertices that lack a symmetric counterpart across axis."""
    transform = _mesh_transform(node)
    shape = _mesh_shape(transform)
    axis_idx = _MIRROR_AXIS_INDEX.get(str(axis).upper(), 0)

    points, vertex_count = _mesh_points(shape)
    asymmetric = []

    quantize = 1.0 / max(1e-6, tolerance)
    grid = {}
    for vid, pt in enumerate(points):
        key = (
            int(round(pt[0] * quantize)),
            int(round(pt[1] * quantize)),
            int(round(pt[2] * quantize)),
        )
        grid[key] = vid

    for vid, pt in enumerate(points):
        if abs(pt[axis_idx]) <= tolerance:
            continue
        refl = list(pt)
        refl[axis_idx] = -refl[axis_idx]
        target_key = (
            int(round(refl[0] * quantize)),
            int(round(refl[1] * quantize)),
            int(round(refl[2] * quantize)),
        )
        if target_key not in grid:
            asymmetric.append(vid)

    return {
        "transform": transform,
        "axis": str(axis).upper(),
        "vertex_count": vertex_count,
        "asymmetric_count": len(asymmetric),
        "asymmetric_vertices": asymmetric,
        "is_symmetric": len(asymmetric) == 0,
    }


def select_asymmetric_skin_vertices(nodes=None, axis="X", tolerance=1e-4):
    """Find and select in Maya's viewport all vertices that lack a symmetric counterpart."""
    if nodes is None:
        nodes = selected_meshes()
    if not isinstance(nodes, (list, tuple, set)):
        nodes = [nodes] if nodes else []

    all_components = []
    for node in nodes:
        if not node or not cmds.objExists(str(node)):
            continue
        try:
            report = inspect_skin_symmetry(node, axis=axis, tolerance=tolerance)
            shape = _mesh_shape(_mesh_transform(node))
            for vid in report["asymmetric_vertices"]:
                all_components.append("{}.vtx[{}]".format(shape, vid))
        except Exception:
            pass

    if all_components:
        cmds.select(all_components, replace=True)
    else:
        cmds.select(clear=True)
    return all_components


def _selected_vertex_indices(node):
    """Return a set of vertex indices currently selected on the given mesh."""
    selection = cmds.ls(selection=True, flatten=True) or []
    if not selection:
        return set()
    transform = _mesh_transform(node)
    shape = _mesh_shape(transform)
    names = {
        transform, shape, _short_name(transform), _short_name(shape)
    }

    indices = set()
    for item in selection:
        if ".vtx[" not in item:
            continue
        parts = item.split(".vtx[")
        mesh_part = parts[0]
        if mesh_part in names or _short_name(mesh_part) in names:
            try:
                idx_str = parts[1].rstrip("]")
                indices.add(int(idx_str))
            except Exception:
                pass
    return indices


# ---------------------------------------------------------------------------
# API undo bridge
# ---------------------------------------------------------------------------

_API_UNDO_COMMAND = "scarToolsSkinApiUndoV6"
_API_UNDO_PLUGIN_FILENAME = "scartools_skin_api_undo_v6.py"
_API_UNDO_REGISTRY_ATTR = "_SCARTOOLS_SKIN_API_UNDO_V6_REGISTRY"


def _api_undo_registry():
    """Return the process-wide payload registry shared with the tiny undo plug-in."""
    registry = getattr(builtins, _API_UNDO_REGISTRY_ATTR, None)
    if registry is None:
        registry = {}
        setattr(builtins, _API_UNDO_REGISTRY_ATTR, registry)
    return registry


def _api_undo_plugin_source():
    """Source for a minimal MPxCommand used only to put API edits on Maya's undo queue."""
    return r'''# -*- coding: utf-8 -*-
import builtins
from array import array
import maya.api.OpenMaya as om

COMMAND_NAME = "scarToolsSkinApiUndoV6"
REGISTRY_ATTR = "_SCARTOOLS_SKIN_API_UNDO_V6_REGISTRY"


maya_useNewAPI = True


class ScarToolsSkinApiUndoCommand(om.MPxCommand):
    def __init__(self):
        super(ScarToolsSkinApiUndoCommand, self).__init__()
        self._payload = None

    @staticmethod
    def creator():
        return ScarToolsSkinApiUndoCommand()

    def doIt(self, args):
        if len(args) < 1:
            raise RuntimeError("Missing Skin Tools undo transaction id.")

        transaction_id = args.asString(0)
        registry = getattr(builtins, REGISTRY_ATTR, None) or {}
        payload = registry.pop(transaction_id, None)
        if payload is None:
            raise RuntimeError(
                "Skin Tools undo payload was not found: {}".format(
                    transaction_id
                )
            )

        self._payload = payload
        try:
            self.redoIt()
        except Exception:
            try:
                self.undoIt()
            except Exception:
                pass
            raise

    def redoIt(self):
        if self._payload:
            self._payload["redo"]()

    def undoIt(self):
        if self._payload:
            self._payload["undo"]()

    def isUndoable(self):
        return True


def initializePlugin(plugin_object):
    plugin = om.MFnPlugin(plugin_object, "XSQUADS", "6.0.0", "Any")
    plugin.registerCommand(COMMAND_NAME, ScarToolsSkinApiUndoCommand.creator)


def uninitializePlugin(plugin_object):
    plugin = om.MFnPlugin(plugin_object)
    plugin.deregisterCommand(COMMAND_NAME)
'''


def _ensure_api_undo_command():
    """Load the tiny undo command plug-in once per Maya session."""
    plugin_path = os.path.join(
        tempfile.gettempdir(), _API_UNDO_PLUGIN_FILENAME
    )
    source = _api_undo_plugin_source()

    # The user still distributes one file. The helper is generated only in
    # Maya's temporary directory and loaded on the first API mirror operation.
    try:
        existing = None
        if os.path.isfile(plugin_path):
            with open(plugin_path, "r") as stream:
                existing = stream.read()
        if existing != source:
            with open(plugin_path, "w") as stream:
                stream.write(source)
    except Exception as exc:
        raise SkinIOError(
            "Could not create the Maya API undo helper:\n{}".format(exc)
        )

    loaded = False
    for plugin_query in (plugin_path, os.path.basename(plugin_path)):
        try:
            if cmds.pluginInfo(plugin_query, query=True, loaded=True):
                loaded = True
                break
        except Exception:
            pass

    if not loaded:
        try:
            cmds.loadPlugin(plugin_path, quiet=True)
        except Exception as exc:
            raise SkinIOError(
                "Could not load the Maya API undo helper:\n{}".format(exc)
            )

    return plugin_path


def _commit_api_undo_payload(redo_callback, undo_callback):
    """Execute one API edit through an undoable MPxCommand."""
    _ensure_api_undo_command()

    transaction_id = uuid.uuid4().hex
    registry = _api_undo_registry()
    registry[transaction_id] = {
        "redo": redo_callback,
        "undo": undo_callback,
    }

    try:
        command = getattr(cmds, _API_UNDO_COMMAND)
        command(transaction_id)
    except Exception:
        registry.pop(transaction_id, None)
        raise


# ---------------------------------------------------------------------------
# Skin mirror - Maya API 2.0
# ---------------------------------------------------------------------------

_MIRROR_AXIS_INDEX = {
    "X": 0,
    "Y": 1,
    "Z": 2,
}


def _point_xyz(point):
    return (float(point.x), float(point.y), float(point.z))


def _point_coord(point, axis_index):
    if axis_index == 0:
        return float(point.x)
    if axis_index == 1:
        return float(point.y)
    return float(point.z)


def _set_reflected_axis(point, axis_index):
    if axis_index == 0:
        point.x = -float(point.x)
    elif axis_index == 1:
        point.y = -float(point.y)
    else:
        point.z = -float(point.z)
    return point


def _reflect_xyz(values, axis_index):
    result = [float(values[0]), float(values[1]), float(values[2])]
    result[axis_index] *= -1.0
    return tuple(result)


def _distance_sq(a, b):
    return (
        (float(a[0]) - float(b[0])) ** 2
        + (float(a[1]) - float(b[1])) ** 2
        + (float(a[2]) - float(b[2])) ** 2
    )


def _joint_world_position(node):
    values = cmds.xform(node, query=True, worldSpace=True, translation=True)
    return (float(values[0]), float(values[1]), float(values[2]))


def _joint_label_info(node):
    """Return Maya joint label metadata when available."""
    result = {"side": None, "type": None, "otherType": ""}
    for attr in ("side", "type"):
        try:
            result[attr] = int(cmds.getAttr("{}.{}".format(node, attr)))
        except Exception:
            pass
    try:
        result["otherType"] = cmds.getAttr(node + ".otherType") or ""
    except Exception:
        pass
    return result


def _mirrored_name_candidates(name):
    """Return conservative left/right name swaps for a namespace-free name."""
    pairs = (
        ("Left", "Right"), ("left", "right"), ("LEFT", "RIGHT"),
        ("_L_", "_R_"), ("_l_", "_r_"),
        (".L", ".R"), (".l", ".r"),
        ("-L", "-R"), ("-l", "-r"),
        ("_L", "_R"), ("_l", "_r"),
        ("L_", "R_"), ("l_", "r_"),
    )
    result = []
    for left, right in pairs:
        if left in name:
            result.append(name.replace(left, right, 1))
        if right in name:
            result.append(name.replace(right, left, 1))
    return result


def _build_mirror_influence_map(influence_paths, axis_index, association="auto", log=None):
    """
    Build source influence index -> mirrored influence index.

    Matching modes:
        - auto: Labels -> Names -> Position -> Self
        - names: Conservative name swaps -> Self
        - labels: Joint labels -> Self
        - positions: Reflected joint position -> Self
    """
    names = [path.fullPathName() for path in influence_paths]
    bases = [_strip_namespace(name) for name in names]
    positions = [_joint_world_position(name) for name in names]
    labels = [_joint_label_info(name) for name in names]

    if not names:
        return []

    mins = [min(pos[i] for pos in positions) for i in range(3)]
    maxs = [max(pos[i] for pos in positions) for i in range(3)]
    diag = math.sqrt(sum((maxs[i] - mins[i]) ** 2 for i in range(3)))
    center_tolerance = max(1e-6, diag * 1e-5)
    position_limit = max(1e-4, diag * 0.08)
    position_limit_sq = position_limit * position_limit

    base_to_indices = {}
    for index, base in enumerate(bases):
        base_to_indices.setdefault(base, []).append(index)

    mapping = list(range(len(names)))
    methods = {"label": 0, "name": 0, "position": 0, "self": 0}

    for source_index, source_name in enumerate(names):
        source_pos = positions[source_index]
        source_label = labels[source_index]

        # Center influences stay on themselves.
        if abs(source_pos[axis_index]) <= center_tolerance:
            mapping[source_index] = source_index
            methods["self"] += 1
            continue

        target_index = None

        # 1) Joint labels. Maya side values commonly use 1=Left, 2=Right.
        if association in ("auto", "labels"):
            source_side = source_label.get("side")
            source_type = source_label.get("type")
            if source_side in (1, 2) and source_type is not None:
                opposite_side = 2 if source_side == 1 else 1
                candidates = []
                for index, info in enumerate(labels):
                    if index == source_index:
                        continue
                    if info.get("side") != opposite_side:
                        continue
                    if info.get("type") != source_type:
                        continue
                    if source_type == 18 and (
                        info.get("otherType") or ""
                    ) != (source_label.get("otherType") or ""):
                        continue
                    candidates.append(index)

                if candidates:
                    reflected = _reflect_xyz(source_pos, axis_index)
                    target_index = min(
                        candidates,
                        key=lambda index: _distance_sq(positions[index], reflected)
                    )
                    methods["label"] += 1

        # 2) Conservative name swaps.
        if target_index is None and association in ("auto", "names"):
            for candidate_name in _mirrored_name_candidates(bases[source_index]):
                indices = base_to_indices.get(candidate_name, [])
                if len(indices) == 1:
                    target_index = indices[0]
                    methods["name"] += 1
                    break

        # 3) Reflected joint position, but only when reasonably close.
        if target_index is None and association in ("auto", "positions"):
            reflected = _reflect_xyz(source_pos, axis_index)
            candidate = min(
                range(len(positions)),
                key=lambda index: _distance_sq(positions[index], reflected)
            )
            if _distance_sq(positions[candidate], reflected) <= position_limit_sq:
                target_index = candidate
                methods["position"] += 1

        # 4) Safer than mapping to an unrelated joint.
        if target_index is None:
            target_index = source_index
            methods["self"] += 1

        mapping[source_index] = target_index

    _log(
        log,
        "Influence mirror map: label={} name={} position={} self={}".format(
            methods["label"], methods["name"], methods["position"], methods["self"]
        )
    )
    return mapping


def _mesh_world_points(shape):
    dag = _dag_path(shape)
    mesh_fn = om.MFnMesh(dag)
    return dag, mesh_fn, mesh_fn.getPoints(om.MSpace.kWorld)


def _mesh_points(shape):
    dag, mesh_fn, points = _mesh_world_points(shape)
    return points, len(points)


def _mesh_point_extent(points):
    if not points:
        return 1.0
    mins = [min(_point_coord(p, i) for p in points) for i in range(3)]
    maxs = [max(_point_coord(p, i) for p in points) for i in range(3)]
    return math.sqrt(sum((maxs[i] - mins[i]) ** 2 for i in range(3))) or 1.0


def _source_vertex_lookup(points, axis_index, source_positive, tolerance):
    """Build a quantized lookup for fast exact/near-exact symmetric pairs."""
    inverse = 1.0 / max(tolerance, 1e-12)
    table = {}
    source_ids = []

    for vertex_id, point in enumerate(points):
        coord = _point_coord(point, axis_index)
        if source_positive:
            if coord <= tolerance:
                continue
        else:
            if coord >= -tolerance:
                continue

        key = (
            int(round(float(point.x) * inverse)),
            int(round(float(point.y) * inverse)),
            int(round(float(point.z) * inverse)),
        )
        table.setdefault(key, []).append(vertex_id)
        source_ids.append(vertex_id)

    return table, source_ids, inverse


def _closest_source_vertex(
    mesh_fn,
    points,
    reflected_point,
    source_lookup,
    inverse_tolerance,
    axis_index,
    source_positive,
    center_tolerance
):
    """Find the source-side vertex corresponding to a reflected target point."""
    key = (
        int(round(float(reflected_point.x) * inverse_tolerance)),
        int(round(float(reflected_point.y) * inverse_tolerance)),
        int(round(float(reflected_point.z) * inverse_tolerance)),
    )
    candidates = source_lookup.get(key)
    if candidates:
        target_xyz = _point_xyz(reflected_point)
        return min(
            candidates,
            key=lambda vertex_id: _distance_sq(_point_xyz(points[vertex_id]), target_xyz)
        )

    # Maya's mesh query is C++ accelerated and provides a robust fallback for
    # geometry that is almost, but not perfectly, symmetrical.
    closest_point, face_id = mesh_fn.getClosestPoint(
        reflected_point,
        om.MSpace.kWorld
    )
    face_vertices = list(mesh_fn.getPolygonVertices(int(face_id)))
    filtered = []
    for vertex_id in face_vertices:
        coord = _point_coord(points[vertex_id], axis_index)
        if source_positive and coord > center_tolerance:
            filtered.append(vertex_id)
        elif (not source_positive) and coord < -center_tolerance:
            filtered.append(vertex_id)

    candidates = filtered or face_vertices
    if not candidates:
        raise SkinIOError("Could not resolve a mirrored source vertex.")

    target_xyz = _point_xyz(reflected_point)
    return min(
        candidates,
        key=lambda vertex_id: _distance_sq(_point_xyz(points[vertex_id]), target_xyz)
    )


def _trim_and_normalize_row(row, max_influences=None):
    if max_influences and max_influences > 0:
        active = [(index, value) for index, value in enumerate(row) if value > EPSILON]
        if len(active) > max_influences:
            keep = set(
                index for index, _value in sorted(
                    active, key=lambda item: item[1], reverse=True
                )[:max_influences]
            )
            for index in range(len(row)):
                if index not in keep:
                    row[index] = 0.0

    total = sum(row)
    if total > EPSILON:
        inv = 1.0 / total
        for index in range(len(row)):
            row[index] *= inv
    return row


def _prepare_mirror_skin_change(
    node,
    axis="X",
    positive_to_negative=True,
    normalize=True,
    tolerance=1e-4,
    selected_vertices_only=False,
    association="auto",
    log=None
):
    """Prepare old/new API weight buffers for one mesh without editing Maya."""
    transform = _mesh_transform(node)
    shape = _mesh_shape(transform)
    skin = _skin_cluster(transform)
    if not skin:
        raise SkinIOError("No skinCluster found on '{}'.".format(transform))

    axis = str(axis).upper()
    axis_index = _MIRROR_AXIS_INDEX.get(axis)
    if axis_index is None:
        raise SkinIOError("Invalid mirror axis '{}'. Use X, Y, or Z.".format(axis))

    started = time.perf_counter()
    dag, mesh_fn, points = _mesh_world_points(shape)
    vertex_count = len(points)
    if not vertex_count:
        raise SkinIOError("Mesh has no vertices: {}".format(transform))

    extent = _mesh_point_extent(points)
    pair_tolerance = max(1e-6, float(tolerance) if tolerance is not None else extent * 2e-5)
    center_tolerance = max(1e-6, pair_tolerance * 0.1)

    source_positive = bool(positive_to_negative)
    target_ids = []
    for vertex_id, point in enumerate(points):
        coord = _point_coord(point, axis_index)
        if source_positive:
            if coord < -center_tolerance:
                target_ids.append(vertex_id)
        else:
            if coord > center_tolerance:
                target_ids.append(vertex_id)

    if not target_ids:
        raise SkinIOError(
            "No destination-side vertices found for {} mirror on '{}'.".format(
                axis, transform
            )
        )

    source_lookup, source_ids, inverse_tolerance = _source_vertex_lookup(
        points,
        axis_index,
        source_positive,
        pair_tolerance
    )
    if not source_ids:
        raise SkinIOError(
            "No source-side vertices found for {} mirror on '{}'.".format(
                axis, transform
            )
        )

    skin_fn = _skin_fn(skin)
    influence_paths = skin_fn.influenceObjects()
    influence_names = [path.fullPathName() for path in influence_paths]
    influence_count = len(influence_paths)
    if not influence_count:
        raise SkinIOError("SkinCluster has no influences: {}".format(skin))

    all_components = _mesh_components(vertex_count)
    result = skin_fn.getWeights(dag, all_components)
    source_weights = result[0]
    actual_influence_count = int(result[1])
    if actual_influence_count != influence_count:
        raise SkinIOError(
            "SkinCluster influence count changed while reading weights: {} -> {}.".format(
                influence_count, actual_influence_count
            )
        )

    influence_map = _build_mirror_influence_map(
        influence_paths,
        axis_index,
        association=association,
        log=log
    )

    maintain_max = False
    max_influences = 0
    try:
        maintain_max = bool(cmds.getAttr(skin + ".maintainMaxInfluences"))
        max_influences = int(cmds.getAttr(skin + ".maxInfluences"))
    except Exception:
        pass

    selected_vtx = _selected_vertex_indices(transform) if selected_vertices_only else None

    old_target = array("d")
    new_target = array("d")
    source_for_target = []
    exact_count = 0
    fallback_count = 0
    pair_cache = {}

    for target_id in target_ids:
        target_base = target_id * influence_count
        old_target.extend(
            float(source_weights[target_base + index])
            for index in range(influence_count)
        )

        target_point = points[target_id]
        reflected = _set_reflected_axis(om.MPoint(target_point), axis_index)
        key = (
            int(round(float(reflected.x) * inverse_tolerance)),
            int(round(float(reflected.y) * inverse_tolerance)),
            int(round(float(reflected.z) * inverse_tolerance)),
        )

        cached = pair_cache.get(key)
        if cached is not None:
            source_id = cached
        else:
            exact_candidates = source_lookup.get(key)
            if exact_candidates:
                target_xyz = _point_xyz(reflected)
                source_id = min(
                    exact_candidates,
                    key=lambda vertex_id: _distance_sq(
                        _point_xyz(points[vertex_id]), target_xyz
                    )
                )
                exact_count += 1
            else:
                source_id = _closest_source_vertex(
                    mesh_fn,
                    points,
                    reflected,
                    source_lookup,
                    inverse_tolerance,
                    axis_index,
                    source_positive,
                    center_tolerance
                )
                fallback_count += 1
            pair_cache[key] = source_id

        source_for_target.append(source_id)
        source_base = source_id * influence_count

        # If component-level mirroring is requested, keep original weights unless vertex is selected
        if selected_vtx and (target_id not in selected_vtx) and (source_id not in selected_vtx):
            new_target.extend(
                float(source_weights[target_base + index])
                for index in range(influence_count)
            )
            continue

        row = [0.0] * influence_count
        for source_influence in range(influence_count):
            value = float(source_weights[source_base + source_influence])
            if abs(value) <= EPSILON:
                continue
            target_influence = influence_map[source_influence]
            row[target_influence] += value

        if normalize:
            _trim_and_normalize_row(
                row,
                max_influences if maintain_max else None
            )
        new_target.extend(row)

    old_blend = None
    new_blend = None
    try:
        all_blend = skin_fn.getBlendWeights(dag, all_components)
        old_blend = array("d", (float(all_blend[index]) for index in target_ids))
        new_blend = array("d", (float(all_blend[index]) for index in source_for_target))
    except Exception as exc:
        _log(log, "Blend-weight mirror skipped: {}".format(exc))

    direction = "+{} -> -{}".format(axis, axis)
    if not positive_to_negative:
        direction = "-{} -> +{}".format(axis, axis)

    return {
        "transform": transform,
        "shape": shape,
        "skin": skin,
        "target_ids": target_ids,
        "influence_names": influence_names,
        "influence_count": influence_count,
        "old_weights": old_target,
        "new_weights": new_target,
        "old_blend": old_blend,
        "new_blend": new_blend,
        "direction": direction,
        "axis": axis,
        "exact_count": exact_count,
        "fallback_count": fallback_count,
        "prepare_seconds": time.perf_counter() - started,
    }


def _apply_api_skin_change(change, use_new=True):
    """Apply either side of a prepared, full or partial API skin edit."""
    shape = change["shape"]
    skin = change["skin"]

    if not cmds.objExists(shape):
        raise SkinIOError("Skin mesh no longer exists: {}".format(shape))
    if not cmds.objExists(skin):
        raise SkinIOError("SkinCluster no longer exists: {}".format(skin))

    dag = _dag_path(shape)
    skin_fn = _skin_fn(skin)
    current_influences = [
        path.fullPathName() for path in skin_fn.influenceObjects()
    ]
    if current_influences != change["influence_names"]:
        raise SkinIOError(
            "SkinCluster influences changed after the prepared operation; "
            "cannot safely undo/redo '{}'.".format(_short_name(shape))
        )

    component_fn = om.MFnSingleIndexedComponent()
    target_components = component_fn.create(om.MFn.kMeshVertComponent)
    component_fn.addElements(change["target_ids"])

    influence_indices = om.MIntArray()
    influence_indices.copy(list(range(change["influence_count"])))

    values = change["new_weights"] if use_new else change["old_weights"]
    target_weights = om.MDoubleArray()
    target_weights.copy(values)

    skin_fn.setWeights(
        dag,
        target_components,
        influence_indices,
        target_weights,
        False
    )

    blend_values = change["new_blend"] if use_new else change["old_blend"]
    if blend_values is not None:
        try:
            target_blend = om.MDoubleArray()
            target_blend.copy(blend_values)
            skin_fn.setBlendWeights(dag, target_components, target_blend)
        except Exception:
            # Standard linear skinning may not expose/use blend weights.
            pass


def _apply_api_skin_changes(changes, use_new=True):
    ordered = changes if use_new else list(reversed(changes))
    for change in ordered:
        _apply_api_skin_change(change, use_new=use_new)


def _commit_api_skin_changes(changes):
    """Apply prepared skin edits as one native Maya undo item."""
    if not changes:
        return
    _commit_api_undo_payload(
        redo_callback=lambda: _apply_api_skin_changes(changes, True),
        undo_callback=lambda: _apply_api_skin_changes(changes, False),
    )


# Internal compatibility aliases retained for the mirror UI.
def _apply_mirror_skin_change(change, use_new=True):
    return _apply_api_skin_change(change, use_new=use_new)


def _apply_mirror_skin_changes(changes, use_new=True):
    return _apply_api_skin_changes(changes, use_new=use_new)


def _commit_mirror_skin_changes(changes):
    """Apply a prepared multi-mesh mirror as one native Maya undo item."""
    if not changes:
        return

    _commit_api_skin_changes(changes)


def mirror_skin_weights(
    node=None,
    axis="X",
    positive_to_negative=True,
    normalize=True,
    tolerance=1e-4,
    selected_vertices_only=False,
    association="auto",
    log=None,
    use_undo=True
):
    """
    Mirror one mesh using Maya API 2.0 bulk weights.

    When use_undo=True (default), the entire mirror is registered as one native
    Maya undo item, so Ctrl+Z restores the original weights and Ctrl+Y redoes it.
    """
    if node is None:
        selection = cmds.ls(sl=True, long=True) or []
        if not selection:
            raise SkinIOError("Select a skinned mesh or mesh transform.")
        node = selection[0]

    if use_undo:
        _ensure_api_undo_command()

    change = _prepare_mirror_skin_change(
        node=node,
        axis=axis,
        positive_to_negative=positive_to_negative,
        normalize=normalize,
        tolerance=tolerance,
        selected_vertices_only=selected_vertices_only,
        association=association,
        log=log
    )

    if use_undo:
        _commit_mirror_skin_changes([change])
    else:
        _apply_mirror_skin_change(change, use_new=True)

    _log(
        log,
        "API mirror: {} | {} | {} target verts | exact={} fallback={} | "
        "Ctrl+Z={} | {:.3f}s prepare".format(
            _short_name(change["transform"]),
            change["direction"],
            len(change["target_ids"]),
            change["exact_count"],
            change["fallback_count"],
            "yes" if use_undo else "no",
            change["prepare_seconds"]
        )
    )
    return change["skin"]


def mirror_skin_weights_from_selected(
    axis="X",
    positive_to_negative=True,
    normalize=True,
    tolerance=1e-4,
    selected_vertices_only=False,
    association="auto",
    meshes=None,
    log=None,
    progress=None,
    use_undo=True
):
    """Mirror one or multiple skinned meshes with Maya API 2.0; shares one undo step."""
    if meshes is not None:
        target_list = list(meshes) if isinstance(meshes, (list, tuple, set)) else [meshes]
        mesh_list = [_mesh_transform(m) for m in target_list if m]
    else:
        mesh_list = selected_meshes()

    if not mesh_list:
        raise SkinIOError("Select or load one or more polygon meshes.")

    old_selection = cmds.ls(sl=True, long=True) or []
    results = {}
    changes = []

    if use_undo:
        _ensure_api_undo_command()

    from scartools.framework import SceneTransaction

    with SceneTransaction(
        "ScarTools_MirrorSkinWeights",
        use_undo=use_undo,
        preserve_selection=True,
        suspend_refresh=len(mesh_list) > 1,
        suspend_evaluation=len(mesh_list) > 1,
        log=log,
    ) as transaction:
        total = len(mesh_list)
        for index, mesh in enumerate(mesh_list):
            if not _skin_cluster(mesh):
                _log(log, "SKIP: No skinCluster on {}".format(_short_name(mesh)))
                results[mesh] = None
            else:
                change = _prepare_mirror_skin_change(
                    node=mesh,
                    axis=axis,
                    positive_to_negative=positive_to_negative,
                    normalize=normalize,
                    tolerance=tolerance,
                    selected_vertices_only=selected_vertices_only,
                    association=association,
                    log=log,
                )
                changes.append(change)
                results[mesh] = change["skin"]

            _progress(
                progress,
                int(((index + 1) / float(total)) * 90),
                "Preparing mirror weights..."
            )

        if changes:
            transaction.mark_mutating()
            if use_undo:
                _commit_mirror_skin_changes(changes)
            else:
                _apply_mirror_skin_changes(changes, use_new=True)
            _progress(progress, 100, "Mirror complete.")

    results["meshes"] = [c["transform"] for c in changes]
    results["changes"] = changes
    return results


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _build_skin_weight_data(
    node=None,
    log=None,
    progress=None,
    sparse=True,
    include_metadata=True
):
    """Pack one mesh into a JSON-safe record without writing a file."""
    if node is None:
        selection = cmds.ls(sl=True, long=True) or []
        if not selection:
            raise SkinIOError(
                "Select a skinned mesh or mesh transform."
            )
        node = selection[0]

    transform = _mesh_transform(node)
    shape = _mesh_shape(transform)
    skin = _skin_cluster(transform)

    if not skin:
        raise SkinIOError(
            "No skinCluster found on '{}'.".format(transform)
        )

    _log(log, "Exporting: {}".format(transform))
    _progress(progress, 0, "Reading skin weights...")

    full_influence_paths, flat_weights, vertex_count, influence_count = _api_export_weights(
        skin, shape
    )
    # Stored influences in JSON: short names for cross-hierarchy & reparenting portability
    influences = [_short_name(p) for p in full_influence_paths]

    _log(log, "Vertices: {}".format(vertex_count))
    _log(log, "Influences: {}".format(len(influences)))

    weights = {}
    total = max(1, vertex_count)
    step = max(1, total // 100)

    if sparse:
        for vertex_id in range(vertex_count):
            base = vertex_id * influence_count
            values = {}
            for influence_id in range(influence_count):
                val = flat_weights[base + influence_id]
                if val > EPSILON or val < -EPSILON:
                    values[influences[influence_id]] = round(float(val), 8)
            if values:
                weights[str(vertex_id)] = values
            if vertex_id % step == 0:
                _progress(
                    progress,
                    int((vertex_id / float(total)) * 100),
                    "Packing vertex weights..."
                )
    else:
        for vertex_id in range(vertex_count):
            base = vertex_id * influence_count
            values = {
                influences[influence_id]: round(float(flat_weights[base + influence_id]), 8)
                for influence_id in range(influence_count)
            }
            weights[str(vertex_id)] = values
            if vertex_id % step == 0:
                _progress(
                    progress,
                    int((vertex_id / float(total)) * 100),
                    "Packing vertex weights..."
                )

    influence_data = {}

    for short_name, full_path in zip(influences, full_influence_paths):
        influence_data[short_name] = {
            "worldMatrix": _world_matrix(full_path),
            "radius": _joint_radius(full_path),
        }

    source_scene = _current_scene_metadata()

    data = {
        "format": "SkinWeightsPro",
        "version": VERSION,
        "sourceScene": source_scene,
        "mesh": _short_name(transform),
        "meshPath": transform,
        "skinCluster": _short_name(skin),
        "vertexCount": vertex_count,
        "influences": influences,
        "influenceData": influence_data,
        "weights": weights,
        "settings": {
            "skinningMethod": int(
                cmds.getAttr(skin + ".skinningMethod")
            ),
            "maxInfluences": int(
                cmds.getAttr(skin + ".maxInfluences")
            ),
            "normalizeWeights": int(
                cmds.getAttr(skin + ".normalizeWeights")
            ),
            "maintainMaxInfluences": int(
                cmds.getAttr(skin + ".maintainMaxInfluences")
            ),
        },
    }

    if include_metadata:
        data["meshSignature"] = _mesh_signature(shape)

    _progress(progress, 100, "Mesh packed.")
    return data


def _atomic_write_json(file_path, data):
    folder = os.path.dirname(file_path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)

    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".scartools_skin_", suffix=".tmp", dir=folder or os.getcwd()
    )
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(data, stream, indent=2, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, file_path)
    except Exception:
        try:
            os.remove(temporary_path)
        except Exception:
            pass
        raise


def export_skin_weights(
    file_path=None,
    node=None,
    log=None,
    progress=None,
    sparse=True,
    include_metadata=True
):
    """Export one mesh inside the strict packed ScarTools JSON format.

    The stable function name is retained for reusable scripts, but the file is
    no longer a loose per-mesh record.  It is a one-record skin package that
    uses the same schema as multi-mesh exports.
    """
    if node is None:
        selection = cmds.ls(sl=True, long=True) or []
        if not selection:
            raise SkinIOError("Select a skinned mesh or mesh transform.")
        node = selection[0]

    transform = _mesh_transform(node)
    if not file_path:
        result = cmds.fileDialog2(
            fileMode=0,
            caption="Export Skin Weights",
            fileFilter="JSON Files (*.json)",
            fileName=_safe_filename(transform) + ".json"
        )
        if not result:
            return None
        file_path = result[0]

    file_path = os.path.normpath(file_path)
    if not file_path.lower().endswith(".json"):
        file_path += ".json"

    return export_skin_package(
        file_path=file_path,
        nodes=[transform],
        log=log,
        progress=progress,
        sparse=sparse,
        include_metadata=include_metadata,
    )


def export_skin_package(
    file_path,
    nodes=None,
    log=None,
    progress=None,
    sparse=True,
    include_metadata=True,
):
    """Pack multiple skinned meshes into one atomic, versioned JSON file."""
    _require_saved_scene()
    if nodes is None:
        nodes = selected_meshes()

    transforms = []
    seen = set()
    for node in nodes or []:
        transform = _mesh_transform(node)
        if transform not in seen:
            seen.add(transform)
            transforms.append(transform)

    if not transforms:
        raise SkinIOError("Select one or more polygon meshes.")

    if not file_path:
        raise SkinIOError("Choose a skin package JSON destination.")
    file_path = os.path.normpath(file_path)
    if not file_path.lower().endswith(".json"):
        file_path += ".json"

    source_scene = _current_scene_metadata()
    parent_folder = os.path.basename(os.path.dirname(file_path))
    if _version_number(parent_folder) is not None:
        source_scene["skinVersion"] = parent_folder

    records = []
    skipped = []
    total = len(transforms)
    for index, transform in enumerate(transforms):
        if not _skin_cluster(transform):
            skipped.append(transform)
            _log(log, "SKIP: No skinCluster on {}".format(_short_name(transform)))
            continue

        def mesh_progress(value, message="", _index=index, _transform=transform):
            overall = int(((_index + (int(value) / 100.0)) / float(total)) * 95)
            label = _short_name(_transform)
            detail = "{} — {}".format(label, message) if message else label
            _progress(progress, overall, detail)

        _log(log, "[{}/{}] Packing {}".format(index + 1, total, transform))
        record = _build_skin_weight_data(
            transform,
            log=log,
            progress=mesh_progress,
            sparse=sparse,
            include_metadata=include_metadata,
        )
        record.pop("sourceScene", None)
        records.append(record)

    if not records:
        raise SkinIOError("None of the selected meshes has a skinCluster.")

    package = {
        "format": SKIN_PACKAGE_FORMAT,
        "formatVersion": SKIN_PACKAGE_VERSION,
        "toolVersion": VERSION,
        "sourceScene": source_scene,
        "meshCount": len(records),
        "meshes": records,
    }

    _progress(progress, 97, "Writing packed skin JSON...")
    try:
        _atomic_write_json(file_path, package)
    except Exception as exc:
        raise SkinIOError("Could not write packed skin JSON: {}".format(exc))

    _progress(progress, 100, "Packed skin export complete.")
    _log(log, "Packed {} mesh(es) into one JSON: {}".format(len(records), file_path))
    return file_path


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _load_raw_json(file_path):
    if not file_path:
        raise SkinIOError("Choose a skin-weight JSON file.")
    file_path = os.path.normpath(file_path)
    if not os.path.isfile(file_path):
        raise SkinIOError("File not found: {}".format(file_path))

    try:
        with open(file_path, "r") as stream:
            data = json.load(stream)
    except Exception as exc:
        raise SkinIOError(
            "Could not read JSON:\n{}".format(exc)
        )

    if not isinstance(data, dict):
        raise SkinIOError("Invalid skin-weight file: root must be a JSON object.")

    return data


def _validate_skin_record(data):
    if not isinstance(data, dict):
        raise SkinIOError("Invalid skin-weight mesh record.")

    required = ("influences", "vertexCount", "weights")
    missing = [key for key in required if key not in data]

    if missing:
        raise SkinIOError(
            "Invalid skin-weight file. Missing: {}".format(
                ", ".join(missing)
            )
        )

    if not isinstance(data["influences"], list) or not all(
        isinstance(x, str) and x for x in data["influences"]
    ):
        raise SkinIOError("Invalid skin-weight file: 'influences' must be a list of names.")

    try:
        vertex_count = int(data["vertexCount"])
    except Exception:
        raise SkinIOError("Invalid skin-weight file: 'vertexCount' must be an integer.")
    if vertex_count < 0:
        raise SkinIOError("Invalid skin-weight file: 'vertexCount' cannot be negative.")

    if not isinstance(data["weights"], dict):
        raise SkinIOError("Invalid skin-weight file: 'weights' must be an object.")

    return data


def _is_skin_package(data):
    return data.get("format") == SKIN_PACKAGE_FORMAT


def _validate_skin_package_data(data, file_path):
    if not _is_skin_package(data):
        raise SkinIOError("File is not a packed ScarTools skin package.")

    version = data.get("formatVersion")
    if not isinstance(version, int) or version != SKIN_PACKAGE_VERSION:
        raise SkinIOError("Unsupported packed skin format version: {}".format(version))

    meshes = data.get("meshes")
    if not isinstance(meshes, list) or not meshes:
        raise SkinIOError("Packed skin JSON contains no mesh records.")
    declared_count = data.get("meshCount", len(meshes))
    if not isinstance(declared_count, int) or declared_count != len(meshes):
        raise SkinIOError(
            "Packed skin JSON meshCount does not match its mesh records."
        )

    validated = []
    for record in meshes:
        validated.append(_validate_skin_record(record))

    package = dict(data)
    package["meshes"] = validated
    package["filePath"] = os.path.normpath(file_path)
    return package


def load_skin_package(file_path):
    """Load and validate one packed multi-mesh skin JSON package."""
    return _validate_skin_package_data(_load_raw_json(file_path), file_path)


def _package_record_for_node(package, node):
    transform = _mesh_transform(node)
    target_path = str(transform)
    target_short = _short_name(transform)
    target_base = _strip_namespace(target_short)
    records = package["meshes"]

    exact = [
        record for record in records
        if str(record.get("meshPath") or "") == target_path
        or str(record.get("mesh") or "") == target_short
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise SkinIOError(
            "Packed skin JSON has multiple exact records for '{}'.".format(target_short)
        )

    compatible = [
        record for record in records
        if _strip_namespace(str(record.get("mesh") or "")) == target_base
    ]
    if len(compatible) == 1:
        return compatible[0]
    if not compatible:
        raise SkinIOError(
            "Packed skin JSON has no record for mesh '{}'.".format(target_short)
        )
    raise SkinIOError(
        "Packed skin JSON mesh match is ambiguous for '{}': {} records.".format(
            target_short, len(compatible)
        )
    )


def _load_json(file_path, node=None):
    data = _load_raw_json(file_path)
    if not _is_skin_package(data):
        raise SkinIOError(
            "Legacy per-mesh skin JSON is not supported. Re-export the asset "
            "as one packed skin_weights_package.json with ScarTools 4.8 or newer."
        )
    package = _validate_skin_package_data(data, file_path)
    if node is None:
        if len(package["meshes"]) != 1:
            raise SkinIOError(
                "Packed skin JSON contains multiple meshes; provide a target mesh."
            )
        record = package["meshes"][0]
    else:
        record = _package_record_for_node(package, node)
    data = dict(record)
    data["sourceScene"] = package.get("sourceScene") or {}
    return _validate_skin_record(data)



def _resolve_or_create_influences(
    source_influences,
    influence_data,
    create_missing,
    log
):
    """Resolve influences in the exact order stored in the JSON."""
    scene_joints = cmds.ls(type="joint", long=True) or []
    lookup = _InfluenceLookup(scene_joints)
    resolved = [None] * len(source_influences)
    missing = []

    for index, source in enumerate(source_influences):
        found = lookup.resolve(source)
        if found:
            resolved[index] = found
        else:
            missing.append((index, source))

    if missing and not create_missing:
        raise SkinIOError(
            "Missing influences:\n{}".format(
                "\n".join(source for _index, source in missing)
            )
        )

    created = []
    for index, source in missing:
        joint = _create_joint_from_data(source, influence_data.get(source, {}))
        resolved[index] = joint
        created.append(joint)

    if created:
        _log(log, "Created {} missing joint(s).".format(len(created)))

    return resolved, created



def _build_flat_weight_array(
    data,
    source_influences,
    resolved_influences,
    actual_influences,
    vertex_count,
    normalize=True
):
    """Build one contiguous API weight buffer directly from sparse JSON."""
    if len(resolved_influences) != len(actual_influences):
        raise SkinIOError(
            "Influence count changed while creating skinCluster. "
            "Source: {} Target: {}".format(
                len(resolved_influences), len(actual_influences)
            )
        )

    actual_index = {name: index for index, name in enumerate(actual_influences)}
    actual_lookup = _InfluenceLookup(actual_influences)
    source_to_target = []
    used_targets = set()

    for influence in resolved_influences:
        target = actual_lookup.resolve(influence)
        if target is None:
            raise SkinIOError(
                "Could not map influence '{}' to the new skinCluster.".format(influence)
            )
        target_index = actual_index[target]
        if target_index in used_targets:
            raise SkinIOError("Influence mapping is ambiguous; refusing to apply weights.")
        used_targets.add(target_index)
        source_to_target.append(target_index)

    name_to_target = {}
    for index, name in enumerate(source_influences):
        tgt = source_to_target[index]
        name_to_target[name] = tgt
        name_to_target[_short_name(name)] = tgt
        name_to_target[_strip_namespace(name)] = tgt

    influence_count = len(actual_influences)

    # A single Python list is substantially cheaper than thousands of nested
    # row lists, and MDoubleArray.copy() transfers it in bulk instead of one
    # Python-to-C++ append call per weight value.
    values = [0.0] * (vertex_count * influence_count)

    for vertex_key, sparse_values in data.get("weights", {}).items():
        vertex_id = int(vertex_key)
        if vertex_id < 0 or vertex_id >= vertex_count:
            continue

        parsed = []
        total = 0.0

        for source_name, value in sparse_values.items():
            target_index = name_to_target.get(source_name)
            if target_index is None:
                target_index = name_to_target.get(_short_name(source_name))
            if target_index is None:
                target_index = name_to_target.get(_strip_namespace(source_name))
            if target_index is None:
                continue

            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise SkinIOError(
                    "Invalid non-finite weight at vertex {} / influence '{}'.".format(
                        vertex_id, source_name
                    )
                )
            if numeric_value < -EPSILON:
                raise SkinIOError(
                    "Invalid negative weight at vertex {} / influence '{}'.".format(
                        vertex_id, source_name
                    )
                )

            parsed.append((target_index, numeric_value))
            total += numeric_value

        scale = 1.0
        if normalize and total > EPSILON:
            scale = 1.0 / total

        base = vertex_id * influence_count
        for target_index, numeric_value in parsed:
            values[base + target_index] = numeric_value * scale

    flat = om.MDoubleArray()
    flat.copy(values)
    return flat


def _create_import_skin_cluster(
    resolved_influences,
    transform,
    skin_name,
    skinning_method,
    max_influences
):
    """Create a lightweight skinCluster without calculating useful bind weights."""
    if not resolved_influences:
        raise SkinIOError("Skin-weight file contains no influences.")

    # Binding every joint at once makes Maya calculate initial distance-based
    # weights that are immediately overwritten by the imported data. Bind one
    # influence first, then add the rest at zero weight to avoid most of that
    # wasted work.
    skin = cmds.skinCluster(
        resolved_influences[0],
        transform,
        toSelectedBones=True,
        bindMethod=0,
        skinMethod=skinning_method,
        normalizeWeights=0,
        maximumInfluences=max(1, max_influences),
        obeyMaxInfluences=False,
        name=skin_name
    )[0]

    remaining = list(resolved_influences[1:])
    if remaining:
        try:
            # Maya 2023 documents addInfluence as a multi-use flag, so all
            # joints can be attached with one command instead of N commands.
            cmds.skinCluster(
                skin,
                edit=True,
                addInfluence=remaining,
                weight=0.0
            )
        except Exception:
            # Some custom influence types reject a mixed batch. Continue only
            # with influences the failed command did not already attach.
            current_lookup = _InfluenceLookup(_skin_influence_paths(skin))
            for influence in remaining:
                if current_lookup.resolve(influence) is not None:
                    continue
                cmds.skinCluster(
                    skin,
                    edit=True,
                    addInfluence=influence,
                    weight=0.0
                )

    return skin


# ---------------------------------------------------------------------------
# Skin copy operations
# ---------------------------------------------------------------------------

_COPY_METHODS = {
    "vertexindex": "vertexIndex",
    "vertexorder": "vertexIndex",
    "closestpoint": "closestPoint",
    "uvspace": "uvSpace",
}


def _copy_method(value):
    key = re.sub(r"[^a-z]", "", str(value or "").lower())
    method = _COPY_METHODS.get(key)
    if method is None:
        raise SkinIOError(
            "Unsupported copy method '{}'. Use Vertex Index, Closest Point, "
            "or UV Space.".format(value)
        )
    return method


def _unique_meshes(nodes, source=None):
    result = []
    seen = set()
    source_transform = _mesh_transform(source) if source else None
    for node in nodes or []:
        transform = _mesh_transform(node)
        if transform == source_transform or transform in seen:
            continue
        seen.add(transform)
        result.append(transform)
    return result


def _current_uv_set(shape):
    values = cmds.polyUVSet(shape, query=True, currentUVSet=True) or []
    return values[0] if values else None


def _skin_setting(skin, attribute, default):
    try:
        return cmds.getAttr("{}.{}".format(skin, attribute))
    except Exception:
        return default


def _prepare_index_copy_change(
    source_skin,
    source_shape,
    target_skin,
    target_shape,
    source_data=None,
):
    """Prepare a vertex-index transfer with target influence reordering."""
    source_names, source_weights, source_vertices, source_count = (
        source_data or _api_export_weights(source_skin, source_shape)
    )
    target_names, target_weights, target_vertices, target_count = (
        _api_export_weights(target_skin, target_shape)
    )
    if source_vertices != target_vertices:
        raise SkinIOError(
            "Vertex Index requires matching vertex counts: source {} / target {}.".format(
                source_vertices, target_vertices
            )
        )

    lookup = _InfluenceLookup(target_names)
    target_index = {name: index for index, name in enumerate(target_names)}
    mapping = []
    missing = []
    for source_name in source_names:
        resolved = lookup.resolve(source_name)
        if resolved is None:
            missing.append(_short_name(source_name))
        else:
            mapping.append(target_index[resolved])
    if missing:
        raise SkinIOError(
            "Target skinCluster is missing source influence(s): {}".format(
                ", ".join(missing)
            )
        )

    copied = [0.0] * (target_vertices * target_count)
    for vertex_id in range(source_vertices):
        source_base = vertex_id * source_count
        target_base = vertex_id * target_count
        for source_index, destination_index in enumerate(mapping):
            copied[target_base + destination_index] += float(
                source_weights[source_base + source_index]
            )

    old_blend = None
    new_blend = None
    try:
        source_fn = _skin_fn(source_skin)
        target_fn = _skin_fn(target_skin)
        source_dag = _dag_path(source_shape)
        target_dag = _dag_path(target_shape)
        source_components = _mesh_components(source_vertices)
        target_components = _mesh_components(target_vertices)
        new_blend = array("d", source_fn.getBlendWeights(source_dag, source_components))
        old_blend = array("d", target_fn.getBlendWeights(target_dag, target_components))
    except Exception:
        old_blend = None
        new_blend = None

    return {
        "transform": _mesh_transform(target_shape),
        "shape": target_shape,
        "skin": target_skin,
        "target_ids": list(range(target_vertices)),
        "influence_names": target_names,
        "influence_count": target_count,
        "old_weights": array("d", target_weights),
        "new_weights": array("d", copied),
        "old_blend": old_blend,
        "new_blend": new_blend,
    }


def _copy_weights_command(
    source_skin,
    target_skin,
    source_shape,
    target_shape,
    method,
    normalize=True,
):
    kwargs = {
        "sourceSkin": source_skin,
        "destinationSkin": target_skin,
        "noMirror": True,
        "normalize": bool(normalize),
        "influenceAssociation": ["name", "label", "closestJoint"],
    }
    if method == "uvSpace":
        source_uv = _current_uv_set(source_shape)
        target_uv = _current_uv_set(target_shape)
        if not source_uv or not target_uv:
            raise SkinIOError("UV Space requires a current UV set on both meshes.")
        kwargs["uvSpace"] = (source_uv, target_uv)
    else:
        kwargs["surfaceAssociation"] = "closestPoint"
        kwargs["smooth"] = True
        kwargs["sampleSpace"] = 0
    cmds.copySkinWeights(**kwargs)


_SKINCLUSTER_COPY_ATTRIBUTES = (
    "envelope",
    "skinningMethod",
    "normalizeWeights",
    "maxInfluences",
    "maintainMaxInfluences",
    "weightDistribution",
    "useComponents",
    "deformUserNormals",
    "dqsSupportNonRigid",
    "dqsScale",
    "relativeSpaceMode",
)


def _copy_skin_cluster_settings(source_skin, target_skin, log=None):
    """Copy supported scalar settings and per-influence bind pre-matrices."""
    copied = []
    for attribute in _SKINCLUSTER_COPY_ATTRIBUTES:
        source_plug = "{}.{}".format(source_skin, attribute)
        target_plug = "{}.{}".format(target_skin, attribute)
        try:
            if not cmds.objExists(source_plug) or not cmds.objExists(target_plug):
                continue
            value = cmds.getAttr(source_plug)
            cmds.setAttr(target_plug, value)
            copied.append(attribute)
        except Exception as exc:
            _log(log, "WARNING: Could not copy {}: {}".format(attribute, exc))

    source_influences = _skin_influence_paths(source_skin)
    target_influences = _skin_influence_paths(target_skin)
    target_lookup = _InfluenceLookup(target_influences)
    source_fn = _skin_fn(source_skin)
    target_fn = _skin_fn(target_skin)
    bind_count = 0
    for source_influence in source_influences:
        resolved = target_lookup.resolve(source_influence)
        if resolved is None:
            continue
        try:
            source_index = source_fn.indexForInfluenceObject(
                _dag_path(source_influence)
            )
            target_index = target_fn.indexForInfluenceObject(
                _dag_path(resolved)
            )
            value = cmds.getAttr(
                "{}.bindPreMatrix[{}]".format(source_skin, source_index)
            )
            if isinstance(value, (tuple, list)) and len(value) == 1:
                value = value[0]
            cmds.setAttr(
                "{}.bindPreMatrix[{}]".format(target_skin, target_index),
                *list(value),
                type="matrix"
            )
            bind_count += 1
        except Exception as exc:
            _log(
                log,
                "WARNING: Could not copy bind pre-matrix for {}: {}".format(
                    _short_name(source_influence), exc
                ),
            )
    return {"attributes": copied, "bindPreMatrices": bind_count}


def _copy_skin(source, targets, method, create_cluster, log, progress, use_undo):
    if isinstance(source, (list, tuple, set)):
        source_list = [s for s in source if s]
    elif source:
        source_list = [source]
    else:
        source_list = []

    if not source_list:
        raise SkinIOError("Load at least one source mesh.")

    if isinstance(targets, (list, tuple, set)):
        target_list = [t for t in targets if t]
    elif targets:
        target_list = [targets]
    else:
        target_list = []

    if not target_list:
        raise SkinIOError("Load at least one target mesh different from the source.")

    method = _copy_method(method)

    if len(source_list) > 1:
        if len(source_list) != len(target_list):
            raise SkinIOError(
                "Source count ({}) and Target count ({}) must match.".format(
                    len(source_list), len(target_list)
                )
            )
        raw_pairs = list(zip(source_list, target_list))
    else:
        src = source_list[0]
        src_trans = _mesh_transform(src)
        target_transforms = _unique_meshes(target_list, src_trans)
        if not target_transforms:
            raise SkinIOError("Load at least one target mesh different from the source.")
        raw_pairs = [(src, tgt) for tgt in target_transforms]

    # Validate the complete operation before changing the scene.
    target_data = []
    source_transforms = []
    source_skins = []
    for src_item, tgt_item in raw_pairs:
        src_trans = _mesh_transform(src_item)
        src_shape = _mesh_shape(src_trans)
        src_skin = _skin_cluster(src_trans)
        if not src_skin:
            raise SkinIOError("Source mesh has no skinCluster: {}".format(src_trans))

        if src_trans not in source_transforms:
            source_transforms.append(src_trans)
        if src_skin not in source_skins:
            source_skins.append(src_skin)

        tgt_trans = _mesh_transform(tgt_item)
        shape = _mesh_shape(tgt_trans)
        skin = _skin_cluster(tgt_trans)
        if create_cluster and skin:
            raise SkinIOError(
                "Copy SkinCluster requires an unskinned target: {}".format(tgt_trans)
            )
        if not create_cluster and not skin:
            raise SkinIOError(
                "Copy Skin Weights requires an existing target skinCluster: {}".format(tgt_trans)
            )
        if method == "vertexIndex" and _mesh_vertex_count(shape) != _mesh_vertex_count(src_shape):
            raise SkinIOError(
                "Vertex Index requires matching vertex counts: {}".format(tgt_trans)
            )
        if method == "uvSpace":
            if not _current_uv_set(src_shape) or not _current_uv_set(shape):
                raise SkinIOError(
                    "UV Space requires a current UV set on source and target: {}".format(tgt_trans)
                )
        if skin:
            lookup = _InfluenceLookup(_skin_influence_paths(skin))
            missing = [name for name in _skin_influence_paths(src_skin) if lookup.resolve(name) is None]
            if missing:
                raise SkinIOError(
                    "Target '{}' is missing {} source influence(s).".format(
                        _short_name(tgt_trans), len(missing)
                    )
                )
        target_data.append([src_trans, src_shape, src_skin, tgt_trans, shape, skin])

    from scartools.framework import SceneTransaction

    changes = []
    target_skins = []
    transaction_name = (
        "ScarTools_CopySkinCluster" if create_cluster else "ScarTools_CopySkinWeights"
    )
    with SceneTransaction(
        transaction_name,
        use_undo=use_undo,
        preserve_selection=True,
        suspend_refresh=len(target_data) > 1,
        suspend_evaluation=len(target_data) > 1,
        log=log,
    ) as transaction:
        if use_undo and method == "vertexIndex":
            _ensure_api_undo_command()

        source_weights_cache = {}

        for index, item in enumerate(target_data):
            src_trans, src_shape, src_skin, target, shape, skin = item
            source_influences = _skin_influence_paths(src_skin)

            source_settings = {
                "skinningMethod": int(_skin_setting(src_skin, "skinningMethod", 0)),
                "maxInfluences": int(_skin_setting(src_skin, "maxInfluences", 4)),
                "normalizeWeights": int(_skin_setting(src_skin, "normalizeWeights", 1)),
                "maintainMaxInfluences": bool(
                    _skin_setting(src_skin, "maintainMaxInfluences", False)
                ),
                "weightDistribution": int(
                    _skin_setting(src_skin, "weightDistribution", 0)
                ),
                "useComponents": bool(_skin_setting(src_skin, "useComponents", False)),
            }
            skinning_method = source_settings["skinningMethod"]
            max_influences = source_settings["maxInfluences"]
            normalize_copy = source_settings["normalizeWeights"] != 0

            if method == "vertexIndex":
                if src_skin not in source_weights_cache:
                    source_weights_cache[src_skin] = _api_export_weights(src_skin, src_shape)
                source_weight_data = source_weights_cache[src_skin]
            else:
                source_weight_data = None

            if create_cluster:
                # Mark before Maya is called: creation can partially mutate and
                # then raise, which must still trigger complete rollback.
                transaction.mark_mutating()
                skin = _create_import_skin_cluster(
                    source_influences,
                    target,
                    "{}_skinCluster".format(_strip_namespace(_short_name(target))),
                    skinning_method,
                    max_influences,
                )
                item[5] = skin
            target_skins.append(skin)

            if method == "vertexIndex":
                changes.append(
                    _prepare_index_copy_change(
                        src_skin,
                        src_shape,
                        skin,
                        shape,
                        source_data=source_weight_data,
                    )
                )
            else:
                transaction.mark_mutating()
                _copy_weights_command(
                    src_skin,
                    skin,
                    src_shape,
                    shape,
                    method,
                    normalize=normalize_copy,
                )

            if create_cluster:
                transaction.mark_mutating()
                _copy_skin_cluster_settings(src_skin, skin, log=log)
            _log(log, "COPIED: {} -> {}".format(_short_name(src_trans), _short_name(target)))
            _progress(
                progress,
                int(((index + 1) / float(len(target_data))) * 90),
                "Copying skin to {}...".format(_short_name(target)),
            )

        if changes:
            transaction.mark_mutating()
            if use_undo:
                _commit_api_skin_changes(changes)
            else:
                _apply_api_skin_changes(changes, True)
        _progress(progress, 100, "Skin copy complete.")

    target_transforms = [item[3] for item in target_data]
    return {
        "source": source_transforms[0] if len(source_transforms) == 1 else source_transforms,
        "source_skin": source_skins[0] if len(source_skins) == 1 else source_skins,
        "targets": target_transforms,
        "target_skins": target_skins,
        "method": method,
    }


def copy_skin_weights(
    source, targets, method="closestPoint", log=None, progress=None, use_undo=True
):
    """Copy weights to already-skinned targets without changing their bindings."""
    return _copy_skin(
        source, targets, method, False, log, progress, use_undo
    )


def copy_skin_cluster(
    source, targets, method="vertexIndex", log=None, progress=None, use_undo=True
):
    """Create source-equivalent skinClusters and weights on unskinned targets."""
    return _copy_skin(
        source, targets, method, True, log, progress, use_undo
    )


def unbind_target_skin_clusters(
    targets, delete_history=False, log=None, progress=None, use_undo=True
):
    """Unbind skinCluster(s) from target mesh(es).

    Args:
        targets: One or more target mesh nodes or transforms.
        delete_history (bool): Whether to delete construction history on the mesh.
        log (callable, optional): Custom logger callback.
        progress (callable, optional): Custom progress callback.
        use_undo (bool): Whether to wrap the unbind operation in Maya undo.

    Returns:
        list: List of target meshes successfully unbound.
    """
    if not targets:
        raise SkinIOError("No target meshes specified to unbind.")

    target_list = list(targets) if isinstance(targets, (list, tuple, set)) else [targets]
    target_transforms = [_mesh_transform(t) for t in target_list if t]
    if not target_transforms:
        raise SkinIOError("No valid target meshes found.")

    from scartools.framework import SceneTransaction

    unbound = []
    with SceneTransaction(
        "ScarTools_UnbindSkinCluster",
        use_undo=use_undo,
        preserve_selection=True,
        log=log,
    ) as transaction:
        total = len(target_transforms)
        for idx, target in enumerate(target_transforms):
            skin = _skin_cluster(target)
            if not skin:
                _log(log, "SKIP: {} has no skinCluster.".format(_short_name(target)))
                continue

            transaction.mark_mutating()
            try:
                cmds.skinCluster(skin, edit=True, unbind=True)
            except Exception:
                try:
                    cmds.delete(skin)
                except Exception:
                    pass

            if delete_history:
                try:
                    shape = _mesh_shape(target)
                    cmds.delete(shape, constructionHistory=True)
                except Exception:
                    pass

            unbound.append(target)
            _log(log, "UNBOUND: skinCluster from {}".format(_short_name(target)))
            _progress(
                progress,
                int(((idx + 1) / float(total)) * 100),
                "Unbound {}".format(_short_name(target)),
            )

    return unbound



def import_skin_weights(
    file_path=None,
    node=None,
    force=False,
    create_missing_joints=True,
    log=None,
    progress=None,
    normalize=True,
    use_undo=True,
    validate_topology=True,
    _record_data=None,
):
    """Import one skin-weight JSON onto a target mesh."""
    if node is None:
        selection = cmds.ls(sl=True, long=True) or []
        if not selection:
            raise SkinIOError("Select the target mesh.")
        node = selection[0]

    transform = _mesh_transform(node)
    shape = _mesh_shape(transform)

    if not file_path:
        result = cmds.fileDialog2(
            fileMode=1,
            caption="Import Skin Weights",
            fileFilter="JSON Files (*.json)"
        )
        if not result:
            return None
        file_path = result[0]

    import_started = time.perf_counter()
    stage_started = import_started
    data = (
        _validate_skin_record(dict(_record_data))
        if _record_data is not None
        else _load_json(file_path, node=transform)
    )
    _validate_json_scene_identity(data, file_path)
    _log(log, "JSON loaded in {:.3f}s".format(time.perf_counter() - stage_started))

    source_vertex_count = int(data["vertexCount"])
    target_vertex_count = _mesh_vertex_count(shape)
    existing_skin = _skin_cluster(transform)

    if existing_skin and not force:
        raise SkinIOError(
            "{} already has skinCluster '{}'. Enable Force Rebind.".format(
                transform, existing_skin
            )
        )

    if source_vertex_count != target_vertex_count:
        raise SkinIOError(
            "Vertex count mismatch.\n\nSource: {}\nTarget: {}\n\n"
            "Import was cancelled to prevent incorrect vertex mapping.".format(
                source_vertex_count, target_vertex_count
            )
        )

    source_signature = data.get("meshSignature")
    if validate_topology and source_signature:
        target_signature = _mesh_signature(shape)
        mismatches = [
            "{}: source={} target={}".format(
                key, source_signature[key], target_signature[key]
            )
            for key in ("vertexCount", "edgeCount", "faceCount")
            if key in source_signature
            and int(source_signature[key]) != int(target_signature[key])
        ]
        if (source_signature.get("topologyHash") and target_signature.get("topologyHash")
                and source_signature.get("topologyHash") != target_signature.get("topologyHash")):
            mismatches.append("topologyHash: connectivity mismatch")
        if mismatches:
            raise SkinIOError(
                "Topology signature mismatch.\n\n{}\n\n"
                "Import was cancelled. Disable topology validation only if "
                "you intentionally accept vertex-order/topology risk.".format(
                    "\n".join(mismatches)
                )
            )

    source_influences = data["influences"]
    influence_data = data.get("influenceData", {})
    settings = data.get("settings", {})
    skinning_method = int(settings.get("skinningMethod", 0))
    max_influences = int(settings.get("maxInfluences", 5))
    normalize_weights = int(settings.get("normalizeWeights", 1))
    maintain_max = int(settings.get("maintainMaxInfluences", 0))

    old_selection = cmds.ls(sl=True, long=True) or []
    skin = None
    created_joints = []

    if use_undo:
        cmds.undoInfo(openChunk=True, chunkName="ScarTools_SkinImport")

    try:
        _log(log, "Resolving {} influences...".format(len(source_influences)))
        stage_started = time.perf_counter()
        resolved, created_joints = _resolve_or_create_influences(
            source_influences,
            influence_data,
            create_missing_joints,
            log
        )
        _log(log, "Influences resolved in {:.3f}s".format(
            time.perf_counter() - stage_started
        ))

        if existing_skin:
            _log(log, "Removing existing skinCluster: {}".format(existing_skin))
            cmds.skinCluster(existing_skin, edit=True, unbind=True)

        _progress(progress, 20, "Creating skinCluster...")
        stage_started = time.perf_counter()
        skin = _create_import_skin_cluster(
            resolved,
            transform,
            _short_name(transform) + "_skinCluster",
            skinning_method,
            max_influences
        )
        _log(log, "Created: {} in {:.3f}s".format(
            skin, time.perf_counter() - stage_started
        ))

        actual_influences = [
            path.fullPathName()
            for path in _skin_fn(skin).influenceObjects()
        ]

        _progress(progress, 40, "Building API weight buffer...")
        stage_started = time.perf_counter()
        flat_weights = _build_flat_weight_array(
            data,
            source_influences,
            resolved,
            actual_influences,
            target_vertex_count,
            normalize=normalize
        )
        _log(log, "Weight buffer built in {:.3f}s".format(
            time.perf_counter() - stage_started
        ))

        _progress(progress, 60, "Applying weights with Maya API...")
        stage_started = time.perf_counter()
        try:
            _api_import_weights(
                skin,
                shape,
                flat_weights,
                target_vertex_count,
                len(actual_influences)
            )
            _log(log, "API weights applied in {:.3f}s".format(
                time.perf_counter() - stage_started
            ))
        except Exception as api_error:
            _log(log, "FAST API FAILED; using slow skinPercent fallback.")
            _log(log, "API error: {}".format(api_error))
            step = max(1, target_vertex_count // 100)
            influence_count = len(actual_influences)

            for vertex_id in range(target_vertex_count):
                base = vertex_id * influence_count
                vertex_values = [
                    (actual_influences[index], float(flat_weights[base + index]))
                    for index in range(influence_count)
                    if abs(flat_weights[base + index]) > EPSILON
                ]
                if vertex_values:
                    cmds.skinPercent(
                        skin,
                        "{}.vtx[{}]".format(shape, vertex_id),
                        transformValue=vertex_values
                    )
                if vertex_id % step == 0:
                    _progress(
                        progress,
                        60 + int((vertex_id / float(max(1, target_vertex_count))) * 30),
                        "Slow fallback: applying weights..."
                    )

            _log(log, "Fallback weights applied in {:.3f}s".format(
                time.perf_counter() - stage_started
            ))

        for attr, value in (
            ("normalizeWeights", normalize_weights),
            ("maintainMaxInfluences", maintain_max),
            ("maxInfluences", max_influences),
        ):
            try:
                cmds.setAttr("{}.{}".format(skin, attr), value)
            except Exception:
                pass

        _progress(progress, 100, "Import complete.")
        _log(
            log,
            "Imported {} verts / {} influences in {:.3f}s total.".format(
                target_vertex_count,
                len(resolved),
                time.perf_counter() - import_started
            )
        )
        return skin

    except Exception:
        # Restore the previous scene state when this import was wrapped in a
        # Maya undo transaction.
        if use_undo:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
            try:
                cmds.undo()
            except Exception:
                pass
        # Keep a failed UI import from leaving a newly-created skinCluster or
        # newly-created helper joints behind.
        if skin and cmds.objExists(skin):
            try:
                cmds.skinCluster(skin, edit=True, unbind=True)
            except Exception:
                try:
                    cmds.delete(skin)
                except Exception:
                    pass

        for joint in reversed(created_joints):
            if cmds.objExists(joint):
                try:
                    cmds.delete(joint)
                except Exception:
                    pass
        raise

    finally:
        if old_selection:
            try:
                cmds.select(old_selection, replace=True)
            except Exception:
                pass
        if use_undo:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass


def import_skin_package(
    file_path,
    nodes=None,
    force=False,
    create_missing_joints=True,
    log=None,
    progress=None,
    normalize=True,
    use_undo=True,
    validate_topology=True,
):
    """Preflight and import a packed multi-mesh package as one undo step.

    The package is parsed once, every mesh match and topology is validated
    before scene mutation, and a runtime failure rolls the whole operation
    back when Maya undo is enabled.
    """
    package = load_skin_package(file_path)
    identity_data = {"sourceScene": package.get("sourceScene") or {}}
    _validate_json_scene_identity(identity_data, file_path)
    targets = selected_meshes() if nodes is None else nodes
    transforms = []
    seen = set()
    for node in targets or []:
        transform = _mesh_transform(node)
        if transform not in seen:
            seen.add(transform)
            transforms.append(transform)
    if not transforms:
        raise SkinIOError("Select one or more target meshes.")

    jobs = []
    problems = []
    for transform in transforms:
        try:
            record = dict(_package_record_for_node(package, transform))
            record["sourceScene"] = package.get("sourceScene") or {}
            shape = _mesh_shape(transform)
            if _skin_cluster(transform) and not force:
                raise SkinIOError("{} already has a skinCluster.".format(transform))
            source_count = int(record["vertexCount"])
            target_count = _mesh_vertex_count(shape)
            if source_count != target_count:
                raise SkinIOError(
                    "{} vertex count mismatch (source {}, target {}).".format(
                        _short_name(transform), source_count, target_count
                    )
                )
            signature = record.get("meshSignature")
            if validate_topology and signature:
                target_signature = _mesh_signature(shape)
                mismatches = [
                    key for key in ("vertexCount", "edgeCount", "faceCount")
                    if key in signature
                    and int(signature[key]) != int(target_signature[key])
                ]
                if mismatches:
                    raise SkinIOError(
                        "{} topology mismatch: {}.".format(
                            _short_name(transform), ", ".join(mismatches)
                        )
                    )
            jobs.append((transform, record))
        except Exception as exc:
            problems.append("{}: {}".format(_short_name(transform), exc))

    if problems:
        raise SkinIOError(
            "Packed skin preflight failed; no scene changes were made:\n{}"
            .format("\n".join(problems))
        )

    old_selection = cmds.ls(sl=True, long=True) or []
    skins = []
    failed = None
    if use_undo:
        cmds.undoInfo(openChunk=True, chunkName="SkinTools_PackageImport")
    try:
        total = len(jobs)
        for index, (transform, record) in enumerate(jobs):
            def mesh_progress(value, message="", _index=index):
                overall = int(((_index + (int(value) / 100.0)) / float(total)) * 100)
                _progress(progress, overall, message)

            _log(log, "[{}/{}] Importing {}".format(
                index + 1, total, _short_name(transform)
            ))
            skins.append(import_skin_weights(
                file_path=file_path,
                node=transform,
                force=force,
                create_missing_joints=create_missing_joints,
                log=log,
                progress=mesh_progress,
                normalize=normalize,
                use_undo=False,
                validate_topology=validate_topology,
                _record_data=record,
            ))
    except Exception as exc:
        failed = exc
    finally:
        if use_undo:
            cmds.undoInfo(closeChunk=True)
        try:
            if old_selection:
                cmds.select(old_selection, replace=True)
            else:
                cmds.select(clear=True)
        except Exception:
            pass

    if failed is not None:
        if use_undo:
            try:
                cmds.undo()
                _log(log, "Import failed; the complete package was rolled back.")
            except Exception as rollback_error:
                _log(log, "WARNING: Automatic rollback failed: {}".format(rollback_error))
        raise failed

    _progress(progress, 100, "Packed skin import complete.")
    return {"skins": skins, "meshes": transforms, "package": file_path}


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------


def selected_meshes():
    """Return unique selected polygon-mesh transforms in selection order."""
    result = []
    seen = set()

    for item in cmds.ls(sl=True, long=True) or []:
        try:
            transform = _mesh_transform(item)
        except Exception:
            continue
        if transform not in seen:
            seen.add(transform)
            result.append(transform)

    return result


def batch_export(directory, log=None, progress=None):
    """
    Export all selected meshes into one new scene snapshot package:
    ``directory/<asset>/v###/skin_weights_package.json``.
    """
    meshes = selected_meshes()

    if not meshes:
        raise SkinIOError(
            "Select one or more polygon meshes."
        )

    _require_saved_scene()
    scene_folder = _current_scene_folder_name()
    scene_dir = _scene_directory(directory, create=True)
    export_dir, version_name = _next_version_directory(scene_dir, create=True)

    _log(log, "Scene folder: {}".format(scene_folder))
    _log(log, "Export version: {}".format(version_name))

    path = os.path.join(export_dir, SKIN_PACKAGE_FILENAME)
    try:
        output = export_skin_package(
            path,
            meshes,
            log=log,
            progress=progress,
        )
    except Exception:
        try:
            if os.path.isdir(export_dir) and not os.listdir(export_dir):
                os.rmdir(export_dir)
        except Exception:
            pass
        raise
    return [output]


def batch_import(directory, force=False, create_missing_joints=True,
                 log=None, progress=None, normalize=True,
                 validate_topology=True):
    """
    Import selected meshes from the newest packed v### snapshot under the
    current stable asset directory.
    """
    meshes = selected_meshes()

    if not meshes:
        raise SkinIOError(
            "Select one or more target meshes."
        )

    if not os.path.isdir(directory):
        raise SkinIOError(
            "Directory does not exist: {}".format(directory)
        )

    _require_saved_scene()
    scene_dir = _scene_directory(directory, create=False)

    if not os.path.isdir(scene_dir):
        raise SkinIOError(
            "No skin-weight folder found for current Maya scene: {}".format(
                scene_dir
            )
        )

    import_dir, version_name = _import_directory_for_scene(scene_dir)
    if not import_dir:
        raise SkinIOError(
            "No versioned skin-weight data found for current Maya scene: {}".format(
                scene_dir
            )
        )

    _log(log, "Import version: {}".format(version_name))

    package_path = os.path.join(import_dir, SKIN_PACKAGE_FILENAME)

    if not os.path.isfile(package_path):
        raise SkinIOError(
            "Packed skin package not found: {}\nLegacy per-mesh JSON files are "
            "not supported in ScarTools 4.8+.".format(package_path)
        )

    result = import_skin_package(
        package_path,
        nodes=meshes,
        force=force,
        create_missing_joints=create_missing_joints,
        normalize=normalize,
        validate_topology=validate_topology,
        use_undo=True,
        log=log,
        progress=progress,
    )
    return result["skins"]
