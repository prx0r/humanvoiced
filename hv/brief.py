"""Production briefs: agent intent -> recordable passages with timing.

Three input modes, one internal schema. Passages split on linguistic and
performance boundaries (sentences), never blind clock slices, so the final
assembly keeps natural prosody. Soft timing lets the editor fit cuts around
speech; hard timing must fit the window or the brief is rejected back to the
agent -- voices are never time-stretched into unnaturalness.
"""
from __future__ import annotations

import re

from hv.util import sha256

MODES = ("script", "storyboard", "timed")
TIMINGS = ("soft", "hard")
WORDS_PER_MINUTE = 150


def split_passages(script_text: str) -> list[str]:
    """Sentence-aware split. Keeps abbreviations and numbers intact."""
    text = re.sub(r"\s+", " ", script_text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # merge fragments too short to perform alone (addresses, asides)
        if out and len(p.split()) < 4 and not p[-1] in ".!?":
            out[-1] = out[-1] + " " + p
        else:
            out.append(p)
    return out


def estimate_ms(words: int, wpm: int = WORDS_PER_MINUTE) -> int:
    return int(words / max(1, wpm) * 60000)


def compile(brief: dict, script_text: str) -> dict:
    """Compile a brief into a segment manifest. Raises ValueError listing
    every problem so the agent can fix the brief in one round trip."""
    errs = []
    mode = brief.get("mode", "script")
    if mode not in MODES:
        errs.append(f"mode must be one of {MODES}")
    direction = brief.get("direction") or {}
    given = brief.get("segments") or []
    target_total = brief.get("target_duration_ms")
    if target_total is not None and (not isinstance(target_total, (int, float))
                                     or target_total <= 0):
        errs.append("target_duration_ms must be a positive number")
    segs: list[dict] = []
    if mode == "script":
        if not (script_text or "").strip():
            errs.append("script_text required for script mode")
        for i, passage in enumerate(split_passages(script_text or "")):
            segs.append({"id": f"p{i + 1:02d}", "script": passage,
                         "target_start_ms": None, "target_end_ms": None,
                         "timing": "soft", "direction": direction.get("style", ""),
                         "retakes_allowed": True})
    else:
        if not given:
            errs.append(f"{mode} mode needs segments[]")
        for i, g in enumerate(given):
            sid = g.get("id") or f"s{i + 1:02d}"
            if not (g.get("script") or "").strip():
                errs.append(f"segment {sid}: script required")
            timing = g.get("timing", "soft")
            if timing not in TIMINGS:
                errs.append(f"segment {sid}: timing must be soft|hard")
            seg = {"id": sid, "script": (g.get("script") or "").strip(),
                   "target_start_ms": g.get("target_start_ms"),
                   "target_end_ms": g.get("target_end_ms"),
                   "timing": timing,
                   "direction": g.get("direction", direction.get("style", "")),
                   "video_reference": g.get("video_reference"),
                   "retakes_allowed": bool(g.get("retakes_allowed", True))}
            if mode == "timed":
                a, b = seg["target_start_ms"], seg["target_end_ms"]
                if not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and 0 <= a < b):
                    errs.append(f"segment {sid}: timed mode needs 0 <= start < end in ms")
                est = estimate_ms(len(seg["script"].split()))
                if seg["timing"] == "hard" and est > (b - a) * 1.5:
                    errs.append(f"segment {sid}: ~{est}ms of speech cannot fit "
                                f"a {int(b - a)}ms hard window; shorten the script")
            segs.append(seg)
    if errs:
        raise ValueError("; ".join(errs))
    # pacing guidance for soft/script modes
    cursor = 0
    for s in segs:
        est = estimate_ms(len(s["script"].split()))
        if s["target_start_ms"] is None:
            s["target_start_ms"] = cursor
        if s["target_end_ms"] is None:
            s["target_end_ms"] = cursor + est
        cursor = s["target_end_ms"] + 400  # breathing room between passages
    manifest = {"mode": mode, "target_duration_ms": target_total,
                "direction": direction, "segments": segs,
                "manifest_sha256": sha256(str(segs))}
    return manifest
