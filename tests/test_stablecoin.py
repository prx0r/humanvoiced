"""Stablecoin + prefs tests."""
import sys
sys.path.insert(0, ".")

import pytest

from hv import stablecoin as S


def test_prefs_require_wallet():
    with pytest.raises(AssertionError):
        S.set_prefs({}, "stablecoin")
    p = S.set_prefs({}, "stablecoin", wallet="0xabc")
    assert p["rail"] == "usdc-base" and p["wallet"] == "0xabc"
    assert S.rail_for(p) == ("USDC", "Base")
    assert S.set_prefs({}, "later")["mode"] == "later"


def test_research_rail_cannot_lock():
    with pytest.raises(AssertionError):
        S.escrow_lock("hvc_1", 15.0, "usdt-tron")
    lock = S.escrow_lock("hvc_1", 15.0, "usdc-base")
    assert lock["state"] == "locked" and lock["amount"] == 15.0


def test_transparency_no_private_data():
    t = S.Transparency()
    t.record_fee(15.0, "AR")
    t.record_contribution(5.0)
    t.record_expense(2.0, "r2")
    pub = t.public()
    assert pub["aggregate_narration_fees_usd"] == 15.0
    assert pub["platform_commissions_usd"] == 0.0
    assert pub["supported_countries"] == ["AR"]
    assert "nar_" not in str(pub)
