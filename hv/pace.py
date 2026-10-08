"""Pace: the narrator's own comfortable speed, learned from practice.

Fixed 150 WPM estimates become a feasibility engine: required pace per
passage (words over available speech seconds, minus pause budget) is
compared against the narrator's measured range, not a universal number.
Labels are comfortable / tight / impractical. Impractical hard windows
reject at brief/assembly time; everything else only advises.
"""
from __future__ import annotations

DEFAULT_WPM = 150.0
PAUSE_BUDGET_MS = 800


def record_sample(doc: dict, words: int, seconds: float) -> dict:
    """Fold one measured sample (practice or uploaded) into the narrator's
    pace EMA. Junk samples (too short/few words) are ignored."""
    if words < 6 or seconds < 2.0:
        return doc.get("pace", {})
    wpm = words / (seconds / 60.0)
    if not 40.0 <= wpm <= 400.0:
        return doc.get("pace", {})
    pace = doc.get("pace") or {}
    prev, n = pace.get("wpm", DEFAULT_WPM), int(pace.get("samples", 0))
    ema = prev + 0.3 * (wpm - prev) if n else wpm
    doc["pace"] = {"wpm": round(ema, 1), "samples": n + 1}
    return doc["pace"]


def narrator_wpm(doc: dict) -> float:
    try:
        return float((doc.get("pace") or {}).get("wpm", DEFAULT_WPM))
    except (TypeError, ValueError):
        return DEFAULT_WPM


def feasibility(seg: dict, wpm: float = DEFAULT_WPM) -> dict:
    """Comfortable / tight / impractical for one passage at this pace."""
    words = len((seg.get("script") or "").split())
    a, b = seg.get("target_start_ms"), seg.get("target_end_ms")
    est_s = round(words / max(1.0, wpm) * 60.0, 1)
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or b <= a:
        return {"words": words, "est_seconds": est_s, "required_wpm": round(wpm, 1),
                "status": "comfortable",
                "reason": "open timing — editor fits the cut around speech"}
    speech_s = max(0.5, (b - a) / 1000.0 - PAUSE_BUDGET_MS / 1000.0)
    required = round(60.0 * words / speech_s, 1)
    if required <= wpm * 1.15:
        status, reason = "comfortable", "fits at natural delivery"
    elif required <= wpm * 1.4:
        status, reason = "tight", "faster than usual — offer a practice take"
    else:
        status, reason = ("impractical",
                          "cannot fit naturally — shorten script or widen window")
    return {"words": words, "est_seconds": est_s, "required_wpm": required,
            "status": status, "reason": reason,
            "timing": seg.get("timing", "soft")}
