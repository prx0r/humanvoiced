"""Demand templates: portfolio + onboarding shaped by validated demand agents seek."""
from __future__ import annotations

TEMPLATES = [
    {"id": "youtube-narration", "label": "YouTube narration",
     "brief": "8–15 min explainer/documentary read, conversational",
     "sample_kind": "natural", "agent_keywords": ["youtube", "narration", "documentary", "explainer"]},
    {"id": "horror-story", "label": "Horror / storytelling",
     "brief": "15–25 min atmospheric read, $1.50/min band",
     "sample_kind": "character", "agent_keywords": ["horror", "storytelling", "atmospheric"]},
    {"id": "history-doc", "label": "History documentary",
     "brief": "10–15 min calm measured read, recurring series",
     "sample_kind": "natural", "agent_keywords": ["history", "documentary", "calm"]},
    {"id": "dub-package", "label": "Native dub + script review",
     "brief": "Translated script approved + WAV + subtitles",
     "sample_kind": "native", "agent_keywords": ["dubbing", "translation", "localisation"]},
    {"id": "character", "label": "Character voice",
     "brief": "Original character with side excerpt",
     "sample_kind": "character", "agent_keywords": ["character", "acting", "roles"]},
    {"id": "podcast-ad", "label": "Podcast / ad read",
     "brief": "30–60s commercial, separate usage terms",
     "sample_kind": "commercial", "agent_keywords": ["advertisement", "podcast", "commercial"]},
]


def onboarding_tasks() -> list[dict]:
    """Template onboarding checklist: record base sample, then demand-led extras."""
    return [{"id": "base-sample", "title": "Record your 30-second natural sample"},
            {"id": "profile", "title": "Review and publish your AI profile"},
            {"id": "prefs", "title": "Choose work you accept + max length"},
            *[{"id": f"extra-{t['id']}", "title": f"Optional: record a {t['label'].lower()} sample (agents search this)"}
              for t in TEMPLATES[1:4]]]


def match_templates(agent_keywords: list[str]) -> list[dict]:
    scored = []
    for t in TEMPLATES:
        hits = sum(1 for k in agent_keywords if k.lower() in " ".join(t["agent_keywords"] + [t["label"]]).lower())
        if hits:
            scored.append((hits, t))
    return [t for _, t in sorted(scored, reverse=True)]
