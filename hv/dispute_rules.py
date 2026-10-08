"""Deterministic dispute triage: rules first, agents second, humans last.

Pipeline: evaluate() → flags[] → route() → tier.
- Tier 1 (automated): undisputed + objectively valid → settle immediately.
- Tier 2 (assisted): correctable defect → AI-guided remediation (correction round).
- Tier 3 (human): contested payment, subjective breach, fraud, sanctions.

Agents may gather evidence, cite clauses, recommend. They can never move
money, sanction, or suspend. Every flag cites the contract clause + evidence.
"""
from __future__ import annotations

TIER_AUTO = "tier1_automated"
TIER_ASSISTED = "tier2_assisted"
TIER_HUMAN = "tier3_human"


def evaluate(report: dict, timeline: dict) -> list[dict]:
    """Deterministic flags from the QC report + server timeline. No LLM."""
    flags = []
    tech = report.get("technical", {})
    align = report.get("script_alignment", {})
    if not tech.get("file_valid"):
        flags.append({"code": "F_INVALID_FILE", "tier": TIER_ASSISTED,
                      "clause": "deliverable.format", "fix": "re-upload valid WAV"})
    if tech.get("clipping_detected"):
        flags.append({"code": "F_CLIPPING", "tier": TIER_ASSISTED,
                      "clause": "acceptance.no_clipping", "fix": "correction round"})
    if not tech.get("noise_threshold_passed", True):
        flags.append({"code": "F_NOISE", "tier": TIER_ASSISTED,
                      "clause": "acceptance.no_excessive_noise", "fix": "correction round"})
    cov = align.get("coverage_estimate", 1.0)
    if cov < 0.9:
        flags.append({"code": "F_INCOMPLETE", "tier": TIER_ASSISTED,
                      "clause": "acceptance.all_passages", "fix": "correction round",
                      "missing": align.get("potential_missing_segments", [])})
    if timeline.get("late"):
        flags.append({"code": "F_LATE", "tier": TIER_HUMAN,
                      "clause": "sla.deadline", "fix": "grace/recovery review"})
    if timeline.get("no_submission_after_grace"):
        flags.append({"code": "F_NON_DELIVERY", "tier": TIER_HUMAN,
                      "clause": "sla.delivery", "fix": "reassign + reliability review"})
    if timeline.get("platform_outage"):
        flags.append({"code": "F_PLATFORM", "tier": TIER_ASSISTED,
                      "clause": "sla.platform_failure", "fix": "extend deadline, no penalty"})
    style = report.get("style", {})
    if style.get("finding") == "likely_mismatch" and style.get("confidence", 0) > 0.85:
        flags.append({"code": "F_STYLE", "tier": TIER_HUMAN,
                      "clause": "brief.delivery_style", "fix": "human assessment vs brief"})
    return flags


def route(flags: list[dict], dispute_open: bool, appeal_open: bool) -> dict:
    """Route to a tier. Money moves only on tier1-auto or human-signed tier3."""
    if dispute_open or appeal_open:
        return {"tier": TIER_HUMAN, "reason": "contested — human decides"}
    tiers = {f["tier"] for f in flags}
    if not flags:
        return {"tier": TIER_AUTO, "reason": "undisputed valid submission",
                "may_settle": True}
    if tiers == {TIER_ASSISTED}:
        return {"tier": TIER_ASSISTED, "reason": "correctable defect",
                "may_settle": False, "next": "correction round"}
    return {"tier": TIER_HUMAN, "reason": "non-correctable or mixed flags",
            "may_settle": False, "next": "human adjudication"}


def agent_recommendation(flags: list[dict], contract: dict) -> dict:
    """What the support/evaluator agent may output: findings + recommendation.
    Advisory only. Never a settlement instruction."""
    r = route(flags, dispute_open=False, appeal_open=False)
    return {"flags": [f["code"] for f in flags], "route": r["tier"],
            "cites": [{"code": f["code"], "clause": f["clause"]} for f in flags],
            "note": "advisory — settlement requires tier1-auto or human signature"}
