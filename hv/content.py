"""Content triage: platform policy gate before dispatch, talent prefs after.

Tiers (heuristic keyword triage, not a legal determination):
- general: ordinary narration, always dispatchable.
- mature: strong language, horror, crime, romance, politics, endorsements.
  Dispatched only to narrators whose content prefs allow each flag.
- restricted: erotic-for-gratification signals, graphic sexual/violent
  detail. Held for human review, never auto-dispatched.
- prohibited: sexual content involving minors, credible threats of violence,
  doxxing/harassment instructions, deceptive real-person endorsement.
  Refused at creation, never stored for dispatch.

Purpose matters: documentary/educational framing words soften sexual/violent
flags from restricted to mature (a documentary discussing assault is not an
erotic performance). This is triage with documented limits, not a court.
Talent prefs can only narrow platform policy, never widen it.
"""
from __future__ import annotations

import re

CATEGORIES = ("strong_language", "horror", "true_crime", "romance",
              "politics", "endorsements")

_PATTERNS = {
    "strong_language": [r"\bfuck\w*", r"\bshit\w*", r"\bcunt\w*", r"\bnigg[ae]r",
                        r"\bmotherfuck", r"\bcock\w*", r"\bpuss\w*"],
    "horror": [r"\bgore\b", r"\bdismember", r"\bhaunt\w*", r"\bdemon\w*",
               r"\bbloodbath", r"\bslasher", r"\bparanormal"],
    "true_crime": [r"\bmurder\w*", r"\bserial killer", r"\bhomicide",
                   r"\btrue crime", r"\bassault\b.{0,20}\b(case|trial|victim)"],
    "romance": [r"\bintima\w*", r"\berotic\w*", r"\bsensual\w*", r"\bbedroom\b",
                r"\bkiss\w+.{0,20}\b(neck|thigh|breast)"],
    "politics": [r"\bvote (for|against)\b", r"\belection\b.{0,20}\b(fraud|steal)",
                 r"\bcall your (senator|mp)\b", r"\bprotest\b.{0,20}\b(march|rally)"],
    "endorsements": [r"\bi (endorse|recommend) this product\b", r"\bbest .{0,20} on the market\b",
                     r"\buse my code\b"],
}

_PROHIBITED = [
    (r"\b(child|minor|kid|teen|underage|under.?age|little (boy|girl))\b.{0,60}\b(sex|sexual|nude|naked|erotic|porn|explicit|intimate|touch|kiss|bed|orgasm|climax|moan)",
     "sexual content involving a minor"),
    (r"\b(sex|sexual|erotic|porn|orgasm|climax|moan|masturbat)\w*.{0,60}\b(child|minor|kid|teen|underage|under.?age|little (boy|girl))",
     "sexual content involving a minor"),
    (r"\bi will (kill|murder|hurt|stab|shoot) you\b", "credible threat of violence"),
    (r"\b(home address|doxx|dox) (is|him|her|them)\b", "doxxing/harassment"),
    (r"\bas (donald trump|joe biden|elon musk|taylor swift|mrbeast)\b.{0,40}\bi (endorse|love|use)",
     "deceptive real-person endorsement"),
]

_RESTRICTED = [
    r"\bfor (your|my|our) (sexual )?(pleasure|gratification|arousal)\b",
    r"\berotic (audio|narration|story|roleplay)\b",
    r"\bgraphic.{0,20}\b(sex|sexual|rape|torture)\b.{0,40}\bin detail\b",
]

_CONTEXT_SOFTENERS = [r"\bdocumentary\b", r"\beducat\w+", r"\bhistor\w+",
                      r"\bnews report\b", r"\btrue crime\b", r"\bawareness\b"]


def _hits(text: str, patterns: list[str]) -> list[str]:
    return [p for p in patterns if re.search(p, text, re.IGNORECASE)]


def classify(script_text: str) -> dict:
    """Returns {tier, flags, prohibited_reason, note}."""
    text = script_text or ""
    for pat, reason in _PROHIBITED:
        if re.search(pat, text, re.IGNORECASE):
            return {"tier": "prohibited", "flags": [], "prohibited_reason": reason,
                    "note": "refused at creation; never dispatched"}
    restricted = _hits(text, _RESTRICTED)
    flags = [c for c in CATEGORIES
             if _hits(text, _PATTERNS[c])]
    if restricted and not any(re.search(s, text, re.IGNORECASE)
                              for s in _CONTEXT_SOFTENERS):
        return {"tier": "restricted", "flags": flags or ["explicit_detail"],
                "prohibited_reason": "",
                "note": "held for human review before any dispatch"}
    if restricted:
        flags = sorted(set(flags) | {"explicit_detail"})
        return {"tier": "mature", "flags": flags, "prohibited_reason": "",
                "note": "documentary/educational framing; talent prefs apply"}
    if flags:
        return {"tier": "mature", "flags": flags, "prohibited_reason": "",
                "note": "talent prefs apply"}
    return {"tier": "general", "flags": [], "prohibited_reason": "",
            "note": "ordinary narration"}


def allowed_for_prefs(flags: list[str], prefs: dict) -> tuple[bool, list[str]]:
    """Talent prefs narrow policy. Missing prefs content block = all allowed
    (opt-out model); an explicit False blocks that flag."""
    content = (prefs or {}).get("content") or {}
    blocked = [f for f in flags if content.get(f) is False]
    return (not blocked, blocked)


DEFAULT_PREFS = {c: True for c in CATEGORIES}
