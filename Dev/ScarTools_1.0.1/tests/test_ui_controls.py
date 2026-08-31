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
    from scartools.ui.controls import (
        SegmentedControl,
        create_segmented_control,
        ToggleSwitch,
        create_toggle_switch,
        LabeledSlider,
        create_labeled_slider,
        MultiSelectComboBox,
    )
    import maya.cmds as cmds
    if cmds.about(batch=True):
        QT_AVAILABLE = False
    else:
        QT_AVAILABLE = True
except Exception:
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE, "Qt is not available in standalone Python")
class TestUIControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QT_AVAILABLE:
            cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_segmented_control(self):
        ctrl = create_segmented_control(["Local", "World"], current=0, accent="primary")
        self.assertEqual(ctrl.current_index(), 0)
        self.assertEqual(ctrl.current_text(), "Local")

        ctrl.set_current_index(1)
        self.assertEqual(ctrl.current_index(), 1)
        self.assertEqual(ctrl.current_text(), "World")

        ctrl.set_current_text("Local")
        self.assertEqual(ctrl.current_index(), 0)

    def test_toggle_switch(self):
        sw = create_toggle_switch("Normalize Weights", checked=False, accent="pipeline")
        self.assertFalse(sw.is_checked())

        sw.set_checked(True)
        self.assertTrue(sw.is_checked())

    def test_labeled_slider(self):
        sl = create_labeled_slider("Tolerance", minimum=0.0, maximum=1.0, value=0.05, step=0.01, decimals=2)
        self.assertAlmostEqual(sl.value(), 0.05, places=2)

        sl.set_value(0.25)
        self.assertAlmostEqual(sl.value(), 0.25, places=2)

    def test_multiselect_combo(self):
        combo = MultiSelectComboBox()
        combo.add_items(["mesh_A", "mesh_B", "mesh_C"])
        self.assertEqual(combo.checked_items(), [])

        combo.set_checked_items(["mesh_A", "mesh_C"])
        self.assertEqual(combo.checked_items(), ["mesh_A", "mesh_C"])

    def test_create_stat_card(self):
        from scartools.ui import create_stat_card
        card, labels = create_stat_card([
            ("Active Shot:", "PRT_SH_020", "primary"),
            ("Project:", "PRT", "blue"),
        ])
        self.assertIsNotNone(card)
        self.assertIn("Active Shot:", labels)
        self.assertEqual(labels["Active Shot:"].text(), "PRT_SH_020")
        self.assertIn("Project:", labels)
        self.assertEqual(labels["Project:"].text(), "PRT")

    def test_create_popup_menu(self):
        from scartools.ui import create_popup_menu, ScarPopupMenu
        menu = create_popup_menu()
        self.assertIsInstance(menu, ScarPopupMenu)
        act1 = menu.addAction("◇  Alembic Settings…")
        act2 = menu.addAction("◇  FBX Settings…")
        menu.addSeparator()
        act3 = menu.addAction("↻  Reset to Default")
        self.assertEqual(len(menu.actions()), 4)


if __name__ == "__main__":
    unittest.main()
