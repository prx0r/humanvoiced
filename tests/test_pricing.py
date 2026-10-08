"""Pricing tests: the wedge economics must hold."""
import sys
sys.path.insert(0, ".")

from hv import pricing as P


def test_wedge_numbers():
    assert P.quote_cents(15) == 125
    assert P.quote_cents(600) == 1100
    assert P.quote_cents(3600) == 4880  # 6100 raw × 0.8 long-form discount


def test_hour_in_band():
    common = P.quote_cents(3600, rarity=1.0, tier=1.0)
    rare = P.quote_cents(3600, rarity=2.0, tier=1.0)
    assert 3000 <= common <= 10000
    assert 3000 <= rare <= 12200


def test_new_voice_never_penalised():
    assert P.tier_for(0, None) == 1.0
    assert P.tier_for(2, 1.0) == 1.0
    assert P.tier_for(200, 0.99) == 2.0


def test_rarity_caps():
    assert P.rarity_for(0, 10) == 2.5
    assert P.rarity_for(100, 1) == 1.0
