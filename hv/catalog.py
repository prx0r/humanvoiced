"""Voice catalog + 3-stage matching with explanations.

Stage 1 eligibility (hard gates) → stage 2 soft suitability (35/25/15/15/10,
neutral for missing history) → stage 3 explained response. Match events
recorded for the learning loop (shown/played/booked/approved/returned).
"""
from __future__ import annotations

WEIGHTS = {"perceptual": 0.35, "delivery": 0.25, "pace": 0.15,
           "category": 0.15, "reliability": 0.10}


def eligible(profile: dict, job: dict) -> tuple[bool, list[str]]:
    reasons = []
    if job.get("language") and job["language"] not in profile.get("languages", []):
        return False, ["language_mismatch"]
    if job.get("category") and job["category"] not in profile.get("capabilities", {}).get("declared", []) + profile.get("capabilities", {}).get("demonstrated", []):
        reasons.append("category_undeclared")
    if job.get("minutes", 0) > profile.get("availability", {}).get("max_minutes_per_job", 10**9):
        return False, ["too_long"]
    if not profile.get("availability", {}).get("accepting_offers", True):
        return False, ["not_accepting"]
    return True, reasons


def suitability(profile: dict, prefs: dict, reliability: float | None) -> tuple[float, list[str], list[str]]:
    feats = profile.get("match_features", {})
    score = (WEIGHTS["perceptual"] * feats.get("perceptual", 0.5)
             + WEIGHTS["delivery"] * feats.get("delivery", 0.5)
             + WEIGHTS["pace"] * feats.get("pace", 0.5)
             + WEIGHTS["category"] * feats.get("category", 0.5)
             + WEIGHTS["reliability"] * (reliability if reliability is not None else 0.5))
    reasons, uncer = [], []
    if feats.get("perceptual", 0) >= 0.7:
        reasons.append("perceived_delivery_match")
    if reliability is None:
        uncer.append("no_prior_contracts")
    if not feats.get("category"):
        uncer.append("no_prior_category_contracts")
    return round(score, 3), reasons, uncer


def search(catalog: list[dict], query: dict, limit: int = 5) -> list[dict]:
    job = query.get("job", {})
    prefs = query.get("preferences", {})
    out = []
    for p in catalog:
        ok, why = eligible(p, job)
        if not ok:
            continue
        rel = p.get("reliability")
        score, reasons, uncer = suitability(p, prefs, rel)
        if job.get("language"):
            reasons = ["confirmed_language_match"] + reasons
        out.append({"voice_id": p["voice_id"], "match_score": score,
                    "match_model": "hv-match-v1", "reasons": reasons,
                    "uncertainties": uncer,
                    "sample_url": f"/v1/voices/{p['voice_id']}/sample",
                    "profile_url": f"/@{p.get('handle', p['voice_id'])}",
                    "can_book": p.get("availability", {}).get("accepting_offers", True)})
    out.sort(key=lambda r: -r["match_score"])
    return out[:limit]


def match_event(voice_id: str, query_ref: str, stage: str) -> dict:
    assert stage in ("shown", "played", "booked", "approved", "returned", "rebooked")
    return {"voice_id": voice_id, "query_ref": query_ref, "stage": stage}
