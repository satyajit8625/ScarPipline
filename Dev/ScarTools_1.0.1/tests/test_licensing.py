# -*- coding: utf-8 -*-
"""Unit tests for ScarTools cryptographic licensing and hardware-locked authentication."""

from __future__ import absolute_import, division, print_function

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_release import install_maya_stubs
install_maya_stubs()

from scartools.licensing import (
    generate_license_key,
    validate_license_key,
    save_license,
    get_installed_license,
    is_activated,
    revoke_license,
    get_machine_hardware_id,
)


class TestLicensing(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get("USERPROFILE") or os.environ.get("HOME")
        if "USERPROFILE" in os.environ:
            os.environ["USERPROFILE"] = self.test_dir
        if "HOME" in os.environ:
            os.environ["HOME"] = self.test_dir

    def tearDown(self):
        if self.original_home:
            if "USERPROFILE" in os.environ:
                os.environ["USERPROFILE"] = self.original_home
            if "HOME" in os.environ:
                os.environ["HOME"] = self.original_home
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_hardware_id_generation(self):
        hwid = get_machine_hardware_id()
        self.assertTrue(hwid.startswith("HW-"))
        self.assertGreaterEqual(len(hwid), 6)

    def test_perpetual_license_generation_and_validation(self):
        user_id = "john.doe"
        hwid = "HW-TEST1234"
        key = generate_license_key(user_id=user_id, hardware_id=hwid, days_valid=0)

        self.assertTrue(key.startswith("SCAR-"))
        self.assertEqual(len(key.split("-")), 5)

        is_valid, msg, details = validate_license_key(user_id, key, current_hardware_id=hwid)
        self.assertTrue(is_valid, msg)
        self.assertTrue(details["is_perpetual"])
        self.assertEqual(details["user_id"], "john.doe")
        self.assertEqual(details["hardware_id"], "HW-TEST1234")
        self.assertEqual(details["expiry_date"], "Perpetual (No Expiry)")

    def test_hardware_lock_rejection_on_different_machine(self):
        user_id = "artist_rig"
        machine_a_hwid = "HW-AAAA1111"
        machine_b_hwid = "HW-BBBB2222"

        # Generate key for Machine A
        key_a = generate_license_key(user_id=user_id, hardware_id=machine_a_hwid)

        # Machine A must pass
        is_valid_a, msg_a, _ = validate_license_key(user_id, key_a, current_hardware_id=machine_a_hwid)
        self.assertTrue(is_valid_a, msg_a)

        # Trying to use Machine A's key on Machine B must FAIL!
        is_valid_b, msg_b, _ = validate_license_key(user_id, key_a, current_hardware_id=machine_b_hwid)
        self.assertFalse(is_valid_b)
        self.assertIn("hardware", msg_b.lower())

    def test_timed_license_generation_and_validation(self):
        user_id = "contractor@vfx.com"
        hwid = "HW-CONT9999"
        key = generate_license_key(user_id=user_id, hardware_id=hwid, days_valid=30)

        is_valid, msg, details = validate_license_key(user_id, key, current_hardware_id=hwid)
        self.assertTrue(is_valid, msg)
        self.assertFalse(details["is_perpetual"])
        self.assertGreater(details["expiry_timestamp"], int(time.time()))

    def test_hours_and_minutes_license_generation_and_validation(self):
        user_id = "temp_contractor"
        hwid = "HW-TEMP1234"

        # 1. Test 2 Hours lease
        key_h = generate_license_key(user_id=user_id, hardware_id=hwid, hours_valid=2)
        is_valid_h, msg_h, details_h = validate_license_key(user_id, key_h, current_hardware_id=hwid)
        self.assertTrue(is_valid_h, msg_h)
        self.assertFalse(details_h["is_perpetual"])
        self.assertAlmostEqual(details_h["expiry_timestamp"] - int(time.time()), 7200, delta=5)

        # 2. Test 30 Minutes lease via duration string "30m"
        key_m = generate_license_key(user_id=user_id, hardware_id=hwid, duration="30m")
        is_valid_m, msg_m, details_m = validate_license_key(user_id, key_m, current_hardware_id=hwid)
        self.assertTrue(is_valid_m, msg_m)
        self.assertFalse(details_m["is_perpetual"])
        self.assertAlmostEqual(details_m["expiry_timestamp"] - int(time.time()), 1800, delta=5)

    def test_invalid_user_rejection(self):
        user_a = "artist_a"
        user_b = "artist_b"
        hwid = get_machine_hardware_id()
        key_a = generate_license_key(user_id=user_a, hardware_id=hwid)

        # Trying to use artist_a's key on artist_b
        is_valid, msg, _ = validate_license_key(user_b, key_a, current_hardware_id=hwid)
        self.assertFalse(is_valid)
        self.assertIn("match", msg.lower())

    def test_tampered_key_rejection(self):
        user_id = "modeler_lead"
        hwid = get_machine_hardware_id()
        key = generate_license_key(user_id=user_id, hardware_id=hwid)

        # Tamper with the signature portion
        parts = key.split("-")
        parts[-1] = "DEADBEEF00000000"
        tampered_key = "-".join(parts)

        is_valid, msg, _ = validate_license_key(user_id, tampered_key, current_hardware_id=hwid)
        self.assertFalse(is_valid)
        self.assertIn("match", msg.lower())

    def test_save_and_read_installed_license(self):
        user_id = "anim_lead"
        hwid = get_machine_hardware_id()
        key = generate_license_key(user_id=user_id, hardware_id=hwid)

        self.assertFalse(is_activated())

        save_license(user_id, key)
        self.assertTrue(is_activated())

        is_valid, _, details = get_installed_license()
        self.assertTrue(is_valid)
        self.assertEqual(details["user_id"], "anim_lead")

        # Test revoke / deactivation
        revoke_license()
        self.assertFalse(is_activated())

    def test_clock_tampering_rollback_detection(self):
        user_id = "timed_user"
        hwid = get_machine_hardware_id()
        key = generate_license_key(user_id=user_id, hardware_id=hwid, days_valid=30)
        save_license(user_id, key)

        # Manually alter the activation timestamp to simulate system clock being set backwards in time
        lic_file = self.test_dir + "/.scartools_license.json"
        with open(lic_file, "r") as f:
            data = json.load(f)
        data["activated_at_epoch"] = int(time.time()) + 100000  # Set future activation date
        with open(lic_file, "w") as f:
            json.dump(data, f)

        is_valid, msg, _ = get_installed_license()
        self.assertFalse(is_valid)
        self.assertIn("clock", msg.lower())

    def test_tool_controller_blocks_when_unlicensed(self):
        from scartools.framework.controller import ToolController
        revoke_license()

        controller = ToolController("test_tool")
        executed = []

        def sample_op():
            executed.append(True)
            return "done"

        result = controller.run("sample_op", sample_op)
        self.assertFalse(result.success)
        self.assertTrue(any(m.code == "unlicensed" for m in result.messages))
        self.assertEqual(len(executed), 0)

    def test_session_token_and_anti_tamper(self):
        from scartools.licensing import (
            LicenseSessionToken,
            verify_session_token,
            require_license,
        )
        # Unlicensed raises RuntimeError
        revoke_license()
        with self.assertRaises(RuntimeError):
            require_license("test_op")

        # Valid license returns authentic session token
        hwid = get_machine_hardware_id()
        key = generate_license_key("artist_token_test", hwid)
        save_license("artist_token_test", key)

        token = require_license("test_op")
        self.assertTrue(verify_session_token(token))
        self.assertTrue(isinstance(token, LicenseSessionToken))
        self.assertTrue(token.is_valid())

        # Spoofed/monkeypatched primitive values must fail verification
        self.assertFalse(verify_session_token(True))
        self.assertFalse(verify_session_token(1))
        self.assertFalse(verify_session_token("valid_token"))
        self.assertFalse(verify_session_token(None))

    def test_central_registry_revocation_and_reinstatement(self):
        user_id = "revoked_user"
        hwid = get_machine_hardware_id()
        key = generate_license_key(user_id, hwid)

        # Create a mock central registry file in test_dir
        registry_file = os.path.join(self.test_dir, "studio_licenses_registry.json")
        os.environ["SCARTOOLS_LICENSE_REGISTRY"] = registry_file

        try:
            # 1. Register as Active
            with open(registry_file, "w") as fp:
                json.dump([{
                    "user_id": user_id,
                    "hardware_id": hwid,
                    "license_key": key,
                    "status": "Active"
                }], fp)

            save_license(user_id, key)
            self.assertTrue(is_activated())

            # 2. Mark as Revoked in central registry
            with open(registry_file, "w") as fp:
                json.dump([{
                    "user_id": user_id,
                    "hardware_id": hwid,
                    "license_key": key,
                    "status": "Revoked",
                    "revoked_at": "2026-08-27 12:00:00"
                }], fp)

            # Verification must now FAIL with revoked status
            is_valid, msg, details = get_installed_license()
            self.assertFalse(is_valid)
            self.assertTrue(details.get("revoked", False))
            self.assertIn("revoked", msg.lower())

            # 3. Local token must be auto-purged
            self.assertFalse(is_activated())

            # 4. Reinstate back to Active in central registry
            with open(registry_file, "w") as fp:
                json.dump([{
                    "user_id": user_id,
                    "hardware_id": hwid,
                    "license_key": key,
                    "status": "Active",
                    "reinstated_at": "2026-08-27 12:05:00"
                }], fp)

            # Re-activating must now succeed
            save_license(user_id, key)
            self.assertTrue(is_activated())

        finally:
            os.environ.pop("SCARTOOLS_LICENSE_REGISTRY", None)

    def test_central_registry_delete_kill_switch(self):
        user_id = "purge_user"
        hwid = get_machine_hardware_id()
        key = generate_license_key(user_id, hwid)

        registry_file = os.path.join(self.test_dir, "studio_licenses_registry.json")
        os.environ["SCARTOOLS_LICENSE_REGISTRY"] = registry_file

        try:
            # 1. Register and activate
            with open(registry_file, "w") as fp:
                json.dump([{
                    "user_id": user_id,
                    "hardware_id": hwid,
                    "license_key": key,
                    "status": "Active"
                }], fp)

            save_license(user_id, key)
            self.assertTrue(is_activated())

            # 2. Trigger Delete (Hard Kill-Switch via Allowlist Removal)
            with open(registry_file, "w") as fp:
                json.dump([], fp)

            # Verification must trigger remote wipe and report deleted
            is_valid, msg, details = get_installed_license(force_check=True)
            self.assertFalse(is_valid)
            self.assertTrue(details.get("deleted", False))
            self.assertEqual(details.get("action"), "delete")
            self.assertFalse(is_activated())

        finally:
            os.environ.pop("SCARTOOLS_LICENSE_REGISTRY", None)

    def test_15_day_offline_heartbeat_expiration(self):
        user_id = "heartbeat_user"
        hwid = get_machine_hardware_id()
        key = generate_license_key(user_id, hwid)
        save_license(user_id, key)
        self.assertTrue(is_activated())

        # Simulate 16 days offline (last sync 16 days ago)
        lic_file = os.path.join(self.test_dir, ".scartools_license.json")
        with open(lic_file, "r") as f:
            data = json.load(f)
        data["last_online_sync"] = int(time.time()) - (16 * 86400)
        data["activated_at_epoch"] = int(time.time()) - (20 * 86400)
        with open(lic_file, "w") as f:
            json.dump(data, f)

        # Must fail and trigger wipe due to offline heartbeat limit
        is_valid, msg, details = get_installed_license(force_check=True)
        self.assertFalse(is_valid)
        self.assertTrue(details.get("heartbeat_expired", False))
        self.assertIn("heartbeat", msg.lower())


if __name__ == "__main__":
    unittest.main()



