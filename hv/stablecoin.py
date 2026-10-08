"""Stablecoin payout rails + preferences + transparency ledger.

USDC-on-Base primary, Solana USDC second, TRON USDT research-only.
Recipient chooses exact token+network. No silent swaps. Noncustodial
posture: platform never holds private keys; conditional locks live in
audited escrow contracts (prototype stage: simulated).
"""
from __future__ import annotations

RAILS = {
    "usdc-base": {"asset": "USDC", "network": "Base", "status": "primary",
                  "min_payout_usd": 5.0},
    "usdc-solana": {"asset": "USDC", "network": "Solana", "status": "candidate",
                    "min_payout_usd": 5.0},
    "usdt-tron": {"asset": "USDT", "network": "TRON", "status": "research",
                  "min_payout_usd": 10.0},
}
PREFS = ("later", "stablecoin", "local_currency")


def set_prefs(narrator_doc: dict, pref: str, wallet: str = "", currency: str = "") -> dict:
    assert pref in PREFS, f"unknown payout preference {pref}"
    if pref == "stablecoin":
        assert wallet, "wallet required for stablecoin payouts"
        rail = next((r for r in RAILS if RAILS[r]["status"] != "research"), "usdc-base")
    else:
        rail = ""
    narrator_doc["payout_pref"] = {"mode": pref, "wallet": wallet,
                                   "currency": currency, "rail": rail}
    return narrator_doc["payout_pref"]


def rail_for(pref: dict) -> tuple[str, str]:
    """Resolve (asset, network) from an explicit narrator choice."""
    rail = RAILS.get(pref.get("rail", ""), RAILS["usdc-base"])
    return rail["asset"], rail["network"]


def escrow_lock(contract_id: str, amount_usdc: float, rail: str = "usdc-base") -> dict:
    assert RAILS[rail]["status"] != "research", "research rails cannot lock funds"
    assert amount_usdc > 0
    return {"contract_id": contract_id, "amount": amount_usdc,
            "asset": RAILS[rail]["asset"], "network": RAILS[rail]["network"],
            "state": "locked", "double_spend_guard": f"{contract_id}:{rail}"}


class Transparency:
    """Public aggregates only. Never per-worker private data."""
    def __init__(self):
        self.fees = 0.0
        self.commissions = 0.0
        self.contributions = 0.0
        self.expenses = 0.0
        self.countries = set()

    def record_fee(self, amount_usd: float, country: str):
        self.fees += amount_usd
        self.countries.add(country)

    def record_contribution(self, amount_usd: float):
        self.contributions += amount_usd

    def record_expense(self, amount_usd: float, label: str):
        self.expenses += amount_usd

    def public(self) -> dict:
        return {"aggregate_narration_fees_usd": round(self.fees, 2),
                "platform_commissions_usd": round(self.commissions, 2),
                "voluntary_contributions_usd": round(self.contributions, 2),
                "operating_expenses_usd": round(self.expenses, 2),
                "supported_countries": sorted(self.countries)}
