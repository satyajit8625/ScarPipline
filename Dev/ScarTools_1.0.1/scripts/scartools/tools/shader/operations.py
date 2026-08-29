"""UI-independent Maya shader package export/import services.

The public functions in this module can be used from Maya UI tools, shelves,
batch jobs, and maya.standalone without importing Qt.
"""

from __future__ import print_function

import json
import os
import re
import shutil
import tempfile
import time
from contextlib import contextmanager

import maya.cmds as cmds

from scartools.framework.snapshots import (
    SnapshotError,
    asset_directory,
    current_scene_metadata,
    require_saved_scene,
    reserve_next_version,
    resolve_import_version,
    validate_scene_identity,
)

from scartools.version import VERSION


FORMAT_NAME = "ScarToolsShaderPackage"
FORMAT_VERSION = 2
SHADER_PACKAGE_BASENAME = "shader_package"
SHADER_PACKAGE_FILENAME = SHADER_PACKAGE_BASENAME + ".json"
ALL_FACES = "__all__"
_INVALID_FILENAME_CHARS = '<>:"/\\|?*'
_FACE_COMPONENT_RE = re.compile(r"^f\[\d+(?::\d+)?\]$")


class ShaderToolsError(Exception):
    """Fatal shader package validation or Maya operation error."""


def _log(callback, message):
    if callback:
        callback(str(message))


def _progress(callback, value, message=""):
    if callback:
        try:
            callback(int(value), str(message))
        except TypeError:
            callback(int(value))


def _short_name(node):
    return str(node).split("|")[-1]


def _base_name(node):
    return _short_name(node).split(":")[-1]


def sanitize_base_name(value, default="shaders_export"):
    """Return a portable filename stem with accidental extensions removed."""
    name = os.path.basename(str(value or "").strip())
    for extension in (".json", ".ma"):
        if name.lower().endswith(extension):
            name = name[:-len(extension)]
            break
    for character in _INVALID_FILENAME_CHARS:
        name = name.replace(character, "_")
    name = name.strip(" .")
    return name or default


@contextmanager
def _preserve_selection():
    selection = cmds.ls(selection=True, long=True) or []
    try:
        yield
    finally:
        try:
            if selection:
                cmds.select(selection, replace=True)
            else:
                cmds.select(clear=True)
        except Exception:
            pass


def _mesh_transform(node):
    if not node or not cmds.objExists(node):
        return None
    node_type = cmds.nodeType(node)
    if node_type == "mesh":
        parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
        return parents[0] if parents else None
    shapes = cmds.listRelatives(
        node, shapes=True, noIntermediate=True, fullPath=True
    ) or []
    if any(cmds.nodeType(shape) == "mesh" for shape in shapes):
        matches = cmds.ls(node, long=True) or [node]
        return matches[0]
    return None


def mesh_transforms(nodes=None):
    """Normalize arbitrary Maya nodes to unique polygon mesh transforms."""
    if nodes is None:
        nodes = cmds.ls(selection=True, long=True) or []
    result = []
    seen = set()
    for node in nodes:
        transform = _mesh_transform(node)
        if transform and transform not in seen:
            seen.add(transform)
            result.append(transform)
    return result


def all_mesh_transforms():
    shapes = cmds.ls(type="mesh", long=True, noIntermediate=True) or []
    return mesh_transforms(shapes)


def _node_aliases(node):
    aliases = {str(node), _short_name(node)}
    matches = cmds.ls(node, long=True) or []
    aliases.update(matches)
    aliases.update(_short_name(match) for match in matches)
    return aliases


def _surface_material(shading_engine):
    materials = cmds.listConnections(
        shading_engine + ".surfaceShader",
        source=True,
        destination=False,
    ) or []
    return materials[0] if materials else None


def _collect_object_assignments(transform, sg_members_cache=None):
    record = {
        "source_path": transform,
        "short_name": _short_name(transform),
        "base_name": _base_name(transform),
        "materials": {},
    }
    shapes = cmds.listRelatives(
        transform, shapes=True, noIntermediate=True, fullPath=True
    ) or []
    transform_aliases = _node_aliases(transform)

    for shape in shapes:
        shape_aliases = _node_aliases(shape)
        accepted_bases = transform_aliases | shape_aliases
        shading_engines = cmds.listSets(
            object=shape, type=1, extendToShape=True
        ) or []
        for shading_engine in shading_engines:
            material = _surface_material(shading_engine)
            if not material:
                continue

            whole_object = False
            faces = []
            if sg_members_cache is not None:
                if shading_engine not in sg_members_cache:
                    sg_members_cache[shading_engine] = (
                        cmds.sets(shading_engine, query=True) or []
                    )
                members = sg_members_cache[shading_engine]
            else:
                members = cmds.sets(shading_engine, query=True) or []
            for member in members:
                base, separator, component = str(member).partition(".")
                if base not in accepted_bases:
                    continue
                if not separator:
                    whole_object = True
                    break
                if _FACE_COMPONENT_RE.match(component):
                    faces.append(component)

            current = record["materials"].get(material, [])
            if whole_object:
                record["materials"][material] = [ALL_FACES]
            elif faces and current != [ALL_FACES]:
                record["materials"][material] = sorted(
                    set(current).union(faces)
                )

    return record


def collect_shader_assignments(objects):
    """Collect normalized assignment records without changing scene state."""
    transforms = mesh_transforms(objects)
    if not transforms:
        raise ShaderToolsError("No polygon mesh transforms were provided.")

    records = []
    materials = set()
    sg_members_cache = {}
    for transform in transforms:
        record = _collect_object_assignments(
            transform, sg_members_cache=sg_members_cache
        )
        records.append(record)
        materials.update(record["materials"])

    if not materials:
        raise ShaderToolsError("No assigned surface shaders were found.")
    return records, sorted(materials)


def _atomic_write_json(path, data):
    folder = os.path.dirname(path)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".scartools_shader_", suffix=".tmp", dir=folder
    )
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(data, stream, indent=2, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.remove(temporary_path)
        except Exception:
            pass
        raise


def inspect_texture_paths(objects=None):
    """Scan materials for file texture nodes and check for missing on-disk images."""
    if objects:
        _, materials = collect_shader_assignments(objects)
    else:
        materials = cmds.ls(materials=True) or []

    file_nodes = set()
    mat_for_file = {}
    for mat in materials:
        history = cmds.listHistory(mat) or []
        for node in history:
            if cmds.nodeType(node) == "file":
                file_nodes.add(node)
                mat_for_file[node] = mat

    valid = []
    missing = []

    for node in sorted(file_nodes):
        raw_path = ""
        try:
            raw_path = cmds.getAttr(node + ".fileTextureName") or ""
        except Exception:
            pass

        if not raw_path:
            missing.append({
                "node": node,
                "path": "",
                "material": mat_for_file.get(node, ""),
                "reason": "Empty texture path",
            })
            continue

        expanded = os.path.expandvars(os.path.expanduser(raw_path))
        is_udim = any(
            tag in expanded
            for tag in ("<UDIM>", "<udim>", "<tile>", "<TILE>", "<UVTILE>")
        )
        if is_udim:
            udim_test = (
                expanded.replace("<UDIM>", "1001")
                .replace("<udim>", "1001")
                .replace("<tile>", "1001")
                .replace("<TILE>", "1001")
                .replace("<UVTILE>", "u1_v1")
            )
            exists = os.path.isfile(udim_test)
        else:
            exists = os.path.isfile(expanded)

        record = {
            "node": node,
            "path": raw_path,
            "resolved_path": expanded,
            "material": mat_for_file.get(node, ""),
            "is_udim": is_udim,
        }
        if exists:
            valid.append(record)
        else:
            record["reason"] = "File not found on disk"
            missing.append(record)

    return {
        "total_textures": len(file_nodes),
        "valid_count": len(valid),
        "missing_count": len(missing),
        "valid_textures": valid,
        "missing_textures": missing,
        "all_valid": len(missing) == 0,
    }


def export_shader_package(
    objects,
    output_directory,
    base_name="shaders_export",
    variant="default",
    log=None,
    progress=None,
):
    """Export shader networks and versioned object/face assignment metadata."""
    from scartools.licensing import require_license
    require_license("Shader Package Export")

    started = time.perf_counter()
    try:
        require_saved_scene()

    except SnapshotError as exc:
        raise ShaderToolsError(str(exc))
    if not output_directory:
        raise ShaderToolsError("Choose an output directory.")
    output_directory = os.path.abspath(os.path.normpath(output_directory))
    if not os.path.isdir(output_directory):
        os.makedirs(output_directory)

    base_name = sanitize_base_name(base_name)
    variant_name = sanitize_base_name(variant or "default")
    maya_path = os.path.join(output_directory, base_name + ".ma")
    json_path = os.path.join(output_directory, base_name + ".json")

    _progress(progress, 5, "Collecting shader assignments...")
    records, materials = collect_shader_assignments(objects)
    _log(log, "Collected {} material(s) from {} object(s) [variant: {}].".format(
        len(materials), len(records), variant_name
    ))

    _progress(progress, 35, "Exporting Maya shader networks...")
    descriptor, staged_maya_path = tempfile.mkstemp(
        prefix="tmp_shader_export_", suffix=".ma", dir=output_directory
    )
    os.close(descriptor)
    if os.path.exists(staged_maya_path):
        try:
            os.remove(staged_maya_path)
        except Exception:
            pass

    export_path = os.path.normpath(staged_maya_path).replace("\\", "/")

    try:
        with _preserve_selection():
            export_nodes = set(materials)
            for mat in materials:
                if not cmds.objExists(mat):
                    continue
                sgs = cmds.listConnections(mat, type="shadingEngine") or []
                export_nodes.update(sgs)
                history = cmds.listHistory(mat, pruneDagObjects=True) or []
                export_nodes.update(history)
                for sg in sgs:
                    sg_hist = cmds.listHistory(sg, pruneDagObjects=True) or []
                    export_nodes.update(sg_hist)

            valid_export_nodes = [
                n for n in export_nodes
                if cmds.objExists(n) and not cmds.nodeType(n) in (
                    "time", "defaultLightSet", "defaultObjectSet", "renderGlobalsList"
                )
            ]
            if not valid_export_nodes:
                valid_export_nodes = list(materials)

            cmds.select(valid_export_nodes, replace=True)
            try:
                cmds.file(
                    export_path,
                    exportSelected=True,
                    type="mayaAscii",
                    constructionHistory=True,
                    channels=True,
                    expressions=True,
                    constraints=False,
                    shader=True,
                    force=True,
                )
            except Exception:
                cmds.file(
                    export_path,
                    exportSelected=True,
                    type="mayaAscii",
                    constructionHistory=True,
                    force=True,
                )

        if not os.path.isfile(staged_maya_path) or os.path.getsize(staged_maya_path) == 0:
            raise RuntimeError("Maya did not produce a shader network file.")
    except Exception as exc:
        try:
            if os.path.exists(staged_maya_path):
                os.remove(staged_maya_path)
        except Exception:
            pass
        raise ShaderToolsError("Could not export Maya shader file: {}".format(exc))



    package = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "tool_version": VERSION,
        "maya_version": str(cmds.about(version=True)),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sourceScene": current_scene_metadata(),
        "ma_file": os.path.basename(maya_path),
        "variant": variant_name,
        "variants": {variant_name: records},
        "object_count": len(records),
        "material_count": len(materials),
        "objects": records,
    }
    _progress(progress, 75, "Writing assignment metadata...")
    backup_maya_path = staged_maya_path + ".previous"
    had_previous_maya = os.path.isfile(maya_path)
    committed = False
    try:
        if had_previous_maya:
            os.replace(maya_path, backup_maya_path)
        os.replace(staged_maya_path, maya_path)
        _atomic_write_json(json_path, package)
        committed = True
    except Exception as exc:
        try:
            if os.path.isfile(maya_path):
                os.remove(maya_path)
            if had_previous_maya and os.path.isfile(backup_maya_path):
                os.replace(backup_maya_path, maya_path)
            if os.path.isfile(staged_maya_path):
                os.remove(staged_maya_path)
        except Exception:
            pass
        raise ShaderToolsError("Could not finalize shader package: {}".format(exc))
    finally:
        try:
            if committed and os.path.isfile(backup_maya_path):
                os.remove(backup_maya_path)
        except Exception:
            pass

    elapsed = time.perf_counter() - started
    _progress(progress, 100, "Export complete.")
    _log(log, "Shader package exported in {:.3f}s.".format(elapsed))
    return {
        "maya_file": maya_path,
        "json_file": json_path,
        "objects": len(records),
        "materials": len(materials),
        "elapsed_seconds": elapsed,
    }


def export_shader_snapshot(
    objects,
    root_directory,
    variant="default",
    log=None,
    progress=None,
):
    """Export one atomic ``<root>/<asset>/v###`` shader snapshot."""
    try:
        require_saved_scene()
        asset_dir = asset_directory(root_directory, create=True)
        version_dir, version_name = reserve_next_version(asset_dir)
    except SnapshotError as exc:
        raise ShaderToolsError(str(exc))
    try:
        result = export_shader_package(
            objects,
            version_dir,
            base_name=SHADER_PACKAGE_BASENAME,
            variant=variant,
            log=log,
            progress=progress,
        )
    except Exception:
        # A failed operation must not leave an empty version in the sequence.
        try:
            if os.path.isdir(version_dir) and not os.listdir(version_dir):
                os.rmdir(version_dir)
        except Exception:
            pass
        raise
    result.update({"version": version_name, "directory": version_dir})
    return result


def resolve_shader_snapshot(root_directory, requested_directory=None):
    """Resolve and validate the current asset's explicit/latest shader JSON."""
    try:
        require_saved_scene()
        asset_dir = asset_directory(root_directory, create=False)
        version_dir, version_name = resolve_import_version(
            asset_dir, requested_directory=requested_directory
        )
    except SnapshotError as exc:
        raise ShaderToolsError(str(exc))
    if not version_dir:
        raise ShaderToolsError(
            "No versioned shader snapshots were found for the current asset: {}"
            .format(asset_dir)
        )
    json_path = os.path.join(version_dir, SHADER_PACKAGE_FILENAME)
    if not os.path.isfile(json_path):
        raise ShaderToolsError("Shader package not found: {}".format(json_path))
    return json_path, version_name


def _normalize_legacy_package(data):
    face_map = data.get("face_map")
    if not isinstance(face_map, dict):
        raise ShaderToolsError("Invalid legacy package: face_map is missing.")
    objects = []
    for object_name, materials in face_map.items():
        objects.append({
            "source_path": object_name,
            "short_name": object_name,
            "base_name": _base_name(object_name),
            "materials": materials,
        })
    return {
        "format": FORMAT_NAME,
        "format_version": 1,
        "tool_version": "legacy",
        "ma_file": data.get("ma_file", "shaders_export.ma"),
        "objects": objects,
    }


def load_shader_package(json_path):
    """Read, normalize, and validate v1 or v2 shader package metadata."""
    if not json_path:
        raise ShaderToolsError("Choose a shader package JSON file.")
    json_path = os.path.abspath(os.path.normpath(json_path))
    if not os.path.isfile(json_path):
        raise ShaderToolsError("Shader package JSON was not found: {}".format(json_path))
    try:
        with open(json_path, "r") as stream:
            data = json.load(stream)
    except Exception as exc:
        raise ShaderToolsError("Could not read shader package JSON: {}".format(exc))
    if not isinstance(data, dict):
        raise ShaderToolsError("Invalid shader package: root must be an object.")
    if "face_map" in data and "objects" not in data:
        data = _normalize_legacy_package(data)

    format_name = data.get("format")
    if format_name not in (None, FORMAT_NAME):
        raise ShaderToolsError(
            "Unsupported shader package format: {}".format(format_name)
        )
    format_version = data.get("format_version", 1)
    if not isinstance(format_version, int) or not 1 <= format_version <= FORMAT_VERSION:
        raise ShaderToolsError(
            "Unsupported shader package version: {}".format(format_version)
        )

    maya_file = data.get("ma_file")
    if (
        not isinstance(maya_file, str)
        or not maya_file.lower().endswith(".ma")
        or os.path.basename(maya_file) != maya_file
    ):
        raise ShaderToolsError("Invalid package ma_file; only a local .ma filename is allowed.")

    objects = data.get("objects")
    if not isinstance(objects, list) or not objects:
        raise ShaderToolsError("Invalid shader package: objects list is empty.")

    normalized_objects = []
    for record in objects:
        if not isinstance(record, dict):
            raise ShaderToolsError("Invalid shader package object record.")
        materials = record.get("materials")
        if not isinstance(materials, dict):
            raise ShaderToolsError("Invalid material assignment map.")
        normalized_materials = {}
        for material, faces in materials.items():
            if not isinstance(material, str) or not material:
                raise ShaderToolsError("Invalid material name in shader package.")
            if not isinstance(faces, list) or not all(isinstance(x, str) for x in faces):
                raise ShaderToolsError("Invalid face list for material '{}'".format(material))
            if faces == [ALL_FACES]:
                normalized_materials[material] = faces
                continue
            invalid = [face for face in faces if not _FACE_COMPONENT_RE.match(face)]
            if invalid:
                raise ShaderToolsError(
                    "Invalid face component '{}' for material '{}'.".format(
                        invalid[0], material
                    )
                )
            normalized_materials[material] = sorted(set(faces))

        source_path = str(record.get("source_path") or record.get("short_name") or "")
        short_name = str(record.get("short_name") or _short_name(source_path))
        normalized_objects.append({
            "source_path": source_path,
            "short_name": short_name,
            "base_name": str(record.get("base_name") or _base_name(short_name)),
            "materials": normalized_materials,
        })

    normalized = dict(data)
    normalized["objects"] = normalized_objects
    normalized["json_path"] = json_path
    normalized["maya_path"] = os.path.join(os.path.dirname(json_path), maya_file)
    return normalized


def _validate_package_scene(package):
    """Apply stable asset-family validation when package metadata provides it."""
    source_scene = package.get("sourceScene") or {}
    if source_scene:
        validate_scene_identity(source_scene, error_type=ShaderToolsError)


def _unique(values):
    result = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _resolve_target(record):
    source_path = record["source_path"]
    if source_path and cmds.objExists(source_path):
        target = _mesh_transform(source_path)
        if target:
            return target, None

    candidates = []
    short_name = record["short_name"]
    base_name = record["base_name"]
    for pattern in (short_name, base_name, "*:" + base_name):
        candidates.extend(cmds.ls(pattern, long=True) or [])
    targets = _unique(_mesh_transform(candidate) for candidate in candidates)
    if len(targets) == 1:
        return targets[0], None
    if not targets:
        return None, "Object not found: {}".format(short_name)
    return None, "Ambiguous object name '{}': {} matches.".format(
        short_name, len(targets)
    )


def _resolve_material(source_name, scene_materials):
    if source_name in scene_materials:
        return source_name
    source_base = _base_name(source_name)
    matches = [name for name in scene_materials if _base_name(name) == source_base]
    return matches[0] if len(matches) == 1 else None


def _shading_engine_name(material):
    name = _short_name(material)
    for suffix in ("_SHD", "_MTL", "_MAT", "_shd", "_mtl", "_mat"):
        if name.endswith(suffix):
            return name[:-len(suffix)] + "_SG"
    return name + "_SG"


def _get_or_create_shading_engine(material):
    connections = []
    try:
        if cmds.attributeQuery("outColor", node=material, exists=True):
            connections = cmds.listConnections(
                material + ".outColor", type="shadingEngine"
            ) or []
    except Exception:
        connections = []
    if not connections:
        try:
            connections = cmds.listConnections(
                material, source=False, destination=True, type="shadingEngine"
            ) or []
        except Exception:
            connections = []
    if connections:
        return connections[0]
    shading_engine = cmds.sets(
        renderable=True,
        noSurfaceShader=True,
        empty=True,
        name=_shading_engine_name(material),
    )
    try:
        if cmds.attributeQuery("outColor", node=material, exists=True):
            cmds.connectAttr(
                material + ".outColor",
                shading_engine + ".surfaceShader",
                force=True,
            )
        else:
            cmds.defaultNavigation(
                connectToExisting=True,
                source=material,
                destination=shading_engine + ".surfaceShader",
                force=True,
            )
    except Exception:
        pass
    return shading_engine


def inspect_shader_package(json_path):
    """Return a read-only scene/package comparison for UI or batch validation."""
    package = load_shader_package(json_path)
    _validate_package_scene(package)
    materials = sorted({
        material
        for record in package["objects"]
        for material in record["materials"]
    })
    scene_materials = set(cmds.ls(materials=True) or [])
    object_rows = []
    for record in package["objects"]:
        target, warning = _resolve_target(record)
        object_rows.append({
            "source": record["short_name"],
            "target": target,
            "status": "found" if target else "missing",
            "warning": warning,
        })
    material_rows = []
    for material in materials:
        target = _resolve_material(material, scene_materials)
        material_rows.append({
            "source": material,
            "target": target,
            "status": "reuse" if target else "import",
        })
    return {
        "package": package,
        "materials": material_rows,
        "objects": object_rows,
        "maya_file_exists": os.path.isfile(package["maya_path"]),
    }


def import_shader_package(
    json_path,
    reuse_existing=True,
    variant=None,
    log=None,
    progress=None,
    use_undo=True,
):
    """Import a shader package and apply its assignments safely."""
    started = time.perf_counter()
    package = load_shader_package(json_path)
    _validate_package_scene(package)

    target_objects = package["objects"]
    if variant:
        variant_key = sanitize_base_name(variant)
        variants = package.get("variants") or {}
        if variant_key in variants:
            target_objects = variants[variant_key]
        else:
            _log(log, "Variant '{}' not found; using default assignments.".format(variant))

    source_materials = sorted({
        material
        for record in target_objects
        for material in record["materials"]
    })
    before_materials = set(cmds.ls(materials=True) or [])
    missing = [
        material for material in source_materials
        if _resolve_material(material, before_materials) is None
    ]

    should_import = bool(missing) or not reuse_existing
    warnings = []
    assignments = 0
    imported_nodes = []
    _progress(progress, 10, "Validating shader package...")

    from scartools.framework import SceneTransaction

    with SceneTransaction(
        "ScarTools_ShaderImport",
        use_undo=use_undo,
        preserve_selection=True,
        suspend_refresh=True,
        log=log,
    ) as transaction:
        if should_import:
            if not os.path.isfile(package["maya_path"]):
                raise ShaderToolsError(
                    "Shader Maya file was not found: {}".format(package["maya_path"])
                )
            _progress(progress, 25, "Importing Maya shader networks...")
            try:
                transaction.mark_mutating()
                imported_nodes = cmds.file(
                    package["maya_path"].replace("\\", "/"),
                    i=True,
                    type="mayaAscii",
                    ignoreVersion=True,
                    mergeNamespacesOnClash=True,
                    namespace=":",
                    preserveReferences=False,
                    importFrameRate=False,
                    importTimeRange="keep",
                    returnNewNodes=True,
                ) or []
            except Exception as exc:
                raise ShaderToolsError("Shader network import failed: {}".format(exc))
            _log(log, "Imported {} Maya node(s).".format(len(imported_nodes)))
        else:
            _log(log, "All package materials already exist; Maya import skipped.")

        scene_materials = set(cmds.ls(materials=True) or [])
        material_map = {
            source: _resolve_material(source, scene_materials)
            for source in source_materials
        }

        total = max(1, len(target_objects))
        for index, record in enumerate(target_objects):
            _progress(
                progress,
                40 + int((index / float(total)) * 55),
                "Applying assignments to {}...".format(record["short_name"]),
            )
            target, target_warning = _resolve_target(record)
            if not target:
                warnings.append(target_warning)
                continue

            for source_material, faces in record["materials"].items():
                material = material_map.get(source_material)
                if not material:
                    warnings.append(
                        "Material unavailable after import: {}".format(source_material)
                    )
                    continue
                transaction.mark_mutating()
                shading_engine = _get_or_create_shading_engine(material)
                try:
                    transaction.mark_mutating()
                    if faces == [ALL_FACES]:
                        cmds.sets(target, edit=True, forceElement=shading_engine)
                    else:
                        components = ["{}.{}".format(target, face) for face in faces]
                        cmds.sets(components, edit=True, forceElement=shading_engine)
                    assignments += 1
                except Exception as exc:
                    warnings.append(
                        "Could not assign {} to {}: {}".format(
                            source_material, record["short_name"], exc
                        )
                    )

    elapsed = time.perf_counter() - started
    _progress(progress, 100, "Import complete.")
    _log(log, "Applied {} assignment(s) in {:.3f}s.".format(assignments, elapsed))
    return {
        "assignments": assignments,
        "warnings": warnings,
        "imported_nodes": len(imported_nodes),
        "reused_materials": len(source_materials) - len(missing),
        "requested_materials": len(source_materials),
        "elapsed_seconds": elapsed,
    }


def collect_and_bundle_textures(
    objects=None,
    destination_dir=None,
    use_relative_paths=False,
    log=None,
):
    """Collect all linked texture files and copy them into destination_dir."""
    if not destination_dir:
        raise ShaderToolsError("Destination directory must be specified.")

    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    inspection = inspect_texture_paths(objects)
    copied = []
    updated_nodes = []
    warnings = []

    for record in inspection.get("valid_textures", []):
        node = record["node"]
        raw_path = record["path"]
        resolved = record["resolved_path"]
        is_udim = record["is_udim"]

        if is_udim:
            src_dir = os.path.dirname(resolved)
            pattern = os.path.basename(resolved)
            regex_str = (
                re.escape(pattern)
                .replace(re.escape("<UDIM>"), r"(\d{4})")
                .replace(re.escape("<udim>"), r"(\d{4})")
                .replace(re.escape("<tile>"), r"(\d{4})")
                .replace(re.escape("<TILE>"), r"(\d{4})")
                .replace(re.escape("<UVTILE>"), r"(u\d+_v\d+)")
            )
            matcher = re.compile("^" + regex_str + "$", re.IGNORECASE)
            found_files = []
            if os.path.isdir(src_dir):
                for f in os.listdir(src_dir):
                    if matcher.match(f):
                        found_files.append(f)

            for f in found_files:
                src_file = os.path.join(src_dir, f)
                dst_file = os.path.join(destination_dir, f)
                try:
                    shutil.copy2(src_file, dst_file)
                    copied.append(dst_file)
                except Exception as exc:
                    warnings.append("Could not copy {}: {}".format(src_file, exc))

            new_tex_path = os.path.join(destination_dir, os.path.basename(raw_path)).replace("\\", "/")
            try:
                cmds.setAttr(node + ".fileTextureName", new_tex_path, type="string")
                updated_nodes.append(node)
            except Exception as exc:
                warnings.append("Could not update node {}: {}".format(node, exc))
        else:
            if os.path.isfile(resolved):
                filename = os.path.basename(resolved)
                dst_file = os.path.join(destination_dir, filename)
                try:
                    shutil.copy2(resolved, dst_file)
                    copied.append(dst_file)
                except Exception as exc:
                    warnings.append("Could not copy {}: {}".format(resolved, exc))

                new_tex_path = dst_file.replace("\\", "/")
                try:
                    cmds.setAttr(node + ".fileTextureName", new_tex_path, type="string")
                    updated_nodes.append(node)
                except Exception as exc:
                    warnings.append("Could not update node {}: {}".format(node, exc))

    _log(log, "Bundled {} texture file(s) across {} node(s).".format(len(copied), len(updated_nodes)))
    return {
        "copied_count": len(copied),
        "updated_nodes": len(updated_nodes),
        "copied_files": copied,
        "warnings": warnings,
        "destination": destination_dir,
    }


def repath_texture_paths(
    objects=None,
    search_pattern="",
    replace_pattern="",
    log=None,
):
    """Search and replace substrings in fileTextureName for connected texture nodes."""
    if not search_pattern:
        return {"updated_count": 0, "warnings": []}

    inspection = inspect_texture_paths(objects)
    all_textures = inspection.get("valid_textures", []) + inspection.get("missing_textures", [])
    updated = 0
    warnings = []

    for record in all_textures:
        node = record["node"]
        raw_path = record["path"]
        if search_pattern in raw_path:
            new_path = raw_path.replace(search_pattern, replace_pattern)
            try:
                cmds.setAttr(node + ".fileTextureName", new_path, type="string")
                updated += 1
            except Exception as exc:
                warnings.append("Could not repath {}: {}".format(node, exc))

    _log(log, "Repathed {} texture node(s).".format(updated))
    return {
        "updated_count": updated,
        "warnings": warnings,
    }
