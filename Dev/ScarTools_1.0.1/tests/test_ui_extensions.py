# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_release import install_maya_stubs
install_maya_stubs()

try:
    from scartools.ui.qt import QtWidgets
    from scartools.ui.widgets import (
        Vector3Input,
        create_vector3_input,
        PathPickerWidget,
        create_path_picker,
        UVTileGrid,
        create_uv_tile_grid,
        CurveEditorWidget,
        create_curve_editor,
        PaletteGrid,
        create_palette_grid,
        TokenTagInput,
        create_token_input,
    )
    from scartools.ui.workspace import (
        StepWizardWidget,
        create_step_wizard,
        PresetManager,
        PresetBar,
        create_preset_bar,
    )
    from scartools.ui.theme import (
        THEMES,
        get_available_themes,
        get_active_theme,
        set_active_theme,
        get_theme_stylesheet,
    )
    from scartools.framework.benchmark import ExecutionTimer, time_operation
    import maya.cmds as cmds
    if cmds.about(batch=True):
        QT_AVAILABLE = False
    else:
        QT_AVAILABLE = True
except Exception as e:
    QT_AVAILABLE = False


class TestUIExtensions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QT_AVAILABLE:
            cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_benchmark_timer(self):
        with ExecutionTimer(operation_name="UnitTestOp", item_count=50) as timer:
            x = sum(i for i in range(1000))
        self.assertGreaterEqual(timer.elapsed_ms, 0.0)
        self.assertIn("UnitTestOp", timer.summary_text())
        self.assertIn("50 item(s)", timer.summary_text())

    def test_multi_theme_engine(self):
        themes = get_available_themes()
        self.assertIn("dark_studio", themes)
        self.assertIn("cyber_obsidian", themes)
        self.assertIn("slate_blue", themes)
        self.assertIn("maya_match", themes)

        set_active_theme("cyber_obsidian")
        self.assertEqual(get_active_theme(), "cyber_obsidian")
        qss = get_theme_stylesheet("cyber_obsidian")
        self.assertIn("#0C0D11", qss)

        # Reset back to dark_studio
        set_active_theme("dark_studio")
        self.assertEqual(get_active_theme(), "dark_studio")

    def test_preset_manager(self):
        pm = PresetManager("test_tool")
        data = {"tolerance": 0.05, "mode": "mirror"}
        self.assertTrue(pm.save_preset("unit_test_preset", data))
        self.assertIn("unit_test_preset", pm.list_presets())

        loaded = pm.load_preset("unit_test_preset")
        self.assertEqual(loaded, data)

        self.assertTrue(pm.delete_preset("unit_test_preset"))
        self.assertNotIn("unit_test_preset", pm.list_presets())

    @unittest.skipUnless(QT_AVAILABLE, "Qt is not available in standalone Python")
    def test_vector3_input(self):
        v = create_vector3_input(1.0, 2.5, -3.0)
        self.assertEqual(v.value(), (1.0, 2.5, -3.0))
        v.set_value(0.0, 10.0, 20.0)
        self.assertEqual(v.value(), (0.0, 10.0, 20.0))
        v.reset_to_zero()
        self.assertEqual(v.value(), (0.0, 0.0, 0.0))

    @unittest.skipUnless(QT_AVAILABLE, "Qt is not available in standalone Python")
    def test_path_picker(self):
        p = create_path_picker(placeholder="Custom path...")
        self.assertEqual(p.path(), "")
        p.set_path("C:/Test/Path.fbx")
        self.assertEqual(p.path(), "C:/Test/Path.fbx")

    @unittest.skipUnless(QT_AVAILABLE, "Qt is not available in standalone Python")
    def test_uv_tile_grid(self):
        grid = create_uv_tile_grid(u_count=10, v_count=4)
        self.assertEqual(grid.selected_udims(), [])
        grid.set_selected_udims([1001, 1002, 1011])
        self.assertEqual(grid.selected_udims(), [1001, 1002, 1011])
        grid.set_tile_state(1001, "active")
        grid.set_tile_state(1002, "missing")

    @unittest.skipUnless(QT_AVAILABLE, "Qt is not available in standalone Python")
    def test_curve_editor(self):
        ce = create_curve_editor()
        ce.set_preset("linear")
        self.assertAlmostEqual(ce.evaluate(0.0), 0.0, places=2)
        self.assertAlmostEqual(ce.evaluate(0.5), 0.5, places=2)
        self.assertAlmostEqual(ce.evaluate(1.0), 1.0, places=2)

    @unittest.skipUnless(QT_AVAILABLE, "Qt is not available in standalone Python")
    def test_token_input(self):
        ti = create_token_input()
        self.assertEqual(ti.tags(), [])
        ti.add_tag("#hero")
        ti.add_tag("#lod0")
        self.assertEqual(ti.tags(), ["#hero", "#lod0"])

    @unittest.skipUnless(QT_AVAILABLE, "Qt is not available in standalone Python")
    def test_step_wizard(self):
        wiz = create_step_wizard(["Mesh", "QA", "Fix", "Export"], current=0)
        self.assertEqual(wiz.current_step(), 0)
        wiz.set_current_step(2)
        self.assertEqual(wiz.current_step(), 2)


if __name__ == "__main__":
    unittest.main()
