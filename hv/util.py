"""Shared primitives: ids, hashes, server timestamps (never client clocks)."""
from __future__ import annotations

import hashlib
import secrets
import time


def uid(prefix: str = "") -> str:
    tok = secrets.token_hex(8)
    return f"{prefix}{tok}" if prefix else tok


def sha256(text: str | bytes) -> str:
    if isinstance(text, str):
        text = text.encode()
    return hashlib.sha256(text).hexdigest()


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
