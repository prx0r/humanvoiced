"""Director: Qwen listens, advises, never judges alone.

Turns a brief + transcript + acoustic measurements into passage-level
performance notes (suspected misreads, pauses, energy mismatch) and
production advice (which preset, how much restoration). Output is a
recommendation: timestamps and suspected errors MUST be checked against
ASR alignment and the original audio before any retake request or payment
decision. Qwen never regenerates audio here.
"""
from __future__ import annotations

import json
import os
import urllib.request

MODEL = "qwen3.8-omni-flash"

PROMPT = """You are a narration director reviewing a voice take against its script.
You receive: script passages, ASR transcript with timings, acoustic measurements.
Return JSON ONLY with this shape:
{"performance_review": {"script_accuracy": "ok|review_required",
 "suspected_issues": [{"passage": "p01", "issue": "...", "recommended_action": "rerecord_passage_3|accept|listen"}],
 "overall": "..."},
 "production_advice": {"mastering_preset": "natural-clean|broadcast-presence|intimate-story|match-my-channel",
 "preserve_breaths": true, "restoration_strength": "none|light|moderate", "notes": "..."},
 "uncertainty": ["..."]}
Rules: never invent words not in the transcript; mark low-confidence findings
in uncertainty; restoration_strength moderate or higher only for noisy takes;
this review advises, it does not decide payment."""


class DirectorUnavailable(RuntimeError):
    pass


def _keys() -> list[tuple[str, str, str]]:
    out = []
    if os.environ.get("DASHSCOPE_API_KEY"):
        out.append(("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
                    os.environ["DASHSCOPE_API_KEY"], MODEL))
    if os.environ.get("OPENROUTER_API_KEY"):
        out.append(("https://openrouter.ai/api/v1/chat/completions",
                    os.environ["OPENROUTER_API_KEY"], MODEL))
    return out


def direct(script: str, transcript: str, segments: list[dict],
           acoustic: dict, direction: str = "") -> dict:
    """Returns the director's JSON + provider. Raises DirectorUnavailable
    without keys (DashScope needs console activation too)."""
    keys = _keys()
    if not keys:
        raise DirectorUnavailable("no director key (DASHSCOPE_API_KEY/OPENROUTER_API_KEY)")
    content = (PROMPT + f"\nDirection: {direction[:300]}\nScript: {script[:2000]}"
               f"\nTranscript: {transcript[:2000]}\nSegments: "
               f"{json.dumps(segments)[:800]}\nAcoustic: {json.dumps(acoustic)[:400]}")
    last = "unknown error"
    for url, key, model in keys:
        try:
            body = json.dumps({"model": model, "messages": [
                {"role": "user", "content": content}],
                "max_tokens": 800}).encode()
            req = urllib.request.Request(url, data=body, method="POST",
                                         headers={"Authorization": f"Bearer {key}",
                                                  "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read() or b"{}")
            text = (((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
            doc = json.loads(text[text.index("{"):text.rindex("}") + 1])
            doc["provider"] = model
            doc["verify"] = ("recommendations only — check timestamps and errors "
                             "against ASR alignment and the original audio")
            return doc
        except Exception as e:
            last = str(e)[:150]
    raise DirectorUnavailable(f"director failed: {last}")
