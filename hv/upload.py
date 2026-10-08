"""Upload completion: bytes in, hash computed server-side, never trusted.

Idempotent on content hash: re-uploading identical bytes returns the
existing receipt instead of duplicating. Original bytes frozen under
data/audio/raw/<sha256>.wav (R2 key layout mirrored for promotion).
"""
from __future__ import annotations

import os
from pathlib import Path

from hv.util import sha256, utcnow

RAW_DIR = os.getenv("HV_AUDIO_DIR", "data/audio/raw")


def store_upload(wav_bytes: bytes, contract_id: str) -> dict:
    if len(wav_bytes) < 44:
        raise ValueError("too small to be a WAV")
    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        raise ValueError("not a WAV file")
    digest = sha256(wav_bytes)
    dest = Path(RAW_DIR) / f"{digest}.wav"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.write_bytes(wav_bytes)
    return {"sha256": digest, "bytes": len(wav_bytes),
            "r2_key": f"audio/raw/{digest}.wav",
            "received_at": utcnow(), "contract_id": contract_id,
            "deduplicated": dest.exists()}
