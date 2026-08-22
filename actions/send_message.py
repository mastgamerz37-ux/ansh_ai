import json
import difflib
import re
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path

from actions.safe_text_entry import safe_type_then_enter
from actions.instagram_browser import (
    prepare_instagram_draft as _controlled_instagram_prepare_draft,
    send_instagram_draft as _controlled_instagram_send_draft,
    clear_instagram_draft as _controlled_instagram_clear_draft,
)

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.06
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

ANSH_TEXT_FOOTER = "CREATED BY ANSH"
AMBIGUOUS_PREFIX = "RECIPIENT_AMBIGUOUS|"
NO_MATCH_PREFIX = "RECIPIENT_NOT_FOUND|"
MESSAGE_DUPLICATE_TTL_SECONDS = 120.0
_recent_send_fingerprints: dict[str, float] = {}
_pending_message_approval: dict = {}
_pending_message_lock = threading.Lock()


def _set_pending_message(platform: str, receiver: str, message: str) -> None:
    with _pending_message_lock:
        _pending_message_approval.clear()
        _pending_message_approval.update({
            "platform": str(platform or "").strip(),
            "receiver": str(receiver or "").strip(),
            "message_text": str(message or "").strip(),
            "created_at": time.time(),
        })


def _get_pending_message() -> dict:
    with _pending_message_lock:
        return dict(_pending_message_approval)


def _clear_pending_message() -> None:
    with _pending_message_lock:
        _pending_message_approval.clear()


def _is_instagram_platform(platform: str) -> bool:
    key = re.sub(r"[^a-z]+", " ", str(platform or "").lower()).strip()
    return key in {"instagram", "ig", "insta"} or "instagram" in key.split()


def _with_ansh_footer(text: str) -> str:
    message = str(text or "").strip()
    if not message:
        return ""
    if ANSH_TEXT_FOOTER in message.upper():
        return message
    return message


def normalize_outgoing_message_text(text: str) -> str:
    message = re.sub(r"[ \t]+", " ", str(text or "").strip())
    message = re.sub(r"\s+\n", "\n", message)
    message = re.sub(r"\n\s+", "\n", message)
    if not message:
        return ""

    def fix_sentence(match: re.Match) -> str:
        prefix = match.group(1)
        char = match.group(2)
        return prefix + char.upper()

    message = re.sub(r"(^|[.!?]\s+)([a-z])", fix_sentence, message)
    return message


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", str(text or ""))
        if not unicodedata.combining(ch)
    )


def _name_norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _strip_accents(text).lower())


def _message_norm(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\bcreated\s+by\s+ansh\b", "", value, flags=re.IGNORECASE)
    value = _strip_accents(value).lower()
    return re.sub(r"[^a-z0-9]+", "", value)


def _send_fingerprint(platform: str, receiver: str, message: str) -> str:
    return "|".join((
        _name_norm(platform),
        _name_norm(receiver),
        _message_norm(message),
    ))


def _prune_recent_sends(now: float | None = None) -> None:
    now = time.time() if now is None else now
    expired = [
        key for key, sent_at in _recent_send_fingerprints.items()
        if now - sent_at > MESSAGE_DUPLICATE_TTL_SECONDS
    ]
    for key in expired:
        _recent_send_fingerprints.pop(key, None)


def _duplicate_message_result(platform: str, receiver: str) -> str:
    target = receiver or "current chat"
    return f"Duplicate message suppressed; already sent to {target} via {platform}."


def _check_duplicate_send(platform: str, receiver: str, message: str) -> str | None:
    now = time.time()
    _prune_recent_sends(now)
    key = _send_fingerprint(platform, receiver, message)
    sent_at = _recent_send_fingerprints.get(key)
    if sent_at and now - sent_at <= MESSAGE_DUPLICATE_TTL_SECONDS:
        return _duplicate_message_result(platform, receiver)
    return None


def _record_successful_send(platform: str, receiver: str, message: str) -> None:
    _prune_recent_sends()
    _recent_send_fingerprints[_send_fingerprint(platform, receiver, message)] = time.time()


def _message_send_succeeded(result: str) -> bool:
    lowered = str(result or "").lower()
    return (
        "message sent" in lowered
        or "safely sent" in lowered
        or "sent in the open" in lowered
        or "sent to" in lowered
    ) and "could not" not in lowered and "duplicate message suppressed" not in lowered


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_os() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


def _paste_text(text: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    paste_hotkey = ("command", "v") if os_name == "mac" else ("ctrl", "v")

    if _PYPERCLIP:
        try:
            pyperclip.copy(text)
            time.sleep(0.15)
            pyautogui.hotkey(*paste_hotkey)
            time.sleep(0.1)
            return
        except Exception as e:
            print(f"[SendMessage] ⚠️ Clipboard paste failed, typing instead: {e}")
    pyautogui.write(text, interval=0.03)


def _clear_and_paste(text: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    select_all = ("command", "a") if os_name == "mac" else ("ctrl", "a")
    pyautogui.hotkey(*select_all)
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    _paste_text(text)


def _open_app(app_name: str) -> bool:
    _require_pyautogui()
    os_name = _get_os()

    try:
        if os_name == "windows":
            pyautogui.press("win")
            time.sleep(0.5)
            _paste_text(app_name)
            time.sleep(0.6)
            pyautogui.press("enter")
            time.sleep(2.5)
            return True

        elif os_name == "mac":
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["open", "-a", f"{app_name}.app"],
                    capture_output=True, text=True, timeout=10,
                )
            time.sleep(2.5)
            return result.returncode == 0

        else: 
            launched = False
            for launcher in [
                ["gtk-launch", app_name.lower()],
                [app_name.lower()],
            ]:
                try:
                    subprocess.Popen(
                        launcher,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            time.sleep(2.5)
            return launched

    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open {app_name}: {e}")
        return False


def _open_browser_url(url: str) -> bool:
    import webbrowser
    try:
        webbrowser.open(url)
        time.sleep(4.0) 
        return True
    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open browser: {e}")
        return False


def _search_in_app(query: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    search_hotkey = ("command", "f") if os_name == "mac" else ("ctrl", "f")

    pyautogui.hotkey(*search_hotkey)
    time.sleep(0.5)
    _clear_and_paste(query)
    time.sleep(1.0)


def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    if not _open_app(app_name):
        return f"Could not open {app_name}."

    time.sleep(1.0)
    if receiver:
        _search_in_app(receiver)
        pyautogui.press("enter")
        time.sleep(0.8)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)
    return f"Message sent to {receiver or 'active chat'} via {app_name}."


def _send_whatsapp(receiver: str, message: str) -> str:
    return _desktop_send("WhatsApp", receiver, message)


def _send_telegram(receiver: str, message: str) -> str:
    return _desktop_send("Telegram", receiver, message)


def _send_signal(receiver: str, message: str) -> str:
    return _desktop_send("Signal", receiver, message)


def _send_discord(receiver: str, message: str) -> str:
    return _desktop_send("Discord", receiver, message)


def _send_instagram(receiver: str, message: str) -> str:
    duplicate_target = receiver or "current chat"
    duplicate = _check_duplicate_send("Instagram", duplicate_target, message)
    if duplicate:
        return duplicate
    return _controlled_instagram_prepare_draft(receiver, message)


def _send_messenger(receiver: str, message: str) -> str:
    return _desktop_send("Messenger", receiver, message)


_PLATFORM_MAP = [
    ({"whatsapp", "wp", "wapp"},              _send_whatsapp),
    ({"telegram", "tg"},                      _send_telegram),
    ({"instagram", "ig", "insta"},            _send_instagram),
    ({"signal"},                               _send_signal),
    ({"discord"},                              _send_discord),
    ({"messenger", "facebook", "fb"},         _send_messenger),
]


def _resolve_platform(platform_str: str):
    key = re.sub(r"\s+", " ", str(platform_str or "").lower()).strip()
    for keywords, handler in _PLATFORM_MAP:
        if key in keywords:
            return handler
    for keywords, handler in _PLATFORM_MAP:
        if any(
            len(keyword) >= 4
            and re.search(
                rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])",
                key,
            )
            for keyword in keywords
        ):
            return handler
    return lambda r, m: _desktop_send(platform_str.strip().title(), r, m)


def send_message(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params       = parameters or {}
    action       = str(params.get("action", "send") or "send").lower().strip()
    receiver     = str(params.get("receiver", "") or "").strip()
    message_text = str(params.get("message_text", "") or "").strip()
    platform     = str(params.get("platform", "whatsapp") or "whatsapp").strip()
    platform_key = platform.lower().strip()

    if action in {"approve", "confirm"}:
        return prepare_message_reply({"action": "approve"}, player=player)
    if action in {"cancel", "discard", "deny"}:
        return prepare_message_reply({"action": "cancel"}, player=player)

    no_recipient_keywords = {
        "current", "active", "focused", "frontmost", "any", "generic",
        "instagram", "ig", "insta",
        "whatsapp", "wp", "wapp",
        "telegram", "tg",
        "discord",
        "messenger", "facebook", "fb",
    }
    recipient_optional = any(keyword in platform_key for keyword in no_recipient_keywords)

    if not receiver and not recipient_optional:
        return "Please specify a recipient."
    if not message_text:
        return "Please specify the message content."

    message_text = _with_ansh_footer(message_text)
    duplicate = _check_duplicate_send(platform, receiver, message_text)
    if duplicate:
        print(f"[SendMessage] ⏭️ {duplicate}")
        if player and hasattr(player, "write_log"):
            player.write_log(f"[msg] {duplicate}")
        return duplicate

    preview = message_text[:50] + ("…" if len(message_text) > 50 else "")
    print(f"[SendMessage] 📨 {platform} → {receiver}: {preview}")
    if player and hasattr(player, "write_log"):
        player.write_log(f"[msg] {platform} → {receiver}")

    try:
        handler = _resolve_platform(platform)
        result  = handler(receiver, message_text)
    except Exception as e:
        result = f"Could not send message: {e}"

    if _message_send_succeeded(result):
        _record_successful_send(platform, receiver, message_text)
        _clear_pending_message()
    elif _is_instagram_platform(platform_key) and "draft typed" in (result or "").lower():
        _set_pending_message(platform, receiver, message_text)

    lowered = (result or "").lower()
    if "draft typed" in lowered:
        status_icon = "📝"
    elif "sent" in lowered:
        status_icon = "✅"
    else:
        status_icon = "❌"
    print(f"[SendMessage] {status_icon} {result}")
    if player and hasattr(player, "write_log"):
        player.write_log(f"[msg] {result}")

    return result


def prepare_message_reply(
    parameters: dict | None = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action", "prepare") or "prepare").lower().strip()

    if action in {"approve", "confirm", "send"}:
        pending = _get_pending_message()
        if not pending:
            return "There is no pending message awaiting approval."
        platform = str(pending.get("platform", "") or "")
        platform_key = platform.lower()
        if _is_instagram_platform(platform_key):
            result = _controlled_instagram_send_draft()
        else:
            result = send_message({
                "action": "send",
                "platform": platform,
                "receiver": pending.get("receiver", ""),
                "message_text": pending.get("message_text", ""),
            }, player=player)
        if _message_send_succeeded(result):
            _record_successful_send(
                platform,
                str(pending.get("receiver", "") or ""),
                str(pending.get("message_text", "") or ""),
            )
            _clear_pending_message()
        return result

    if action in {"cancel", "discard", "deny"}:
        pending = _get_pending_message()
        platform_key = str(pending.get("platform", "") or "").lower()
        cleared = True
        if _is_instagram_platform(platform_key):
            cleared = _controlled_instagram_clear_draft()
        _clear_pending_message()
        return "Pending message cancelled." if cleared else "Pending message cancelled, but the visible draft could not be cleared."

    receiver = str(params.get("receiver", "") or "").strip()
    message_text = str(params.get("message_text", "") or params.get("draft", "") or "").strip()
    platform = str(params.get("platform", "whatsapp") or "whatsapp").strip()
    if not message_text:
        return "Please provide the reply text to prepare."

    platform_key = platform.lower()
    if _is_instagram_platform(platform_key):
        prepared_text = _with_ansh_footer(message_text)
        result = _controlled_instagram_prepare_draft(receiver, prepared_text)
        if "draft typed" not in result.lower():
            return result
        _set_pending_message(platform, receiver, prepared_text)
    else:
        _set_pending_message(platform, receiver, message_text)

    payload = {
        "platform": platform,
        "receiver": receiver or "current chat",
        "message_text": normalize_outgoing_message_text(message_text),
    }
    return (
        "MESSAGE_APPROVAL_REQUIRED|"
        + json.dumps(payload, separators=(",", ":"))
        + "\nDraft prepared. Ask the user to approve, revise, or cancel it."
    )