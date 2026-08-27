# -*- coding: utf-8 -*-
"""Unit tests for 1-to-Many and N-to-N Copy SkinCluster and Unbind features."""

from __future__ import print_function

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tests.test_release import install_maya_stubs
install_maya_stubs()

from scartools.tools.skin.operations import (
    SkinIOError,
    copy_skin_cluster,
    copy_skin_weights,
    unbind_target_skin_clusters,
)
import maya.cmds as cmds


class TestSkinCopyMulti(unittest.TestCase):
    """Test 1-to-many and N-to-N copy operations."""

    def test_copy_api_exports(self):
        """Verify unbind_target_skin_clusters is exported in public API."""
        from scartools.tools.skin.api import unbind_target_skin_clusters as api_unbind
        self.assertTrue(callable(api_unbind))

    def test_empty_sources_raises(self):
        """Empty sources must raise SkinIOError."""
        with self.assertRaises(SkinIOError):
            copy_skin_cluster([], ["target1"])

    def test_empty_targets_raises(self):
        """Empty targets must raise SkinIOError."""
        with self.assertRaises(SkinIOError):
            copy_skin_cluster(["source1"], [])

    def test_count_mismatch_raises(self):
        """Mismatched source and target counts (>1) must raise SkinIOError."""
        orig_obj_exists = cmds.objExists
        cmds.objExists = lambda x: True
        try:
            with self.assertRaises(SkinIOError) as ctx:
                copy_skin_cluster(["src1", "src2", "src3"], ["tgt1", "tgt2"])
            self.assertIn("Source count (3) and Target count (2) must match", str(ctx.exception))
        finally:
            cmds.objExists = orig_obj_exists

    def test_unbind_empty_targets_raises(self):
        """Unbind with empty targets must raise SkinIOError."""
        with self.assertRaises(SkinIOError):
            unbind_target_skin_clusters([])

    def test_unbind_executes_successfully(self):
        """Unbind must unbind skinCluster and return unbound meshes."""
        operations = sys.modules["scartools.tools.skin.operations"]
        orig_mesh_transform = operations._mesh_transform
        orig_skin_cluster = operations._skin_cluster
        orig_skinCluster_cmd = getattr(cmds, "skinCluster", None)

        unbound_skins = []
        try:
            operations._mesh_transform = lambda node: str(node)
            operations._skin_cluster = lambda node: str(node) + "SkinCluster"
            cmds.skinCluster = lambda skin, **kwargs: unbound_skins.append(skin)

            result = unbind_target_skin_clusters(["meshA", "meshB"])
            self.assertEqual(result, ["meshA", "meshB"])
            self.assertEqual(unbound_skins, ["meshASkinCluster", "meshBSkinCluster"])
        finally:
            operations._mesh_transform = orig_mesh_transform
            operations._skin_cluster = orig_skin_cluster
            if orig_skinCluster_cmd is None:
                delattr(cmds, "skinCluster")
            else:
                cmds.skinCluster = orig_skinCluster_cmd


    def test_n_to_n_copy_executes_successfully(self):
        """N-to-N copy must transfer each source to its matching target."""
        operations = sys.modules["scartools.tools.skin.operations"]
        names = (
            "_mesh_transform", "_mesh_shape", "_skin_cluster",
            "_skin_influence_paths", "_mesh_vertex_count", "_skin_setting",
            "_api_export_weights", "_prepare_index_copy_change",
            "_commit_api_skin_changes", "_copy_skin_cluster_settings",
            "_create_import_skin_cluster",
        )
        originals = {name: getattr(operations, name, None) for name in names}
        try:
            operations._mesh_transform = lambda node: str(node)
            operations._mesh_shape = lambda node: str(node) + "Shape"
            operations._skin_cluster = lambda node: {
                "src1": "src1Skin", "src2": "src2Skin"
            }.get(str(node))
            operations._skin_influence_paths = lambda _skin: ["|rig|jointA"]
            operations._mesh_vertex_count = lambda _shape: 10
            operations._skin_setting = lambda _skin, _attr, default: default
            operations._api_export_weights = lambda skin, shape: (["|rig|jointA"], [1.0] * 10, 10, 1)
            operations._prepare_index_copy_change = lambda s_skin, s_shape, t_skin, t_shape, source_data=None: {
                "transform": str(t_shape),
            }
            operations._commit_api_skin_changes = lambda changes: len(changes)
            operations._copy_skin_cluster_settings = lambda s_skin, t_skin, log=None: {}
            operations._create_import_skin_cluster = lambda infs, tgt, name, sm, mi: str(tgt) + "CreatedSkin"

            result = copy_skin_cluster(["src1", "src2"], ["tgt1", "tgt2"], method="vertexIndex")
            self.assertEqual(result["targets"], ["tgt1", "tgt2"])
            self.assertEqual(result["source"], ["src1", "src2"])
            self.assertEqual(result["target_skins"], ["tgt1CreatedSkin", "tgt2CreatedSkin"])
        finally:
            for name, val in originals.items():
                if val is not None:
                    setattr(operations, name, val)

    def test_skin_copy_window_has_side_by_side_layout(self):
        """Verify SkinCopyToolWindow defines side-by-side Sources and Targets tables."""
        windows_src = (SCRIPTS / "scartools" / "tools" / "skin" / "ui" / "windows.py").read_text(encoding="utf-8")
        self.assertIn("class SkinCopyToolWindow", windows_src)
        self.assertIn("self.source_table", windows_src)
        self.assertIn("self.target_table", windows_src)
        self.assertIn("self.load_sources_button", windows_src)
        self.assertIn("self.load_targets_button", windows_src)
        self.assertIn("tables_layout = QtWidgets.QHBoxLayout()", windows_src)

    def test_skin_mirror_window_features(self):
        """Verify SkinMirrorToolWindow defines mesh table, tolerance, and influence association."""
        windows_src = (SCRIPTS / "scartools" / "tools" / "skin" / "ui" / "windows.py").read_text(encoding="utf-8")
        self.assertIn("class SkinMirrorToolWindow", windows_src)
        self.assertIn("self.mesh_table", windows_src)
        self.assertIn("self.load_meshes_button", windows_src)
        self.assertIn("self.clear_meshes_button", windows_src)
        self.assertIn("self.tolerance_spin", windows_src)
        self.assertIn("self.assoc_combo", windows_src)
        self.assertIn("self._has_selected_vertices", windows_src)

    def test_mirror_operations_support_multimesh_and_components(self):
        """Verify operations.py mirror functions accept tolerance, scope, and multi-mesh."""
        from scartools.tools.skin import operations
        import inspect
        sig = inspect.signature(operations.mirror_skin_weights_from_selected)
        self.assertIn("meshes", sig.parameters)
        self.assertIn("tolerance", sig.parameters)
        self.assertIn("selected_vertices_only", sig.parameters)
        self.assertIn("association", sig.parameters)

        self.assertTrue(callable(operations.select_asymmetric_skin_vertices))
        self.assertTrue(callable(operations.inspect_skin_symmetry))

    def test_reparented_joint_influence_resolution(self):
        """Verify _InfluenceLookup correctly resolves short names when DAG paths change."""
        from scartools.tools.skin.operations import _InfluenceLookup
        scene_joints = [
            "|Rig_GRP|Skeleton|root",
            "|Rig_GRP|Skeleton|root|spine_01",
            "|Rig_GRP|Skeleton|root|spine_01|Chest|spine_02",
        ]
        lookup = _InfluenceLookup(scene_joints)
        # 1. Exact short name lookup
        self.assertEqual(lookup.resolve("spine_02"), "|Rig_GRP|Skeleton|root|spine_01|Chest|spine_02")
        # 2. Old full DAG path before reparenting
        self.assertEqual(lookup.resolve("|old_hierarchy|spine_02"), "|Rig_GRP|Skeleton|root|spine_01|Chest|spine_02")
        # 3. Namespace-stripped lookup
        self.assertEqual(lookup.resolve("char:spine_02"), "|Rig_GRP|Skeleton|root|spine_01|Chest|spine_02")


if __name__ == "__main__":
    unittest.main()
