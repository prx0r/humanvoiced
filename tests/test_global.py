"""Global tests: coverage gating, FX display, payout batching."""
import sys
sys.path.insert(0, ".")

from hv import globalx as G


def test_discoverable_not_bookable():
    ok, why = G.bookable_in("KH")
    assert ok is False and "KH" in why
    assert G.coverage_for("KH")["public_discovery"] is True
    assert G.bookable_in("GB")[0] is True
    assert G.bookable_in("XX")[0] is False


def test_usd_reference_display():
    assert G.display_price(15, "KHR") == {"usd": 15, "currency": "KHR", "local": 61500.0}
    assert G.display_price(15, "ZZZ")["currency"] == "USD"


def test_combined_payouts():
    assert G.combine_payouts([100, 100], 500) == {"releasable": False, "held_minor": 200,
                                                 "minimum_minor": 500}
    assert G.combine_payouts([300, 300], 500)["releasable"] is True
