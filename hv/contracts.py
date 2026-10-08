"""Immutable narration contracts — validation + lifecycle.

from_brief() builds a proposed contract from an agent brief.
accept() freezes terms (server timestamp, deadline from acceptance).
No silent overwrites: post-acceptance changes are amendments (new version).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from hv.util import sha256, uid

STATUSES = ("proposed", "offered", "accepted", "submitted", "in_correction",
            "delivered", "disputed", "settled", "cancelled", "reassigned")

# Launch policy v0.1 (TECH-SPEC §8.5): offer expiry window minutes.
OFFER_EXPIRY_MINUTES = (5, 15)
REVIEW_WINDOW_SECONDS = 86400


@dataclass
class HVContract:
    contract_id: str = field(default_factory=lambda: "hvc_" + uid()[:8])
    version: int = 1
    principal_id: str = ""
    agent_id: str = ""
    narrator_id: str = ""
    script_sha256: str = ""
    brief_sha256: str = ""
    terms_version: str = "2026-10-01"
    payout_usd: float = 0.0
    funding_status: str = "pending"
    delivery_seconds: int = 7200
    deliverable_format: str = "wav"
    deliverable_sample_rate: int = 48000
    deliverable_channels: int = 1
    included_corrections: int = 1
    review_window_seconds: int = REVIEW_WINDOW_SECONDS
    commercial_usage: str = "online_video"
    voice_cloning_allowed: bool = False
    status: str = "proposed"
    accepted_at: str = ""
    deadline_at: str = ""

    def validate(self) -> list[str]:
        errs = []
        if not self.principal_id:
            errs.append("principal_id required (agents are not counterparties)")
        if not self.agent_id:
            errs.append("agent_id required")
        if self.payout_usd <= 0:
            errs.append("payout_usd must be positive")
        if self.delivery_seconds < 60:
            errs.append("delivery_seconds minimum 60")
        if self.deliverable_format != "wav":
            errs.append("deliverable.format must be wav")
        if self.deliverable_sample_rate not in (44100, 48000):
            errs.append("sample_rate must be 44100/48000")
        if self.status not in STATUSES:
            errs.append(f"unknown status {self.status}")
        return errs

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in (
            "contract_id", "version", "principal_id", "agent_id", "narrator_id",
            "script_sha256", "brief_sha256", "terms_version", "payout_usd",
            "funding_status", "delivery_seconds", "deliverable_format",
            "deliverable_sample_rate", "deliverable_channels",
            "included_corrections", "review_window_seconds", "commercial_usage",
            "voice_cloning_allowed", "status", "accepted_at", "deadline_at")}


def from_brief(brief: dict, script_text: str, principal_id: str, agent_id: str) -> HVContract:
    return HVContract(
        principal_id=principal_id,
        agent_id=agent_id,
        script_sha256=sha256(script_text),
        brief_sha256=sha256(str(sorted(brief.items()))),
        payout_usd=float(brief.get("payout_usd", 0)),
        delivery_seconds=int(brief.get("delivery_seconds", 7200)),
        commercial_usage=brief.get("commercial_usage", "online_video"),
        voice_cloning_allowed=False,
        status="proposed",
    )


def accept(contract: HVContract, narrator_id: str, funded: bool,
           now: datetime | None = None) -> HVContract:
    """Freeze terms at acceptance. Funding must already be secured."""
    if not funded:
        raise ValueError("cannot accept: funding not secured")
    if contract.status not in ("proposed", "offered"):
        raise ValueError(f"cannot accept from status {contract.status}")
    now = now or datetime.now(timezone.utc)
    contract.narrator_id = narrator_id
    contract.accepted_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    contract.deadline_at = (now + timedelta(seconds=contract.delivery_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract.funding_status = "secured"
    contract.status = "accepted"
    return contract


def amend(contract: HVContract, changes: dict) -> HVContract:
    """Post-acceptance change = new version, back to proposed. Never overwrite."""
    if contract.status == "accepted":
        nxt = HVContract(**{**contract.to_dict(), "version": contract.version + 1,
                             "status": "proposed", "accepted_at": "", "deadline_at": ""})
        for k, v in changes.items():
            if hasattr(nxt, k):
                setattr(nxt, k, v)
        return nxt
    for k, v in changes.items():
        if hasattr(contract, k):
            setattr(contract, k, v)
    return contract
