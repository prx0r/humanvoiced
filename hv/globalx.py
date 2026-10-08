"""Global layer: payout coverage registry, multilingual samples, display FX.

Discoverable everywhere; bookable only where a verified payout route exists.
The API must refuse money before acceptance when no route is verified —
never silently fail after the worker records.
"""
from __future__ import annotations

# Illustrative registry shape; production rows need provider verification.
COVERAGE = {
    "GB": {"profile_creation": True, "public_discovery": True,
           "paid_bookings": True, "supported_payouts": ["bank", "stripe"],
           "crypto_payouts": "verified", "minimum_payout_usd": 5.0},
    "KH": {"profile_creation": True, "public_discovery": True,
           "paid_bookings": "pending_provider_verification",
           "supported_payouts": [], "crypto_payouts": "requires_local_review",
           "minimum_payout_usd": None},
}

# Indicative USD→local display rates (quotes always bind in USD first).
FX = {"USD": 1.0, "GBP": 0.79, "EUR": 0.92, "KHR": 4100.0, "INR": 83.0, "PHP": 58.0}


def coverage_for(country_code: str) -> dict:
    c = COVERAGE.get((country_code or "").upper())
    if not c:
        return {"profile_creation": True, "public_discovery": True,
                "paid_bookings": "pending_provider_verification",
                "supported_payouts": [], "crypto_payouts": "requires_local_review",
                "minimum_payout_usd": None}
    return c


def bookable_in(country_code: str) -> tuple[bool, str]:
    c = coverage_for(country_code)
    if c["paid_bookings"] is True:
        return True, "ok"
    return False, f"payouts not yet verified for {country_code or '?'} — profile stays discoverable"


def display_price(usd: float, currency: str) -> dict:
    rate = FX.get((currency or "USD").upper())
    if not rate:
        return {"usd": usd, "currency": "USD", "local": usd}
    return {"usd": usd, "currency": currency.upper(), "local": round(usd * rate, 2)}


def combine_payouts(amounts_minor: list[int], minimum_minor: int) -> dict:
    """Batch micro-earnings into one viable withdrawal."""
    total = sum(amounts_minor)
    if total < minimum_minor:
        return {"releasable": False, "held_minor": total, "minimum_minor": minimum_minor}
    return {"releasable": True, "amount_minor": total, "jobs": len(amounts_minor)}
