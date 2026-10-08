"""Voice references: freeze the exact sample booked, compare delivery to it.

Booking locks (sample_id, version, sha256). Delivery is compared against
THAT reference — never a generic demo, never a vibe score. Findings are
per-dimension and advisory except script/technical facts.
"""
from __future__ import annotations

from hv.util import utcnow


def lock_reference(sample_id: str, version: int, sha256: str, style: str) -> dict:
    return {"sample_id": sample_id, "version": version, "sha256": sha256,
            "style": style, "locked_at": utcnow()}


def compare_report(reference: dict, delivery: dict) -> dict:
    """delivery: {script_coverage, tech_pass, consistency, style_note}.
    Returns per-dimension findings; only script/tech facts can fail a job."""
    con = delivery.get("consistency", "advisory")
    findings = {
        "script": "pass" if delivery.get("script_coverage", 0) >= 0.99 else "correct",
        "technical": "pass" if delivery.get("tech_pass") else "correct",
        "consistency": "pass" if con in ("match", "likely_match") else "advisory",
        "style": "advisory",
    }
    needs_human = findings["script"] == "correct" and delivery.get("ambiguous", False)
    rec = "approve" if all(v in ("pass", "advisory") for v in findings.values()) else "correct"
    return {"reference": reference["sample_id"], "findings": findings,
            "recommendation": "human_review" if needs_human else rec,
            "note": "consistency/style are advisory; only script/technical facts fail"}
