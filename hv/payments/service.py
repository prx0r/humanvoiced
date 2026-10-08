"""Payment orchestration: one contract system, capability-aware rails."""
from __future__ import annotations

from hv.payments import quotes as Q


class PaymentService:
    def __init__(self, store):
        self.store = store
        self.adapters = {}

    def register(self, adapter):
        self.adapters[adapter.name] = adapter

    def methods(self) -> list[dict]:
        return [a.capabilities() for a in self.adapters.values()]

    def quote(self, contract: dict, rail_name: str) -> dict:
        ad = self.adapters[rail_name]
        caps = ad.capabilities()
        return {"rail": rail_name, "asset": caps["asset"], "network": caps["network"],
                **Q.fee_breakdown(contract["payout_usd"])}

    def fund(self, contract: dict, rail_name: str) -> dict:
        ad = self.adapters[rail_name]
        if not ad.capabilities().get("supports_protected_funding"):
            raise ValueError(f"{rail_name} cannot protected-fund; refusing escrow claim")
        return ad.create_intent(contract)
