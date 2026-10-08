"""Pricing engine — fitted curve + heat tiers, zero commission.

Customer curve P(t) = 1.5362 + 1.6503*t^0.71 (t in finished-audio minutes):
15s→$2.15 · 1m→$3.19 · 5m→$6.71 · 10m→$10 · 20m→$15.38 · 30m→$20 · 60m→$31.74.

Single checkout minimum $3.50 (batched clips keep unit price).
Narrator receives 100% of the customer price (0% platform commission;
processor/escrow costs are a platform expense, donations separate).
Minimum narrator payout $2.25. Duration derives from frozen script word
count at agreed pace — never from narrator speed.
Tier multipliers: standard 1.0×, proven 1.3×, specialist 1.8×, priority 1.5×.
"""
from __future__ import annotations

BASE = 1.0
CHECKOUT_MIN = 3.50
NARRATOR_SHARE = 1.0
NARRATOR_MIN_PAYOUT = 2.25
WORDS_PER_MINUTE = 150

# Buyer-paid service fee (HumanVoiced revenue, NOT commission).
# The narrator always receives 100% of narrator_payout; the buyer pays
# payout + fee, disclosed as separate lines. Flat $1 keeps short-form
# viable (a $5 fee would exceed a short's entire payout); volume and
# studio upgrades carry the economics, not the fee. Illustrative.
SERVICE_FEE_USD = 1.00

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
    """Narration quote. Single orders floor the payout at $3.50; batched
    clips keep unit price. Buyer total adds the service fee on a separate
    line — narrator payout is never reduced by it."""
    unit = round(curve(t_minutes) * TIERS.get(tier, 1.0), 2)
    total = unit if batched else max(CHECKOUT_MIN, unit)
    payout = round(max(NARRATOR_MIN_PAYOUT, total * NARRATOR_SHARE), 2)
    return {"customer_price": round(total + SERVICE_FEE_USD, 2),
            "narrator_payout": payout,
            "service_fee_usd": SERVICE_FEE_USD, "tier": tier, "batched": batched}


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


# Studio processing revenue (HumanVoiced service lines, NOT commission).
# Basic pack is included in the marketplace service ($0). Studio upgrades
# are disclosed as a separate buyer-paid fee and NEVER deducted from the
# narrator's agreed payout. Prices illustrative, not validated.
PROCESSING = {
    "basic_pack_usd": 0.0,
    "studio_upgrade_usd": 3.00,
}


def processing_quote(tier: str = "basic") -> dict:
    """Separate service-line quote. Narrator payout is untouched by design."""
    if tier == "studio":
        return {"tier": "studio",
                "processing_fee_usd": PROCESSING["studio_upgrade_usd"],
                "narrator_payout_change_usd": 0.0,
                "note": "HumanVoiced service, billed separately from narration"}
    return {"tier": "basic", "processing_fee_usd": 0.0,
            "narrator_payout_change_usd": 0.0,
            "note": "included in the marketplace service"}
