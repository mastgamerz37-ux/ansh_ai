"""ANSH AI Licensing & 3-Day Trial Engine.
Developed by Anshu Dubey.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .keys import is_valid_product_key, normalize_key

TRIAL_DURATION_SECONDS = 3 * 24 * 3600  # 3 Days (72 Hours)
_SECRET_SALT = b"ANSHU_DUBEY_LICENSE_SALT_SECURE_2026"


def get_app_data_dir() -> Path:
    """Return the user-isolated application data directory (%APPDATA%/ANSH_AI)."""
    if platform.system() == "Windows":
        app_data = os.environ.get("APPDATA")
        if app_data:
            path = Path(app_data) / "ANSH_AI"
        else:
            path = Path.home() / "AppData" / "Roaming" / "ANSH_AI"
    else:
        path = Path.home() / ".ansh_ai"

    path.mkdir(parents=True, exist_ok=True)
    return path


LICENSE_FILE = get_app_data_dir() / "license.dat"


def _encrypt_data(raw_text: str) -> str:
    """Obfuscated / HMAC hashed envelope."""
    data = raw_text.encode("utf-8")
    sig = hashlib.sha256(_SECRET_SALT + data).hexdigest()
    payload = json.dumps({"d": raw_text, "s": sig})
    return base64.b64encode(payload.encode("utf-8")).decode("utf-8")


def _decrypt_data(enc_text: str) -> str | None:
    """Validate and decrypt envelope."""
    try:
        payload = json.loads(base64.b64decode(enc_text.encode("utf-8")).decode("utf-8"))
        raw_text = payload.get("d", "")
        sig = payload.get("s", "")
        expected_sig = hashlib.sha256(_SECRET_SALT + raw_text.encode("utf-8")).hexdigest()
        if sig == expected_sig:
            return raw_text
    except Exception:
        pass
    return None


def _get_registry_license() -> str:
    """Read license from Windows registry."""
    if platform.system() != "Windows":
        return ""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\ANSH_AI\Licensing",
            0,
            winreg.KEY_READ,
        )
        val, _ = winreg.QueryValueEx(key, "LicenseData")
        winreg.CloseKey(key)
        return str(val or "")
    except Exception:
        return ""


def _save_registry_license(data: str) -> None:
    """Save license to Windows registry."""
    if platform.system() != "Windows":
        return
    try:
        import winreg
        key = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"Software\ANSH_AI\Licensing",
            0,
            winreg.KEY_ALL_ACCESS,
        )
        winreg.SetValueEx(key, "LicenseData", 0, winreg.REG_SZ, data)
        winreg.CloseKey(key)
    except Exception:
        pass


@dataclass
class LicenseStatus:
    is_valid: bool
    is_trial: bool
    is_expired: bool
    trial_days_left: float
    trial_hours_left: float
    message: str
    product_key: str = ""
    tamper_detected: bool = False


class LicensingEngine:
    def __init__(self):
        self.state_file = LICENSE_FILE
        self._ensure_init()

    def _load_state(self) -> dict:
        # Check file first
        if self.state_file.exists():
            try:
                enc = self.state_file.read_text(encoding="utf-8").strip()
                dec = _decrypt_data(enc)
                if dec:
                    return json.loads(dec)
            except Exception:
                pass

        # Check registry backup
        reg_enc = _get_registry_license()
        if reg_enc:
            dec = _decrypt_data(reg_enc)
            if dec:
                return json.loads(dec)

        return {}

    def _save_state(self, state: dict) -> None:
        raw_text = json.dumps(state)
        enc = _encrypt_data(raw_text)
        try:
            self.state_file.write_text(enc, encoding="utf-8")
        except Exception:
            pass
        _save_registry_license(enc)

    def _ensure_init(self) -> None:
        state = self._load_state()
        now = time.time()
        if not state:
            state = {
                "installed_at": now,
                "last_seen_at": now,
                "product_key": "",
                "activated": False,
            }
            self._save_state(state)

    def get_status(self) -> LicenseStatus:
        state = self._load_state()
        now = time.time()
        product_key = state.get("product_key", "")
        activated = state.get("activated", False)

        # 1. Activated with valid product key
        if activated and product_key and is_valid_product_key(product_key):
            return LicenseStatus(
                is_valid=True,
                is_trial=False,
                is_expired=False,
                trial_days_left=0.0,
                trial_hours_left=0.0,
                message="Permanent License Activated",
                product_key=normalize_key(product_key),
            )

        installed_at = state.get("installed_at", now)
        last_seen_at = state.get("last_seen_at", now)

        # 2. Tamper check: Clock rollback detection
        tamper = False
        if now < last_seen_at - 60:  # rolled back by more than a minute
            tamper = True

        # Update last seen timestamp
        if not tamper:
            state["last_seen_at"] = now
            self._save_state(state)

        elapsed = now - installed_at
        remaining = TRIAL_DURATION_SECONDS - elapsed

        if tamper:
            return LicenseStatus(
                is_valid=False,
                is_trial=True,
                is_expired=True,
                trial_days_left=0.0,
                trial_hours_left=0.0,
                message="System clock rollback detected. Product Key required to unlock.",
                tamper_detected=True,
            )

        if remaining <= 0:
            return LicenseStatus(
                is_valid=False,
                is_trial=True,
                is_expired=True,
                trial_days_left=0.0,
                trial_hours_left=0.0,
                message="Your 3-day free trial has expired. Please enter a valid Product Key to continue.",
            )

        days_left = remaining / 86400.0
        hours_left = remaining / 3600.0
        return LicenseStatus(
            is_valid=True,
            is_trial=True,
            is_expired=False,
            trial_days_left=days_left,
            trial_hours_left=hours_left,
            message=f"Free Trial Active: {int(days_left)} days ({int(hours_left)} hours) remaining",
        )

    def activate(self, product_key: str) -> tuple[bool, str]:
        norm = normalize_key(product_key)
        if not is_valid_product_key(norm):
            return False, "Invalid Product Key. Please check the key and try again."

        state = self._load_state()
        state["product_key"] = norm
        state["activated"] = True
        state["activated_at"] = time.time()
        self._save_state(state)
        return True, f"Success! Product Key {norm} activated permanently. Thank you for using ANSH AI!"


_engine: LicensingEngine | None = None


def get_licensing_engine() -> LicensingEngine:
    global _engine
    if _engine is None:
        _engine = LicensingEngine()
    return _engine


def check_license_status() -> LicenseStatus:
    return get_licensing_engine().get_status()


def activate_license(product_key: str) -> tuple[bool, str]:
    return get_licensing_engine().activate(product_key)
