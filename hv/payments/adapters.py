"""Rail adapters: honest capabilities, production gates closed by default."""
from __future__ import annotations


class Base:
    name = "base"
    asset = ""
    network = ""

    def capabilities(self) -> dict:
        raise NotImplementedError

    def create_intent(self, contract: dict) -> dict:
        raise NotImplementedError


class StellarEscrow(Base):
    """Trustless Work V1 shape (Stellar USDC, milestones, resolver).
    Testnet only until stuck-fund/audit/legal checks pass."""
    name = "stellar_usdc_trustless_work_v1"
    asset = "USDC"
    network = "stellar"

    def capabilities(self) -> dict:
        return {"rail": self.name, "asset": self.asset, "network": self.network,
                "supports_protected_funding": True, "supports_milestones": True,
                "supports_refund": True, "supports_dispute_resolution": True,
                "supports_unilateral_platform_release": False,
                "production_enabled": False}

    def create_intent(self, contract: dict) -> dict:
        return {"rail": self.name, "contract_id": contract["contract_id"],
                "amount_usdc": contract["payout_usd"], "state": "testnet_intent"}


class X402Base(Base):
    """x402 V2 USDC payment adapter. Direct settlement only — NOT escrow."""
    name = "x402_base_usdc"
    asset = "USDC"
    network = "base"

    def capabilities(self) -> dict:
        return {"rail": self.name, "asset": self.asset, "network": self.network,
                "supports_protected_funding": False, "supports_milestones": False,
                "supports_refund": True, "supports_dispute_resolution": False,
                "supports_unilateral_platform_release": False,
                "production_enabled": False}

    def create_intent(self, contract: dict) -> dict:
        return {"rail": self.name, "contract_id": contract["contract_id"],
                "amount_usdc": contract["payout_usd"], "state": "direct_payment"}


class StripeConnect(Base):
    name = "stripe_connect"
    asset = "USD"
    network = "stripe"

    def capabilities(self) -> dict:
        return {"rail": self.name, "asset": self.asset, "network": self.network,
                "supports_protected_funding": True, "supports_milestones": False,
                "supports_refund": True, "supports_dispute_resolution": False,
                "supports_unilateral_platform_release": False,
                "production_enabled": False,
                "note": "eligibility-gated; US-platform stablecoin limits apply"}

    def create_intent(self, contract: dict) -> dict:
        return {"rail": self.name, "contract_id": contract["contract_id"],
                "amount_usd": contract["payout_usd"], "state": "test_intent"}


class Simulated(Base):
    name = "simulated"
    asset = "USD"
    network = "test"

    def capabilities(self) -> dict:
        return {"rail": self.name, "asset": self.asset, "network": self.network,
                "supports_protected_funding": False, "supports_milestones": False,
                "supports_refund": True, "supports_dispute_resolution": False,
                "supports_unilateral_platform_release": False,
                "production_enabled": False, "test_only": True}

    def create_intent(self, contract: dict) -> dict:
        return {"rail": self.name, "contract_id": contract["contract_id"],
                "state": "test_intent"}
