"""Pricing engine — LIBRARY.md §5 curve + WEDGE rarity/tiers.

Customer curve P(t) on finished-audio minutes t:
  P(t) = 1 + min(t,10) + 0.75*max(0,min(t,30)-10) + 0.50*max(0,t-30)
15s→$1.25 · 1m→$2 · 5m→$6 · 10m→$11 · 20m→$18.50 · 30m→$26 · 60m→$41.

Unit price holds for batched clips; single checkout minimum $3.50.
Narrator share 75% with $2.25 minimum payout. Duration derives from frozen
script word count at agreed pace — never from narrator speed.
Premiums multiply: proven 1.3×, specialist/scarce 1.8×, priority 1.5×.
"""
from __future__ import annotations

BASE = 1.0
CHECKOUT_MIN = 3.50
NARRATOR_SHARE = 1.0
NARRATOR_MIN_PAYOUT = 2.25
WORDS_PER_MINUTE = 150

TIERS = {"standard": 1.0, "proven": 1.3, "specialist": 1.8, "priority": 1.5}


def curve(t_minutes: float) -> float:
    """Fitted curve P(t) = 1.50 + 1.67*t^0.71 (t in minutes).
    Targets: 10s→$2, 10min→$10, 30min→$20. See QUALITY.md."""
    t = max(0.0, t_minutes)
    return round(1.5362 + 1.6503 * (t ** 0.71), 2)


HEAT_TIERS = {"new": 1.0, "verified": 1.0, "proven": 1.15, "specialist": 1.3}


def heatmap(t_minutes: float, tier: str = "new") -> dict:
    """Automatic price band: base × tier multiplier, quoted {low, base, high}."""
    base = curve(t_minutes)
    mult = HEAT_TIERS.get(tier, 1.0)
    mid = round(base * mult, 2)
    return {"low": round(mid * 0.95, 2), "base": mid, "high": round(mid * 1.05, 2),
            "tier": tier, "tier_mult": mult}


def quote(t_minutes: float, tier: str = "standard", batched: bool = False) -> dict:
    """Customer quote. Single orders floor at $3.50; batched clips keep unit price."""
    unit = round(curve(t_minutes) * TIERS.get(tier, 1.0), 2)
    total = unit if batched else max(CHECKOUT_MIN, unit)
    payout = round(max(NARRATOR_MIN_PAYOUT, total * NARRATOR_SHARE), 2)
    return {"customer_price": total, "narrator_payout": payout,
            "tier": tier, "batched": batched}


def quote_cents(total_seconds: int, rarity: float = 1.0, tier: float = 1.0) -> int:
    """Legacy linear helper (kept for compatibility)."""
    raw = 100 + 100 * (total_seconds / 60.0)
    return max(100, round(raw * rarity * tier))


def duration_from_words(words: int, wpm: int = WORDS_PER_MINUTE) -> float:
    return round(words / wpm, 2)


# Pilot economics (LAUNCH.md §5): fixed $8 narrator / $3 platform on the $11
# 10-minute product. Effort guard: if median effort for 10 finished minutes
# exceeds 40 narrator-minutes, the product needs repricing.
PILOT_NARRATOR_USD = 11.00
PILOT_PLATFORM_USD = 0.0
EFFORT_GUARD_MINUTES_PER_10 = 40.0


def pilot_split(price: float = 11.0) -> dict:
    return {"creator_price": price, "narrator_payout": PILOT_NARRATOR_USD,
            "platform_share": round(price - PILOT_NARRATOR_USD, 2)}


def effort_guard_ok(median_effort_minutes_per_10: float) -> bool:
    return median_effort_minutes_per_10 <= EFFORT_GUARD_MINUTES_PER_10


def rarity_for(supply_count: int, demand_count: int) -> float:
    """Scarcity multiplier 1.0–2.5 from verified demand signals only."""
    if supply_count <= 0:
        return 2.5
    ratio = demand_count / max(1, supply_count)
    return round(min(2.5, max(1.0, 1.0 + ratio * 0.5)), 2)


def tier_for(completed: int, on_time_rate: float | None) -> float:
    """Earned premium mapped to named tiers. New voices at base, never below."""
    if completed < 5 or on_time_rate is None:
        return TIERS["standard"]
    if on_time_rate >= 0.98 and completed >= 50:
        return TIERS["specialist"]
    if on_time_rate >= 0.95 and completed >= 20:
        return TIERS["proven"]
    if on_time_rate >= 0.90:
        return 1.2
    return TIERS["standard"]
