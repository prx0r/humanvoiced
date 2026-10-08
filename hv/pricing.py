"""Pricing engine: $1 base + $1 per finished minute, prorated per second.

15s → $1.25 · 10min → $11.00 · 1hr → $61.00 (before modifiers).
Modifiers: length discount (volume), rarity multiplier (supply scarcity),
narrator tier (earned premium, never a new-voice penalty).
Minor units (cents) internally. Quotes bind (contract_id, version, expiry).
"""
from __future__ import annotations

BASE_CENTS = 100
PER_MINUTE_CENTS = 100


def length_discount(total_seconds: int) -> float:
    if total_seconds > 3600:
        return 0.75
    if total_seconds > 1800:
        return 0.80
    if total_seconds > 600:
        return 0.90
    return 1.0


def quote_cents(total_seconds: int, rarity: float = 1.0, tier: float = 1.0) -> int:
    raw = BASE_CENTS + PER_MINUTE_CENTS * (total_seconds / 60.0)
    return max(100, round(raw * length_discount(total_seconds) * rarity * tier))


def rarity_for(supply_count: int, demand_count: int) -> float:
    """Scarcity multiplier 1.0–2.5 from supply/demand. Rare accents price high."""
    if supply_count <= 0:
        return 2.5
    ratio = demand_count / max(1, supply_count)
    return round(min(2.5, max(1.0, 1.0 + ratio * 0.5)), 2)


def tier_for(completed: int, on_time_rate: float | None) -> float:
    """Earned premium. New voices price at base (1.0) — never discounted."""
    if completed < 5 or on_time_rate is None:
        return 1.0
    if on_time_rate >= 0.98 and completed >= 50:
        return 2.0
    if on_time_rate >= 0.95 and completed >= 20:
        return 1.5
    if on_time_rate >= 0.90:
        return 1.2
    return 1.0
