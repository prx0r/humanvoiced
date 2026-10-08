"""NoSlop script preflight: writing feedback before paid recording.

Uses NoSlop's pattern detector (cliches, repetition, flat prose) in-process
when available, or a NOSLOP_URL HTTP endpoint. Suggest-only by design: the
agent may revise BEFORE the narrator records; the script is never rewritten
here, funding is never blocked, and no AI-vs-human verdict is consulted --
short scripts make classifiers unreliable and the patterns (not the score)
are the useful signal.
"""
from __future__ import annotations

import json
import os
import urllib.request


class NoslopUnavailable(RuntimeError):
    pass


def _local_detect(text: str) -> dict | None:
    try:
        import sys as _s
        if "/root/noslop" not in _s.path:
            _s.path.insert(0, "/root/noslop")
        from miner.src.detector import detect as _d
        r = _d(text)
        return {"patterns_found": dict(r.patterns_found),
                "details": [{"tag": d["tag"], "text": d["text"][:200],
                             "line": d["line"]} for d in r.details[:30]],
                "pattern_count": r.pattern_count,
                "pattern_rate": r.pattern_rate,
                "engine": "noslop-local"}
    except Exception:
        return None


def _remote_detect(text: str) -> dict | None:
    url = os.environ.get("NOSLOP_URL", "")
    if not url:
        return None
    try:
        req = urllib.request.Request(url.rstrip("/") + "/v1/detect",
                                     data=json.dumps({"text": text}).encode(),
                                     method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read() or b"{}")
        if r.status == 402:
            return None  # paid gate; not our path
        pats = d.get("patterns_found") or d.get("patterns") or {}
        det = d.get("details") or d.get("findings") or []
        return {"patterns_found": pats, "details": det[:30],
                "pattern_count": d.get("pattern_count", len(det)),
                "pattern_rate": d.get("pattern_rate", 0),
                "engine": "noslop-remote"}
    except Exception:
        return None


def preflight(script: str) -> dict:
    """Advisory writing findings. Raises NoslopUnavailable when no engine."""
    if not (script or "").strip():
        raise NoslopUnavailable("empty script")
    out = _local_detect(script) or _remote_detect(script)
    if not out:
        raise NoslopUnavailable("no noslop engine (local import + NOSLOP_URL both failed)")
    out["mode"] = "suggest_only"
    out["note"] = ("patterns are suggestions for the agent's pre-recording "
                   "revision; never a funding gate, never a rewrite")
    return out
