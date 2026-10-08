"""Audio pipeline: ingest → VAD → acoustic → transcribe → describe → merge.

Stages are independent and idempotent, keyed by sample_sha256 +
pipeline_version. Providers are interfaces; local deterministic fallbacks
run without keys or GPUs. Heavy models (Whisper/Qwen/Gemini) plug in
behind transcribe.py / describe.py without touching the schema.
"""
from __future__ import annotations

PIPELINE_VERSION = "2026-10-08.1"


def vad_segments(frames: list[float], sample_rate: int, thresh: float = 0.02) -> list[dict]:
    """Energy VAD over mono frames (stand-in for Silero; same output shape)."""
    win = max(1, sample_rate // 50)
    segs, start = [], None
    for i in range(0, len(frames), win):
        e = sum(abs(x) for x in frames[i:i + win]) / win
        t = i / sample_rate
        if e >= thresh and start is None:
            start = t
        elif e < thresh and start is not None:
            segs.append({"start": round(start, 2), "end": round(t, 2)})
            start = None
    if start is not None:
        segs.append({"start": round(start, 2), "end": round(len(frames) / sample_rate, 2)})
    return segs


def acoustic(frames: list[float], sample_rate: int, segments: list[dict]) -> dict:
    """Deterministic measurements with uncertainty. No LLM numbers, ever."""
    import math
    speech = sum(s["end"] - s["start"] for s in segments)
    total = len(frames) / sample_rate if frames else 0
    peak = max((abs(x) for x in frames), default=0.0)
    gaps = [b["start"] - a["end"] for a, b in zip(segments, segments[1:])]
    gaps.sort()
    def pct(q):
        return round(gaps[min(len(gaps) - 1, int(q * len(gaps)))] * 1000) if gaps else 0
    return {"speech_fraction": round(speech / total, 3) if total else 0.0,
            "peak": round(peak, 4),
            "clipping_detected": peak >= 0.999,
            "pause_mean_ms": round(sum(gaps) / len(gaps) * 1000) if gaps else 0,
            "pause_median_ms": pct(0.5), "pause_p90_ms": pct(0.9),
            "rms_dbfs": round(20 * math.log10(sum(x * x for x in frames) / len(frames)) , 2) if frames else -96.0,
            "uncertainty": "energy-vad fallback; replace with Silero + pitch tracker"}


VOCAB = {"texture": ["smooth", "breathy", "husky", "raspy", "grainy", "airy"],
         "resonance": ["full", "light", "rounded", "bright"],
         "energy": ["relaxed", "moderate", "animated"],
         "prosody": ["restrained", "conversational", "expressive", "dramatic"],
         "delivery": ["understated", "storytelling", "measured", "lively"]}


def describe_stub(transcript: str, acoustic_m: dict) -> dict:
    """Shape of the audio-LLM output (Gemini/Qwen3-Omni plug in here).
    Conservative: graded multi-labels with evidence placeholders, unknowns
    allowed, no demographics, no overall score."""
    words = transcript.split()
    return {"texture": [{"label": "smooth", "confidence": "uncalibrated",
                         "evidence": {"start_sec": 0.0, "end_sec": 10.0}}],
            "prosody": [{"label": "conversational", "confidence": "uncalibrated",
                         "evidence": {"start_sec": 10.0, "end_sec": 20.0}}],
            "energy": "moderate", "delivery": ["natural_storytelling"],
            "description": f"Natural read, ~{len(words)} words transcribed.",
            "model": "stub-0.1", "forbidden_inferred": []}


def merge(sample_sha: str, acoustic_m: dict, described: dict, transcript: str) -> dict:
    """Combine evidence; flag contradictions instead of hiding them."""
    flags = []
    if acoustic_m.get("clipping_detected") and "clean" in described.get("description", ""):
        flags.append("descriptor_contradicts_measurement")
    return {"schema_version": "voice-profile.v1",
            "analysis_version": PIPELINE_VERSION,
            "sample_sha256": sample_sha,
            "acoustic": acoustic_m,
            "perceptual": described,
            "transcript_words": len(transcript.split()),
            "contradictions": flags}


def analyze(frames: list[float], sample_rate: int, transcript: str, sample_sha: str) -> dict:
    segs = vad_segments(frames, sample_rate)
    ac = acoustic(frames, sample_rate, segs)
    de = describe_stub(transcript, ac)
    return {"segments": segs, **merge(sample_sha, ac, de, transcript)}
