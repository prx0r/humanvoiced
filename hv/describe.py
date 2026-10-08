"""Voice description via OpenRouter (Omni-Flash text-side).

Sends transcript + acoustic measurements (never raw audio — Omni-Flash on
OpenRouter is text I/O) with the constrained-extractor prompt. Returns the
same controlled-JSON shape as hv.audio.describe_stub. Falls back to the
stub with zero keys, zero spend.
"""
from __future__ import annotations

import json
import os
import urllib.request

PROMPT = ("Describe only audible vocal characteristics implied by this "
          "transcript metadata. Use controlled vocabulary: texture "
          "(smooth/breathy/husky/raspy/grainy/airy), resonance, energy, "
          "prosody, delivery. Never infer ethnicity, nationality, age, "
          "gender, personality, or medical states. Unknown where evidence "
          "is insufficient. Return JSON only, no overall score.")


def describe_openrouter(transcript: str, acoustic: dict) -> dict:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return _chat_complete("https://openrouter.ai/api/v1/chat/completions", key,
                              "qwen/qwen3.8-omni-flash", transcript, acoustic)
    return _dashscope_describe(transcript, acoustic)


def _dashscope_describe(transcript: str, acoustic: dict) -> dict:
    import os as _os
    key = _os.environ.get("DASHSCOPE_API_KEY", "")
    if not key:
        from hv import audio as _a
        return _a.describe_stub(transcript, acoustic)
    return _chat_complete("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
                          key, "qwen3.8-omni-flash", transcript, acoustic)


def _chat_complete(url: str, key: str, model: str, transcript: str, acoustic: dict) -> dict:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT + f"\nTranscript: {transcript[:800]}\nAcoustic: {json.dumps(acoustic)[:400]}"}],
        "max_tokens": 400}).encode()
    req = urllib.request.Request(url,
                                 data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read() or b"{}")
    text = (((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
    try:
        start = text.index("{")
        return json.loads(text[start:text.rindex("}") + 1])
    except ValueError:
        if isinstance(d, dict) and d.get("error"):
            return {"error": str(d["error"])[:200], "model": model}
        return {"description": text[:500], "model": model,
                "unparsed": True}
