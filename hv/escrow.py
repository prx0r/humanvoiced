"""Funded-contract payment machine: rails move, escrow protects, disputes judge.

Rail interface (all nine, honest capabilities): quote, createFundingRequest,
verifyFunding, lock, getBalance, release, refund, split, getTransactions.
Invariant: payment_confirmed != funds_escrowed.
Integer minor units only. Idempotency keys on every settlement instruction.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from hv.util import sha256, uid


@dataclass
class PaymentIntent:
    intent_id: str = field(default_factory=lambda: "pi_" + uid())
    contract_id: str = ""
    rail: str = "simulated"
    asset: str = "USD"
    amount_minor: int = 0
    recipient: str = ""
    expires_at: str = ""
    idempotency_key: str = field(default_factory=uid)
    state: str = "quoted"  # quoted → funded → locked → released|refunded|split


class Rail:
    name = "base"
    supports_lock = False

    def quote(self, amount_minor: int, asset: str) -> dict:
        return {"rail": self.name, "amount_minor": amount_minor, "asset": asset}

    def verify_funding(self, intent: PaymentIntent) -> bool:
        raise NotImplementedError

    def lock(self, intent: PaymentIntent) -> dict:
        raise NotImplementedError(f"{self.name} cannot truthfully advertise lock()")

    def release(self, intent: PaymentIntent, to: str) -> dict:
        raise NotImplementedError

    def refund(self, intent: PaymentIntent) -> dict:
        raise NotImplementedError


class SimulatedRail(Rail):
    """Day-1 stand-in: ledger-backed, no real money. Capabilities honest."""
    name = "simulated"
    supports_lock = True

    def __init__(self):
        self.balances: dict[str, int] = {}
        self.locked: dict[str, int] = {}
        self.seen_keys: set[str] = set()

    def verify_funding(self, intent: PaymentIntent) -> bool:
        return intent.amount_minor > 0

    def lock(self, intent: PaymentIntent) -> dict:
        if intent.intent_id in self.locked:
            raise ValueError("already locked")
        self.locked[intent.intent_id] = intent.amount_minor
        intent.state = "locked"
        return {"locked": intent.amount_minor}

    def _settle_once(self, key: str):
        if key in self.seen_keys:
            raise ValueError("duplicate settlement instruction")
        self.seen_keys.add(key)

    def release(self, intent: PaymentIntent, to: str) -> dict:
        self._settle_once(intent.idempotency_key + ":release")
        amt = self.locked.pop(intent.intent_id, 0)
        if amt <= 0:
            raise ValueError("nothing locked")
        if amt > intent.amount_minor:
            raise ValueError("release exceeds balance")
        self.balances[to] = self.balances.get(to, 0) + amt
        intent.state = "released"
        return {"to": to, "amount_minor": amt}

    def refund(self, intent: PaymentIntent) -> dict:
        self._settle_once(intent.intent_id + ":refund")
        amt = self.locked.pop(intent.intent_id, 0)
        intent.state = "refunded"
        return {"amount_minor": amt}


class X402Rail(Rail):
    """Adapter shape for official x402 V2 (PAYMENT-SIGNATURE headers).
    Lock NOT supported by the protocol itself — escrow stays in our engine."""
    name = "x402"
    supports_lock = False

    def verify_funding(self, intent: PaymentIntent) -> bool:
        return intent.amount_minor > 0  # real adapter: verify on-chain/facilitator


class QPayRail(Rail):
    """Separate Q+Pay adapter (legacy X-PAYMENT style, NOT x402 V2).
    Non-custodial collection only — never advertises lock()."""
    name = "qpay"
    supports_lock = False

    def verify_funding(self, intent: PaymentIntent) -> bool:
        return intent.amount_minor > 0


def escrow_fingerprint(contract_id: str, intent: PaymentIntent) -> str:
    return sha256(f"{contract_id}:{intent.intent_id}:{intent.amount_minor}:{intent.asset}")
