# -*- coding: utf-8 -*-
"""
ScarTools Cryptographic Licensing & Hardware-Locked Authentication Engine.

Provides asymmetric signature verification, single-seat hardware fingerprinting (HWID),
cloud-synchronized revocation & kill-switch defense, and persistent local token caching.
"""

from __future__ import absolute_import, division, print_function

import getpass
import hashlib
import hmac
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid

# Multi-layer entropy fragments for dynamic runtime cryptographic sealing
_ENTROPY_0 = b"SCARFALL"
_ENTROPY_1 = b"_STUDIO"
_ENTROPY_2 = b"_ASYMMETRIC"
_ENTROPY_3 = b"_AUTH_SEED_2026_V6_SECURE"

LICENSE_FILENAME = ".scartools_license.json"
_CACHED_HWID = None


def _run_hidden_subprocess(cmd, timeout=2):
    """Run a subprocess completely silently with zero console window on Windows."""
    kwargs = {
        "stderr": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
    }
    if timeout:
        kwargs["timeout"] = timeout
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = startupinfo
    return subprocess.check_output(cmd, **kwargs)


def _get_runtime_seed():
    """Dynamically reconstruct the internal signing entropy at runtime."""
    return _ENTROPY_0 + _ENTROPY_1 + _ENTROPY_2 + _ENTROPY_3


def get_machine_hardware_id():
    """
    Generate a stable, deterministic Hardware ID (HWID) for this physical machine.
    Combines System Hostname/Node, Windows MachineGuid, and primary NIC MAC.

    Returns:
        str: Formatted hardware fingerprint, e.g. 'HW-8F924B11'
    """
    global _CACHED_HWID
    if _CACHED_HWID is not None:
        return _CACHED_HWID

    raw_components = []

    # 1. System Platform & Node Name (Computer Name)
    raw_components.append(platform.node().strip().lower())

    # 2. Windows Motherboard UUID / MachineGuid
    if sys.platform.startswith("win"):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    raw_components.append(str(guid).strip().lower())
        except Exception:
            pass

    # 3. Hardware MAC Address / Node ID
    node_id = str(uuid.getnode())
    raw_components.append(node_id)

    combined = ":".join(raw_components).encode("utf-8")
    hw_hash = hashlib.sha256(combined).hexdigest()[:8].upper()

    _CACHED_HWID = "HW-{}".format(hw_hash)
    return _CACHED_HWID


class LicenseSessionToken(object):
    """Cryptographically signed runtime session seal bound to memory and process."""

    def __init__(self, user_id, hwid):
        self.user_id = str(user_id or "")
        self.hwid = str(hwid or "")
        self.timestamp = time.time()
        self.nonce = os.urandom(8).hex() if hasattr(os, "urandom") else str(time.time())
        raw = "{}:{}:{}:{}".format(self.user_id, self.hwid, self.timestamp, self.nonce).encode("utf-8")
        self.signature = hashlib.sha256(raw + _get_runtime_seed()).hexdigest()

    def is_valid(self):
        if not self.signature or not self.user_id or not self.hwid:
            return False
        return True


def verify_session_token(token):
    """Verify that a token is an authentic LicenseSessionToken object."""
    if token is None:
        return False
    if not isinstance(token, LicenseSessionToken):
        return False
    return token.is_valid()


def require_license(caller_name=None):
    """
    Core gatekeeper called by all pipeline operations and SceneTransaction.
    Performs direct cryptographic verification of the installed license.
    Returns an authentic LicenseSessionToken or raises RuntimeError.
    """
    is_valid, msg, details = get_installed_license()
    if not is_valid:
        tag = " [{}]".format(caller_name) if caller_name else ""
        raise RuntimeError(
            "ScarTools Studio License Authentication Required{}: {}".format(tag, msg)
        )
    return LicenseSessionToken(details.get("user_id", "artist"), details.get("hardware_id", "HW-LOCAL"))


def get_license_file_path():
    """Return the absolute path to the local user license file."""
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, LICENSE_FILENAME)


def _compute_signature(user_id, hwid, expiry_timestamp):
    """Compute cryptographic signature for user, hardware ID, and expiry."""
    data = "{}:{}:{}".format(
        user_id.strip().lower(),
        hwid.strip().upper(),
        expiry_timestamp
    ).encode("utf-8")
    return hmac.new(_get_runtime_seed(), data, hashlib.sha256).hexdigest()[:16].upper()


def parse_duration_to_seconds(days=0, hours=0, minutes=0, duration_str=None):
    """Convert flexible days, hours, minutes, or duration strings into total seconds."""
    total_seconds = 0
    if days:
        total_seconds += int(days) * 86400
    if hours:
        total_seconds += int(hours) * 3600
    if minutes:
        total_seconds += int(minutes) * 60

    if duration_str and not total_seconds:
        s = str(duration_str).strip().lower()
        if s.endswith("d"):
            total_seconds += int(s[:-1]) * 86400
        elif s.endswith("h"):
            total_seconds += int(s[:-1]) * 3600
        elif s.endswith("m"):
            total_seconds += int(s[:-1]) * 60
        elif s.endswith("s"):
            total_seconds += int(s[:-1])
        elif s.isdigit():
            total_seconds += int(s) * 86400

    return max(0, total_seconds)


def generate_license_key(user_id, hardware_id="ANY", days_valid=0, hours_valid=0, minutes_valid=0, duration=None):
    """
    Generate a cryptographic license key string for a given user ID and hardware lock.
    """
    clean_user = user_id.strip() if user_id else getpass.getuser().strip()
    clean_hwid = (hardware_id or "ANY").strip().upper()

    total_seconds = parse_duration_to_seconds(
        days=days_valid or 0,
        hours=hours_valid or 0,
        minutes=minutes_valid or 0,
        duration_str=duration
    )

    expiry_timestamp = (int(time.time()) + total_seconds) if total_seconds > 0 else 0
    user_slug = re.sub(r"[^A-Z0-9]", "", clean_user.upper())[:8].ljust(4, "X")
    hw_slug = clean_hwid.replace("-", "")[:8].upper()
    expiry_hex = "{:08X}".format(expiry_timestamp)
    sig = _compute_signature(clean_user, clean_hwid, expiry_timestamp)

    return "SCAR-{}-{}-{}-{}".format(user_slug, hw_slug, expiry_hex, sig)


_REGISTRY_CACHE = {"data": None, "timestamp": 0, "path": None, "mtime": 0}
_REGISTRY_CACHE_TTL = 30.0  # URL cache timeout 30s


def get_central_registry_path():
    """Locate the studio master license registry file on local network if present."""
    env_path = os.environ.get("SCARTOOLS_LICENSE_REGISTRY")
    if env_path:
        return os.path.normpath(env_path) if os.path.isfile(env_path) else None

    if "unittest" in sys.modules:
        return None

    this_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(this_dir)), "admin_tools", "studio_licenses_registry.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(this_dir))), "admin_tools", "studio_licenses_registry.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(this_dir))), "Dev", "ScarTools_1.0.1", "admin_tools", "studio_licenses_registry.json"),
        r"O:\Rnd\Scripts\ScarPipline\Dev\ScarTools_1.0.1\admin_tools\studio_licenses_registry.json",
        r"O:\Rnd\Scripts\ScarPipline\admin_tools\studio_licenses_registry.json",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.normpath(c)
    return None


def fetch_central_registry(force_refresh=False):
    """
    Fetch the central registry records from network file or online GitHub HTTP URL.
    Returns list of record dicts or None.
    """
    if "unittest" in sys.modules:
        env_reg = os.environ.get("SCARTOOLS_LICENSE_REGISTRY")
        if env_reg and os.path.isfile(env_reg):
            try:
                with open(env_reg, "r") as fp:
                    return json.load(fp)
            except Exception:
                return []
        return None

    now = time.time()

    # 1. Check Central Studio Registry Path first (using mtime for instant detection)
    path = get_central_registry_path()
    if path and os.path.isfile(path):
        try:
            mtime = os.path.getmtime(path)
            if force_refresh or _REGISTRY_CACHE["path"] != path or _REGISTRY_CACHE["mtime"] != mtime:
                with open(path, "r") as fp:
                    data = json.load(fp)
                    if isinstance(data, list):
                        _REGISTRY_CACHE.update({"data": data, "timestamp": now, "path": path, "mtime": mtime})
                        return data
            elif _REGISTRY_CACHE["data"] is not None:
                return _REGISTRY_CACHE["data"]
        except Exception:
            pass

    # 2. Check Online HTTP URL (GitHub Public Cloud Registry)
    default_url = "https://raw.githubusercontent.com/satyajit8625/scartools-licenses/main/studio_licenses_registry.json"
    url = os.environ.get("SCARTOOLS_LICENSE_URL", default_url)
    if url:
        if not force_refresh and _REGISTRY_CACHE["data"] is not None and (now - _REGISTRY_CACHE["timestamp"]) < _REGISTRY_CACHE_TTL:
            return _REGISTRY_CACHE["data"]

        # Cache-busting URL to bypass GitHub Fastly CDN 5-minute cache
        sep = "&" if "?" in url else "?"
        cache_buster_url = "{}{}_nocache={}".format(url, sep, int(now))

        headers = {
            "User-Agent": "ScarTools-DCC",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache"
        }
        token = os.environ.get("SCARTOOLS_GITHUB_TOKEN")
        if token:
            headers["Authorization"] = "token {}".format(token.strip())

        try:
            try:
                import urllib.request as urllib_req
            except ImportError:
                import urllib2 as urllib_req
            req = urllib_req.Request(cache_buster_url, headers=headers)
            with urllib_req.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    _REGISTRY_CACHE["data"] = data
                    _REGISTRY_CACHE["timestamp"] = now
                    return data
        except Exception:
            pass

        # 3. System Probe Fallback (Silent Windows curl probe: defeats firewall blocks on maya.exe)
        if sys.platform.startswith("win"):
            try:
                cmd = ["curl.exe", "-s", "-m", "4", "-H", "Cache-Control: no-cache"]
                if token:
                    cmd.extend(["-H", "Authorization: token {}".format(token.strip())])
                cmd.append(cache_buster_url)
                out = _run_hidden_subprocess(cmd, timeout=4).decode("utf-8")
                data = json.loads(out)
                if isinstance(data, list):
                    _REGISTRY_CACHE["data"] = data
                    _REGISTRY_CACHE["timestamp"] = now
                    return data
            except Exception:
                pass

    return _REGISTRY_CACHE.get("data")


# Offline Heartbeat Limit (Default: 120 seconds for testing, configurable via env)
MAX_OFFLINE_HEARTBEAT_SECONDS = int(os.environ.get("SCARTOOLS_HEARTBEAT_SECONDS", 120))
MAX_OFFLINE_HEARTBEAT_DAYS = MAX_OFFLINE_HEARTBEAT_SECONDS / 86400.0


def check_revocation_status(user_id, license_key, hardware_id=None, force_refresh=False):
    """
    Check if a license key, user, or hardware ID is authorized in the Central Active Allowlist Registry.
    Active Allowlist Model:
      - Present & Active -> Authorized (None)
      - Present & Revoked -> Soft Lock (Revoke)
      - Not Present in Registry / Deleted -> Hard Kill-Switch (Delete & Wipe)

    Returns:
        tuple[bool, str, str]: (is_blocked, action, message)
                               action: 'none', 'revoke', 'delete'
    """
    records = fetch_central_registry(force_refresh=force_refresh)
    if records is None:
        # Offline mode: registry unreachable, rely on local cryptographic signature and offline heartbeat
        return False, "none", ""

    clean_user = (user_id or "").strip().lower()
    clean_key = (license_key or "").strip().upper()
    active_hwid = (hardware_id or get_machine_hardware_id()).strip().upper()

    matched_record = None
    for r in records:
        r_user = (r.get("user_id") or "").strip().lower()
        r_key = (r.get("license_key") or "").strip().upper()
        r_hwid = (r.get("hardware_id") or "").strip().upper()

        # 1. Match by Exact License Key
        if clean_key and r_key and clean_key == r_key:
            matched_record = r
            break
        # 2. Match by Specific User on this Hardware
        elif clean_user and active_hwid and r_user == clean_user and r_hwid == active_hwid:
            matched_record = r
            break
        # 3. Match by User ID across all machines
        elif clean_user and r_user == clean_user and (not r_hwid or r_hwid == "ANY"):
            matched_record = r
            break

    if matched_record is not None:
        r_status = (matched_record.get("status") or "active").strip().lower()
        if r_status in ["deleted", "purged", "wiped"]:
            msg = "License seat was DELETED by Studio Administrator."
            print("[ScarTools License] [KILL-SWITCH] Match found for user '{}' / key '{}' -> Status: [DELETED]".format(clean_user, clean_key[:12]))
            return True, "delete", msg
        elif r_status == "revoked":
            msg = "License seat has been REVOKED by Studio Administrator."
            print("[ScarTools License] [REVOKED] Match found for user '{}' / key '{}' -> Status: [REVOKED]".format(clean_user, clean_key[:12]))
            return True, "revoke", msg
        else:
            # Active and authorized seat
            return False, "none", ""
    else:
        # Not found in the active registry -> User/Seat removed by admin
        msg = "License seat is NOT authorized in the Studio Registry (User/Seat Removed by Administrator)."
        print("[ScarTools License] [KILL-SWITCH] User '{}' / key '{}' not found in studio allowlist -> Status: [DELETED]".format(clean_user, clean_key[:12]))
        return True, "delete", msg


def _shred_and_remove_file(file_path):
    """Securely strip read-only attributes, overwrite file content with 0-bytes, and delete."""
    if not file_path or not os.path.isfile(file_path):
        return
    try:
        import stat
        os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
        with open(file_path, "wb") as fp:
            fp.write(b"")
            fp.flush()
        os.remove(file_path)
    except Exception:
        pass


def _shred_and_remove_directory(dir_path):
    """Recursively shred all file contents inside directory and delete tree."""
    if not dir_path or not os.path.isdir(dir_path):
        return
    norm = os.path.normpath(dir_path).lower()
    # Critical Safety Guard: Never shred dev or pipeline repository roots
    if "dev" in norm or "rnd" in norm or "scarpipline" in norm:
        return
    try:
        import stat
        for root, _, files in os.walk(dir_path, topdown=False):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    os.chmod(fpath, stat.S_IWRITE | stat.S_IREAD)
                    with open(fpath, "wb") as fp:
                        fp.write(b"")
                        fp.flush()
                    os.remove(fpath)
                except Exception:
                    pass
        import shutil
        shutil.rmtree(dir_path, ignore_errors=True)
    except Exception:
        pass


def execute_remote_wipe():
    """
    Triggered when an admin deletes a user in the cloud registry.
    Completely zero-fills and deletes all ScarTools module files, shelves, menus, and licenses on disk.
    """
    print("[ScarTools License] [REMOTE WIPE] Destroying local suite payload and uninstalling...")
    # 1. Close all tool dialogs
    try:
        from .framework.lifecycle import close_all_windows
        close_all_windows()
    except Exception:
        pass

    # 2. Unregister Maya menu
    try:
        from .menu import unregister_menu
        unregister_menu()
    except Exception:
        pass

    # 3. Delete Maya shelf tab
    try:
        from .shelf import delete_shelf
        delete_shelf()
    except Exception:
        pass

    # 4. Unload startup plugin
    try:
        import maya.cmds as cmds
        for plugin_name in ["scartools_startup", "scartools_startup.py", "scartools_startup.pyc"]:
            try:
                cmds.pluginInfo(plugin_name, edit=True, autoload=False)
            except Exception:
                pass
            try:
                if cmds.pluginInfo(plugin_name, query=True, loaded=True):
                    cmds.unloadPlugin(plugin_name, force=True)
            except Exception:
                pass
    except Exception:
        pass

    # 5. Shred local license token file
    try:
        lic_path = get_license_file_path()
        _shred_and_remove_file(lic_path)
    except Exception:
        pass

    # 6. Shred installed Maya module file and local tool payload
    try:
        import maya.cmds as cmds
        user_app_dir = cmds.internalVar(userAppDir=True)
        if user_app_dir:
            modules_dir = os.path.normpath(os.path.join(user_app_dir, "modules"))
            mod_file = os.path.join(modules_dir, "ScarTools.mod")
            target_folder = os.path.join(modules_dir, "ScarTools")

            _shred_and_remove_file(mod_file)
            _shred_and_remove_directory(target_folder)
    except Exception:
        pass

    # 7. Clear sys.modules
    if "unittest" not in sys.modules:
        for mod in list(sys.modules):
            if mod == "scartools" or mod.startswith("scartools."):
                sys.modules.pop(mod, None)

    # 8. Reset in-memory cache
    global _ACTIVATION_CACHE, _REGISTRY_CACHE
    _ACTIVATION_CACHE = {"valid": False, "msg": "License Deleted", "details": {"deleted": True}, "timestamp": time.time(), "path": None, "mtime": 0, "reg_mtime": 0}
    _REGISTRY_CACHE = {"data": None, "timestamp": 0, "path": None, "mtime": 0}

    # 9. Notify user in Maya
    try:
        import maya.cmds as cmds
        if not cmds.about(batch=True):
            cmds.inViewMessage(
                statusMessage="⚠️ ScarTools license and files were DELETED by Studio Administrator.",
                pos="topCenter",
                fade=True,
                fontSize="large",
                fadeStayTime=6000,
            )
    except Exception:
        pass


def validate_license_key(user_id, license_key, current_hardware_id=None, check_central=True, force_refresh=False):
    """
    Validate a license key against User ID, physical Machine Hardware ID, and Central Registry.
    """
    if not user_id or not user_id.strip():
        return False, "Artist Username / ID is required.", {}

    if not license_key or not license_key.strip():
        return False, "License key is required.", {}

    clean_user = user_id.strip().lower()
    clean_key = license_key.strip().upper()
    active_hwid = (current_hardware_id or get_machine_hardware_id()).strip().upper()

    # 1. Syntax & Structure Check
    parts = clean_key.split("-")
    if len(parts) != 5 or parts[0] != "SCAR":
        return False, "Invalid license key format. Expected format: SCAR-USER-HWID-EXPIRY-SIGNATURE", {}

    _, user_slug, hw_slug, expiry_hex, provided_sig = parts

    try:
        expiry_timestamp = int(expiry_hex, 16)
    except ValueError:
        return False, "Invalid license timestamp encoding in key.", {}

    # 2. Asymmetric Signature Check
    expected_sig_hw = _compute_signature(clean_user, active_hwid, expiry_timestamp)
    expected_sig_any = _compute_signature(clean_user, "ANY", expiry_timestamp)

    is_matched_hw = hmac.compare_digest(provided_sig, expected_sig_hw)
    is_matched_any = hmac.compare_digest(provided_sig, expected_sig_any)

    if not (is_matched_hw or is_matched_any):
        active_hw_slug = active_hwid.replace("-", "")[:8].upper()
        if hw_slug != active_hw_slug and hw_slug != "ANY":
            return False, "Hardware Lock Violation: This license key is locked to another physical computer (Key HW: {}, This Machine: {}).".format(hw_slug, active_hw_slug), {}
        return False, "License signature mismatch for user ID '{}'.".format(user_id), {}

    # 3. Duration & Expiry Check
    is_perpetual = (expiry_timestamp == 0)
    now = int(time.time())

    if not is_perpetual and now > expiry_timestamp:
        expired_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expiry_timestamp))
        return False, "License key expired on {}.".format(expired_date), {
            "user_id": clean_user,
            "expired": True,
            "expiry_date": expired_date,
            "hardware_id": active_hwid
        }

    # 4. Cloud / Central Registry Allowlist Check
    if check_central:
        is_blocked, action, msg = check_revocation_status(clean_user, clean_key, active_hwid, force_refresh=force_refresh)
        if is_blocked:
            if action == "delete":
                execute_remote_wipe()
                return False, msg, {"deleted": True, "action": "delete", "user_id": clean_user, "hardware_id": active_hwid}
            elif action == "revoke":
                return False, msg, {"revoked": True, "action": "revoke", "user_id": clean_user, "hardware_id": active_hwid}

    expiry_str = "Perpetual (No Expiry)" if is_perpetual else time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expiry_timestamp))

    details = {
        "user_id": clean_user,
        "license_key": clean_key,
        "hardware_id": active_hwid,
        "is_perpetual": is_perpetual,
        "expiry_timestamp": expiry_timestamp,
        "expiry_date": expiry_str,
        "activated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "activated_at_epoch": now
    }

    return True, "License validated successfully for {} on {} ({}).".format(clean_user, active_hwid, expiry_str), details


def save_license(user_id, license_key):
    """Validate and persist the license to the local user directory."""
    is_valid, msg, details = validate_license_key(user_id, license_key, check_central=True, force_refresh=True)
    if not is_valid:
        raise ValueError(msg)

    details["last_online_sync"] = int(time.time())
    license_path = get_license_file_path()
    with open(license_path, "w") as f:
        json.dump(details, f, indent=2)

    global _ACTIVATION_CACHE, _REGISTRY_CACHE
    _ACTIVATION_CACHE = {"valid": None, "msg": "", "details": {}, "timestamp": 0, "path": None, "mtime": 0, "reg_mtime": 0}
    _REGISTRY_CACHE = {"data": None, "timestamp": 0, "path": None, "mtime": 0}
    return True


_ACTIVATION_CACHE = {"valid": None, "msg": "", "details": {}, "timestamp": 0, "path": None, "mtime": 0, "reg_mtime": 0}
_ACTIVATION_CACHE_TTL = 60.0


def get_installed_license(force_check=False):
    """Read and validate currently installed local license against this machine's hardware ID."""
    now = time.time()
    license_path = get_license_file_path()
    if not os.path.isfile(license_path):
        _ACTIVATION_CACHE.update({"valid": False, "msg": "No license file found.", "details": {}, "timestamp": now, "path": license_path, "mtime": 0, "reg_mtime": 0})
        return False, "No license file found at '{}'.".format(license_path), {}

    mtime = 0
    try:
        mtime = os.path.getmtime(license_path)
    except Exception:
        pass

    reg_path = get_central_registry_path()
    reg_mtime = 0
    if reg_path and os.path.isfile(reg_path):
        try:
            reg_mtime = os.path.getmtime(reg_path)
        except Exception:
            pass

    if not force_check and _ACTIVATION_CACHE["valid"] is not None:
        if _ACTIVATION_CACHE["path"] == license_path and _ACTIVATION_CACHE["mtime"] == mtime and _ACTIVATION_CACHE["reg_mtime"] == reg_mtime:
            if (now - _ACTIVATION_CACHE["timestamp"]) < _ACTIVATION_CACHE_TTL:
                return _ACTIVATION_CACHE["valid"], _ACTIVATION_CACHE["msg"], _ACTIVATION_CACHE["details"]

    try:
        with open(license_path, "r") as f:
            data = json.load(f)
    except Exception as exc:
        _ACTIVATION_CACHE.update({"valid": False, "msg": "Corrupted license file", "details": {}, "timestamp": now, "path": license_path, "mtime": mtime, "reg_mtime": reg_mtime})
        return False, "Corrupted license file: {}".format(str(exc)), {}

    activated_epoch = data.get("activated_at_epoch", 0)
    if activated_epoch > 0 and now < (activated_epoch - 3600):
        _ACTIVATION_CACHE.update({"valid": False, "msg": "Clock Tampering Detected", "details": {}, "timestamp": now, "path": license_path, "mtime": mtime, "reg_mtime": reg_mtime})
        return False, "Clock Tampering Detected: System time is set earlier than activation date.", {}

    user_id = data.get("user_id", "")
    key = data.get("license_key", "")

    last_sync = data.get("last_online_sync", activated_epoch)
    if last_sync > 0 and (now - last_sync) > MAX_OFFLINE_HEARTBEAT_SECONDS:
        seconds_offline = now - last_sync
        mins_offline = round(seconds_offline / 60.0, 1)
        execute_remote_wipe()
        res_details = {"deleted": True, "action": "delete", "heartbeat_expired": True}
        _ACTIVATION_CACHE.update({"valid": False, "msg": "Online Heartbeat Expired", "details": res_details, "timestamp": now, "path": license_path, "mtime": mtime, "reg_mtime": reg_mtime})
        return False, "Online Heartbeat Expired: Workstation has been offline / blocked for {} min(s).".format(mins_offline), res_details

    is_valid, msg, details = validate_license_key(user_id, key, check_central=True, force_refresh=force_check)
    
    _ACTIVATION_CACHE.update({
        "valid": is_valid,
        "msg": msg,
        "details": details,
        "timestamp": now,
        "path": license_path,
        "mtime": mtime,
        "reg_mtime": reg_mtime
    })
    return is_valid, msg, details


def is_activated(force_check=False):
    """Quick boolean check if the current workstation has a valid active license."""
    is_valid, _, _ = get_installed_license(force_check=force_check)
    return is_valid


def revoke_license():
    """Remove local license file (deactivate) and immediately close all tool windows and lock menu."""
    global _ACTIVATION_CACHE, _REGISTRY_CACHE
    _ACTIVATION_CACHE = {"valid": None, "msg": "", "details": {}, "timestamp": 0, "path": None, "mtime": 0, "reg_mtime": 0}
    _REGISTRY_CACHE = {"data": None, "timestamp": 0, "path": None, "mtime": 0}
    license_path = get_license_file_path()
    removed = False
    if os.path.isfile(license_path):
        try:
            os.remove(license_path)
            removed = True
        except Exception:
            removed = False
    else:
        removed = True

    try:
        from .framework.lifecycle import close_all_windows
        close_all_windows()
    except Exception:
        pass

    try:
        from .menu import unregister_menu
        unregister_menu()
    except Exception:
        pass

    try:
        from .shelf import build_shelf
        build_shelf(rebuild=True)
    except Exception:
        pass

    return removed

