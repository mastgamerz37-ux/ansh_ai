"""Cryptographic Product Key validation and master key registry for ANSH AI.
Developed by Anshu Dubey.
"""

from __future__ import annotations

import hashlib
import hmac
import re

_KEY_SECRET = b"ANSHU_DUBEY_ANSH_AI_SECURE_SALT_2026_MASTER"

# 10 Pre-generated Master Product Keys for ANSH AI
MASTER_PRODUCT_KEYS = [
    "ANSH-7K9A-2M8X-9P4W-3B5D",
    "ANSH-4R8C-6N2J-8T1Y-7F9L",
    "ANSH-9W2M-3B7D-5K8X-1P4N",
    "ANSH-2T5Y-8F1L-4R9C-6N3J",
    "ANSH-8K3X-1P6N-7W2M-9B4D",
    "ANSH-3B9D-5K2X-8T4Y-1F7L",
    "ANSH-6N1J-7F4L-2T8Y-9R3C",
    "ANSH-1P7N-9B3D-4R6C-8K2X",
    "ANSH-5K8X-2T1Y-6N9J-3B7D",
    "ANSH-8T4Y-6N7J-1P2N-5K9X",
]


def normalize_key(raw_key: str) -> str:
    """Format key to standard uppercase format: ANSH-XXXX-XXXX-XXXX-XXXX."""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(raw_key or "")).upper()
    if cleaned.startswith("ANSH"):
        cleaned = cleaned[4:]
    if len(cleaned) != 16:
        return str(raw_key or "").strip().upper()
    return f"ANSH-{cleaned[0:4]}-{cleaned[4:8]}-{cleaned[8:12]}-{cleaned[12:16]}"


def is_valid_product_key(product_key: str) -> bool:
    """Validate product key against master keys or mathematical signature."""
    norm = normalize_key(product_key)
    if norm in MASTER_PRODUCT_KEYS:
        return True

    # Mathematical signature check for algorithmic keys
    pattern = r"^ANSH-([A-Z0-9]{4})-([A-Z0-9]{4})-([A-Z0-9]{4})-([A-Z0-9]{4})$"
    m = re.match(pattern, norm)
    if not m:
        return False

    payload = f"{m.group(1)}{m.group(2)}{m.group(3)}".encode("utf-8")
    expected_check = hmac.new(_KEY_SECRET, payload, hashlib.sha256).hexdigest().upper()[:4]
    return m.group(4) == expected_check
