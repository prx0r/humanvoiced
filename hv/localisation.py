"""Localisation engine: bilingual quals, chained jobs, dub packages.

Capabilities are independently verified: narration-only, review-only, or
combined. Translation review needs a second qualification (comprehension +
natural target writing), never self-declared fluency alone. Jobs the worker
can't do chain: reviewer approves script → narrator records; agent coordinates.
"""
from __future__ import annotations

import difflib

CAPABILITIES = ("narrate_en", "narrate_hi", "narrate_es",
                "review_en_hi", "review_en_es", "character")

PACKAGE_PRICES_10MIN = {"narrate": 11.0, "review_low": 12.0,
                        "review_high": 20.0, "dub_low": 25.0, "dub_high": 40.0}


def qualified_for(worker_caps: set[str], job: dict) -> tuple[bool, str]:
    """Check capability + bilingual qualification for a localisation job."""
    need = job.get("requires", [])
    missing = [c for c in need if c not in worker_caps]
    if missing:
        return False, f"missing capabilities: {missing}"
    if job.get("kind") in ("review", "dub"):
        pair = job.get("pair", "")
        qual = f"review_{pair.replace('-', '_')}"
        if qual not in worker_caps and "narrate" not in qual:
            pass  # combined-service workers carry review_* explicitly
        if qual not in worker_caps:
            return False, f"bilingual qualification {qual} not verified"
    return True, "ok"


def chain_jobs(job: dict) -> list[dict]:
    """Split dub jobs when one worker lacks both halves: review → narrate."""
    if job.get("kind") != "dub" or job.get("single_worker"):
        return [job]
    review = dict(job, kind="review", stage=1,
                  requires=[f"review_{job.get('pair', 'en-hi').replace('-', '_')}"])
    narrate = dict(job, kind="narrate", stage=2, depends_on="stage:1",
                   requires=[f"narrate_{job.get('target', 'hi')}"])
    return [review, narrate]


def edits_json(draft_lines: list[str], approved_lines: list[str]) -> list[dict]:
    """Line-level edit record: what the human changed and where."""
    out = []
    for i, (d, a) in enumerate(zip(draft_lines, approved_lines)):
        if d != a:
            out.append({"scene": i + 1, "draft": d, "approved": a,
                        "changed": True})
    return out


def to_srt(segments: list[dict]) -> str:
    """Subtitles from approved-script alignment segments."""
    def ts(s: float) -> str:
        ms = int(s * 1000)
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        sec, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{sec:02},{ms:03}"
    blocks = []
    for i, s in enumerate(segments, 1):
        blocks.append(f"{i}\n{ts(s['start'])} --> {ts(s['end'])}\n{s['text']}\n")
    return "\n".join(blocks)


def package_manifest(contract_id: str, pair: str) -> list[str]:
    src, tgt = pair.split("-")
    return [f"original.{src}.txt", "draft.%s.txt" % tgt, "approved.%s.txt" % tgt,
            "edits.json", f"narration.{tgt}.wav", f"subtitles.{tgt}.srt",
            "alignment.json", "quality-report.json"]


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()
