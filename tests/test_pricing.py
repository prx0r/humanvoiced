"""Pricing tests: LIBRARY.md §5 curve, checkout floor, payout share."""
import sys
sys.path.insert(0, ".")

from hv import pricing as P


def test_curve_table():
    assert P.curve(0.25) == 1.25
    assert P.curve(1) == 2.0
    assert P.curve(5) == 6.0
    assert P.curve(10) == 11.0
    assert P.curve(20) == 18.5
    assert P.curve(30) == 26.0
    assert P.curve(60) == 41.0


def test_checkout_floor_and_batch():
    assert P.quote(0.25)["customer_price"] == 3.50
    assert P.quote(0.25, batched=True)["customer_price"] == 1.25
    assert P.quote(10) == {"customer_price": 11.0, "narrator_payout": 8.25,
                           "tier": "standard", "batched": False}


def test_duration_from_words():
    assert P.duration_from_words(1500) == 10.0


def test_new_voice_never_penalised():
    assert P.tier_for(0, None) == 1.0
    assert P.tier_for(2, 1.0) == 1.0
    assert P.tier_for(200, 0.99) == 1.8


def test_rarity_caps():
    assert P.rarity_for(0, 10) == 2.5
    assert P.rarity_for(100, 1) == 1.0
