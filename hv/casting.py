"""Casting layer: roles with sides, stage direction, multi-role cast lists.

A role = character brief + audition side (excerpt) + voice requirements.
Stage direction rides on the contract (scene instructions), versioned with
the script — never verbal-only. Cast lists fill N roles in one agent call.
Pick-up lines reuse the corrections flow (small, fast, priced per line).
"""
from __future__ import annotations

from hv.util import sha256, utcnow


def role(project: str, character: str, side_text: str, voice_reqs: dict,
         lines_count: int | None = None) -> dict:
    return {"role_id": f"role_{sha256(character + side_text)[:8]}",
            "project": project, "character": character,
            "side_text": side_text, "side_sha256": sha256(side_text),
            "voice_reqs": voice_reqs,
            "lines_count": lines_count or len(side_text.split())}


def stage_direction(contract_id: str, notes: str, scenes: list[dict] | None = None) -> dict:
    """Director notes attached to a contract, versioned with the script."""
    return {"contract_id": contract_id, "notes": notes,
            "scenes": scenes or [], "sha256": sha256(notes),
            "attached_at": utcnow()}


def cast_list(project: str, roles: list[dict], catalog: list[dict]) -> list[dict]:
    """Match each role against narrator character profiles. One call, N roles."""
    from hv import catalog as _cat
    out = []
    for r in roles:
        req = dict(r.get("voice_reqs", {}))
        q = {"job": {"language": req.get("language", "en"),
                     "category": "character",
                     "duration_minutes": req.get("minutes", 5)},
             "preferences": {"prosody": [req.get("prosody", "expressive")]},
             "limit": 3}
        cands = []
        for n in catalog:
            chars = (n.get("characters") or [])
            hit = [c for c in chars if req.get("trait", "") in str(c)]
            if hit or not req.get("trait"):
                cands.append({"voice_id": n["voice_id"], "handle": n.get("handle", ""),
                              "matched_character": (hit + ["natural"])[0]})
        out.append({"role_id": r["role_id"], "character": r["character"],
                    "candidates": cands[:3]})
    return out


def pickup_price(lines: int, per_line_usd: float = 1.0) -> dict:
    return {"lines": lines, "price_usd": round(max(2.0, lines * per_line_usd), 2),
            "flow": "corrections"}
