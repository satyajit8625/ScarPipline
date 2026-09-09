"""Declarative validation primitives shared by preflight-driven tools."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidationIssue:
    check: str
    severity: str
    message: str
    node: str = ""
    fix: str = ""

    @property
    def blocks(self):
        return self.severity.lower() == "error"


@dataclass
class ValidationReport:
    context: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)

    def add(self, check, severity, message, node="", fix=""):
        issue = ValidationIssue(check, severity, message, node, fix)
        self.issues.append(issue)
        return issue

    @property
    def blockers(self):
        return tuple(issue for issue in self.issues if issue.blocks)

    @property
    def valid(self):
        return not self.blockers


import re
import maya.cmds as cmds


def _mesh_node(node):
    if not cmds.objExists(node):
        return None
    if cmds.nodeType(node) == "mesh":
        return node
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, type="mesh") or []
    return shapes[0] if shapes else None


def inspect_mesh_topology(nodes=None):
    """Scan meshes for topology anomalies (non-manifold, lamina, etc.)."""
    if nodes is None:
        nodes = cmds.ls(selection=True, long=True) or []
    elif isinstance(nodes, str):
        nodes = [nodes]

    results = {}
    for node in nodes:
        shape = _mesh_node(node)
        if not shape:
            continue

        try:
            non_manifold_vtx = cmds.polyInfo(shape, nonManifoldVertices=True) or []
        except Exception:
            non_manifold_vtx = []

        try:
            non_manifold_edges = cmds.polyInfo(shape, nonManifoldEdges=True) or []
        except Exception:
            non_manifold_edges = []

        try:
            lamina_faces = cmds.polyInfo(shape, laminaFaces=True) or []
        except Exception:
            lamina_faces = []

        vtx_ids = []
        for line in non_manifold_vtx:
            match = re.findall(r"\.vtx\[(\d+)\]", line)
            vtx_ids.extend([int(x) for x in match])

        edge_ids = []
        for line in non_manifold_edges:
            match = re.findall(r"\.e\[(\d+)\]", line)
            edge_ids.extend([int(x) for x in match])

        face_ids = []
        for line in lamina_faces:
            match = re.findall(r"\.f\[(\d+)\]", line)
            face_ids.extend([int(x) for x in match])

        all_shapes = cmds.listRelatives(node, shapes=True, type="mesh") or []
        intermediate = []
        for s in all_shapes:
            try:
                if cmds.getAttr(s + ".intermediateObject"):
                    intermediate.append(s)
            except Exception:
                pass

        is_clean = not (vtx_ids or edge_ids or face_ids or intermediate)
        results[node] = {
            "shape": shape,
            "clean": is_clean,
            "non_manifold_vertices": sorted(set(vtx_ids)),
            "non_manifold_edges": sorted(set(edge_ids)),
            "lamina_faces": sorted(set(face_ids)),
            "intermediate_shapes": intermediate,
        }

    return results


def select_mesh_topology_issues(node, issue_type="all"):
    """Select topology issue components in Maya viewport."""
    reports = inspect_mesh_topology([node])
    data = reports.get(node)
    if not data:
        return []

    shape = data["shape"]
    to_select = []
    if issue_type in ("all", "non_manifold_vertices"):
        to_select.extend(["{}.vtx[{}]".format(shape, i) for i in data["non_manifold_vertices"]])
    if issue_type in ("all", "non_manifold_edges"):
        to_select.extend(["{}.e[{}]".format(shape, i) for i in data["non_manifold_edges"]])
    if issue_type in ("all", "lamina_faces"):
        to_select.extend(["{}.f[{}]".format(shape, i) for i in data["lamina_faces"]])

    if to_select:
        try:
            cmds.select(to_select, replace=True)
        except Exception:
            pass
    return to_select


__all__ = [
    "ValidationIssue",
    "ValidationReport",
    "inspect_mesh_topology",
    "select_mesh_topology_issues",
]
