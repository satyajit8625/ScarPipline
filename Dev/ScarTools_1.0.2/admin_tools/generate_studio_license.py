#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ScarTools Studio License Key Generator (Admin Tool).

Use this tool to generate cryptographic, hardware-locked single-seat
license keys for artists, departments, or freelance contractors.

Usage CLI:
    python generate_studio_license.py --user john.doe --hwid HW-8F92-4B11 --perpetual
    python generate_studio_license.py --user contractor --hwid HW-8F92-4B11 --days 90

Usage Interactive:
    python generate_studio_license.py
"""

from __future__ import absolute_import, division, print_function

import argparse
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SCARTOOLS_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "scripts", "scartools")
if not os.path.isdir(SCARTOOLS_DIR):
    SCARTOOLS_DIR = os.path.join(CURRENT_DIR, "scripts", "scartools")
if SCARTOOLS_DIR not in sys.path:
    sys.path.insert(0, SCARTOOLS_DIR)

try:
    from licensing import generate_license_key, validate_license_key, get_machine_hardware_id
except ImportError:
    import licensing
    generate_license_key = licensing.generate_license_key
    validate_license_key = licensing.validate_license_key
    get_machine_hardware_id = licensing.get_machine_hardware_id


def main():
    parser = argparse.ArgumentParser(
        description="ScarTools 1.0.0 Hardware-Locked Studio License Generator"
    )

    parser.add_argument(
        "--user", "-u",
        help="Artist Username or Email (e.g. 'john.doe' or 'john@studio.com')"
    )
    parser.add_argument(
        "--hwid", "-w",
        help="Target Machine Hardware ID (e.g. 'HW-8F92-4B11' or 'ANY')"
    )
    parser.add_argument(
        "--days", "-d",
        type=float,
        default=0.0,
        help="Days valid from today (e.g. 1, 30, 90)"
    )
    parser.add_argument(
        "--hours", "-H",
        type=float,
        default=0.0,
        help="Hours valid from now (e.g. 2, 8, 24)"
    )
    parser.add_argument(
        "--minutes", "-m",
        type=float,
        default=0.0,
        help="Minutes valid from now (e.g. 15, 30, 45)"
    )
    parser.add_argument(
        "--duration",
        help="Duration string (e.g. '30m' for 30 mins, '2h' for 2 hours, '1d' for 1 day)"
    )
    parser.add_argument(
        "--perpetual", "-p",
        action="store_true",
        help="Generate a perpetual license (no expiry)"
    )

    args = parser.parse_args()

    user_id = args.user
    hardware_id = args.hwid
    duration_str = args.duration
    days_val = args.days
    hours_val = args.hours
    mins_val = args.minutes

    if not user_id:
        print("=" * 65)
        print("  [SCARTOOLS STUDIO LICENSE GENERATOR (ADMIN)]")
        print("=" * 65)
        local_hwid = get_machine_hardware_id()
        print("  Current Machine HWID: {}\n".format(local_hwid))

        try:
            user_id = input("Enter Artist Username / Studio ID (e.g. john.doe): ").strip()
        except EOFError:
            user_id = "studio_artist"

        if not user_id:
            print("Error: Username cannot be empty.")
            sys.exit(1)

        try:
            hwid_input = input("Enter Artist Machine HWID (or press Enter for this PC '{}'): ".format(local_hwid)).strip()
            hardware_id = hwid_input if hwid_input else local_hwid
        except EOFError:
            hardware_id = local_hwid

        try:
            dur_input = input("Enter Validity (e.g. '30m' for 30 mins, '2h' for 2 hours, '1d' for 1 day, or '0' for Perpetual): ").strip()
            duration_str = dur_input if dur_input else "0"
        except (ValueError, EOFError):
            duration_str = "0"
    else:
        if args.perpetual:
            duration_str = "0"
            days_val = 0
            hours_val = 0
            mins_val = 0
        if not hardware_id:
            hardware_id = get_machine_hardware_id()

    try:
        key = generate_license_key(
            user_id=user_id,
            hardware_id=hardware_id,
            days_valid=days_val,
            hours_valid=hours_val,
            minutes_valid=mins_val,
            duration=duration_str
        )
        is_valid, msg, details = validate_license_key(user_id, key, current_hardware_id=hardware_id, check_central=False)

        print("\n" + "=" * 65)
        print("  [OK] HARDWARE-LOCKED LICENSE GENERATED SUCCESSFULLY")
        print("=" * 65)
        print("  Artist / User ID   : {}".format(details.get("user_id", user_id)))
        print("  Hardware ID (HWID) : {}".format(details.get("hardware_id", hardware_id)))
        print("  License Key        : {}".format(key))
        print("  Validity           : {}".format(details.get("expiry_date", "Perpetual")))
        print("=" * 65)
        print("\nNote: This key is cryptographically locked to hardware '{}'.".format(details["hardware_id"]))
        print("It will NOT work if copied to any other laptop or PC.\n")

        # Auto-register in Studio Master Registry
        try:
            from manage_licenses import register_license
            register_license(
                user_id=details["user_id"],
                hardware_id=details["hardware_id"],
                license_key=key,
                expiry_date=details["expiry_date"],
                notes="Generated via admin tool"
            )
            print("[INFO] License logged to central studio registry (manage_licenses.py).")
        except Exception:
            pass

    except Exception as exc:
        print("Error generating license: {}".format(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
