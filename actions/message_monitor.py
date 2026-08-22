import json
import re
import subprocess
from pathlib import Path

from actions.instagram_browser import read_instagram_open_chat


def _base_dir() -> Path:
    if getattr(__import__("sys"), "frozen", False):
        return Path(__import__("sys").executable).parent
    return Path(__file__).resolve().parent.parent


def _get_os() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _clean_line(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _is_noise_line(text: str) -> bool:
    value = _clean_line(text).lower()
    if not value:
        return True
    if value in {
        "messages", "search", "notes", "requests", "message...", "message",
        "imessage", "to:", "new message", "details", "info",
    }:
        return True
    if re.match(r"^(active|online|seen|sent|delivered|read|typing|now)$", value):
        return True
    if re.match(r"^(active|seen|sent|delivered|read).*(ago|now)$", value):
        return True
    if re.match(r"^\d+[smhdw]\b", value) or value.endswith(" ago"):
        return True
    return False


def _format_update(update: dict) -> str:
    if not update.get("ok"):
        platform = update.get("platform", "Messaging")
        return f"{platform}: could not read open chat. {update.get('error', 'Open a supported chat and try again.')}"
    platform = update.get("platform", "Messaging")
    recipient = update.get("recipient") or "unknown recipient"
    latest = update.get("latest_message") or "No readable message found."
    can_reply = "yes" if update.get("can_reply") else "no"
    count = update.get("message_count") or len(update.get("conversation_context") or update.get("visible_messages") or [])
    return f"{platform}: {recipient} latest message: \"{latest}\". Read {count} current-chat lines. Can reply: {can_reply}."


def check_messages(parameters: dict | None = None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    platform = str(params.get("platform", "all") or "all").lower().strip()
    try:
        max_messages = int(params.get("max_messages", 30) or 30)
    except Exception:
        max_messages = 30
    updates = []
    if platform in {"all", "instagram", "ig", "insta"}:
        updates.append(read_instagram_open_chat())
    readable = [u for u in updates if u.get("ok")]
    summary = "\n".join(_format_update(update) for update in updates)
    payload = {"updates": updates, "readable_count": len(readable)}
    return "MESSAGES_CHECKED|" + json.dumps(payload, separators=(",", ":")) + "\n" + summary
