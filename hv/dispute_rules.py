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

# Published rule IDs (LIBRARY.md §7). Agents may cite, never invent.
RULES = {
    "PAY-001": "funds not secured → no actionable contract",
    "SLA-001": "offer expires unaccepted → close, no penalty",
    "SLA-002": "deadline missed → notify, preserve logs, recovery",
    "SLA-003": "platform outage → suspend deadline penalty",
    "QC-001": "undecodable upload → ask replacement",
    "QC-002": "alignment gaps → flag exact passages",
    "REV-001": "locked script changed → require amendment",
    "PAY-002": "valid delivery accepted → authorise release",
    "PAY-003": "review window expires silent → authorise if policy permits",
    "DIS-001": "substantive dispute → freeze settlement, escalate",
    "REP-001": "confirmed worker fault → update reliability after review rights",
}


def evaluate(report: dict, timeline: dict) -> list[dict]:
    """Deterministic flags from the QC report + server timeline. No LLM.
    Missing evidence is UNKNOWN (→ human), never satisfactory."""
    flags = []
    tech = report.get("technical", {})
    align = report.get("script_alignment", {})
    if "file_valid" not in tech:
        flags.append({"code": "F_UNKNOWN_TECH", "rule": "QC-001", "tier": TIER_HUMAN,
                      "clause": "evidence.completeness", "fix": "run QC before judging"})
    elif not tech.get("file_valid"):
        flags.append({"code": "F_INVALID_FILE", "rule": "QC-001", "tier": TIER_ASSISTED,
                      "clause": "deliverable.format", "fix": "re-upload valid WAV"})
    if tech.get("clipping_detected"):
        flags.append({"code": "F_CLIPPING", "rule": "QC-001", "tier": TIER_ASSISTED,
                      "clause": "acceptance.no_clipping", "fix": "correction round"})
    if "noise_threshold_passed" not in tech and "file_valid" in tech:
        flags.append({"code": "F_UNKNOWN_NOISE", "rule": "QC-001", "tier": TIER_HUMAN,
                      "clause": "evidence.completeness", "fix": "run QC before judging"})
    elif not tech.get("noise_threshold_passed", True):
        flags.append({"code": "F_NOISE", "rule": "QC-001", "tier": TIER_ASSISTED,
                      "clause": "acceptance.no_excessive_noise", "fix": "correction round"})
    if "coverage_estimate" not in align:
        flags.append({"code": "F_UNKNOWN_ALIGN", "rule": "QC-002", "tier": TIER_HUMAN,
                      "clause": "evidence.completeness", "fix": "run alignment before judging"})
        cov = 1.0
    else:
        cov = align.get("coverage_estimate", 1.0)
    if cov < 0.9:
        flags.append({"code": "F_INCOMPLETE", "rule": "QC-002", "tier": TIER_ASSISTED,
                      "clause": "acceptance.all_passages", "fix": "correction round",
                      "missing": align.get("potential_missing_segments", [])})
    if timeline.get("late"):
        flags.append({"code": "F_LATE", "rule": "SLA-002", "tier": TIER_HUMAN,
                      "clause": "sla.deadline", "fix": "grace/recovery review"})
    if timeline.get("no_submission_after_grace"):
        flags.append({"code": "F_NON_DELIVERY", "rule": "SLA-002", "tier": TIER_HUMAN,
                      "clause": "sla.delivery", "fix": "reassign + reliability review"})
    if timeline.get("platform_outage"):
        flags.append({"code": "F_PLATFORM", "rule": "SLA-003", "tier": TIER_ASSISTED,
                      "clause": "sla.platform_failure", "fix": "extend deadline, no penalty"})
    style = report.get("style", {})
    if style.get("finding") == "likely_mismatch" and style.get("confidence", 0) > 0.85:
        flags.append({"code": "F_STYLE", "rule": "DIS-001", "tier": TIER_HUMAN,
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
