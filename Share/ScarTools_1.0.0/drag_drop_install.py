# -*- coding: utf-8 -*-
"""ScarTools 1.0.0 Maya drag-and-drop installer & license activation entry point."""

from __future__ import print_function


import getpass
import hashlib
import hmac
import importlib
import json
import os
import re
import shutil
import sys
import time
import traceback
import uuid

import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    # Maya 2023 uses PySide2. Prefer its native binding if a pip-installed
    # PySide6 also happens to be visible in the artist's environment.
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance


_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.join(_CURRENT_DIR, "scripts")
if os.path.isdir(_SCRIPTS_DIR) and _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

TOOL_NAME = "ScarTools"
DISPLAY_NAME = "ScarTools"
VERSION = "1.0.0"
MIN_MAYA_VERSION = 2023

STARTUP_PLUGIN = "scartools_startup.py"
WINDOW_OBJECT_NAME = "ScarToolsInstallerWindow"
WM_NCLBUTTONDBLCLK = 0x00A3
HTCAPTION = 2

STUDIO_SECRET_SALT = b"SCARFALL_STUDIO_ASYMMETRIC_AUTH_SEED_2026_V6_SECURE"
LICENSE_FILENAME = ".scartools_license.json"

RUNTIME_DIRECTORIES = ("scripts", "plug-ins", "icons")
WINDOW_MARGIN = 14
WINDOW_SPACING = 10
GROUP_SPACING = 8
SECONDARY_BUTTON_HEIGHT = 34
PRIMARY_BUTTON_HEIGHT = 34
PRIMARY_BUTTON_WIDTH = 150


# ---------------------------------------------------------------------------
# Licensing Engine
# ---------------------------------------------------------------------------

def _get_license_file_path():
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, LICENSE_FILENAME)


def get_machine_hardware_id():
    raw_components = []
    import platform
    raw_components.append(platform.node().strip().lower())
    if sys.platform.startswith("win"):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    raw_components.append(str(guid).strip().lower())
        except Exception:
            pass
    node_id = str(uuid.getnode())
    raw_components.append(node_id)
    combined = ":".join(raw_components).encode("utf-8")
    hw_hash = hashlib.sha256(combined).hexdigest()[:8].upper()
    return "HW-{}".format(hw_hash)


def _compute_signature(user_id, hwid, expiry_timestamp):
    data = "{}:{}:{}".format(user_id.strip().lower(), hwid.strip().upper(), expiry_timestamp).encode("utf-8")
    return hmac.new(STUDIO_SECRET_SALT, data, hashlib.sha256).hexdigest()[:16].upper()


def validate_license_key(user_id, license_key, current_hardware_id=None):
    """
    Validate a license key against User ID, physical Machine Hardware ID, and Central Cloud Registry.

    Returns:
        tuple[bool, str, dict]: (is_valid, message, license_details)
    """
    if not user_id or not user_id.strip():
        return False, "Artist Username / ID is required.", {}

    if not license_key or not license_key.strip():
        return False, "License key is required.", {}

    clean_user = user_id.strip().lower()
    clean_key = license_key.strip().upper()
    active_hwid = (current_hardware_id or get_machine_hardware_id()).strip().upper()

    # 1. Check Central / GitHub Cloud Registry
    default_url = "https://raw.githubusercontent.com/satyajit8625/scartools-licenses/main/studio_licenses_registry.json"
    url = os.environ.get("SCARTOOLS_LICENSE_URL", default_url)
    try:
        sep = "&" if "?" in url else "?"
        cache_buster_url = "{}{}_nocache={}".format(url, sep, int(time.time()))
        headers = {
            "User-Agent": "ScarTools-DCC",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache"
        }
        try:
            import urllib.request as urllib_req
        except ImportError:
            import urllib2 as urllib_req
        req = urllib_req.Request(cache_buster_url, headers=headers)
        with urllib_req.urlopen(req, timeout=4.0) as resp:
            records = json.loads(resp.read().decode("utf-8"))
            if isinstance(records, list):
                matched_record = None
                for r in records:
                    r_user = (r.get("user_id") or "").strip().lower()
                    r_key = (r.get("license_key") or "").strip().upper()
                    r_hwid = (r.get("hardware_id") or "").strip().upper()

                    if clean_key and r_key and clean_key == r_key:
                        matched_record = r
                        break
                    elif clean_user and active_hwid and r_user == clean_user and r_hwid == active_hwid:
                        matched_record = r
                        break
                    elif clean_user and r_user == clean_user and (not r_hwid or r_hwid == "ANY"):
                        matched_record = r
                        break

                if matched_record is not None:
                    r_status = (matched_record.get("status") or "active").strip().lower()
                    if r_status in ["deleted", "purged", "wiped"]:
                        return False, "License seat was DELETED by Studio Administrator.", {"deleted": True, "action": "delete"}
                    elif r_status == "revoked":
                        return False, "License seat has been REVOKED by Studio Administrator.", {"revoked": True, "action": "revoke"}
                else:
                    return False, "License seat is NOT authorized in the Studio Registry (Seat not in allowlist).", {"deleted": True, "action": "delete"}
    except Exception:
        pass

    parts = clean_key.split("-")
    if len(parts) != 5 or parts[0] != "SCAR":
        return False, "Invalid license key format. Expected SCAR-XXXX-XXXX-XXXX-XXXX.", {}

    _, user_slug, hw_slug, expiry_hex, provided_sig = parts

    try:
        expiry_timestamp = int(expiry_hex, 16)
    except ValueError:
        return False, "Invalid license timestamp encoding.", {}

    expected_sig_hw = _compute_signature(clean_user, active_hwid, expiry_timestamp)
    expected_sig_any = _compute_signature(clean_user, "ANY", expiry_timestamp)

    is_matched_hw = hmac.compare_digest(provided_sig, expected_sig_hw)
    is_matched_any = hmac.compare_digest(provided_sig, expected_sig_any)

    if not (is_matched_hw or is_matched_any):
        active_hw_slug = active_hwid.replace("-", "")[:8].upper()
        if hw_slug != active_hw_slug and hw_slug != "ANY":
            return False, "Hardware Lock Violation: This license key is locked to another physical computer (Key HW: {}, This Machine: {}).".format(hw_slug, active_hw_slug), {}
        return False, "License signature mismatch for user ID '{}'.".format(user_id), {}

    is_perpetual = (expiry_timestamp == 0)
    now = int(time.time())

    if not is_perpetual and now > expiry_timestamp:
        expired_date = time.strftime("%Y-%m-%d", time.localtime(expiry_timestamp))
        return False, "License key expired on {}.".format(expired_date), {
            "user_id": clean_user,
            "expired": True,
            "expiry_date": expired_date,
            "hardware_id": active_hwid
        }

    expiry_str = "Perpetual (No Expiry)" if is_perpetual else time.strftime("%Y-%m-%d", time.localtime(expiry_timestamp))

    details = {
        "user_id": clean_user,
        "license_key": clean_key,
        "hardware_id": active_hwid,
        "is_perpetual": is_perpetual,
        "expiry_timestamp": expiry_timestamp,
        "expiry_date": expiry_str,
        "activated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    return True, "License validated successfully for {} on {} ({}).".format(clean_user, active_hwid, expiry_str), details


def save_license(user_id, license_key):
    is_valid, msg, details = validate_license_key(user_id, license_key)
    if not is_valid:
        raise ValueError(msg)

    license_path = _get_license_file_path()
    with open(license_path, "w") as f:
        json.dump(details, f, indent=2)
    return True


def get_installed_license():
    license_path = _get_license_file_path()
    if not os.path.isfile(license_path):
        return False, "No license file found.", {}

    try:
        with open(license_path, "r") as f:
            data = json.load(f)
    except Exception as exc:
        return False, "Corrupted license file: {}".format(str(exc)), {}

    user_id = data.get("user_id", "")
    key = data.get("license_key", "")
    return validate_license_key(user_id, key)


def is_activated():
    is_valid, _, _ = get_installed_license()
    return is_valid


# ---------------------------------------------------------------------------
# UI Helpers & Maya Integration
# ---------------------------------------------------------------------------

def _configure_setup_button(button, role="secondary", fixed_width=None):
    role = str(role or "secondary")
    button.setProperty("role", role)
    button.setFixedHeight(
        PRIMARY_BUTTON_HEIGHT if role == "primary" else SECONDARY_BUTTON_HEIGHT
    )
    if fixed_width is not None:
        button.setFixedWidth(int(fixed_width))
    return button


def _is_native_titlebar_double_click(message):
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        from ctypes import wintypes
        native_message = ctypes.cast(
            int(message), ctypes.POINTER(wintypes.MSG)
        ).contents
        return (
            int(native_message.message) == WM_NCLBUTTONDBLCLK
            and int(native_message.wParam) == HTCAPTION
        )
    except Exception:
        return False


def _layout_widgets(layout):
    if layout is None:
        return
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        if widget is not None:
            yield widget
            continue
        child_layout = item.layout()
        if child_layout is not None:
            for child_widget in _layout_widgets(child_layout):
                yield child_widget


def _non_client_double_click_type():
    event_type = getattr(QtCore.QEvent, "NonClientAreaMouseButtonDblClick", None)
    if event_type is None and hasattr(QtCore.QEvent, "Type"):
        event_type = getattr(
            QtCore.QEvent.Type, "NonClientAreaMouseButtonDblClick", None
        )
    return event_type


def _maya_major_version():
    text = str(cmds.about(version=True) or "")
    match = re.search(r"(?:^|\D)(20\d{2})(?:\D|$)", text)
    if match:
        return int(match.group(1))
    api_version = int(cmds.about(apiVersion=True))
    return api_version // 10000


def _ensure_supported():
    version = _maya_major_version()
    if version < MIN_MAYA_VERSION:
        raise RuntimeError(
            "ScarTools requires Maya {} or newer. Running Maya {}.".format(
                MIN_MAYA_VERSION, version
            )
        )
    return version


def maya_main_window():
    pointer = omui.MQtUtil.mainWindow()
    if pointer is None:
        return None
    return wrapInstance(int(pointer), QtWidgets.QWidget)


def _source_path():
    candidates = [
        globals().get("__file__"),
        _source_path.__code__.co_filename,
    ]
    for candidate in candidates:
        if candidate:
            candidate = os.path.abspath(candidate)
            if os.path.isfile(candidate):
                return candidate
    raise RuntimeError("Could not resolve the ScarTools installer path.")


def _bundle_app_icon_path():
    path = os.path.join(
        os.path.dirname(_source_path()), "icons", "scarfall_app_icon.png"
    )
    return path if os.path.isfile(path) else None


def _installation_paths():
    modules_root = os.path.normpath(
        os.path.join(cmds.internalVar(userAppDir=True), "modules")
    )
    return (
        modules_root,
        os.path.join(modules_root, TOOL_NAME),
        os.path.join(modules_root, TOOL_NAME + ".mod"),
    )


def _installed_version(target_root):
    version_file = os.path.join(
        target_root, "scripts", "scartools", "version.py"
    )
    if os.path.isfile(version_file):
        try:
            with open(version_file, "r") as stream:
                match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)', stream.read(), re.M)
            return match.group(1) if match else "Unknown"
        except Exception:
            return "Unknown"
    version_pyc = os.path.join(
        target_root, "scripts", "scartools", "version.pyc"
    )
    if os.path.isfile(version_pyc):
        return VERSION
    return None


def _plugin_candidates():
    return (
        STARTUP_PLUGIN,
        os.path.splitext(STARTUP_PLUGIN)[0],
    )


def _close_running_tool():
    try:
        lifecycle = sys.modules.get("scartools.framework.lifecycle")
        if lifecycle and hasattr(lifecycle, "close_all_windows"):
            lifecycle.close_all_windows()
    except Exception:
        pass

    try:
        for widget in list(QtWidgets.QApplication.topLevelWidgets()):
            object_name = str(widget.objectName() or "")
            if (
                (
                    object_name.startswith("ScarTools")
                    or object_name.startswith("SkinWeightsPro")
                )
                and object_name != WINDOW_OBJECT_NAME
            ):
                widget.close()
                widget.deleteLater()
        QtWidgets.QApplication.processEvents()
    except Exception:
        pass


def _unload_existing_plugin():
    _close_running_tool()
    for candidate in _plugin_candidates():
        try:
            cmds.pluginInfo(candidate, edit=True, autoload=False)
        except Exception:
            pass
        try:
            if cmds.pluginInfo(candidate, query=True, loaded=True):
                cmds.unloadPlugin(candidate, force=True)
        except Exception:
            pass


def _clear_loaded_modules():
    for module_name in list(sys.modules):
        if module_name == "scartools" or module_name.startswith("scartools."):
            sys.modules.pop(module_name, None)
    importlib.invalidate_caches()


def _write_module_file(module_file, target_root):
    normalized_root = target_root.replace("\\", "/")
    content = (
        "+ {name} {version} {root}\n"
        "PYTHONPATH +:= scripts\n"
        "MAYA_PLUG_IN_PATH +:= plug-ins\n"
        "XBMLANGPATH +:= icons\n"
    ).format(name=TOOL_NAME, version=VERSION, root=normalized_root)
    temporary_file = module_file + ".tmp"
    with open(temporary_file, "w") as stream:
        stream.write(content)
    os.replace(temporary_file, module_file)


def _runtime_ignore(_directory, names):
    ignored = set()
    has_py = any(name.endswith(".py") for name in names)
    for name in names:
        if name == "__pycache__" or name == "source":
            ignored.add(name)
        elif name.endswith((".pyc", ".pyo")) and has_py:
            # Only ignore pyc if py source is present
            ignored.add(name)
    return ignored



def _copy_runtime_payload(source_root, staging_root):
    os.makedirs(staging_root)
    try:
        for directory in RUNTIME_DIRECTORIES:
            source = os.path.join(source_root, directory)
            if not os.path.isdir(source):
                raise RuntimeError(
                    "ScarTools release is missing the {} folder.".format(directory)
                )
            shutil.copytree(
                source,
                os.path.join(staging_root, directory),
                ignore=_runtime_ignore,
            )
    except Exception:
        if os.path.isdir(staging_root):
            shutil.rmtree(staging_root)
        raise


def _activate_plugin_file(target_root, plugin_filename):
    scripts_path = os.path.join(target_root, "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)

    plugins_folder = os.path.join(target_root, "plug-ins")

    # Ensure MAYA_PLUG_IN_PATH contains the target plugin folder
    plugin_paths = os.environ.get("MAYA_PLUG_IN_PATH", "").split(os.pathsep)
    _clear_loaded_modules()
    plugin_path = os.path.join(plugins_folder, plugin_filename)
    if not os.path.isfile(plugin_path):
        base_name = os.path.splitext(plugin_filename)[0]
        for candidate_ext in [".py", ".pyc"]:
            cand = os.path.join(plugins_folder, base_name + candidate_ext)
            if os.path.isfile(cand):
                plugin_path = cand
                break

    try:
        loaded_name = cmds.loadPlugin(plugin_path, quiet=True)
    except Exception:
        loaded_name = cmds.loadPlugin(plugin_filename, quiet=True)

    if isinstance(loaded_name, (list, tuple)):
        loaded_name = loaded_name[0]
    cmds.pluginInfo(loaded_name, edit=True, autoload=True)
    return loaded_name



def _activate_plugin(target_root):
    return _activate_plugin_file(target_root, STARTUP_PLUGIN)


def install(user_id=None, license_key=None, confirm=False):
    """Install/update atomically and activate the menu in this Maya session."""
    del confirm
    _ensure_supported()

    if user_id and license_key:
        try:
            save_license(user_id, license_key)
        except Exception:
            pass

    source_root = os.path.dirname(_source_path())
    modules_root, target_root, module_file = _installation_paths()


    if not os.path.isdir(os.path.join(source_root, "scripts", "scartools")):
        raise RuntimeError(
            "Keep drag_drop_install.py beside the scripts, plug-ins, and icons folders."
        )

    if not os.path.isdir(modules_root):
        os.makedirs(modules_root)

    previous_module_data = None
    if os.path.isfile(module_file):
        with open(module_file, "rb") as stream:
            previous_module_data = stream.read()

    _unload_existing_plugin()

    if os.path.normcase(source_root) == os.path.normcase(target_root):
        _write_module_file(module_file, target_root)
        _activate_plugin(target_root)
        try:
            from scartools.shelf import build_shelf
            build_shelf(rebuild=True)
        except Exception:
            pass
        return target_root

    staging_root = target_root + ".staging_" + uuid.uuid4().hex
    backup_root = target_root + ".backup"
    old_target_moved = False
    new_target_installed = False

    try:
        _copy_runtime_payload(source_root, staging_root)

        if os.path.isdir(backup_root):
            shutil.rmtree(backup_root)
        if os.path.isdir(target_root):
            os.replace(target_root, backup_root)
            old_target_moved = True

        os.replace(staging_root, target_root)
        new_target_installed = True
        _write_module_file(module_file, target_root)
        _activate_plugin(target_root)
        try:
            from scartools.shelf import build_shelf
            build_shelf(rebuild=True)
        except Exception:
            pass

        if os.path.isdir(backup_root):
            shutil.rmtree(backup_root)
        return target_root
    except Exception:
        _unload_existing_plugin()
        if os.path.isdir(staging_root):
            shutil.rmtree(staging_root)
        if new_target_installed and os.path.isdir(target_root):
            shutil.rmtree(target_root)
        if old_target_moved and os.path.isdir(backup_root):
            os.replace(backup_root, target_root)

        if previous_module_data is None:
            if os.path.isfile(module_file):
                os.remove(module_file)
        else:
            with open(module_file, "wb") as stream:
                stream.write(previous_module_data)

        if old_target_moved and os.path.isdir(target_root):
            try:
                _activate_plugin(target_root)
            except Exception:
                pass
        raise


def uninstall():
    try:
        from scartools.shelf import delete_shelf
        delete_shelf()
    except Exception:
        pass
    _, target_root, module_file = _installation_paths()
    _unload_existing_plugin()
    _clear_loaded_modules()

    removal_root = None
    if os.path.isdir(target_root):
        removal_root = target_root + ".uninstalling_" + uuid.uuid4().hex
        os.replace(target_root, removal_root)

    try:
        if os.path.isfile(module_file):
            os.remove(module_file)
        if removal_root and os.path.isdir(removal_root):
            shutil.rmtree(removal_root)
    except Exception:
        if removal_root and os.path.isdir(removal_root) and not os.path.exists(target_root):
            os.replace(removal_root, target_root)
        raise
    return True


# ---------------------------------------------------------------------------
# License Activation Dialog
# ---------------------------------------------------------------------------

class LicenseActivationDialog(QtWidgets.QDialog):
    """Clean Maya dialog to authenticate user and activate ScarTools studio license."""

    def __init__(self, parent=None):
        super(LicenseActivationDialog, self).__init__(parent)
        self.setWindowTitle("ScarTools — Studio License Activation")
        self.setObjectName("ScarToolsLicenseDialog")
        self.setMinimumSize(500, 310)
        self.resize(520, 330)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self._build_ui()
        self._apply_style()
        self._prefill_credentials()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QtWidgets.QLabel("Studio License Activation")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        desc = QtWidgets.QLabel(
            "Please confirm your Artist User ID and Studio License Key to proceed with installation on this machine."
        )
        desc.setObjectName("DialogDesc")
        desc.setWordWrap(True)
        root.addWidget(desc)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        # HWID Row with Copy Button
        hwid_row = QtWidgets.QHBoxLayout()
        hwid_val = get_machine_hardware_id()
        self.hwid_display = QtWidgets.QLineEdit(hwid_val)
        self.hwid_display.setObjectName("InputField")
        self.hwid_display.setReadOnly(True)
        self.hwid_display.setStyleSheet(
            "color: #CFC7DE; background: #181818; border: 1px solid #444444; border-radius: 5px; "
            "padding: 6px 10px; font-weight: 700; font-family: Consolas, monospace; font-size: 12px; min-height: 22px;"
        )

        self.copy_hwid_btn = QtWidgets.QPushButton("📋 Copy HWID")
        self.copy_hwid_btn.setObjectName("SecondaryButton")
        self.copy_hwid_btn.setFixedHeight(30)
        self.copy_hwid_btn.clicked.connect(self._copy_hwid)
        hwid_row.addWidget(self.hwid_display, 1)
        hwid_row.addWidget(self.copy_hwid_btn)
        form.addRow("Machine HWID:", hwid_row)

        self.user_input = QtWidgets.QLineEdit()
        self.user_input.setObjectName("InputField")
        default_user = getpass.getuser()
        self.user_input.setText(default_user)
        self.user_input.setPlaceholderText("e.g. john.doe or artist@studio.com")
        self.user_input.setStyleSheet(
            "color: #FFFFFF; background: #181818; border: 1px solid #444444; border-radius: 5px; "
            "padding: 6px 10px; font-weight: 600; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; min-height: 22px;"
        )
        form.addRow("Artist User ID:", self.user_input)

        self.key_input = QtWidgets.QLineEdit()
        self.key_input.setObjectName("InputField")
        self.key_input.setPlaceholderText("SCAR-XXXX-XXXX-XXXXXXXX-XXXXXXXX")
        self.key_input.setStyleSheet(
            "color: #FFFFFF; background: #181818; border: 1px solid #444444; border-radius: 5px; "
            "padding: 6px 10px; font-weight: 600; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; min-height: 22px;"
        )
        form.addRow("License Key:", self.key_input)
        root.addLayout(form)


        info_note = QtWidgets.QLabel(
            "💡 Tip: Click 'Copy HWID' and send it along with your User ID to your Studio Lead to receive your single-seat key."
        )
        info_note.setObjectName("InfoNote")
        info_note.setStyleSheet("color: #94A3B8; font-size: 11px;")
        info_note.setWordWrap(True)
        root.addWidget(info_note)

        self.error_label = QtWidgets.QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)

        self.activate_btn = QtWidgets.QPushButton("🚀 Activate License")
        self.activate_btn.setObjectName("PrimaryButton")
        self.activate_btn.setFixedHeight(34)
        self.activate_btn.setMinimumWidth(160)
        self.activate_btn.clicked.connect(self._handle_activation)

        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.activate_btn)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

    def _prefill_credentials(self):
        has_lic, _, details = get_installed_license()
        if has_lic and details:
            self.user_input.setText(details.get("user_id", getpass.getuser()))
            self.key_input.setText(details.get("license_key", ""))
            self.error_label.setStyleSheet("color: #34D399; font-weight: 600; font-size: 11.5px;")
            self.error_label.setText("✓ Verified for {} ({})".format(details.get("user_id"), details.get("expiry_date")))
        else:
            # Check for bundled license file beside drag_drop_install.py
            source_root = os.path.dirname(_source_path())
            bundled_license = os.path.join(source_root, LICENSE_FILENAME)
            if not os.path.isfile(bundled_license):
                bundled_license = os.path.join(source_root, "studio_license.json")
            if os.path.isfile(bundled_license):
                try:
                    with open(bundled_license, "r") as f:
                        b_data = json.load(f)
                    b_user = b_data.get("user_id", getpass.getuser())
                    b_key = b_data.get("license_key", "")
                    if b_key:
                        self.user_input.setText(b_user)
                        self.key_input.setText(b_key)
                        return
                except Exception:
                    pass
            self.user_input.setText(getpass.getuser())
            self.key_input.setText("")



    def _copy_hwid(self):
        hwid_text = self.hwid_display.text().strip()
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(hwid_text)
        self.copy_hwid_btn.setText("✓ Copied!")
        QtCore.QTimer.singleShot(2000, lambda: self.copy_hwid_btn.setText("📋 Copy HWID"))

    def _handle_activation(self):
        user_id = self.user_input.text().strip()
        key = self.key_input.text().strip()

        is_valid, msg, details = validate_license_key(user_id, key)
        if not is_valid:
            self.error_label.setText("❌ " + msg)
            return

        try:
            save_license(user_id, key)
            self.error_label.setStyleSheet("color: #34d399;")
            self.error_label.setText("✓ License activated successfully for {}!".format(details["user_id"]))
            QtWidgets.QApplication.processEvents()
            self.accept()
        except Exception as exc:
            self.error_label.setText("❌ Error saving license: " + str(exc))

    def _apply_style(self):
        try:
            from scartools.ui.theme import apply as apply_theme
            apply_theme(self)
        except Exception:
            pass



# ---------------------------------------------------------------------------
# Installer Main Window
# ---------------------------------------------------------------------------

class InstallerWindow(QtWidgets.QDialog):
    """Consistent ScarTools setup and maintenance window."""

    def __init__(self, parent=None):
        super(InstallerWindow, self).__init__(
            parent if parent is not None else maya_main_window()
        )
        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle("ScarTools - Setup & Activation")
        app_icon = _bundle_app_icon_path()
        if app_icon:
            self.setWindowIcon(QtGui.QIcon(app_icon))
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.setMinimumSize(560, 390)
        self.resize(580, 400)
        self._rolled_up = False
        self._rollup_pending = False
        self._rollup_state = []
        self._build_ui()
        self._connect()
        self._apply_style()
        self._refresh_state()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(
            WINDOW_MARGIN, WINDOW_MARGIN, WINDOW_MARGIN, WINDOW_MARGIN
        )
        root.setSpacing(WINDOW_SPACING)

        header_frame = QtWidgets.QFrame()
        header_frame.setObjectName("Header")
        header = QtWidgets.QHBoxLayout(header_frame)
        header.setContentsMargins(12, 9, 14, 9)
        header.setSpacing(11)
        logo_label = QtWidgets.QLabel()
        logo_label.setObjectName("SetupLogo")
        logo_label.setFixedSize(42, 42)
        logo_label.setAlignment(QtCore.Qt.AlignCenter)
        app_icon = _bundle_app_icon_path()
        if app_icon:
            logo_label.setPixmap(
                QtGui.QPixmap(app_icon).scaled(
                    32,
                    32,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
        logo_label.setToolTip("ScarFall / ScarTools")
        header.addWidget(logo_label)
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(2)
        self.title_label = QtWidgets.QLabel(DISPLAY_NAME)
        self.title_label.setObjectName("SetupTitle")
        subtitle = QtWidgets.QLabel(
            "Maya 2023+  •  ScarFall Department Tool Suite"
        )
        subtitle.setObjectName("SetupSubtitle")
        title_box.addWidget(self.title_label)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        version_badge = QtWidgets.QLabel("v{}".format(VERSION))
        version_badge.setObjectName("VersionBadge")
        version_badge.setAlignment(QtCore.Qt.AlignCenter)
        header.addWidget(version_badge)
        root.addWidget(header_frame)

        card = QtWidgets.QFrame()
        card.setObjectName("StatusCard")
        self.status_card = card
        card_layout = QtWidgets.QGridLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setHorizontalSpacing(10)
        card_layout.setVerticalSpacing(10)

        # Row 0: STATUS
        status_caption = QtWidgets.QLabel("STATUS")
        status_caption.setObjectName("Caption")
        self.status_label = QtWidgets.QLabel()
        self.status_label.setObjectName("StatusPill")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        
        card_layout.addWidget(status_caption, 0, 0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        card_layout.addWidget(self.status_label, 0, 1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        # Row 1: STUDIO LICENSE
        license_caption = QtWidgets.QLabel("STUDIO LICENSE")
        license_caption.setObjectName("Caption")
        
        self.license_label = QtWidgets.QLabel("Checking...")
        self.license_label.setObjectName("LicensePill")
        self.license_label.setAlignment(QtCore.Qt.AlignCenter)
        
        self.license_btn = QtWidgets.QPushButton("Activate Key...")
        self.license_btn.setObjectName("LicenseBtn")
        self.license_btn.setFixedHeight(24)
        self.license_btn.setFixedWidth(110)
        self.license_btn.clicked.connect(self._open_license_dialog)
        
        card_layout.addWidget(license_caption, 1, 0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        card_layout.addWidget(self.license_label, 1, 1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        card_layout.addWidget(self.license_btn, 1, 2, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        # Row 2: INSTALL LOCATION Caption
        location_caption = QtWidgets.QLabel("INSTALL LOCATION")
        location_caption.setObjectName("Caption")
        card_layout.addWidget(location_caption, 2, 0, 1, 3, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Row 3: INSTALL LOCATION Path
        self.location_label = QtWidgets.QLabel()
        self.location_label.setObjectName("Location")
        self.location_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        card_layout.addWidget(self.location_label, 3, 0, 1, 3)

        card_layout.setColumnStretch(0, 0)
        card_layout.setColumnStretch(1, 1)
        card_layout.setColumnStretch(2, 0)
        root.addWidget(card)

        self.message_label = QtWidgets.QLabel(
            "Install adds the ScarTools Maya menu automatically. Uninstall "
            "removes the suite; artist-exported packages remain untouched."
        )
        self.message_label.setObjectName("Message")
        self.message_label.setWordWrap(True)
        root.addWidget(self.message_label)

        self.compatibility_label = QtWidgets.QLabel()
        self.compatibility_label.setObjectName("Compatibility")
        root.addWidget(self.compatibility_label)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(10)
        self.install_button = QtWidgets.QPushButton("INSTALL")
        self.install_button.setObjectName("PrimaryButton")
        _configure_setup_button(
            self.install_button, role="primary", fixed_width=150
        )
        self.uninstall_button = QtWidgets.QPushButton("UNINSTALL")
        self.uninstall_button.setObjectName("DangerButton")
        _configure_setup_button(
            self.uninstall_button, role="danger", fixed_width=110
        )
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.setObjectName("CloseButton")
        _configure_setup_button(self.close_button, fixed_width=80)
        buttons.addStretch(1)
        buttons.addWidget(self.install_button, 0, QtCore.Qt.AlignVCenter)
        buttons.addWidget(self.uninstall_button, 0, QtCore.Qt.AlignVCenter)
        buttons.addWidget(self.close_button, 0, QtCore.Qt.AlignVCenter)
        root.addLayout(buttons)

    def _connect(self):
        self.install_button.clicked.connect(self._run_install)
        self.uninstall_button.clicked.connect(self._run_uninstall)
        self.close_button.clicked.connect(self.close)

    def _open_license_dialog(self):
        dlg = LicenseActivationDialog(self)
        if hasattr(dlg, "exec"):
            dlg.exec()
        else:
            dlg.exec_()
        self._refresh_state()

    def nativeEvent(self, event_type, message):
        if _is_native_titlebar_double_click(message):
            self._queue_rollup()
            return True, 0
        return super(InstallerWindow, self).nativeEvent(event_type, message)

    def event(self, event):
        event_type = _non_client_double_click_type()
        if event_type is not None and event.type() == event_type:
            self._queue_rollup()
            event.accept()
            return True
        return super(InstallerWindow, self).event(event)

    def _queue_rollup(self):
        if self._rollup_pending:
            return
        self._rollup_pending = True

        def apply_toggle():
            try:
                self._toggle_rollup()
            finally:
                self._rollup_pending = False

        QtCore.QTimer.singleShot(0, apply_toggle)

    def _toggle_rollup(self):
        root = self.layout()
        if not self._rolled_up:
            self._rollup_state = [
                (widget, widget.isVisible()) for widget in _layout_widgets(root)
            ]
            for widget, _ in self._rollup_state:
                widget.hide()
            margins = root.contentsMargins()
            self._rollup_restore_layout = (
                margins.left(), margins.top(), margins.right(), margins.bottom(),
                root.spacing(),
            )
            self._rollup_restore_sizes = (
                QtCore.QSize(self.minimumSize()),
                QtCore.QSize(self.maximumSize()),
                QtCore.QSize(self.size()),
            )
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
            self.setMinimumHeight(1)
            self.setMaximumHeight(1)
            self.resize(self.width(), 1)
            self._rolled_up = True
            return

        minimum, maximum, size = self._rollup_restore_sizes
        left, top, right, bottom, spacing = self._rollup_restore_layout
        root.setContentsMargins(left, top, right, bottom)
        root.setSpacing(spacing)
        self.setMinimumSize(minimum)
        self.setMaximumSize(maximum)
        for widget, was_visible in self._rollup_state:
            widget.setVisible(was_visible)
        self.resize(size)
        self._rolled_up = False

    def _refresh_state(self):
        _, target_root, _ = _installation_paths()
        installed = _installed_version(target_root)
        maya_version = _maya_major_version()
        compatible = maya_version >= MIN_MAYA_VERSION
        self.compatibility_label.setText(
            "Maya {} detected  •  {}".format(
                maya_version,
                "SUPPORTED" if compatible else "UNSUPPORTED",
            )
        )
        self.location_label.setText(target_root.replace("\\", "/"))

        # License Check
        has_license, lic_msg, lic_details = get_installed_license()
        if has_license:
            self.license_label.setText("✓ " + lic_details.get("user_id", "") + " (" + lic_details.get("expiry_date", "") + ")")
            self.license_label.setStyleSheet("color: #34D399; background: #132E22; border: 1px solid #1B4D3E; border-radius: 4px; padding: 2px 6px; font-weight: 700; font-size: 10px;")
            self.license_btn.setText("Change...")
        else:
            self.license_label.setText("NOT ACTIVATED")
            self.license_label.setStyleSheet("color: #FB7185; background: #331A1E; border: 1px solid #5C2B32; border-radius: 4px; padding: 2px 6px; font-weight: 700; font-size: 10px;")
            self.license_btn.setText("Activate Key...")

        if installed is None:
            self.status_label.setText("NOT INSTALLED")
            self.install_button.setText("INSTALL")
            self.uninstall_button.setEnabled(False)
        elif installed == VERSION:
            self.status_label.setText("INSTALLED  v{}".format(installed))
            self.install_button.setText("REPAIR / REINSTALL")
            self.uninstall_button.setEnabled(True)
        else:
            self.status_label.setText("INSTALLED  v{}".format(installed))
            self.install_button.setText("UPDATE TO v{}".format(VERSION))
            self.uninstall_button.setEnabled(True)

        if not compatible:
            self.install_button.setEnabled(False)
            self.message_label.setText(
                "This release supports Maya {} and newer.".format(
                    MIN_MAYA_VERSION
                )
            )

    def _set_busy(self, busy, message=None):
        self.install_button.setEnabled(not busy)
        self.uninstall_button.setEnabled(not busy)
        self.close_button.setEnabled(not busy)
        if message:
            self.message_label.setText(message)
        QtWidgets.QApplication.processEvents()

    def _show_error(self, title, error):
        self.message_label.setText("Operation failed. No existing install was lost.")
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QtWidgets.QMessageBox.Critical)
        box.setText(str(error))
        box.setDetailedText(traceback.format_exc())
        if hasattr(box, "exec"):
            box.exec()
        else:
            box.exec_()

    def _run_install(self):
        # 1. If not activated, attempt automatic activation from bundled license file
        if not is_activated():
            source_root = os.path.dirname(_source_path())
            for cand in [LICENSE_FILENAME, "studio_license.json"]:
                bundled = os.path.join(source_root, cand)
                if os.path.isfile(bundled):
                    try:
                        with open(bundled, "r") as f:
                            b_data = json.load(f)
                        b_user = b_data.get("user_id", getpass.getuser())
                        b_key = b_data.get("license_key", "")
                        if b_key:
                            save_license(b_user, b_key)
                            break
                    except Exception:
                        pass

        # 2. If still not activated, open activation dialog
        if not is_activated():
            dlg = LicenseActivationDialog(self)
            res = dlg.exec() if hasattr(dlg, "exec") else dlg.exec_()
            if not is_activated():
                self.message_label.setText("Installation paused. Valid studio license authentication required.")
                self._refresh_state()
                return

        self._set_busy(True, "Installing and registering the ScarTools menu...")
        try:
            install()
            self.message_label.setText(
                "Installation complete. Open Modeling (Sanitizer), Rigging (Skin Tools & Character Finalizer), "
                "or Texturing (Shader Tools) from the ScarTools menu."
            )
        except Exception as exc:
            self._show_error("Installation Failed", exc)
        finally:
            self._set_busy(False)
            self._refresh_state()

    def _run_uninstall(self):
        answer = QtWidgets.QMessageBox.question(
            self,
            "Uninstall ScarTools",
            "Remove ScarTools from this Maya user?\n\n"
            "Artist-exported skin and shader packages will not be deleted.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return

        self._set_busy(True, "Unloading and removing ScarTools...")
        try:
            uninstall()
            self.message_label.setText(
                "Uninstall complete. Artist-exported packages were preserved."
            )
        except Exception as exc:
            self._show_error("Uninstall Failed", exc)
        finally:
            self._set_busy(False)
            self._refresh_state()

    def _apply_style(self):
        try:
            from scartools.ui.theme import apply as apply_theme
            apply_theme(self)
        except Exception:
            pass



_installer_window = None


def show_installer(user_id=None, license_key=None):
    global _installer_window

    if user_id and license_key:
        try:
            save_license(user_id, license_key)
        except Exception:
            pass

    try:
        if _installer_window:
            _installer_window.close()
            _installer_window.deleteLater()
    except Exception:
        pass

    # Purge any stale in-memory cached modules
    for mod in list(sys.modules.keys()):
        if mod.startswith("scartools"):
            try:
                del sys.modules[mod]
            except Exception:
                pass

    _installer_window = InstallerWindow(parent=maya_main_window())
    _installer_window.show()
    _installer_window.raise_()
    _installer_window.activateWindow()
    return _installer_window


def onMayaDroppedPythonFile(*_):
    """Maya drag-and-drop entry point."""
    for mod in list(sys.modules.keys()):
        if mod.startswith("scartools") or mod == "drag_drop_install":
            try:
                del sys.modules[mod]
            except Exception:
                pass
    return show_installer()




if __name__ == "__main__":
    show_installer()
