"""Launch-metric + pilot-pricing tests."""
import sys
sys.path.insert(0, ".")

from hv import growth as G
from hv import pricing as P


def test_pilot_split():
    s = P.pilot_split()
    assert s == {"creator_price": 11.0, "narrator_payout": 11.0, "platform_share": 0.0}


def test_effort_guard():
    assert P.effort_guard_ok(30) is True
    assert P.effort_guard_ok(60) is False


def test_first_dollar_and_repeat():
    narr = [{"age_days": 40, "earned_usd": 8}, {"age_days": 40, "earned_usd": 0},
            {"age_days": 5, "earned_usd": 0}]
    assert G.first_dollar_rate(narr) == {"rate": 0.5, "n": 2}
    assert G.repeat_rate([{"orders": 3}, {"orders": 1}]) == {"rate": 0.5, "n": 2}
    assert G.repeat_rate([]) == {"rate": None, "n": 0}
