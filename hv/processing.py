"""Processing engine: deterministic DSP on the backend, never on the phone.

Basic (always included): preserve original, high-pass rumble, EBU R128
loudness normalize, lookahead limit, MP3 copy.
Studio (optional paid upgrade): + FFT denoise, gentle compression, preset
EQ character, A/B measurements against the original.

No neural models, no GPU, no voice cloning. Every output is reproducible
from (original sha256, filter chain, settings, ffmpeg version) and recorded
in the manifest. Severe defects (clipping, echoes, missing words) are flagged
for rerecording, never silently "fixed".
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile

TIMEOUT = 300

COMPRESSION = {
    "gentle": "threshold=-20dB:ratio=2:attack=20:release=200:makeup=2dB",
    "medium": "threshold=-18dB:ratio=3:attack=10:release=150:makeup=4dB",
    "firm": "threshold=-16dB:ratio=4:attack=5:release=100:makeup=6dB",
}

EQ = {
    "flat": None,
    "warm": "bass=g=2:f=120,treble=g=-1:f=8000",
    "bright": "treble=g=2:f=6000",
}


class ProcessingError(RuntimeError):
    pass


def ffmpeg_version() -> str:
    try:
        out = subprocess.run(["ffmpeg", "-version"], capture_output=True,
                             text=True, timeout=15).stdout
        return (out.splitlines() or ["unknown"])[0][:120]
    except Exception:
        return "unknown"


def denoise_backend() -> str:
    """Best available neural denoise backend. DeepFilterNet3 (MIT/Apache,
    CPU-capable) when installed with weights; otherwise 'none' and the
    deterministic afftdn stage carries denoising. Never downloads."""
    try:
        __import__("deepfilternet")
        return "deepfilternet"
    except Exception:
        return "none"


def neural_denoise(src_wav: str, dst_wav: str) -> dict:
    """Optional DeepFilterNet3 pass. Raises ProcessingError when unavailable;
    the caller falls back to afftdn. Kept out of the default chain until the
    10-voice benchmark (fidelity vs afftdn) lands."""
    if denoise_backend() != "deepfilternet":
        raise ProcessingError("deepfilternet not installed")
    p = _run(["deep-filter", src_wav, "-o", os.path.dirname(dst_wav) or "."])
    if p.returncode != 0:
        raise ProcessingError("deepfilternet failed: " + p.stderr[-300:])
    return {"backend": "deepfilternet", "note": "benchmark pending"}


def sha_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT)
    except FileNotFoundError:
        raise ProcessingError("ffmpeg not installed")
    except subprocess.TimeoutExpired:
        raise ProcessingError("ffmpeg timed out")


def measure_loudness(wav_path: str) -> dict:
    """EBU R128 measurement via loudnorm first pass. Returns integrated LUFS,
    true peak dBTP, LRA when available; {} if unmeasurable."""
    p = _run(["ffmpeg", "-hide_banner", "-i", wav_path, "-map", "0:a",
              "-filter:a", "loudnorm=print_format=json", "-f", "null", "-"])
    try:
        blob = p.stderr[p.stderr.index("{"):p.stderr.rindex("}") + 1]
        d = json.loads(blob)
        return {"input_i": float(d.get("input_i", 0)),
                "input_tp": float(d.get("input_tp", 0)),
                "input_lra": float(d.get("input_lra", 0)),
                "input_thresh": float(d.get("input_thresh", 0))}
    except (ValueError, TypeError, KeyError):
        return {}


def _dual_loudnorm(src: str, dst: str, pre: str, target_lufs: float) -> dict:
    """Two-pass loudnorm with a pre-filter chain. Returns measured loudness."""
    meas = measure_loudness(src)
    if not meas:
        raise ProcessingError("could not measure loudness")
    filt = (pre + "," if pre else "") + (
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:"
        f"measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
        f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:"
        f"offset=0:linear=true,alimiter=limit=0.95")
    p = _run(["ffmpeg", "-hide_banner", "-y", "-i", src,
              "-filter:a", filt, "-ar", "48000", "-ac", "1", dst])
    if p.returncode != 0 or not os.path.exists(dst):
        raise ProcessingError("loudnorm pass failed: " + p.stderr[-300:])
    return meas


def basic_pack(src_wav: str, out_dir: str, target_lufs: float = -19.0) -> dict:
    """Usable master + MP3. Never claims denoising."""
    os.makedirs(out_dir, exist_ok=True)
    master = os.path.join(out_dir, "narration.wav")
    meas = _dual_loudnorm(src_wav, master, "highpass=f=80", target_lufs)
    mp3 = os.path.join(out_dir, "narration.mp3")
    p = _run(["ffmpeg", "-hide_banner", "-y", "-i", master,
              "-codec:a", "libmp3lame", "-b:a", "192k", mp3])
    if p.returncode != 0:
        raise ProcessingError("mp3 export failed: " + p.stderr[-300:])
    return {"narration.wav": master, "narration.mp3": mp3,
            "measured": meas, "chain": "highpass=80,loudnorm,alimiter"}


def studio_master(src_wav: str, out_dir: str, preset: dict) -> dict:
    """Enhanced master per channel preset. Denoise/compress/EQ per settings."""
    os.makedirs(out_dir, exist_ok=True)
    pre = f"highpass=f=80,afftdn=nr={preset['denoise_db']}:nf=-25"
    comp = COMPRESSION[preset["compression"]]
    chain = f"{pre},acompressor={comp}"
    if EQ[preset["eq"]]:
        chain += "," + EQ[preset["eq"]]
    studio = os.path.join(out_dir, "studio.wav")
    meas = _dual_loudnorm(src_wav, studio, chain, preset["target_lufs"])
    mp3 = os.path.join(out_dir, "studio.mp3")
    p = _run(["ffmpeg", "-hide_banner", "-y", "-i", studio,
              "-codec:a", "libmp3lame", "-b:a", "192k", mp3])
    if p.returncode != 0:
        raise ProcessingError("studio mp3 export failed: " + p.stderr[-300:])
    return {"studio.wav": studio, "studio.mp3": mp3, "measured": meas,
            "chain": chain + ",loudnorm,alimiter",
            "preset": {k: preset[k] for k in ("target_lufs", "denoise_db",
                                             "compression", "eq")}}


def duration_sec(wav_path: str) -> float:
    try:
        import wave as _w
        with _w.open(wav_path, "rb") as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 0.0


def integrity_check(orig_wav: str, proc_wav: str,
                    orig_text: str = "", proc_text: str = "") -> dict:
    """Speech-integrity gate: duration must match; when transcripts exist
    their word overlap must clear 0.9. Anything else -> manual review."""
    d0, d1 = duration_sec(orig_wav), duration_sec(proc_wav)
    dur_ok = d0 > 0 and abs(d0 - d1) / d0 <= 0.05
    overlap, w0 = 1.0, []
    if orig_text or proc_text:
        w0 = orig_text.lower().split()
        w1 = set(proc_text.lower().split())
        hits = sum(1 for w in w0 if w in w1)
        overlap = round(hits / max(1, len(w0)), 4)
    text_ok = overlap >= 0.9
    passed = bool(dur_ok and text_ok)
    return {"duration_ok": dur_ok, "transcript_overlap": overlap,
            "checked_words": len(w0), "passed": passed,
            "verdict": "deliver" if passed else "manual_review"}


def srt_from_segments(segments: list[dict]) -> str:
    def ts(s: float) -> str:
        s = max(0.0, float(s))
        h, rem = divmod(int(s * 1000), 3600000)
        m, rem = divmod(rem, 60000)
        sec, ms = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
    out = []
    for i, seg in enumerate(segments, 1):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        out.append(f"{i}\n{ts(seg.get('start', 0))} --> {ts(seg.get('end', 0))}\n{text}\n")
    return "\n".join(out) + ("\n" if out else "")


def workdir() -> str:
    d = tempfile.mkdtemp(prefix="hv-pack-")
    return d
