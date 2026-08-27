"""Qt-free production operations for ScarTools Character Finalizer."""

from __future__ import print_function

import importlib
import os

import maya.cmds as cmds

from scartools.version import VERSION


class CharacterFinalizerError(RuntimeError):
    """Raised when a character cannot be finalized safely."""


SIDES = ("L", "R")
LEGACY_FOLLOW_ATTRS = ("followMain", "followRoot", "followChest")
SPACE_SWITCH_FILENAME = "Arm_Follow_Space_Switch_V001.smd"
SPACE_SWITCH_ENV = "SCARTOOLS_SPACE_SWITCH_SMD"
OWNER_ATTR = "scarToolsOwner"
OWNER_VALUE = "character_finalizer"
SPACE_SWITCH_TAG = "scarToolsSpaceSwitchSmd"


def _log(callback, message):
    if callback:
        callback(str(message))


def _progress(callback, value, message):
    if callback:
        callback(int(value), str(message))


def normalize_namespace(namespace):
    return str(namespace or "").strip().strip(":")


def namespaced(name, namespace=""):
    namespace = normalize_namespace(namespace)
    return "{}:{}".format(namespace, name) if namespace else str(name)


def selected_namespace(selection=None):
    """Return the namespace of the first selected Maya node."""
    selection = selection or (cmds.ls(selection=True, long=True) or [])
    if not selection:
        return ""
    leaf = str(selection[0]).split("|")[-1].split(".")[0]
    return leaf.rsplit(":", 1)[0] if ":" in leaf else ""


def _resolve_node(name, namespace="", required=True):
    candidate = namespaced(name, namespace)
    matches = cmds.ls(candidate, long=True) or []
    matches = list(dict.fromkeys(matches))
    if len(matches) == 1:
        return matches[0]
    if not matches and not required:
        return ""
    if not matches:
        raise CharacterFinalizerError("Missing node: {}".format(candidate))
    raise CharacterFinalizerError(
        "Node is not unique: {} ({} matches)".format(candidate, len(matches))
    )


def resolve_space_switch_path(explicit_path=""):
    """Resolve the SMD from an explicit, environment, or workspace path."""
    candidates = []
    if explicit_path:
        candidates.append(explicit_path)
    environment_path = os.environ.get(SPACE_SWITCH_ENV, "")
    if environment_path:
        candidates.append(environment_path)
    try:
        workspace = cmds.workspace(query=True, rootDirectory=True) or ""
    except Exception:
        workspace = ""
    if workspace:
        candidates.extend((
            os.path.join(workspace, "Scripts", "SpaceSwitch", SPACE_SWITCH_FILENAME),
            os.path.join(workspace, "scripts", "SpaceSwitch", SPACE_SWITCH_FILENAME),
        ))
    for candidate in candidates:
        path = os.path.normpath(os.path.expandvars(os.path.expanduser(candidate)))
        if os.path.isfile(path):
            return path
    if explicit_path:
        return os.path.normpath(os.path.expandvars(os.path.expanduser(explicit_path)))
    return ""


def _space_manager():
    try:
        return importlib.import_module(
            "mgear.rigbits.space_manager.spaceManagerUtils"
        ), ""
    except Exception as exc:
        return None, str(exc)


def _plug_has_dependencies(plug):
    connections = cmds.listConnections(
        plug, source=True, destination=True, plugs=True
    ) or []
    try:
        keyed = bool(cmds.keyframe(plug, query=True, keyframeCount=True) or 0)
    except Exception:
        keyed = False
    return connections, keyed


def _find_face_visibility_source(namespace=""):
    preferred = namespaced("Main", namespace)
    if cmds.objExists(preferred) and cmds.attributeQuery(
        "face_ctrl_vis", node=preferred, exists=True
    ):
        return "{}.face_ctrl_vis".format(preferred)

    pattern = (
        "{}:*.face_ctrl_vis".format(normalize_namespace(namespace))
        if namespace else
        "*.face_ctrl_vis"
    )
    plugs = cmds.ls(pattern) or []
    plugs = list(dict.fromkeys(str(plug) for plug in plugs))
    if len(plugs) == 1:
        return plugs[0]
    if len(plugs) > 1:
        raise CharacterFinalizerError(
            "Multiple face_ctrl_vis attributes found in namespace '{}'.".format(
                normalize_namespace(namespace) or "<root>"
            )
        )
    raise CharacterFinalizerError(
        "No face_ctrl_vis attribute found in namespace '{}'.".format(
            normalize_namespace(namespace) or "<root>"
        )
    )


def _check(label, status, message, blocking=False):
    return {
        "label": str(label),
        "status": str(status),
        "message": str(message),
        "blocking": bool(blocking),
    }


def inspect_character(namespace="", smd_path=""):
    """Return a non-mutating finalization preflight report."""
    from scartools.licensing import require_license
    require_license("Character Finalizer Preflight")

    namespace = normalize_namespace(namespace)

    checks = []
    nodes = {}

    required_names = ["Main", "headRig_grp"]
    for side in SIDES:
        required_names.extend((
            "IKArm_{}".format(side),
            "PoleArm_{}".format(side),
            "PoleOffsetArm_{}".format(side),
        ))

    for name in required_names:
        try:
            node = _resolve_node(name, namespace)
            nodes[name] = node
            referenced = False
            try:
                referenced = bool(cmds.referenceQuery(node, isNodeReferenced=True))
            except Exception:
                pass
            checks.append(_check(
                name,
                "Blocked" if referenced else "Ready",
                "Referenced node cannot be finalized safely." if referenced else node,
                blocking=referenced,
            ))
        except Exception as exc:
            checks.append(_check(name, "Missing", exc, blocking=True))

    locked_scale = []
    for name in ("headRig_grp", "PoleOffsetArm_L", "PoleOffsetArm_R"):
        node = nodes.get(name)
        if not node:
            continue
        for attr in ("scaleX", "scaleY", "scaleZ"):
            plug = "{}.{}".format(node, attr)
            try:
                if cmds.getAttr(plug, lock=True):
                    locked_scale.append(plug)
            except Exception:
                pass
    checks.append(_check(
        "Required scale channels",
        "Unlock" if locked_scale else "Ready",
        (
            "Will unlock: {}".format(", ".join(locked_scale))
            if locked_scale else
            "Required scale channels are already unlocked."
        ),
    ))

    manager, manager_error = _space_manager()
    checks.append(_check(
        "mGear Space Manager",
        "Ready" if manager else "Missing",
        "Available" if manager else manager_error,
        blocking=manager is None,
    ))

    resolved_smd = resolve_space_switch_path(smd_path)
    checks.append(_check(
        "Space-switch definition",
        "Ready" if resolved_smd and os.path.isfile(resolved_smd) else "Missing",
        resolved_smd or "No readable {} path found.".format(SPACE_SWITCH_FILENAME),
        blocking=not (resolved_smd and os.path.isfile(resolved_smd)),
    ))

    try:
        face_source = _find_face_visibility_source(namespace)
        head = nodes.get("headRig_grp") or _resolve_node("headRig_grp", namespace)
        destination = "{}.visibility".format(head)
        checks.append(_check(
            "Face control visibility",
            "Ready",
            "{} -> {} (forced)".format(face_source, destination),
        ))
    except Exception as exc:
        face_source = ""
        checks.append(_check(
            "Face control visibility", "Missing", exc, blocking=True
        ))

    for side in SIDES:
        ik = nodes.get("IKArm_{}".format(side))
        if not ik:
            continue
        blocked_attrs = []
        for attr in LEGACY_FOLLOW_ATTRS:
            if not cmds.attributeQuery(attr, node=ik, exists=True):
                continue
            plug = "{}.{}".format(ik, attr)
            connections, keyed = _plug_has_dependencies(plug)
            if connections or keyed:
                blocked_attrs.append(attr)
        checks.append(_check(
            "{} legacy follow attributes".format(side),
            "Blocked" if blocked_attrs else "Ready",
            (
                "Connected/keyed attributes: {}".format(", ".join(blocked_attrs))
                if blocked_attrs else
                "Safe to migrate or already clean."
            ),
            blocking=bool(blocked_attrs),
        ))

    for side in SIDES:
        driven = nodes.get("PoleOffsetArm_{}".format(side))
        if not driven:
            continue
        managed_name = namespaced(
            "ScarTools_PoleArm_{}_Follow_parentConstraint".format(side), namespace
        )
        constraints = cmds.listConnections(
            driven, source=True, destination=False, type="parentConstraint"
        ) or []
        unmanaged = [
            item for item in set(constraints)
            if str(item).split("|")[-1] != managed_name
        ]
        checks.append(_check(
            "{} pole-vector follow".format(side),
            "Blocked" if unmanaged else ("Repair" if constraints else "Create"),
            (
                "Unmanaged parentConstraint: {}".format(", ".join(unmanaged))
                if unmanaged else
                "Existing managed setup will be repaired." if constraints else
                "Ready to create."
            ),
            blocking=bool(unmanaged),
        ))

    blocking = [item for item in checks if item["blocking"]]
    return {
        "ok": not blocking,
        "namespace": namespace,
        "smd_path": resolved_smd,
        "nodes": nodes,
        "face_source_plug": face_source,
        "checks": checks,
        "blocking": blocking,
    }


def build_plan(namespace="", smd_path=""):
    """Return the explicit steps that finalize_character will execute."""
    report = inspect_character(namespace=namespace, smd_path=smd_path)
    return {
        "preflight": report,
        "steps": (
            "unlock_required_scale_channels",
            "remove_safe_legacy_follow_attributes",
            "apply_mgear_space_switch",
            "build_or_repair_pole_vector_follow_L",
            "build_or_repair_pole_vector_follow_R",
            "force_connect_face_control_visibility",
            "validate_finalized_character",
        ),
    }


def _unlock_plug(plug):
    if not cmds.objExists(plug):
        raise CharacterFinalizerError("Missing destination plug: {}".format(plug))
    try:
        locked = bool(cmds.getAttr(plug, lock=True))
    except Exception:
        locked = False
    if locked:
        cmds.setAttr(plug, lock=False)
        return True
    return False


def _unlock_scale(node):
    unlocked = []
    for attr in ("scaleX", "scaleY", "scaleZ"):
        plug = "{}.{}".format(node, attr)
        if _unlock_plug(plug):
            unlocked.append(plug)
    return unlocked


def _force_connect(source, destination):
    _unlock_plug(destination)
    existing = cmds.listConnections(
        destination, source=True, destination=False, plugs=True
    ) or []
    if len(existing) == 1 and existing[0] == source:
        return "skipped"
    cmds.connectAttr(source, destination, force=True)
    return "connected"


def _tag_node(node):
    if not cmds.attributeQuery(OWNER_ATTR, node=node, exists=True):
        cmds.addAttr(node, longName=OWNER_ATTR, dataType="string")
    plug = "{}.{}".format(node, OWNER_ATTR)
    _unlock_plug(plug)
    cmds.setAttr(plug, OWNER_VALUE, type="string")


def _same_node(first, second):
    try:
        uuid_a = (cmds.ls(first, uuid=True) or [None])[0]
        uuid_b = (cmds.ls(second, uuid=True) or [None])[0]
        if uuid_a is not None and uuid_b is not None:
            return uuid_a == uuid_b
        return str(first).split("|")[-1] == str(second).split("|")[-1]
    except Exception:
        return str(first).split("|")[-1] == str(second).split("|")[-1]


def _constraint_weight_plugs(constraint, main, ik):
    targets = cmds.parentConstraint(constraint, query=True, targetList=True) or []
    aliases = cmds.parentConstraint(constraint, query=True, weightAliasList=True) or []
    if len(targets) != len(aliases):
        raise CharacterFinalizerError(
            "Could not resolve weight aliases for {}.".format(constraint)
        )
    mapping = {}
    for target, alias in zip(targets, aliases):
        if _same_node(target, main):
            mapping["main"] = "{}.{}".format(constraint, alias)
        elif _same_node(target, ik):
            mapping["ik"] = "{}.{}".format(constraint, alias)
    if set(mapping) != {"main", "ik"}:
        raise CharacterFinalizerError(
            "Unexpected targets on parentConstraint {}.".format(constraint)
        )
    return mapping


def _ensure_node(node_type, name):
    if cmds.objExists(name):
        if cmds.nodeType(name) != node_type:
            raise CharacterFinalizerError(
                "{} exists but is not a {} node.".format(name, node_type)
            )
        return name, False
    node = cmds.createNode(node_type, name=name)
    _tag_node(node)
    return node, True


def _ensure_pole_vector_follow(side, namespace, nodes):
    ctrl = nodes["PoleArm_{}".format(side)]
    driven = nodes["PoleOffsetArm_{}".format(side)]
    main = nodes["Main"]
    ik = nodes["IKArm_{}".format(side)]

    follow_plug = "{}.follow".format(ctrl)
    if not cmds.attributeQuery("follow", node=ctrl, exists=True):
        cmds.addAttr(
            ctrl, longName="follow", attributeType="double",
            minValue=0, maxValue=10, defaultValue=0, keyable=True
        )
    else:
        _unlock_plug(follow_plug)
        cmds.setAttr(follow_plug, edit=True, keyable=True)

    constraint_name = namespaced(
        "ScarTools_PoleArm_{}_Follow_parentConstraint".format(side), namespace
    )
    created = False
    if cmds.objExists(constraint_name):
        if cmds.nodeType(constraint_name) != "parentConstraint":
            raise CharacterFinalizerError(
                "{} exists but is not a parentConstraint.".format(constraint_name)
            )
        constraint = constraint_name
    else:
        constraint = cmds.parentConstraint(
            main, ik, driven, maintainOffset=True, name=constraint_name
        )[0]
        _tag_node(constraint)
        created = True

    weights = _constraint_weight_plugs(constraint, main, ik)
    md_name = namespaced("ScarTools_PoleArm_{}_Follow_MD".format(side), namespace)
    rev_name = namespaced("ScarTools_PoleArm_{}_Follow_REV".format(side), namespace)
    md, md_created = _ensure_node("multiplyDivide", md_name)
    reverse, rev_created = _ensure_node("reverse", rev_name)
    cmds.setAttr("{}.operation".format(md), 1)
    cmds.setAttr("{}.input2X".format(md), 0.1)
    _force_connect(follow_plug, "{}.input1X".format(md))
    _force_connect("{}.outputX".format(md), "{}.inputX".format(reverse))
    _force_connect("{}.outputX".format(md), weights["ik"])
    _force_connect("{}.outputX".format(reverse), weights["main"])
    return {
        "constraint": constraint,
        "multiply": md,
        "reverse": reverse,
        "created": bool(created or md_created or rev_created),
    }


def _remove_legacy_attributes(nodes, log=None):
    removed = []
    for side in SIDES:
        node = nodes["IKArm_{}".format(side)]
        for attr in LEGACY_FOLLOW_ATTRS:
            if not cmds.attributeQuery(attr, node=node, exists=True):
                continue
            plug = "{}.{}".format(node, attr)
            connections, keyed = _plug_has_dependencies(plug)
            if connections or keyed:
                raise CharacterFinalizerError(
                    "Cannot delete keyed or connected legacy attribute: {}".format(plug)
                )
            _unlock_plug(plug)
            cmds.deleteAttr(node, attribute=attr)
            removed.append(plug)
            _log(log, "Removed legacy attribute: {}".format(plug))
    return removed


def _apply_space_switch(nodes, smd_path, log=None):
    main = nodes["Main"]
    if cmds.attributeQuery(SPACE_SWITCH_TAG, node=main, exists=True):
        recorded = cmds.getAttr("{}.{}".format(main, SPACE_SWITCH_TAG)) or ""
        if os.path.normcase(os.path.normpath(recorded)) == os.path.normcase(
            os.path.normpath(smd_path)
        ):
            _log(log, "Space switch already applied; skipped duplicate build.")
            return "skipped"

    manager, error = _space_manager()
    if manager is None:
        raise CharacterFinalizerError("mGear Space Manager unavailable: {}".format(error))
    _create_spaces_reusing_attributes(manager, smd_path, log=log)
    if not cmds.attributeQuery(SPACE_SWITCH_TAG, node=main, exists=True):
        cmds.addAttr(main, longName=SPACE_SWITCH_TAG, dataType="string")
    tag_plug = "{}.{}".format(main, SPACE_SWITCH_TAG)
    _unlock_plug(tag_plug)
    cmds.setAttr(tag_plug, os.path.normpath(smd_path), type="string")
    _log(log, "Applied space switch: {}".format(smd_path))
    return "applied"


def _create_spaces_reusing_attributes(manager, smd_path, log=None):
    """Run mGear Space Manager while safely reusing existing UI attributes.

    mGear's SMD builder creates its constraints first and then calls addAttr on
    the configured UI host. Maya raises "Found no valid items to add the
    attribute to" when that attribute is already present. During this one
    synchronous build only, intercept addAttr and treat a matching existing
    plug as reusable. All other addAttr calls continue to Maya unchanged.
    """
    original_add_attr = cmds.addAttr
    reused = set()

    def add_or_reuse(*args, **kwargs):
        node = args[0] if args else kwargs.get("node")
        attr = (
            kwargs.get("longName")
            or kwargs.get("ln")
            or kwargs.get("shortName")
            or kwargs.get("sn")
        )
        if node and attr:
            node = str(node)
            attr = str(attr)
            try:
                exists = cmds.attributeQuery(attr, node=node, exists=True)
            except Exception:
                exists = False
            if exists:
                plug = "{}.{}".format(node, attr)
                _unlock_plug(plug)
                if kwargs.get("keyable") or kwargs.get("k"):
                    try:
                        cmds.setAttr(plug, edit=True, keyable=True)
                    except Exception:
                        pass
                if plug not in reused:
                    reused.add(plug)
                    _log(log, "Reused existing space-switch attribute: {}".format(plug))
                return None
        return original_add_attr(*args, **kwargs)

    cmds.addAttr = add_or_reuse
    try:
        manager.create_spaces(smd_path)
    finally:
        cmds.addAttr = original_add_attr

    return sorted(reused)


def finalize_character(
    namespace="", smd_path="", dry_run=False, log=None, progress=None
):
    """Preflight and finalize one character as a single Maya undo operation."""
    plan = build_plan(namespace=namespace, smd_path=smd_path)
    report = plan["preflight"]
    if dry_run:
        return plan
    if not report["ok"]:
        details = "; ".join(item["message"] for item in report["blocking"])
        raise CharacterFinalizerError("Preflight blocked finalization: {}".format(details))

    nodes = report["nodes"]
    namespace = report["namespace"]
    from scartools.framework import SceneTransaction

    result = {
        "namespace": namespace,
        "smd_path": report["smd_path"],
        "unlocked_scale": [],
        "legacy_removed": [],
        "space_switch": "",
        "pole_vector_follow": {},
        "face_visibility": "",
    }

    with SceneTransaction(
        "ScarTools_CharacterFinalizer",
        use_undo=True,
        preserve_selection=True,
        suspend_refresh=True,
        log=log,
    ) as transaction:
        for node_name in ("headRig_grp", "PoleOffsetArm_L", "PoleOffsetArm_R"):
            transaction.mark_mutating()
            result["unlocked_scale"].extend(_unlock_scale(nodes[node_name]))
        _progress(progress, 12, "Required scale channels unlocked")
        transaction.mark_mutating()
        result["legacy_removed"] = _remove_legacy_attributes(nodes, log=log)
        _progress(progress, 25, "Legacy follow attributes migrated")
        transaction.mark_mutating()
        result["space_switch"] = _apply_space_switch(
            nodes, report["smd_path"], log=log
        )
        _progress(progress, 50, "mGear space switch ready")
        for side in SIDES:
            transaction.mark_mutating()
            result["pole_vector_follow"][side] = _ensure_pole_vector_follow(
                side, namespace, nodes
            )
            _log(log, "Built or repaired {} pole-vector follow.".format(side))
            _progress(
                progress,
                65 if side == "L" else 82,
                "{} pole-vector follow ready".format(side),
            )

        face_destination = "{}.visibility".format(nodes["headRig_grp"])
        transaction.mark_mutating()
        result["face_visibility"] = _force_connect(
            report["face_source_plug"], face_destination
        )
        _log(log, "Connected {} -> {}.".format(
            report["face_source_plug"], face_destination
        ))
        _progress(progress, 94, "Face control visibility connected")

    result["validation"] = inspect_character(
        namespace=namespace, smd_path=report["smd_path"]
    )
    _progress(progress, 100, "Character validation complete")
    _log(log, "Character finalization completed with one Maya undo step.")
    return result


__all__ = [
    "CharacterFinalizerError",
    "SPACE_SWITCH_ENV",
    "SPACE_SWITCH_FILENAME",
    "build_plan",
    "finalize_character",
    "inspect_character",
    "namespaced",
    "normalize_namespace",
    "resolve_space_switch_path",
    "selected_namespace",
]
