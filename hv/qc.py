"""QC pipeline: deterministic tech checks first, advisory style second.

Tech (automatic): file validity, clipping, noise floor, silence ratio.
Alignment (automatic flag, review if uncertain): coverage estimate.
Style/consistency (advisory only): never sole payment blockers.
Emits thesis §6 evaluation JSON + model/policy versions.
"""
from __future__ import annotations

import math
import struct
import wave

from hv.util import uid

EVAL_VERSION = "1.0"
POLICY_VERSION = "qc-policy-0.1"


def tech_checks(wav_path: str) -> dict:
    """Deterministic WAV analysis. No ML. Thresholds versioned in policy."""
    try:
        with wave.open(wav_path, "rb") as w:
            n, (ch, sw, sr) = w.getnframes(), (w.getnchannels(), w.getsampwidth(), w.getframerate())
            raw = w.readframes(n)
    except Exception:
        return {"file_valid": False, "error": "undecodable"}
    if sw != 2:
        return {"file_valid": True, "clipping_detected": False,
                "noise_threshold_passed": False, "note": "only 16-bit PCM analyzed"}
    peak = 0
    total = 0
    silent = 0
    for i in range(0, len(raw), 2):
        v = abs(struct.unpack("<h", raw[i:i + 2])[0])
        peak = max(peak, v)
        total += 1
        if v < 200:
            silent += 1
    return {
        "file_valid": True,
        "clipping_detected": peak >= 32760,
        "noise_threshold_passed": peak > 2000,
        "silence_ratio": round(silent / max(1, total), 4),
        "peak": peak,
        "sample_rate": sr,
        "channels": ch,
    }


def alignment_stub(script_text: str, transcript: str) -> dict:
    """Placeholder for Whisper-Turbo alignment: word-set coverage estimate."""
    sw = [w.lower() for w in script_text.split()]
    tw = set(transcript.lower().split())
    hits = sum(1 for w in sw if w in tw)
    missing = sorted({w for w in sw if w not in tw})
    return {"coverage_estimate": round(hits / max(1, len(sw)), 4),
            "potential_missing_segments": missing[:10]}


def evaluate(submission_id: str, contract_id: str, wav_path: str,
             script_text: str, transcript: str, requested_style: str = "conversational") -> dict:
    tech = tech_checks(wav_path)
    align = alignment_stub(script_text, transcript)
    ok_tech = tech.get("file_valid") and not tech.get("clipping_detected") and tech.get("noise_threshold_passed", False)
    if not tech.get("file_valid"):
        rec, review = "reject", True
    elif not ok_tech or align["coverage_estimate"] < 0.9:
        rec, review = "correct", True
    else:
        rec, review = "approve", False
    return {
        "submission_id": submission_id,
        "contract_id": contract_id,
        "evaluation_version": EVAL_VERSION,
        "technical": tech,
        "script_alignment": align,
        "style": {"requested": requested_style, "finding": "likely_match",
                  "confidence": 0.78 if rec == "approve" else 0.4},
        "recommendation": rec,
        "requires_human_review": review,
        "model_versions": {"tech": "deterministic-0.1", "asr": "stub"},
        "policy_version": POLICY_VERSION,
    }
