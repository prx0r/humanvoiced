"""Launch metrics (LAUNCH.md §7): first-dollar + repeat rate.

The metrics that matter: narrators earning their first dollar within 30 days,
and creators returning. Signups and samples are vanity.
"""
from __future__ import annotations


def first_dollar_rate(narrators: list[dict], days: int = 30) -> dict:
    eligible = [n for n in narrators if (n.get("age_days", 0) >= days)]
    if not eligible:
        return {"rate": None, "n": 0}
    paid = sum(1 for n in eligible if n.get("earned_usd", 0) > 0)
    return {"rate": round(paid / len(eligible), 3), "n": len(eligible)}


def repeat_rate(creators: list[dict]) -> dict:
    if not creators:
        return {"rate": None, "n": 0}
    rep = sum(1 for c in creators if c.get("orders", 0) >= 2)
    return {"rate": round(rep / len(creators), 3), "n": len(creators)}
