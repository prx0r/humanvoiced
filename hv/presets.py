"""Channel sound presets: a creator's reusable production character.

A preset fixes loudness target, denoise strength, compression and EQ
character so episode 14 sounds like episode 1 across different narrators.
Presets never touch words or vocal identity — levels and tone only.
Values are starting points, not official platform loudness requirements.
"""
from __future__ import annotations

import re

# Illustrative reference loudness for narration. Not a YouTube/podcast
# requirement; agreed with the creator per channel.
REFERENCE_LUFS = -19.0

RANGES = {
    "target_lufs": (-30.0, -14.0),
    "denoise_db": (0.0, 24.0),
    "compression": ("gentle", "medium", "firm"),
    "eq": ("flat", "warm", "bright"),
}

BUILTINS = {
    "calm-documentary": {"target_lufs": -19.0, "denoise_db": 8.0,
                         "compression": "gentle", "eq": "warm",
                         "outputs": ["wav", "mp3"]},
    "conversational-podcast": {"target_lufs": -19.0, "denoise_db": 12.0,
                               "compression": "medium", "eq": "flat",
                               "outputs": ["wav", "mp3"]},
    "dramatic-storytelling": {"target_lufs": -18.0, "denoise_db": 6.0,
                              "compression": "gentle", "eq": "warm",
                              "outputs": ["wav", "mp3"]},
    "shortform-social": {"target_lufs": -16.0, "denoise_db": 12.0,
                         "compression": "firm", "eq": "bright",
                         "outputs": ["wav", "mp3"]},
}


def validate(spec: dict) -> list[str]:
    errs = []
    name = spec.get("name", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{2,40}", name or ""):
        errs.append("name must be 2-40 chars: letters, numbers, _.-")
    try:
        t = float(spec.get("target_lufs", REFERENCE_LUFS))
        if not RANGES["target_lufs"][0] <= t <= RANGES["target_lufs"][1]:
            errs.append("target_lufs out of range -30..-14")
    except (TypeError, ValueError):
        errs.append("target_lufs must be numeric")
    try:
        d = float(spec.get("denoise_db", 0))
        if not RANGES["denoise_db"][0] <= d <= RANGES["denoise_db"][1]:
            errs.append("denoise_db out of range 0..24")
    except (TypeError, ValueError):
        errs.append("denoise_db must be numeric")
    if spec.get("compression", "gentle") not in RANGES["compression"]:
        errs.append("compression must be gentle/medium/firm")
    if spec.get("eq", "flat") not in RANGES["eq"]:
        errs.append("eq must be flat/warm/bright")
    outs = spec.get("outputs", ["wav", "mp3"])
    if not outs or any(o not in ("wav", "mp3") for o in outs):
        errs.append("outputs must be a subset of [wav, mp3]")
    return errs


def normalize(spec: dict) -> dict:
    """Fill defaults; caller must validate() first."""
    return {"name": spec["name"],
            "target_lufs": float(spec.get("target_lufs", REFERENCE_LUFS)),
            "denoise_db": float(spec.get("denoise_db", 0)),
            "compression": spec.get("compression", "gentle"),
            "eq": spec.get("eq", "flat"),
            "outputs": list(spec.get("outputs", ["wav", "mp3"]))}
