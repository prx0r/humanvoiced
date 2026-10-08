"""Capture QC: honest PCM measurements for guidance, never verdicts.

Measures room-noise baseline, peak/clipping, speech level and an estimated
speech-to-noise difference from decoded mono frames. Thresholds produce
advisory messages only — phone and laptop processing varies too much for
automatic rejection. Shared by the browser sound check (same math in
studio.js) and backend upload analysis.
"""
from __future__ import annotations

import math

SILENCE_FLOOR_DBFS = -96.0


def dbfs(rms: float) -> float:
    if rms <= 0.00001:
        return SILENCE_FLOOR_DBFS
    return max(SILENCE_FLOOR_DBFS, round(20 * math.log10(rms), 1))


def window_rms(frames: list[float]) -> float:
    if not frames:
        return 0.0
    return math.sqrt(sum(x * x for x in frames) / len(frames))


def measure(frames: list[float], sample_rate: int) -> dict:
    """Full-file metrics: peak, RMS, estimated noise floor (quietest 5%),
    speech level (loudest-half mean) and advisory flags."""
    if not frames:
        return {"error": "empty audio"}
    peak = max(abs(x) for x in frames)
    win = max(1, sample_rate // 10)  # 100ms windows
    win_rms = [window_rms(frames[i:i + win]) for i in range(0, len(frames), win)]
    if not win_rms:
        return {"error": "too short"}
    ordered = sorted(win_rms)
    noise = sum(ordered[:max(1, len(ordered) // 20)]) / max(1, len(ordered) // 20)
    loud = ordered[len(ordered) // 2:]
    speech = sum(loud) / len(loud)
    speech_db, noise_db = dbfs(speech), dbfs(noise)
    flags = []
    if peak >= 0.985:
        flags.append("clipping")
    if noise_db > -40:
        flags.append("noisy_room")
    if speech_db < -30:
        flags.append("quiet_voice")
    snr = round(speech_db - noise_db, 1)
    if snr < 10:
        flags.append("low_snr")
    return {"peak": round(peak, 4), "rms_dbfs": dbfs(window_rms(frames)),
            "noise_floor_dbfs": noise_db, "speech_dbfs": speech_db,
            "snr_db": snr, "clipping_detected": peak >= 0.985,
            "flags": flags, "advisory_only": True}


ADVICE = {
    "clipping": "Your voice is distorting. Move farther away or lower the input level.",
    "noisy_room": "Try a quieter room or turn off the fan.",
    "quiet_voice": "Move your phone slightly closer (15-20 cm, slightly off-axis).",
    "low_snr": "Your voice is barely above the room noise - closer or quieter.",
}


def advise(metrics: dict) -> list[str]:
    """Human-readable hints for each flag. Empty means ready to record."""
    if metrics.get("error"):
        return ["We could not measure that audio."]
    out = [ADVICE[f] for f in metrics.get("flags", []) if f in ADVICE]
    if not out:
        out = ["Sounds good. Start recording."]
    return out
