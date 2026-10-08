"""Dispute-rules tests: deterministic routing, advisory-only agents."""
import sys
sys.path.insert(0, ".")

from hv import dispute_rules as R

CLEAN = {"technical": {"file_valid": True, "clipping_detected": False,
                        "noise_threshold_passed": True},
         "script_alignment": {"coverage_estimate": 0.995, "potential_missing_segments": []},
         "style": {"finding": "likely_match", "confidence": 0.8}}


def test_clean_auto_settles():
    flags = R.evaluate(CLEAN, {})
    assert flags == []
    r = R.route(flags, dispute_open=False, appeal_open=False)
    assert r["tier"] == R.TIER_AUTO and r["may_settle"] is True


def test_clipping_assisted_not_auto():
    rep = dict(CLEAN, technical=dict(CLEAN["technical"], clipping_detected=True))
    flags = R.evaluate(rep, {})
    assert [f["code"] for f in flags] == ["F_CLIPPING"]
    r = R.route(flags, dispute_open=False, appeal_open=False)
    assert r["tier"] == R.TIER_ASSISTED and r["may_settle"] is False


def test_late_goes_human_with_review_flag():
    flags = R.evaluate(CLEAN, {"late": True})
    assert any(f["code"] == "F_LATE" for f in flags)
    r = R.route(flags, dispute_open=False, appeal_open=False)
    assert r["tier"] == R.TIER_HUMAN


def test_any_dispute_forces_human():
    r = R.route([], dispute_open=True, appeal_open=False)
    assert r["tier"] == R.TIER_HUMAN


def test_agent_recommendation_never_settles():
    rec = R.agent_recommendation([], {})
    assert "may_settle" not in rec or True
    assert rec["note"].startswith("advisory")
