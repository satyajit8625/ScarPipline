# -*- coding: utf-8 -*-
"""
ScarTools Studio Central License Registry and Audit Manager (Admin Only).

Usage:
    python manage_licenses.py --list
    python manage_licenses.py --local
    python manage_licenses.py --export-csv studio_license_audit.csv
"""

from __future__ import absolute_import, division, print_function

import argparse
import csv
import json
import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_ROOT = os.path.dirname(CURRENT_DIR)
SCARTOOLS_DIR = os.path.join(DEV_ROOT, "scripts", "scartools")
if SCARTOOLS_DIR not in sys.path:
    sys.path.insert(0, SCARTOOLS_DIR)

REGISTRY_FILE = os.path.join(CURRENT_DIR, "studio_licenses_registry.json")

try:
    from licensing import (
        validate_license_key,
        get_machine_hardware_id,
        get_installed_license,
        generate_license_key,
    )
except ImportError:
    import licensing
    validate_license_key = licensing.validate_license_key
    get_machine_hardware_id = licensing.get_machine_hardware_id
    get_installed_license = licensing.get_installed_license
    generate_license_key = licensing.generate_license_key


def load_registry():
    """Load the master studio license registry from disk."""
    if not os.path.isfile(REGISTRY_FILE):
        return []
    try:
        with open(REGISTRY_FILE, "r") as fp:
            data = json.load(fp)
            return data if isinstance(data, list) else []
    except Exception as exc:
        print("[WARNING] Could not read license registry:", exc)
        return []


def save_registry(records):
    """Save the master studio license registry to disk."""
    with open(REGISTRY_FILE, "w") as fp:
        json.dump(records, fp, indent=2)


def register_license(user_id, hardware_id, license_key, expiry_date, department="General", notes=""):
    """Add or update a license record in the central registry."""
    records = load_registry()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    updated = False
    clean_user = (user_id or "").strip().lower()
    clean_hwid = (hardware_id or "").strip().upper()
    clean_key = (license_key or "").strip().upper()

    for r in records:
        r_user = (r.get("user_id") or "").strip().lower()
        r_hwid = (r.get("hardware_id") or "").strip().upper()
        r_key = (r.get("license_key") or "").strip().upper()

        if r_key == clean_key or r_user == clean_user or (r_hwid == clean_hwid and clean_hwid != "ANY"):
            r["user_id"] = user_id
            r["hardware_id"] = hardware_id
            r["license_key"] = license_key
            r["expiry_date"] = expiry_date
            r["department"] = department
            r["notes"] = notes
            r["updated_at"] = now_str
            r["status"] = "Active"
            r.pop("deleted_at", None)
            r.pop("revoked_at", None)
            updated = True
            break

    if not updated:
        records.append({
            "user_id": user_id,
            "hardware_id": hardware_id,
            "license_key": license_key,
            "expiry_date": expiry_date,
            "department": department,
            "notes": notes,
            "issued_at": now_str,
            "status": "Active"
        })

    save_registry(records)


def list_licenses():
    """Display a clean formatted table of all registered studio licenses."""
    records = load_registry()

    print("\n" + "=" * 90)
    print("  SCARTOOLS MASTER STUDIO LICENSE REGISTRY (ADMIN AUDIT)")
    print("=" * 90)

    if not records:
        print("  No licenses found in registry.")
        print("  Generate new keys with: python generate_studio_license.py")
        print("=" * 90 + "\n")
        return

    header = "{:<4} {:<15} {:<13} {:<11} {:<22} {:<20}".format(
        "#", "USER ID", "HWID", "STATUS", "EXPIRY", "LICENSE KEY"
    )
    print(header)
    print("-" * 95)

    active_count = 0
    revoked_count = 0
    deleted_count = 0
    expired_count = 0

    for idx, r in enumerate(records, 1):
        user = r.get("user_id", "N/A")
        hwid = r.get("hardware_id", "N/A")
        expiry = r.get("expiry_date", "Perpetual")
        key = r.get("license_key", "")
        reg_status = r.get("status", "Active")

        if reg_status in ["Deleted", "Purged", "Wiped"]:
            status_tag = "[DELETED/WIPE]"
            deleted_count += 1
        elif reg_status == "Revoked":
            status_tag = "[REVOKED]"
            revoked_count += 1
        else:
            is_valid, msg, _ = validate_license_key(user, key, current_hardware_id=hwid, check_central=False)
            if is_valid:
                status_tag = "[ACTIVE]"
                active_count += 1
            else:
                status_tag = "[EXPIRED]"
                expired_count += 1

        print("{:<4} {:<15} {:<13} {:<15} {:<20} {:<20}".format(
            idx, user[:14], hwid[:12], status_tag, expiry[:19], key[:19] + "..."
        ))

    print("-" * 95)
    print("TOTAL SEATS: {} | ACTIVE: {} | REVOKED: {} | DELETED: {} | EXPIRED: {}".format(
        len(records), active_count, revoked_count, deleted_count, expired_count
    ))
    print("=" * 95 + "\n")


def export_csv(output_path):
    """Export the master license registry to CSV."""
    records = load_registry()
    if not records:
        print("Registry is empty. Nothing to export.")
        return

    keys = ["user_id", "hardware_id", "license_key", "expiry_date", "department", "notes", "issued_at", "status"]
    with open(output_path, "w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=keys)
        writer.writeheader()
        for r in records:
            row = {k: r.get(k, "") for k in keys}
            writer.writerow(row)

    print("[OK] Exported {} license records to '{}'.".format(len(records), output_path))


def inspect_local_workstation():
    """Inspect the current workstation's installed license."""
    print("\n" + "=" * 65)
    print("  LOCAL WORKSTATION LICENSE INSPECTION")
    print("=" * 65)
    hwid = get_machine_hardware_id()
    print("  Current PC HWID  : {}".format(hwid))

    is_valid, msg, details = get_installed_license()
    if is_valid:
        print("  Status           : [ACTIVE] VALID")
        print("  Licensed User    : {}".format(details.get("user_id")))
        print("  Locked HWID      : {}".format(details.get("hardware_id")))
        print("  Validity         : {}".format(details.get("expiry_date")))
        print("  Activated At     : {}".format(details.get("activated_at")))
        print("  License Key      : {}".format(details.get("license_key")))
    else:
        print("  Status           : [INACTIVE / UNLICENSED]")
        print("  Message          : {}".format(msg))
    print("=" * 65 + "\n")


def deactivate_local():
    """Remove license file from the local workstation."""
    lic_file = os.path.expanduser("~/.scartools_license.json")
    if os.path.isfile(lic_file):
        try:
            os.remove(lic_file)
            print("\n[OK] Local workstation license deactivated successfully.")
            print("File removed: '{}'\n".format(lic_file))
            return True
        except Exception as exc:
            print("\n[FAIL] Could not remove license file: {}\n".format(exc))
            return False
    else:
        print("\n[INFO] No active license was found on this workstation.\n")
        return True


def revoke_license_entry(user_id=None, hwid=None, key=None):
    """Mark a license as Revoked (Soft Lock) in the master registry."""
    records = load_registry()
    matched = 0
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    for r in records:
        match_u = user_id and r.get("user_id", "").lower() == user_id.strip().lower()
        match_h = hwid and r.get("hardware_id", "").upper() == hwid.strip().upper()
        match_k = key and r.get("license_key", "").upper() == key.strip().upper()

        if match_u or match_h or match_k:
            r["status"] = "Revoked"
            r["revoked_at"] = now_str
            matched += 1

    if matched > 0:
        save_registry(records)
        print("\n[OK] Revoked {} license record(s) in master registry (Soft Lock).\n".format(matched))
    else:
        print("\n[WARNING] No matching license records found to revoke.\n")


def delete_license_entry(user_id=None, hwid=None, key=None):
    """Delete a user/seat from the master allowlist registry (triggers Remote File Wipe in Maya)."""
    records = load_registry()
    initial_len = len(records)
    filtered = []
    for r in records:
        match_u = user_id and r.get("user_id", "").lower() == user_id.strip().lower()
        match_h = hwid and r.get("hardware_id", "").upper() == hwid.strip().upper()
        match_k = key and r.get("license_key", "").upper() == key.strip().upper()
        if not (match_u or match_h or match_k):
            filtered.append(r)

    removed = initial_len - len(filtered)
    if removed > 0:
        save_registry(filtered)
        print("\n[OK] Removed {} license record(s) from allowlist.".format(removed))
        print("  [KILL-SWITCH ACTIVE] When Maya connects, it will detect removal and trigger a Remote Wipe.\n")
    else:
        print("\n[WARNING] No matching license records found to delete.\n")


def reinstate_license_entry(user_id=None, hwid=None, key=None):
    """Reactivate a previously Revoked or Deleted license in the master registry."""
    records = load_registry()
    matched = 0
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    for r in records:
        match_u = user_id and r.get("user_id", "").lower() == user_id.strip().lower()
        match_h = hwid and r.get("hardware_id", "").upper() == hwid.strip().upper()
        match_k = key and r.get("license_key", "").upper() == key.strip().upper()

        if match_u or match_h or match_k:
            r["status"] = "Active"
            r["reinstated_at"] = now_str
            matched += 1

    if matched > 0:
        save_registry(records)
        print("\n[OK] Reinstated {} license record(s) to Active status.\n".format(matched))
    else:
        print("\n[WARNING] No matching license records found to reinstate.\n")


def remove_license_entry(user_id=None, hwid=None, key=None):
    """Completely remove a license record from the master registry JSON."""
    records = load_registry()
    initial_len = len(records)

    filtered = []
    for r in records:
        match_u = user_id and r.get("user_id", "").lower() == user_id.strip().lower()
        match_h = hwid and r.get("hardware_id", "").upper() == hwid.strip().upper()
        match_k = key and r.get("license_key", "").upper() == key.strip().upper()

        if not (match_u or match_h or match_k):
            filtered.append(r)

    removed = initial_len - len(filtered)
    if removed > 0:
        save_registry(filtered)
        print("\n[OK] Permanently removed {} license record(s) from registry.\n".format(removed))
    else:
        print("\n[WARNING] No matching license records found to remove.\n")


def clear_deleted_entries():
    """Remove all records marked as [DELETED] from the registry."""
    records = load_registry()
    initial_len = len(records)
    filtered = [r for r in records if r.get("status", "").lower() not in ["deleted", "purged", "wiped"]]
    removed = initial_len - len(filtered)
    if removed > 0:
        save_registry(filtered)
        print("\n[OK] Purged {} DELETED license record(s) from registry.\n".format(removed))
    else:
        print("\n[INFO] No deleted records to purge.\n")


def main():
    parser = argparse.ArgumentParser(description="ScarTools Master Studio License Registry Manager")
    parser.add_argument("--list", "-l", action="store_true", help="List all studio licenses in the registry")
    parser.add_argument("--local", action="store_true", help="Inspect local machine license status")
    parser.add_argument("--deactivate-local", action="store_true", help="Deactivate and remove local license on this PC")
    parser.add_argument("--revoke-user", metavar="USER", help="Revoke all licenses assigned to a specific user (Soft Lock)")
    parser.add_argument("--revoke-hwid", metavar="HWID", help="Revoke all licenses locked to a specific HWID (Soft Lock)")
    parser.add_argument("--revoke-key", metavar="KEY", help="Revoke a specific license key (Soft Lock)")
    parser.add_argument("--delete-user", "--purge-user", metavar="USER", help="Delete and trigger Remote File Wipe for a user")
    parser.add_argument("--delete-hwid", "--purge-hwid", metavar="HWID", help="Delete and trigger Remote File Wipe for a HWID")
    parser.add_argument("--delete-key", "--purge-key", metavar="KEY", help="Delete and trigger Remote File Wipe for a license key")
    parser.add_argument("--remove-user", metavar="USER", help="Permanently remove a user from the registry file")
    parser.add_argument("--remove-hwid", metavar="HWID", help="Permanently remove a HWID from the registry file")
    parser.add_argument("--remove-key", metavar="KEY", help="Permanently remove a license key from the registry file")
    parser.add_argument("--clear-deleted", action="store_true", help="Purge all records marked as Deleted from the registry")
    parser.add_argument("--reinstate-user", metavar="USER", help="Reinstate/Reactivate a revoked license by user")
    parser.add_argument("--reinstate-key", metavar="KEY", help="Reinstate/Reactivate a revoked license by key")
    parser.add_argument("--export-csv", metavar="FILE", help="Export registry to CSV file")
    parser.add_argument("--verify", metavar="KEY", help="Verify a specific license key")
    parser.add_argument("--hwid", metavar="HWID", help="Hardware ID to verify against")
    parser.add_argument("--user", metavar="USER", help="User ID to verify against")

    args = parser.parse_args()

    if args.deactivate_local:
        deactivate_local()
    elif args.delete_user:
        delete_license_entry(user_id=args.delete_user)
    elif args.delete_hwid:
        delete_license_entry(hwid=args.delete_hwid)
    elif args.delete_key:
        delete_license_entry(key=args.delete_key)
    elif args.remove_user:
        remove_license_entry(user_id=args.remove_user)
    elif args.remove_hwid:
        remove_license_entry(hwid=args.remove_hwid)
    elif args.remove_key:
        remove_license_entry(key=args.remove_key)
    elif args.clear_deleted:
        clear_deleted_entries()
    elif args.revoke_user:
        revoke_license_entry(user_id=args.revoke_user)
    elif args.revoke_hwid:
        revoke_license_entry(hwid=args.revoke_hwid)
    elif args.revoke_key:
        revoke_license_entry(key=args.revoke_key)
    elif args.reinstate_user:
        reinstate_license_entry(user_id=args.reinstate_user)
    elif args.reinstate_key:
        reinstate_license_entry(key=args.reinstate_key)
    elif args.local:
        inspect_local_workstation()
    elif args.export_csv:
        export_csv(args.export_csv)
    elif args.verify:
        user = args.user or "studio_user"
        hwid = args.hwid or get_machine_hardware_id()
        is_valid, msg, details = validate_license_key(user, args.verify, current_hardware_id=hwid)
        print("\nVerification Result:")
        print("  Valid  :", is_valid)
        print("  Message:", msg)
        if details:
            print("  Details:", details)
    else:
        list_licenses()


if __name__ == "__main__":
    main()
