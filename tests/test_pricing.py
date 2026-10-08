"""Pricing tests: fitted curve, checkout floor, payout share."""
import sys
sys.path.insert(0, ".")

from hv import pricing as P


def test_fitted_curve_table():
    assert P.curve(10 / 60) == 2.0
    assert P.curve(0.25) == 2.15
    assert P.curve(1) == 3.19
    assert P.curve(5) == 6.71
    assert P.curve(10) == 10.0
    assert P.curve(20) == 15.38
    assert P.curve(30) == 20.0
    assert P.curve(60) == 31.74


def test_checkout_floor_and_batch():
    assert P.quote(0.25)["customer_price"] == 3.50
    assert P.quote(0.25, batched=True)["customer_price"] == 2.15
    q = P.quote(10)
    assert q["customer_price"] == 10.0 and q["narrator_payout"] == 7.5


def test_duration_from_words():
    assert P.duration_from_words(1500) == 10.0


def test_new_voice_never_penalised():
    assert P.tier_for(0, None) == 1.0
    assert P.tier_for(2, 1.0) == 1.0
    assert P.tier_for(200, 0.99) == 1.8


def test_rarity_caps():
    assert P.rarity_for(0, 10) == 2.5
    assert P.rarity_for(100, 1) == 1.0
