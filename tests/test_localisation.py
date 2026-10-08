"""Localisation tests: quals, chains, packages, subtitles."""
import sys
sys.path.insert(0, ".")

from hv import localisation as L


def test_bilingual_qual_required():
    job = {"kind": "review", "pair": "en-hi", "requires": ["review_en_hi"]}
    ok, _ = L.qualified_for({"review_en_hi"}, job)
    assert ok
    ok, why = L.qualified_for({"narrate_hi"}, job)
    assert not ok and "review_en_hi" in why


def test_narration_only_cannot_review():
    job = {"kind": "dub", "pair": "en-hi", "requires": ["review_en_hi", "narrate_hi"]}
    ok, _ = L.qualified_for({"narrate_hi"}, job)
    assert not ok


def test_chain_splits_dub():
    job = {"kind": "dub", "pair": "en-hi", "target": "hi"}
    stages = L.chain_jobs(job)
    assert [s["kind"] for s in stages] == ["review", "narrate"]
    assert stages[1]["depends_on"] == "stage:1"
    assert L.chain_jobs({"kind": "narrate"})[0]["kind"] == "narrate"


def test_package_and_srt():
    assert L.package_manifest("hvc_1", "en-hi") == [
        "original.en.txt", "draft.hi.txt", "approved.hi.txt", "edits.json",
        "narration.hi.wav", "subtitles.hi.srt", "alignment.json", "quality-report.json"]
    srt = L.to_srt([{"start": 0.0, "end": 2.5, "text": "line one"}])
    assert srt.startswith("1\n00:00:00,000 --> 00:00:02,500\nline one")


def test_edits_record():
    e = L.edits_json(["a", "b", "c"], ["a", "B!", "c", "d"])
    assert e[0]["change"] == "replace" and e[0]["approved"] == ["B!"]
    assert e[1]["change"] == "insert" and e[1]["approved"] == ["d"]
    assert L.edits_json(["a"], ["a"]) == []
