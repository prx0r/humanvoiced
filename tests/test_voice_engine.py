"""Audio pipeline + catalog search tests."""
import sys
sys.path.insert(0, ".")

from hv import audio as A
from hv import catalog as C


def _frames(sr=16000, secs=2.0):
    import math
    n = int(sr * secs)
    out = []
    for i in range(n):
        t = i / sr
        out.append(0.3 * math.sin(2 * math.pi * 120 * t) if (t % 1.0) < 0.7 else 0.001)
    return out


def test_pipeline_layers():
    frames = _frames()
    rep = A.analyze(frames, 16000, "hello world calm documentary test", "abc123")
    assert rep["segments"] and rep["acoustic"]["speech_fraction"] > 0.5
    assert rep["acoustic"]["clipping_detected"] is False
    assert rep["perceptual"]["model"] == "stub-0.1"
    assert rep["sample_sha256"] == "abc123"


def test_search_eligibility_then_rank():
    cat = [{"voice_id": "v1", "handle": "alex", "languages": ["en"],
            "capabilities": {"declared": ["youtube_narration"], "demonstrated": []},
            "availability": {"accepting_offers": True, "max_minutes_per_job": 60},
            "match_features": {"perceptual": 0.9, "delivery": 0.8, "pace": 0.7, "category": 0.6},
            "reliability": None},
           {"voice_id": "v2", "handle": "sam", "languages": ["hi"],
            "capabilities": {"declared": [], "demonstrated": []},
            "availability": {"accepting_offers": True, "max_minutes_per_job": 60},
            "match_features": {}, "reliability": None}]
    q = {"job": {"language": "en", "category": "youtube_narration",
                 "duration_minutes": 12, "deadline_hours": 24},
         "preferences": {}, "limit": 5}
    res = C.search(cat, q)
    assert [r["voice_id"] for r in res] == ["v1"]
    assert res[0]["uncertainties"] == ["no_prior_contracts", "no_prior_category_contracts"] or \
        "no_prior_contracts" in res[0]["uncertainties"]
    assert res[0]["profile_url"] == "/@alex" and res[0]["can_book"] is True


def test_match_event_stages():
    e = C.match_event("v1", "q1", "booked")
    assert e["stage"] == "booked"
    try:
        C.match_event("v1", "q1", "nope")
        assert False
    except AssertionError:
        pass
