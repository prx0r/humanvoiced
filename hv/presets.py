"""Channel sound presets: a creator's reusable production character.

A preset fixes loudness target, denoise strength, leveling, compression,
de-essing and EQ character so episode 14 sounds like episode 1 across
different narrators. The agent picks one ID; everything else is
implementation. Presets never touch words or vocal identity, never add
reverb by default, and always record model/software versions so a tool
update cannot silently change a channel's sound.
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
    "eq": ("flat", "warm", "bright", "presence"),
}

ENGINE_VERSION = "hv-studio-0.2"


def _p(**kw) -> dict:
    base = {"target_lufs": REFERENCE_LUFS, "denoise_db": 8.0,
            "compression": "gentle", "eq": "flat", "deess": True,
            "ride": True, "outputs": ["wav", "mp3"],
            "engine": ENGINE_VERSION}
    base.update(kw)
    return base


BUILTINS = {
    # P0 creator-facing four.
    "natural-clean": _p(target_lufs=-19.0, denoise_db=8.0,
                        compression="gentle", eq="flat"),
    "broadcast-presence": _p(target_lufs=-16.0, denoise_db=10.0,
                             compression="medium", eq="presence"),
    "intimate-story": _p(target_lufs=-19.0, denoise_db=6.0,
                         compression="gentle", eq="warm", deess=False),
    "match-my-channel": _p(target_lufs=-19.0, denoise_db=8.0,
                           compression="gentle", eq="flat",
                           reference_id=None),
    # First-generation names, kept as aliases.
    "calm-documentary": _p(target_lufs=-19.0, denoise_db=8.0,
                           compression="gentle", eq="warm"),
    "conversational-podcast": _p(target_lufs=-19.0, denoise_db=12.0,
                                 compression="medium", eq="flat"),
    "dramatic-storytelling": _p(target_lufs=-18.0, denoise_db=6.0,
                                compression="gentle", eq="warm"),
    "shortform-social": _p(target_lufs=-16.0, denoise_db=12.0,
                           compression="firm", eq="bright"),
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
        errs.append("eq must be flat/warm/bright/presence")
    for flag in ("deess", "ride"):
        if not isinstance(spec.get(flag, True), bool):
            errs.append(f"{flag} must be true/false")
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
            "deess": bool(spec.get("deess", True)),
            "ride": bool(spec.get("ride", True)),
            "reference_id": spec.get("reference_id"),
            "outputs": list(spec.get("outputs", ["wav", "mp3"])),
            "engine": ENGINE_VERSION}
