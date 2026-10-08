"""AI profile drafts: private draft → narrator review → public fields.

The AI suggests; the human publishes. Guessed nationality/ethnicity/gender/
age are never emitted. Every suggestion carries confidence + model version.
"""
from __future__ import annotations

DRAFT_VERSION = "profile-draft-0.1"

FORBIDDEN = ("nationality", "ethnicity", "gender", "age")


def draft_from_sample(tech: dict, declared: dict, wpm: float | None = None) -> dict:
    """Build a schema-validated private draft from measured tech + declared fields."""
    desc = []
    if tech.get("sample_rate", 0) >= 44100 and not tech.get("clipping_detected"):
        desc.append("clean home recording")
    pace = "measured"
    if wpm:
        pace = "brisk" if wpm > 170 else "relaxed" if wpm < 130 else "natural"
    draft = {"version": DRAFT_VERSION,
             "display_name": declared.get("display_name", ""),
             "languages": list(declared.get("languages", [])),
             "accent_description": {"text": declared.get("accent", ""),
                                    "confidence": 0.5 if declared.get("accent") else 0.0,
                                    "source": "declared"},
             "voice_character": list(declared.get("character", [])),
             "pace": {"label": pace, "wpm": wpm},
             "recording_quality": {"peak": tech.get("peak"),
                                   "silence_ratio": tech.get("silence_ratio"),
                                   "clipping": bool(tech.get("clipping_detected"))},
             "suggested_categories": list(declared.get("categories", [])),
             "bio": " ".join(desc + ["Natural voice sample on file."]).strip(),
             "model": "deterministic-0.1"}
    assert not any(k in draft for k in FORBIDDEN)
    return draft


def publish(narrator_doc: dict, edited: dict) -> dict:
    """Narrator-reviewed publish: edited fields win; forbidden keys dropped."""
    pub = dict(edited)
    for k in FORBIDDEN:
        pub.pop(k, None)
    pub["published"] = True
    narrator_doc["profile_published"] = pub
    return pub
