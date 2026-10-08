"""AB harness: compare samples, languages, providers, descriptor sets.

Every variant runs the same audio pipeline shape; results carry provider +
model versions so wins are attributable. Agreement scoring: how often two
variants produce the same transcript words / descriptors.
"""
from __future__ import annotations


def run_variant(frames: list[float], sample_rate: int, transcript_fn, label: str) -> dict:
    from hv import audio as _a
    segs = _a.vad_segments(frames, sample_rate)
    ac = _a.acoustic(frames, sample_rate, segs)
    tx = transcript_fn()
    return {"variant": label, "segments": len(segs), "acoustic": ac,
            "transcript": tx}


def agreement(a: dict, b: dict) -> dict:
    wa, wb = set(a.get("transcript", "").lower().split()), set(b.get("transcript", "").lower().split())
    inter = len(wa & wb)
    union = len(wa | wb) or 1
    sa = a.get("acoustic", {})
    sb = b.get("acoustic", {})
    return {"word_jaccard": round(inter / union, 3),
            "speech_fraction_delta": round(abs(sa.get("speech_fraction", 0) - sb.get("speech_fraction", 0)), 3),
            "same_clipping_call": sa.get("clipping_detected") == sb.get("clipping_detected")}


def multilingual_matrix(samples: list[dict], transcribe_fn) -> list[dict]:
    """samples: [{language, frames, sample_rate}]. Returns per-language results."""
    out = []
    for s in samples:
        tx = transcribe_fn(s["frames"], s["sample_rate"], s["language"])
        out.append({"language": s["language"], "words": len(tx.split()),
                    "empty": not tx.strip()})
    return out
