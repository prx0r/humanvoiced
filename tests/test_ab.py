"""AB tests: variants agree on structure, multilingual matrix runs."""
import sys
sys.path.insert(0, ".")

from hv import ab as AB


def _frames():
    import math
    out = []
    for i in range(16000):
        t = i / 16000
        out.append(0.3 * math.sin(2 * math.pi * 120 * t) if (t % 1.0) < 0.7 else 0.001)
    return out


def test_variant_agreement():
    f = _frames()
    a = AB.run_variant(f, 16000, lambda: "hello world test", "whisper")
    b = AB.run_variant(f, 16000, lambda: "hello world test!", "qwen")
    ag = AB.agreement(a, b)
    assert ag["word_jaccard"] >= 0.5
    assert ag["same_clipping_call"] is True


def test_multilingual_matrix():
    f = _frames()
    m = AB.multilingual_matrix(
        [{"language": "en", "frames": f, "sample_rate": 16000},
         {"language": "hi", "frames": f, "sample_rate": 16000}],
        lambda fr, sr, lang: "hello world" if lang == "en" else "")
    assert [r["language"] for r in m] == ["en", "hi"]
    assert m[0]["empty"] is False and m[1]["empty"] is True


def test_providers_map():
    import os
    from hv import providers as PR
    assert "transcribe" in PR.PROVIDERS and "synthesize" in PR.PROVIDERS
    a = PR.available()
    assert a["transcribe"] == "cf-whisper-turbo"
    assert set(a) == {"transcribe", "describe", "translate", "synthesize", "realtime", "reason", "notes"}
