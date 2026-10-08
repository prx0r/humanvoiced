"""Hosted cleanup providers: one-request narration cleaning.

Registry of what each provider actually does, costs and needs. Local DSP
remains the default (zero marginal cost, fully reproducible); hosted
providers are benchmark contestants and paid upgrades. Without keys every
hosted call refuses with a clear message -- never a silent local fallback
masquerading as a provider result.

veed/clean-audio on fal.ai is the price/performance first trial
(MossFormer2 48k, -19 LUFS default, async queue). Auphonic is the complete
mastering reference. ElevenLabs Voice Isolator is the difficult-audio
baseline. Prices below are provider-published; re-verify at integration.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

# Provider-published price/offers. Re-verify when keys land.
VEED_SLUG = "veed/clean-audio"
VEED_PER_MIN_USD = 0.0125
VEED_MIN_MINUTES = 1.0
VEED_DEFAULT_LUFS = -19.0

PROVIDERS = {
    "local": {"role": "default DSP chain, zero marginal cost",
              "needs_key": None, "production_enabled": True},
    "veed-fal": {"role": "default hosted cleaner (MossFormer2 48k)",
                 "needs_key": "FAL_KEY", "production_enabled": False,
                 "note": "needs FAL_KEY + blind benchmark before default"},
    "auphonic": {"role": "complete mastering reference / premium renderer",
                 "needs_key": "AUPHONIC_KEY", "production_enabled": False},
    "elevenlabs-isolator": {"role": "difficult-audio baseline",
                            "needs_key": "ELEVENLABS_KEY", "production_enabled": False},
}


class ProviderUnavailable(RuntimeError):
    pass


def fal_key() -> str:
    return os.environ.get("FAL_KEY", "")


def _req(url: str, key: str, payload: dict | None = None,
         timeout: int = 60) -> dict:
    data = json.dumps(payload or {}).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        method="POST" if payload is not None else "GET",
        headers={"Authorization": f"Key {key}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except Exception as e:
        raise ProviderUnavailable(f"fal request failed: {e}"[:200])


def fal_upload(wav_path: str, key: str) -> str:
    """Upload local audio to fal storage; returns the file URL for queue input."""
    import mimetypes
    fname = os.path.basename(wav_path)
    init = _req("https://rest.alpha.fal.ai/storage/upload/initiate", key,
                {"file_name": fname,
                 "content_type": mimetypes.guess_type(fname)[0] or "audio/wav"})
    upload_url = init.get("upload_url")
    file_url = init.get("file_url")
    if not upload_url or not file_url:
        raise ProviderUnavailable(f"fal storage init failed: {str(init)[:200]}")
    with open(wav_path, "rb") as f:
        blob = f.read()
    put = urllib.request.Request(upload_url, data=blob, method="PUT",
                                 headers={"Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(put, timeout=120):
            pass
    except Exception as e:
        raise ProviderUnavailable(f"fal upload failed: {e}"[:200])
    return file_url


def veed_clean(src_wav: str, dst_path: str, key: str = "",
               target_lufs: float = VEED_DEFAULT_LUFS,
               poll_timeout: int = 1200) -> dict:
    """Run veed/clean-audio through the fal queue. Sync poll (processing runs
    ~0.2-0.5x audio duration plus queue startup). Raises ProviderUnavailable
    without a key or on job failure -- callers fall back only explicitly."""
    key = key or fal_key()
    if not key:
        raise ProviderUnavailable("FAL_KEY missing: hosted cleaning unavailable")
    audio_url = fal_upload(src_wav, key)
    sub = _req(f"https://queue.fal.run/{VEED_SLUG}",
               key, {"audio_url": audio_url, "target_lufs": target_lufs})
    rid = sub.get("request_id")
    if not rid:
        raise ProviderUnavailable(f"fal submit failed: {str(sub)[:200]}")
    deadline = time.time() + poll_timeout
    while time.time() < deadline:
        st = _req(f"https://queue.fal.run/{VEED_SLUG}/requests/{rid}/status", key)
        status = st.get("status")
        if status in ("COMPLETED", "FAILED"):
            break
        time.sleep(10)
    else:
        raise ProviderUnavailable("fal job timed out waiting")
    if st.get("status") != "COMPLETED":
        raise ProviderUnavailable(f"fal job failed: {str(st)[:300]}")
    data = st.get("data") or st.get("response") or {}
    audio = data.get("audio") or {}
    url = audio.get("url")
    if not url:
        raise ProviderUnavailable(f"fal result had no audio url: {str(data)[:200]}")
    _download(url, dst_path)
    return {"provider": "veed-fal", "model": VEED_SLUG,
            "target_lufs": target_lufs, "request_id": rid,
            "result_name": audio.get("file_name", "")}


def _download(url: str, dst_path: str):
    try:
        with urllib.request.urlopen(url, timeout=300) as r, open(dst_path, "wb") as f:
            f.write(r.read())
    except Exception as e:
        raise ProviderUnavailable(f"result download failed: {e}"[:200])


def clean_quote_usd(minutes: float) -> float:
    """VEED passthrough estimate: per-minute rate, one-minute minimum."""
    billed = max(VEED_MIN_MINUTES, minutes)
    return round(billed * VEED_PER_MIN_USD, 4)
