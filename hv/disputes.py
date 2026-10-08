"""Dispute queue: case management before AI arbitration.

Agents gather evidence, cite clauses, recommend. They never seize funds or
issue sanctions. Settlement needs a signed instruction + closed appeal window.
"""
from __future__ import annotations

from hv.util import uid, utcnow

TYPES = ("non_delivery", "wrong_script", "clipping_noise", "wrong_voice",
         "style_dispute", "scope_change", "platform_outage", "synthetic",
         "unfair_review", "payment")

OUTCOMES = ("full_payout", "correction", "partial_payment", "refund",
            "reassign", "no_fault_extend", "sanction_review")


class DisputeQueue:
    def __init__(self):
        self.cases: dict[str, dict] = {}

    def open(self, contract_id: str, dtype: str, raised_by: str, claim: str) -> dict:
        assert dtype in TYPES, f"unknown dispute type {dtype}"
        case = {"case_id": uid("dsp_"), "contract_id": contract_id, "type": dtype,
                "raised_by": raised_by, "claim": claim, "status": "open",
                "responses": [], "decision": None, "appeal": None,
                "opened_at": utcnow()}
        self.cases[case["case_id"]] = case
        return case

    def respond(self, case_id: str, side: str, text: str, evidence_refs: list | None = None) -> dict:
        case = self.cases[case_id]
        case["responses"].append({"side": side, "text": text,
                                  "evidence_refs": evidence_refs or [], "at": utcnow()})
        return case

    def decide(self, case_id: str, outcome: str, worker_share_bps: int,
               buyer_share_bps: int, evidence_root: str, policy_version: str,
               decided_by: str = "human_reviewer") -> dict:
        assert outcome in OUTCOMES, f"unknown outcome {outcome}"
        assert worker_share_bps + buyer_share_bps == 10000, "shares must total 10000bps"
        case = self.cases[case_id]
        case["decision"] = {"outcome": outcome, "worker_share_bps": worker_share_bps,
                            "buyer_share_bps": buyer_share_bps, "evidence_root": evidence_root,
                            "policy_version": policy_version, "decided_by": decided_by,
                            "appeal_status": "open", "settlement_authorised": False,
                            "decided_at": utcnow()}
        case["status"] = "decided"
        return case

    def close_appeal_window(self, case_id: str) -> dict:
        case = self.cases[case_id]
        d = case.get("decision") or {}
        d["appeal_status"] = "closed"
        d["settlement_authorised"] = True
        case["status"] = "resolved"
        return case
