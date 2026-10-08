"""Audio pipeline: ingest → VAD → acoustic → transcribe → describe → merge.

Stages are independent and idempotent, keyed by sample_sha256 +
pipeline_version. Providers are interfaces; local deterministic fallbacks
run without keys or GPUs. Heavy models (Whisper/Qwen/Gemini) plug in
behind transcribe.py / describe.py without touching the schema.
"""
from __future__ import annotations

PIPELINE_VERSION = "2026-10-08.2"


def decode_wav_mono(wav_bytes: bytes, max_seconds: int = 120) -> tuple[list[float], int]:
    """Decode 16-bit PCM WAV bytes to mono float frames (-1..1), downmixing
    channels by averaging complete frames. Raises ValueError on bad input."""
    import io as _io
    import struct as _st
    import wave as _wv
    with _wv.open(_io.BytesIO(wav_bytes), "rb") as _w:
        ch, sw, sr, n = _w.getnchannels(), _w.getsampwidth(), _w.getframerate(), _w.getnframes()
        if sw != 2:
            raise ValueError("only 16-bit PCM supported")
        if ch not in (1, 2) or n <= 0:
            raise ValueError("invalid WAV parameters")
        raw = _w.readframes(n)
    total_samples = len(raw) // 2
    nframes = total_samples // ch
    fmt = "<" + "h" * total_samples
    ints = _st.unpack(fmt, raw[:total_samples * 2])
    mono: list[float] = []
    for i in range(nframes):
        s = 0
        for c in range(ch):
            s += ints[i * ch + c]
        mono.append((s / ch) / 32768.0)
    cap = sr * max_seconds
    return mono[:cap], sr


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
    mean_sq = sum(x * x for x in frames) / len(frames) if frames else 0.0
    if mean_sq <= 0:
        rms_dbfs = -96.0
    else:
        rms_dbfs = round(10 * math.log10(mean_sq), 2)  # == 20*log10(rms)
    return {"speech_fraction": round(speech / total, 3) if total else 0.0,
            "peak": round(peak, 4),
            "clipping_detected": peak >= 0.999,
            "pause_mean_ms": round(sum(gaps) / len(gaps) * 1000) if gaps else 0,
            "pause_median_ms": pct(0.5), "pause_p90_ms": pct(0.9),
            "rms_dbfs": rms_dbfs,
            "uncertainty": "energy-vad fallback; replace with Silero + pitch tracker"}


VOCAB = {"texture": ["smooth", "breathy", "husky", "raspy", "grainy", "airy"],
         "resonance": ["full", "light", "rounded", "bright"],
         "energy": ["relaxed", "moderate", "animated"],
         "prosody": ["restrained", "conversational", "expressive", "dramatic"],
         "delivery": ["understated", "storytelling", "measured", "lively"]}


def describe_stub(transcript: str, acoustic_m: dict) -> dict:
    """Honest placeholder shape when no audio-capable model is available.
    Perceptual fields are `unknown` — never manufactured. The audio-LLM
    (Qwen3-Omni/Gemini) plugs in here via hv/describe.py without touching
    callers. Deterministic acoustic measurements remain the only trusted data.
    """
    words = transcript.split()
    return {"texture": [{"label": "unknown", "confidence": "none",
                         "evidence": {"start_sec": 0.0, "end_sec": 0.0}}],
            "prosody": [{"label": "unknown", "confidence": "none",
                         "evidence": {"start_sec": 0.0, "end_sec": 0.0}}],
            "energy": "unknown", "delivery": [],
            "description": (f"Perceptual analysis pending audio-capable model; "
                            f"~{len(words)} words transcribed, measurements only."),
            "model": "stub-0.1", "placeholders": True,
            "forbidden_inferred": []}


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
