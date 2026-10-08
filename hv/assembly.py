"""Assembly: accepted takes -> continuous timeline master, sample-accurate.

Gain-matches takes, trims edge silence (keeping handles), joins with short
raised-cosine crossfades or breathing pauses, and places hard-timed passages
inside their windows. A take that cannot fit a hard window overflows the
whole assembly with details -- the agent shortens the script or orders a
retake; voices are never time-stretched. Every step lands in the edit map,
which becomes the provenance record (takes kept, including rejected ones).
"""
from __future__ import annotations

import wave

import numpy as _np

TARGET_SR = 48000
TARGET_RMS_DBFS = -20.0
CROSSFADE_MS = 80
BREATH_MS = 300
TRIM_THRESH = 0.02  # -34 dBFS edge silence
TRIM_KEEP_MS = 120


class AssemblyError(ValueError):
    pass


def _decode(path: str) -> tuple[_np.ndarray, int]:
    from hv.audio import decode_wav_mono
    with open(path, "rb") as f:
        frames, sr = decode_wav_mono(f.read())
    return _np.array(frames, dtype=_np.float64), sr


def _resample(x: _np.ndarray, sr: int) -> _np.ndarray:
    if sr == TARGET_SR or len(x) == 0:
        return x
    from scipy.signal import resample as _rs
    n = int(len(x) * TARGET_SR / sr)
    return _rs(x, n).astype(_np.float64)


def _rms(x: _np.ndarray) -> float:
    return float(_np.sqrt(_np.mean(x ** 2))) if len(x) else 0.0


def _trim(x: _np.ndarray) -> tuple[_np.ndarray, int, int]:
    """Trim edge silence below threshold, keeping handles. Returns audio,
    ms trimmed from start/end."""
    if len(x) == 0:
        return x, 0, 0
    loud = _np.where(_np.abs(x) >= TRIM_THRESH)[0]
    if len(loud) == 0:
        return x[:0], 0, 0
    keep = int(TARGET_SR * TRIM_KEEP_MS / 1000)
    a = max(0, int(loud[0]) - keep)
    b = min(len(x), int(loud[-1]) + keep)
    ms = 1000 / TARGET_SR
    return x[a:b], int(a * ms), int((len(x) - b) * ms)


def _raised_cosine(n: int) -> _np.ndarray:
    t = _np.linspace(0, 1, max(2, n))
    return 0.5 - 0.5 * _np.cos(_np.pi * t)


def assemble(segments: list[dict], take_paths: dict[str, str],
             out_path: str) -> dict:
    """segments: manifest order. take_paths: seg_id -> accepted take wav.
    Returns {master_sha..., edit_map, total_ms}. Raises AssemblyError."""
    import hashlib as _h
    from hv.util import utcnow as _now
    timeline = _np.zeros(0, dtype=_np.float64)
    edit_map: list[dict] = []
    cursor_ms = 0.0
    for seg in segments:
        sid = seg["id"]
        if sid not in take_paths:
            raise AssemblyError(f"segment {sid}: no accepted take")
        x, sr = _decode(take_paths[sid])
        x = _resample(x, sr)
        x, trim_a, trim_b = _trim(x)
        if len(x) == 0:
            raise AssemblyError(f"segment {sid}: take is silent")
        rms = _rms(x)
        gain_db = TARGET_RMS_DBFS - (20 * _np.log10(rms) if rms > 1e-5 else -96.0)
        peak = float(_np.max(_np.abs(x))) if len(x) else 0.0
        if peak * 10 ** (gain_db / 20) > 0.99:  # never clip while matching
            gain_db = 20 * _np.log10(0.99 / peak) if peak > 0 else 0.0
            limited = True
        else:
            limited = False
        x = x * 10 ** (gain_db / 20)
        dur_ms = len(x) / TARGET_SR * 1000
        a, b = seg.get("target_start_ms"), seg.get("target_end_ms")
        if seg.get("timing") == "hard" and a is not None and b is not None:
            if dur_ms > (b - a):
                raise AssemblyError(
                    f"segment {sid}: {dur_ms:.0f}ms of speech cannot fit "
                    f"{b - a:.0f}ms hard window; shorten the script or retake")
            offset_ms = float(a)
        else:
            offset_ms = max(cursor_ms, float(a or 0))
        need = int(offset_ms * TARGET_SR / 1000)
        if need > len(timeline):
            timeline = _np.pad(timeline, (0, need - len(timeline)))
        # crossfade only when the take starts inside existing audio
        start = need
        if start < len(timeline) and len(timeline) - start >= 64:
            n = min(int(CROSSFADE_MS * TARGET_SR / 1000), len(timeline) - start, len(x))
            w = _raised_cosine(n)
            timeline[start:start + n] = timeline[start:start + n] * (1 - w) + x[:n] * w
            rest = x[n:]
            end = start + n
            if end + len(rest) > len(timeline):
                timeline = _np.pad(timeline, (0, end + len(rest) - len(timeline)))
            timeline[end:end + len(rest)] = rest
            cursor_ms = (end + len(rest)) / TARGET_SR * 1000
            cf_n = n
        else:
            if start + len(x) > len(timeline):
                timeline = _np.pad(timeline, (0, start + len(x) - len(timeline)))
            timeline[start:start + len(x)] = x
            cursor_ms = (start + len(x)) / TARGET_SR * 1000 + BREATH_MS
            cf_n = 0
        edit_map.append({"seg": sid, "gain_db": round(float(gain_db), 2),
                         "gain_limited": limited, "offset_ms": round(offset_ms, 1),
                         "duration_ms": round(dur_ms, 1),
                         "trimmed_ms": [trim_a, trim_b],
                         "crossfade_ms": round(cf_n / TARGET_SR * 1000, 1),
                         "timing": seg.get("timing", "soft")})
    # end breathing room, then write 16-bit master
    tail = int(BREATH_MS * TARGET_SR / 1000)
    timeline = _np.pad(timeline, (0, tail))
    pcm = _np.clip(timeline, -1.0, 1.0)
    pcm16 = (pcm * 32767).astype(_np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TARGET_SR)
        w.writeframes(pcm16.tobytes())
    with open(out_path, "rb") as f:
        sha = _h.sha256(f.read()).hexdigest()
    return {"master_sha256": sha, "path": out_path, "edit_map": edit_map,
            "total_ms": round(len(timeline) / TARGET_SR * 1000, 1),
            "built_at": _now(), "sample_rate": TARGET_SR}
