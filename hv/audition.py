"""Auditions: agent posts a ~10-second side, narrators submit reads,
agent/creator compares and decides. Future-weighted: structure now, volume later.

Flow: casting_call (side script + role + deadline) → submissions (one per
narrator, WAV bytes, server-hashed) → comparison view (same side, N reads)
→ decision (winner → contract offer). Unchosen reads stay private.
"""
from __future__ import annotations

from hv.util import sha256, utcnow


def casting_call(project: str, role: str, side_text: str, deadline_at: str,
                 max_words: int = 30) -> dict:
    words = side_text.split()
    if len(words) > max_words:
        raise ValueError(f"audition side too long ({len(words)} > {max_words} words)")
    return {"casting_id": "aud_" + sha256(project + role + side_text)[:8],
            "project": project, "role": role, "side_text": side_text,
            "side_sha256": sha256(side_text), "deadline_at": deadline_at,
            "submissions": {}, "decision": None, "created_at": utcnow()}


def submit_read(casting: dict, narrator_id: str, wav_sha256: str) -> dict:
    if casting.get("decision"):
        raise ValueError("casting already decided")
    casting["submissions"][narrator_id] = {"sha256": wav_sha256, "at": utcnow()}
    return {"narrator_id": narrator_id, "sha256": wav_sha256}


def compare(casting: dict) -> list[dict]:
    """Same side, N reads: the comparison view agents decide from."""
    return [{"narrator_id": n, "sha256": s["sha256"], "at": s["at"],
             "side_sha256": casting["side_sha256"]}
            for n, s in casting["submissions"].items()]


def decide(casting: dict, winner_id: str, notes: str = "") -> dict:
    if winner_id not in casting["submissions"]:
        raise ValueError("winner did not submit")
    casting["decision"] = {"winner": winner_id, "notes": notes, "at": utcnow()}
    return casting["decision"]
