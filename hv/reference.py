"""Reference matching: one channel sound, every narrator.

Measure a spectral profile (octave-band energies + loudness) from an
approved reference master, then EQ-match each new take toward it with
gains capped at +/-6 dB. Matching moves tone toward the channel — it never
makes voices identical and never touches words, timing or identity.
"""
from __future__ import annotations

import math

BANDS = [125, 250, 500, 1000, 2000, 4000, 8000]
MATCH_CAP_DB = 6.0


def band_energies(frames: list[float], sample_rate: int) -> dict[int, float]:
    """Mean dB per octave band via FFT. Silence floor -96 dB."""
    import numpy as _np
    if not frames or sample_rate <= 0:
        return {f: -96.0 for f in BANDS}
    x = _np.array(frames, dtype=_np.float64)
    spec = _np.abs(_np.fft.rfft(x * _np.hanning(len(x)))) ** 2
    freqs = _np.fft.rfftfreq(len(x), 1 / sample_rate)
    out = {}
    for f in BANDS:
        lo, hi = f / math.sqrt(2), f * math.sqrt(2)
        sel = spec[(freqs >= lo) & (freqs < hi)]
        e = float(_np.mean(sel)) if sel.size else 0.0
        out[f] = round(10 * math.log10(e + 1e-12), 1)
    ref = out[1000]
    return {f: round(v - ref, 1) for f, v in out.items()}  # relative to 1k


def measure_file(path: str) -> dict:
    """Full profile from a WAV file: bands + EBU loudness when measurable."""
    from hv.audio import decode_wav_mono
    from hv import processing as _proc
    with open(path, "rb") as f:
        frames, sr = decode_wav_mono(f.read())
    loud = _proc.measure_loudness(path)
    return {"bands": band_energies(frames, sr),
            "lufs": loud.get("input_i"),
            "true_peak": loud.get("input_tp")}


def match_curve(take_bands: dict, ref_bands: dict,
                cap_db: float = MATCH_CAP_DB) -> str:
    """firequalizer gain entries moving take toward reference, capped."""
    entries = []
    for f in BANDS:
        key = f if f in ref_bands else str(f)
        delta = float(ref_bands.get(key, ref_bands.get(str(key), 0)))
        base = float(take_bands.get(f, take_bands.get(str(f), 0)))
        g = max(-cap_db, min(cap_db, round(delta - base, 1)))
        entries.append(f"entry({f},{g})")
    return "gain_entry='" + ";".join(entries) + "'"
