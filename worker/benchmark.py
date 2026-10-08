"""A/B benchmark harness: ours vs reference masters, measured + blind.

Owner flow (credits are bought by the owner, never this box):
  1. Collect 5+ real phone recordings (bedroom, fan, reflective, noisy).
  2. Run our studio pack on each; run Auphonic (paid credits) on each.
  3. python3 -m worker.benchmark ours/ ref/ --out bench/  -> table + blind set.
  4. Listen blind (someone else holds key.json), pick winners, then reveal.
  5. If ours is comparable, ship default at ~zero marginal cost; if the
     reference wins on bad mics, it justifies the premium restoration tier.
  6. Reverse-engineer honestly: the winner's measured profile (loudness,
     band balance, noise floor) becomes a match-my-channel reference --
     production choices measured, never code copied.

Usage: python3 -m worker.benchmark A_DIR B_DIR --out OUT [--label-a ours]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys

sys.path.insert(0, ".")


def measure(path: str) -> dict:
    from hv import capture_qc as _q
    from hv import processing as _p
    from hv.audio import decode_wav_mono
    with open(path, "rb") as f:
        frames, sr = decode_wav_mono(f.read())
    m = _q.measure(frames, sr)
    loud = _p.measure_loudness(path)
    return {"noise_floor_dbfs": m.get("noise_floor_dbfs"),
            "snr_db": m.get("snr_db"),
            "clipping": m.get("clipping_detected"),
            "lufs": loud.get("input_i"),
            "true_peak": loud.get("input_tp"),
            "duration_s": round(_p.duration_sec(path), 1)}


def compare(a_dir: str, b_dir: str, out: str, label_a="ours",
            label_b="reference", seed=7) -> dict:
    from hv import processing as _p
    aud = sorted(f for f in os.listdir(a_dir) if f.lower().endswith(".wav"))
    bud = sorted(f for f in os.listdir(b_dir) if f.lower().endswith(".wav"))
    names = sorted(set(aud) & set(bud))
    if not names:
        raise SystemExit("no matching .wav filenames in both dirs")
    os.makedirs(out, exist_ok=True)
    blind = os.path.join(out, "blind")
    os.makedirs(blind, exist_ok=True)
    rng = random.Random(seed)
    rows, key = [], {}
    for n in names:
        pa, pb = os.path.join(a_dir, n), os.path.join(b_dir, n)
        ma, mb = measure(pa), measure(pb)
        rows.append({"clip": n, label_a: ma, label_b: mb,
                     "lufs_delta": _r(mb.get("lufs"), ma.get("lufs")),
                     "snr_delta": _r(mb.get("snr_db"), ma.get("snr_db"))})
        tags = [f"{label_a}:{n}", f"{label_b}:{n}"]
        rng.shuffle(tags)
        for i, tag in enumerate(tags):
            fn = f"{os.path.splitext(n)[0]}-{chr(65 + i)}.wav"
            shutil.copy(pa if tag.startswith(label_a) else pb,
                        os.path.join(blind, fn))
            key[fn] = tag
    with open(os.path.join(out, "table.json"), "w") as f:
        json.dump(rows, f, indent=1)
    with open(os.path.join(out, "key.json"), "w") as f:
        json.dump({"key": key, "note": "evaluator must not open until scoring done",
                   "ffmpeg": _p.ffmpeg_version()}, f, indent=1)
    md = ["| clip | LUFS(ref-ours) | SNR(ref-ours) |", "|---|---|---|"]
    md += [f"| {r['clip']} | {r['lufs_delta']} | {r['snr_delta']} |" for r in rows]
    with open(os.path.join(out, "table.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"compared {len(rows)} clips -> {out}/table.md + blind/ ({len(key)} files)")
    print("RULE: score the blind/ files first. Open key.json only after.")
    return {"rows": rows, "key": key}


def _r(a, b):
    try:
        return round(float(a) - float(b), 1)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a_dir")
    ap.add_argument("b_dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label-a", default="ours")
    ap.add_argument("--label-b", default="reference")
    args = ap.parse_args()
    compare(args.a_dir, args.b_dir, args.out, args.label_a, args.label_b)


if __name__ == "__main__":
    main()
