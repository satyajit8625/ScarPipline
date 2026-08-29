"""Headless architecture and release checks for ScarTools 1.0.1."""

from __future__ import print_function

import ast
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCARTOOLS = SCRIPTS / "scartools"


def source(path):
    return Path(path).read_text(encoding="utf-8")


def install_maya_stubs():
    maya = sys.modules.get("maya")
    if maya is None:
        maya = types.ModuleType("maya")
        sys.modules["maya"] = maya

    cmds = sys.modules.get("maya.cmds")
    if cmds is None:
        cmds = types.ModuleType("maya.cmds")
        sys.modules["maya.cmds"] = cmds
    maya.cmds = cmds

    state = {"selection": ["|character|body"], "events": [], "batch": True}

    def about(version=False, apiVersion=False, batch=False, **_):
        if version:
            return "2023"
        if apiVersion:
            return 20230000
        if batch:
            return state["batch"]
        return "2023"

    def ls(*_, **kwargs):
        if kwargs.get("selection") or kwargs.get("sl"):
            return list(state["selection"])
        return []

    def select(items=None, replace=False, clear=False, **_):
        if clear:
            state["selection"] = []
        elif replace:
            state["selection"] = list(items or [])
        state["events"].append(("select", tuple(state["selection"])))

    def undo_info(openChunk=False, closeChunk=False, chunkName="", **_):
        if openChunk:
            state["events"].append(("open", chunkName))
        if closeChunk:
            state["events"].append(("close", chunkName))

    def undo():
        state["events"].append(("undo",))

    def refresh(suspend=False, force=False, **_):
        state["events"].append(("refresh", bool(suspend), bool(force)))

    cmds.about = about
    cmds.ls = ls
    cmds.select = select
    cmds.undoInfo = undo_info
    cmds.undo = undo
    cmds.refresh = refresh
    cmds.objExists = lambda node: True
    cmds.nodeType = lambda node: "mesh"
    cmds.loadPlugin = lambda *a, **kw: None
    cmds.pluginInfo = lambda *a, **kw: True

    mel = sys.modules.get("maya.mel")
    if mel is None:
        mel = types.ModuleType("maya.mel")
        sys.modules["maya.mel"] = mel
    mel.eval = lambda *args, **kwargs: None
    maya.mel = mel

    maya_api = sys.modules.get("maya.api")
    if maya_api is None:
        maya_api = types.ModuleType("maya.api")
        maya_api.__path__ = []
        sys.modules["maya.api"] = maya_api
    maya.api = maya_api

    open_maya = sys.modules.get("maya.api.OpenMaya")
    if open_maya is None:
        open_maya = types.ModuleType("maya.api.OpenMaya")
        sys.modules["maya.api.OpenMaya"] = open_maya
    maya_api.OpenMaya = open_maya

    open_maya_anim = sys.modules.get("maya.api.OpenMayaAnim")
    if open_maya_anim is None:
        open_maya_anim = types.ModuleType("maya.api.OpenMayaAnim")
        sys.modules["maya.api.OpenMayaAnim"] = open_maya_anim
    maya_api.OpenMayaAnim = open_maya_anim

    # Isolate test license in a temporary directory so real machine home is never touched
    import tempfile
    import os
    if not getattr(sys, "_scartools_test_temp_home", None):
        sys._scartools_test_temp_home = tempfile.mkdtemp()
        os.environ["USERPROFILE"] = sys._scartools_test_temp_home
        os.environ["HOME"] = sys._scartools_test_temp_home
        try:
            from scartools.licensing import generate_license_key, save_license
            key = generate_license_key("test_user", days_valid=0)
            save_license("test_user", key)
        except Exception:
            pass

    return state


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_path = list(sys.path)
        sys.path.insert(0, str(SCRIPTS))
        cls.maya_state = install_maya_stubs()

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls._old_path



    def setUp(self):
        self.maya_state["events"][:] = []
        self.maya_state["selection"][:] = ["|character|body"]

    def test_python_39_syntax(self):
        for path in ROOT.rglob("*.py"):
            ast.parse(source(path), filename=str(path), feature_version=(3, 9))

    def test_one_suite_package_and_no_legacy_top_level_tools(self):
        packages = sorted(path.name for path in SCRIPTS.iterdir() if path.is_dir())
        self.assertEqual(packages, ["scartools"])
        self.assertFalse((SCRIPTS / "skin_weights_pro").exists())
        self.assertFalse((SCRIPTS / "shader_tools").exists())
        self.assertFalse((SCRIPTS / "character_finalizer").exists())

    def test_all_tools_follow_same_contract(self):
        expected = {
            "__init__.py", "api", "controller.py", "manifest.py",
            "operations.py", "ui", "ui_spec.py",
        }
        for tool in ("skin", "shader", "character_finalizer", "modeling"):
            folder = SCARTOOLS / "tools" / tool
            names = {path.name for path in folder.iterdir()}
            self.assertTrue(expected.issubset(names), (tool, expected - names))
            self.assertNotIn("core.py", names)
            self.assertNotIn("version.py", names)
            self.assertNotIn("menu.py", names)

    def test_one_central_version(self):
        version_files = list(SCARTOOLS.rglob("version.py"))
        self.assertEqual(version_files, [SCARTOOLS / "version.py"])
        self.assertIn('VERSION = "1.0.1"', source(version_files[0]))

    def test_builtin_manifests_use_new_paths(self):
        builtin = source(SCARTOOLS / "builtin.py")
        self.assertNotIn("skin_weights_pro", builtin)
        self.assertIn("scartools.tools.skin.manifest:MANIFEST", builtin)
        self.assertIn("scartools.tools.shader.manifest:MANIFEST", builtin)
        self.assertIn(
            "scartools.tools.character_finalizer.manifest:MANIFEST", builtin
        )
        self.assertIn("scartools.tools.modeling.manifest:MANIFEST", builtin)
        self.assertIn("scartools.tools.udim.manifest:MANIFEST", builtin)
        self.assertIn("scartools.tools.renamer.manifest:MANIFEST", builtin)

    def test_manifests_share_contract_and_maya_floor(self):
        from scartools.catalog import manifests

        values = manifests()
        self.assertEqual(len(values), 6)
        for manifest in values:
            self.assertEqual(manifest.version, "1.0.1")
            self.assertEqual(manifest.min_maya_version, 2023)
            self.assertTrue(manifest.package.startswith("scartools.tools."))
            self.assertTrue(manifest.controller_entry_point)
            self.assertTrue(manifest.ui_spec_entry_point)
            self.assertTrue(manifest.services)



    def test_services_are_lazy_and_callable_by_entry_point(self):
        from scartools import find_service, register_builtin_services
        from scartools.framework import SERVICES

        registered = register_builtin_services()
        self.assertIn("skin.copy_weights", registered)
        self.assertIn("shader.export_package", registered)
        self.assertIn("character.finalize", registered)
        self.assertIn("modeling.inspect", registered)
        definition = find_service("skin.copy_weights")
        self.assertTrue(definition.mutates_scene)
        self.assertEqual(
            definition.entry_point,
            "scartools.tools.skin.api:copy_skin_weights",
        )
        self.assertGreaterEqual(len(SERVICES.definitions()), 12)

    def test_headless_catalog_does_not_load_qt(self):
        before = set(sys.modules)
        import scartools.catalog
        scartools.catalog.manifest_data()
        loaded = set(sys.modules) - before
        self.assertFalse(any(name.startswith("PySide") for name in loaded))
        self.assertNotIn("scartools.ui", loaded)

    def test_central_scene_transaction_rolls_back_partial_failure(self):
        from scartools.framework import SceneTransaction

        with self.assertRaisesRegex(RuntimeError, "injected"):
            with SceneTransaction("FaultInjection", suspend_refresh=True) as transaction:
                transaction.mark_mutating()
                raise RuntimeError("injected")

        event_names = [event[0] for event in self.maya_state["events"]]
        self.assertEqual(event_names[0], "open")
        self.assertIn("close", event_names)
        self.assertIn("undo", event_names)
        self.assertEqual(self.maya_state["selection"], ["|character|body"])

    def test_central_operation_result(self):
        from scartools.framework import OperationResult

        result = OperationResult("test")
        result.info("started")
        result.warning("recoverable")
        result.complete()
        self.assertTrue(result.success)
        self.assertEqual(len(result.warnings), 1)
        result.error("failed")
        self.assertFalse(result.success)

    def test_central_ui_modules_and_tokens_exist(self):
        ui = SCARTOOLS / "ui"
        for name in (
            "components.py", "logs.py", "progress.py", "qt.py", "rollup.py",
            "theme.py", "tokens.py", "window.py",
        ):
            self.assertTrue((ui / name).is_file(), name)
        tokens = source(ui / "tokens.py")
        self.assertIn("PRIMARY_BUTTON_HEIGHT = 42", tokens)
        self.assertIn("SECONDARY_BUTTON_HEIGHT = 30", tokens)
        self.assertIn("WINDOW_MARGIN = 14", tokens)

    def test_every_tool_window_uses_central_base_and_theme(self):
        for tool in ("skin", "shader", "character_finalizer"):
            windows = source(SCARTOOLS / "tools" / tool / "ui" / "windows.py")
            self.assertIn("BaseToolDialog", windows)
            self.assertIn("from scartools.ui.theme import", windows)
            self.assertNotIn("from scartools.qt", windows)
            self.assertNotIn("from scartools.theme", windows)

    def test_lifecycle_closes_main_and_child_windows(self):
        from scartools.framework.lifecycle import WindowRegistry

        class Signal:
            def connect(self, _):
                pass

        class Window:
            def __init__(self):
                self.closed = False
                self.deleted = False
                self.destroyed = Signal()

            def close(self):
                self.closed = True

            def deleteLater(self):
                self.deleted = True

        registry = WindowRegistry()
        main = registry.register("skin", Window())
        child = registry.register("skin", Window())
        self.assertEqual(registry.close("skin"), 2)
        self.assertTrue(main.closed and main.deleted)
        self.assertTrue(child.closed and child.deleted)

    def test_copy_skin_has_atomic_gate_cache_and_normalization_policy(self):
        skin = source(SCARTOOLS / "tools" / "skin" / "operations.py")
        self.assertIn("transaction.mark_mutating()", skin)
        self.assertIn("source_weight_data", skin)
        self.assertIn("source_data=source_weight_data", skin)
        self.assertIn("normalize=normalize_copy", skin)
        self.assertIn("_copy_skin_cluster_settings", skin)
        self.assertIn("bindPreMatrix", skin)

    def test_copy_skin_rolls_back_when_maya_mutates_then_raises(self):
        operations = __import__(
            "scartools.tools.skin.operations", fromlist=["operations"]
        )
        names = (
            "_mesh_transform", "_mesh_shape", "_skin_cluster",
            "_skin_influence_paths", "_mesh_vertex_count", "_skin_setting",
        )
        originals = {name: getattr(operations, name) for name in names}
        cmds = sys.modules["maya.cmds"]
        old_copy = getattr(cmds, "copySkinWeights", None)
        try:
            operations._mesh_transform = lambda node: str(node)
            operations._mesh_shape = lambda node: str(node) + "Shape"
            operations._skin_cluster = lambda node: {
                "source": "sourceSkin", "target": "targetSkin"
            }.get(str(node))
            operations._skin_influence_paths = lambda _skin: ["|rig|jointA"]
            operations._mesh_vertex_count = lambda _shape: 10
            operations._skin_setting = lambda _skin, _attr, default: default

            def partial_failure(**_):
                self.maya_state["events"].append(("partial-mutation",))
                raise RuntimeError("copy failed after mutation")

            cmds.copySkinWeights = partial_failure
            with self.assertRaisesRegex(RuntimeError, "after mutation"):
                operations.copy_skin_weights(
                    "source", ["target"], method="closestPoint"
                )
            names_seen = [event[0] for event in self.maya_state["events"]]
            self.assertLess(
                names_seen.index("partial-mutation"), names_seen.index("undo")
            )
        finally:
            for name, value in originals.items():
                setattr(operations, name, value)
            if old_copy is None:
                delattr(cmds, "copySkinWeights")
            else:
                cmds.copySkinWeights = old_copy

    def test_copy_ui_prunes_deleted_or_renamed_nodes(self):
        windows = source(SCARTOOLS / "tools" / "skin" / "ui" / "windows.py")
        self.assertIn("def _prune_dead_nodes", windows)
        self.assertIn("cmds.objExists(self._source)", windows)
        self.assertIn("cmds.objExists(mesh)", windows)

    def test_skin_package_is_strictly_packed(self):
        operations = source(SCARTOOLS / "tools" / "skin" / "operations.py")
        windows = source(SCARTOOLS / "tools" / "skin" / "ui" / "windows.py")
        self.assertIn('SKIN_PACKAGE_FORMAT = "ScarToolsSkinPackage"', operations)
        self.assertIn('SKIN_PACKAGE_FILENAME = "skin_weights_package.json"', operations)
        self.assertIn("Legacy individual mesh JSON files are not supported", windows)

    def test_api_undo_bridge_targets_maya_2023_api2(self):
        operations = source(SCARTOOLS / "tools" / "skin" / "operations.py")
        self.assertIn("maya_useNewAPI = True", operations)
        self.assertIn("if len(args) < 1", operations)
        self.assertNotIn("args.length", operations)
        self.assertIn("scartools_skin_api_undo_v6.py", operations)

    def test_character_finalizer_is_project_portable(self):
        operations = source(
            SCARTOOLS / "tools" / "character_finalizer" / "operations.py"
        )
        self.assertNotIn(r"O:\scarfall2.0", operations)
        self.assertIn("SCARTOOLS_SPACE_SWITCH_SMD", operations)
        self.assertIn("SceneTransaction", operations)

    def test_installer_is_single_entry_and_has_no_legacy_imports(self):
        installers = sorted(path.name for path in ROOT.glob("drag_drop_install*.py"))
        self.assertEqual(installers, ["drag_drop_install.py"])
        installer = source(ROOT / installers[0])
        self.assertIn('VERSION = "1.0.1"', installer)
        self.assertNotIn("skin_weights_pro", installer)
        self.assertNotIn("LEGACY_TOOL", installer)
        self.assertIn(
            'RUNTIME_DIRECTORIES = ("scripts", "plug-ins", "icons")', installer
        )


    def test_installer_payload_has_no_cache_or_icon_sources(self):
        installer = source(ROOT / "drag_drop_install.py")
        self.assertIn('name == "__pycache__" or name == "source"', installer)
        self.assertIn("name.endswith((\".pyc\", \".pyo\"))", installer)

    def test_character_finalizer_same_node_handles_nonexistent_nodes(self):
        from scartools.tools.character_finalizer.operations import _same_node
        self.assertFalse(_same_node("nonexistent_node_a", "nonexistent_node_b"))
        self.assertTrue(_same_node("node_a", "node_a"))

    def test_tool_controller_does_not_false_positive_on_zero_failed(self):
        from scartools.framework import ToolController
        controller = ToolController("test_tool")
        result = controller.run("test_op", lambda log: log("Checked 10 items (0 failed)"))
        self.assertTrue(result.success)
        self.assertEqual(len(result.errors), 0)

    def test_scene_version_regex_consistency(self):
        from scartools.framework.snapshots import asset_key
        from scartools.tools.skin.operations import _scene_asset_key
        test_names = [
            "Hero_Rig_01.ma",
            "Hero_Rig_v01.ma",
            "Hero_Rig_ver02.ma",
            "Hero_Rig-1.ma",
            "Hero_Rig.02.ma",
            "Hero_Rig_version_03.ma",
        ]
        for name in test_names:
            self.assertEqual(asset_key(name), _scene_asset_key(name))

    def test_service_registry_lazy_resolution(self):
        from scartools.framework import SERVICES
        from scartools.builtin import register_builtin_services
        register_builtin_services(clear=True)
        service = SERVICES.get("skin.copy_weights")
        self.assertIsNotNone(service)
        self.assertEqual(service.service_id, "skin.copy_weights")

    def test_menu_has_about_scartools_before_version(self):
        menu_src = source(SCARTOOLS / "menu.py")
        self.assertIn('"About ScarTools"', menu_src)
        self.assertNotIn('"Build ScarTools Shelf"', menu_src)
        about_idx = menu_src.find('"About ScarTools"')
        version_idx = menu_src.find('"ScarTools v{}"')
        self.assertGreater(about_idx, 0)
        self.assertGreater(version_idx, about_idx)

    def test_shelf_tools_definition(self):
        from scartools.shelf import SHELF_TOOLS, SHELF_NAME
        self.assertEqual(SHELF_NAME, "ScarTools")
        self.assertEqual(len(SHELF_TOOLS), 8)
        labels = [t["label"] for t in SHELF_TOOLS]
        overlays = [t["overlay_label"] for t in SHELF_TOOLS]
        self.assertIn("Skin Tools", labels)
        self.assertIn("Shader Tools", labels)
        self.assertIn("Character Finalizer", labels)
        self.assertIn("Generate UDIM", labels)
        self.assertIn("Pipeline Renamer", labels)
        self.assertIn("Log Viewer", labels)
        self.assertIn("About ScarTools", labels)
        self.assertIn("Skin", overlays)
        self.assertIn("Shader", overlays)
        self.assertIn("Rig", overlays)
        self.assertIn("UDIM", overlays)
        self.assertIn("Rename", overlays)
        self.assertIn("Logs", overlays)
        self.assertIn("About", overlays)




    def test_scene_transaction_suspend_evaluation(self):
        from scartools.framework import SceneTransaction
        tx = SceneTransaction("TestBatch", suspend_evaluation=True)
        self.assertTrue(tx.suspend_evaluation)
        with tx:
            pass

    def test_skin_health_and_symmetry_api(self):
        from scartools.tools.skin.api import (
            inspect_skin_health,
            select_skin_issue_vertices,
            inspect_skin_symmetry,
        )
        self.assertTrue(callable(inspect_skin_health))
        self.assertTrue(callable(select_skin_issue_vertices))
        self.assertTrue(callable(inspect_skin_symmetry))

    def test_shader_variants_and_texture_validator(self):
        from scartools.tools.shader.api import (
            inspect_texture_paths,
            export_shader_package,
            import_shader_package,
        )
        self.assertTrue(callable(inspect_texture_paths))
        self.assertTrue(callable(export_shader_package))
        self.assertTrue(callable(import_shader_package))

    def test_skin_symmetry_math(self):
        from scartools.tools.skin.operations import _MIRROR_AXIS_INDEX
        self.assertEqual(_MIRROR_AXIS_INDEX["X"], 0)
        self.assertEqual(_MIRROR_AXIS_INDEX["Y"], 1)
        self.assertEqual(_MIRROR_AXIS_INDEX["Z"], 2)

    def test_modeling_tool_api(self):
        from scartools.tools.modeling.api import (
            inspect_model_and_scene,
            select_issue_components,
            fix_all_safe_issues,
            fix_make_names_unique,
            fix_add_geo_suffixes,
            fix_add_grp_suffixes,
            fix_shader_suffixes,
            fix_freeze_transforms,
            fix_center_pivots,
            fix_delete_construction_history,
            fix_delete_intermediate_shapes,
            fix_unlock_normals,
            fix_clean_scene_clutter,
        )
        self.assertTrue(callable(inspect_model_and_scene))
        self.assertTrue(callable(select_issue_components))
        self.assertTrue(callable(fix_all_safe_issues))
        self.assertTrue(callable(fix_make_names_unique))
        self.assertTrue(callable(fix_add_geo_suffixes))
        self.assertTrue(callable(fix_add_grp_suffixes))
        self.assertTrue(callable(fix_shader_suffixes))
        self.assertTrue(callable(fix_freeze_transforms))
        self.assertTrue(callable(fix_center_pivots))
        self.assertTrue(callable(fix_delete_construction_history))
        self.assertTrue(callable(fix_delete_intermediate_shapes))
        self.assertTrue(callable(fix_unlock_normals))
        self.assertTrue(callable(fix_clean_scene_clutter))

    def test_modeling_manifest(self):
        from scartools.tools.modeling.manifest import MANIFEST
        self.assertEqual(MANIFEST.tool_id, "model_sanitizer")
        self.assertEqual(MANIFEST.department, "modeling")
        self.assertEqual(MANIFEST.version, "1.0.1")
        self.assertIn("modeling.inspect", MANIFEST.capabilities)
        self.assertIn("modeling.fix", MANIFEST.capabilities)


    def test_builtin_modules_include_modeling(self):
        from scartools.builtin import BUILTIN_TOOL_MODULES, BUILTIN_TOOL_MANIFESTS
        self.assertIn("scartools.tools.modeling", BUILTIN_TOOL_MODULES)
        self.assertIn("scartools.tools.modeling.manifest:MANIFEST", BUILTIN_TOOL_MANIFESTS)


    def test_menu_departments_have_no_vfx_or_cfx(self):
        from scartools.menu import DEPARTMENTS
        dept_ids = [d[0] for d in DEPARTMENTS]
        self.assertNotIn("vfx", dept_ids)
        self.assertNotIn("cfx", dept_ids)
        self.assertIn("modeling", dept_ids)
        self.assertIn("rigging", dept_ids)
        self.assertIn("texturing", dept_ids)

if __name__ == "__main__":
    unittest.main()
