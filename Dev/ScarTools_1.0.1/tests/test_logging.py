# -*- coding: utf-8 -*-
"""Unit tests for Centralized Logging and GlobalLogStore."""

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

from scartools.framework.logging import (
    GlobalLogStore,
    LogEntry,
    detect_level,
    emit_log,
    log_store,
    LEVEL_INFO,
    LEVEL_SUCCESS,
    LEVEL_WARNING,
    LEVEL_ERROR,
)


class TestGlobalLogging(unittest.TestCase):

    def setUp(self):
        self.store = log_store()
        self.store.clear()

    def tearDown(self):
        self.store.clear()

    def test_semantic_detection(self):
        self.assertEqual(detect_level("ERROR: ❌ Missing Tile Gaps"), LEVEL_ERROR)
        self.assertEqual(detect_level("CRITICAL: Non-manifold topology found"), LEVEL_ERROR)
        self.assertEqual(detect_level("FAILED: Export failed"), LEVEL_ERROR)
        self.assertEqual(detect_level("WARNING: ⚠️ 3 issues detected"), LEVEL_WARNING)
        self.assertEqual(detect_level("SKIPPED: Mesh has no skin cluster"), LEVEL_WARNING)
        self.assertEqual(detect_level("SUCCESS: ✓ All 26 checks passed"), LEVEL_SUCCESS)
        self.assertEqual(detect_level("DONE: Applied 150 shader assignments"), LEVEL_SUCCESS)
        self.assertEqual(detect_level("INFO: Scanning 5 file texture nodes..."), LEVEL_INFO)

    def test_emit_and_counts(self):
        emit_log("INFO: Started scan", source="UDIM Manager")
        emit_log("WARNING: ⚠️ Texture missing", source="Shader Tools")
        emit_log("ERROR: ❌ Skin bind failed", source="Skin Tools")
        emit_log("SUCCESS: ✓ Renamed 10 nodes", source="Renamer")

        counts = self.store.get_counts()
        self.assertEqual(counts["all"], 4)
        self.assertEqual(counts[LEVEL_INFO], 1)
        self.assertEqual(counts[LEVEL_WARNING], 1)
        self.assertEqual(counts[LEVEL_ERROR], 1)
        self.assertEqual(counts[LEVEL_SUCCESS], 1)

    def test_filter_by_level(self):
        emit_log("INFO: 1", source="ToolA")
        emit_log("ERROR: ❌ 2", source="ToolB")
        emit_log("ERROR: ❌ 3", source="ToolA")

        errors = self.store.get_entries(level=LEVEL_ERROR)
        self.assertEqual(len(errors), 2)
        for e in errors:
            self.assertEqual(e.level, LEVEL_ERROR)

    def test_filter_by_source(self):
        emit_log("INFO: Msg 1", source="UDIM Manager")
        emit_log("INFO: Msg 2", source="Shader Tools")
        emit_log("SUCCESS: Msg 3", source="UDIM Manager")

        udim_entries = self.store.get_entries(source="UDIM Manager")
        self.assertEqual(len(udim_entries), 2)
        for e in udim_entries:
            self.assertEqual(e.source, "UDIM Manager")

    def test_search_filter(self):
        emit_log("SUCCESS: ✓ Pirate_Ship_SG_BaseColor loaded", source="UDIM Manager")
        emit_log("INFO: Cloth_SG_BaseColor single texture", source="UDIM Manager")
        emit_log("ERROR: ❌ Camera missing", source="Renamer")

        results = self.store.get_entries(query="pirate_ship")
        self.assertEqual(len(results), 1)
        self.assertIn("Pirate_Ship", results[0].message)

    def test_subscriber_event_stream(self):
        received = []

        def on_log(entry):
            if entry:
                received.append(entry)

        self.store.subscribe(on_log)
        try:
            emit_log("INFO: Realtime message", source="TestRunner")
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0].source, "TestRunner")
            self.assertEqual(received[0].message, "INFO: Realtime message")
        finally:
            self.store.unsubscribe(on_log)


if __name__ == "__main__":
    unittest.main()
