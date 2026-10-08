"""Curve + heatmap + reference tests."""
import sys
sys.path.insert(0, ".")

from hv import pricing as P
from hv import voice_reference as V


def test_fitted_curve_hits_targets():
    assert P.curve(10 / 60) == 2.0
    assert P.curve(10) == 10.0
    assert P.curve(30) == 20.0
    assert P.curve(60) == 31.74


def test_heatmap_bands():
    b = P.heatmap(10, "proven")
    assert b == {"low": 10.92, "base": 11.5, "high": 12.08, "tier": "proven", "tier_mult": 1.15}
    n = P.heatmap(10, "new")
    assert n["base"] == 10.0 and n["low"] < 10.0 < n["high"]


def test_reference_lock_and_compare():
    ref = V.lock_reference("sample_238", 2, "a" * 64, "documentary")
    assert ref["version"] == 2
    good = V.compare_report(ref, {"script_coverage": 0.995, "tech_pass": True,
                                  "consistency": "likely_match"})
    assert good["recommendation"] == "approve"
    bad = V.compare_report(ref, {"script_coverage": 0.9, "tech_pass": True,
                                 "consistency": "likely_match"})
    assert bad["recommendation"] == "correct"
    assert bad["findings"]["style"] == "advisory"
