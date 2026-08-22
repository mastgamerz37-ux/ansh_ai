import json
import os
import platform
import sys
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def get_app_data_dir() -> Path:
    """Return %APPDATA%/ANSH_AI on Windows, ~/.ansh_ai elsewhere."""
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

BASE_DIR        = get_base_dir()
LOCAL_CONFIG    = BASE_DIR / "config" / "api_keys.json"
APPDATA_DIR     = get_app_data_dir()
CONFIG_FILE     = APPDATA_DIR / "api_keys.json"

def ensure_config_dir() -> None:
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "config").mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists() or LOCAL_CONFIG.exists()

def load_api_keys() -> dict:
    # 1. Try AppData first
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 2. Fallback to local project config and migrate
    if LOCAL_CONFIG.exists():
        try:
            data = json.loads(LOCAL_CONFIG.read_text(encoding="utf-8"))
            if data:
                try:
                    ensure_config_dir()
                    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
                except Exception:
                    pass
                return data
        except Exception:
            pass

    return {}

def save_api_keys(gemini_api_key: str) -> None:
    ensure_config_dir()
    data = load_api_keys()
    data["gemini_api_key"] = gemini_api_key.strip()
    data_json = json.dumps(data, indent=2)

    try:
        CONFIG_FILE.write_text(data_json, encoding="utf-8")
    except Exception as e:
        print(f"[Config] AppData save failed: {e}")

    try:
        LOCAL_CONFIG.write_text(data_json, encoding="utf-8")
    except Exception:
        pass

def get_gemini_key() -> str | None:
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    key = load_api_keys().get("gemini_api_key")
    return key.strip() if key else None

def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)

def get_assistant_name() -> str:
    """Return the configured assistant name, or 'ANSH' if not set."""
    return load_api_keys().get("assistant_name", "ANSH") or "ANSH"

def get_user_name() -> str:
    """Return the configured user name for addressing."""
    return load_api_keys().get("user_name", "")

def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to config."""
    ensure_config_dir()
    data = load_api_keys()
    data["assistant_name"] = assistant_name.strip() or "ANSH"
    data["user_name"] = user_name.strip()
    data_json = json.dumps(data, indent=4)

    try:
        CONFIG_FILE.write_text(data_json, encoding="utf-8")
    except Exception:
        pass

    try:
        LOCAL_CONFIG.write_text(data_json, encoding="utf-8")
    except Exception:
        pass

def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)

def save_brief_enabled(enabled: bool) -> None:
    ensure_config_dir()
    data = load_api_keys()
    data["morning_brief_enabled"] = enabled
    data_json = json.dumps(data, indent=4)

    try:
        CONFIG_FILE.write_text(data_json, encoding="utf-8")
    except Exception:
        pass

    try:
        LOCAL_CONFIG.write_text(data_json, encoding="utf-8")
    except Exception:
        pass