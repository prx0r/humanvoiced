"""Transcription provider: Cloudflare Workers AI Whisper default.

~$0.000513/min → a 30s sample costs ~$0.00026. Local deterministic stub
when no credentials (tests/dev). Transcripts feed script alignment and
draft prefill; never the sole basis for quality judgments.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request


def _vault(key: str) -> str:
    try:
        out = subprocess.run(["agent-vault", "vault", "credential", "get", key, "--vault", "oracle"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return out.splitlines()[-1] if out else ""
    except Exception:
        return ""


def transcribe(wav_bytes: bytes, language: str = "en") -> dict:
    """Returns {text, language, segments, vtt, provider}. Raises on failure."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN") or _vault("CLOUDFLARE_API_TOKEN")
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or _vault("CLOUDFLARE_ACCOUNT_ID")
    if not token or not acct:
        return {"text": "", "language": language, "segments": [],
                "provider": "none", "note": "no credentials"}
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/openai/whisper-large-v3-turbo",
        data=wav_bytes, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "audio/wav"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read() or b"{}")
    res = (d.get("result") or {})
    return {"text": res.get("text", ""), "language": (res.get("transcription_info") or {}).get("language", language),
            "segments": res.get("segments", []), "vtt": res.get("vtt", ""),
            "provider": "cf-whisper-turbo"}
