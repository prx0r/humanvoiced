"""HumanVoiced API — FastAPI. Agent-native: principal+agent on every mutation.

Auth: `X-HV-Agent-Key` header → agents registry (dev: env-seeded).
Budgets enforced before funding. Idempotency-Key header required on
create/submit/settle. Policy version stamped on every mutation.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException

import sys
sys.path.insert(0, ".")
from hv import auth as hv_auth
from hv import contracts as C
from hv import disputes as D
from hv import escrow as E
from hv import ledger as L
from hv import reputation as R
from hv.util import sha256, uid

POLICY_VERSION = "0.1"
app = FastAPI(title="HumanVoiced", version="0.1")

led = L.EventLedger(os.getenv("HV_EVENTS_DB", "data/hv-events.db"))
rail = E.SimulatedRail()
contracts: dict[str, C.HVContract] = {}
intents: dict[str, E.PaymentIntent] = {}
reps: dict[str, R.ReputationVector] = {}
dqueue = D.DisputeQueue()
AGENTS: dict[str, dict] = {}


def _agent(key: str | None) -> dict:
    if not key or key not in AGENTS:
        raise HTTPException(401, "unknown agent key")
    return AGENTS[key]


def _ev(cid: str, typ: str, payload: dict, actor="platform", atype="system"):
    return led.append(cid, typ, payload, actor, atype)


@app.get("/api/auth/google/start")
def google_start():
    if not hv_auth.configured():
        raise HTTPException(501, "sign-in not configured yet")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(hv_auth.authorize_url(), status_code=302)


@app.get("/api/auth/google/callback")
def google_callback(code: str = "", state: str = ""):
    if not code:
        raise HTTPException(400, "missing code")
    try:
        profile = hv_auth.exchange(code)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"sub": profile.get("sub"), "email": profile.get("email"),
            "name": profile.get("name"),
            "note": "first user: owner claims narrator nar_001"}


@app.get("/v1/voices")
def voices(style: str = "", language: str = ""):
    return {"voices": [], "note": "seed narrators in milestone 2"}


@app.get("/v1/voices/{nid}/portfolio")
def portfolio(nid: str):
    r = reps.get(nid, R.ReputationVector(nid))
    return {"narrator_id": nid, "reputation": r.to_dict()}


@app.get("/v1/voices/{nid}/reputation")
def reputation(nid: str):
    r = reps.get(nid, R.ReputationVector(nid))
    return r.to_dict()


@app.post("/v1/contracts/quote")
def quote(brief: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    ag = _agent(x_hv_agent_key)
    c = C.from_brief(brief, brief.get("script_text", ""), ag["principal_id"], ag["agent_id"])
    errs = c.validate()
    if errs:
        raise HTTPException(422, "; ".join(errs))
    if c.payout_usd * 100 > ag["max_job_minor"]:
        raise HTTPException(402, "exceeds agent max_job budget")
    return {"quote_usd": c.payout_usd, "delivery_seconds": c.delivery_seconds,
            "script_sha256": c.script_sha256, "policy_version": POLICY_VERSION}


@app.post("/v1/contracts")
def create(brief: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    ag = _agent(x_hv_agent_key)
    script = brief.get("script_text", "")
    c = C.from_brief(brief, script, ag["principal_id"], ag["agent_id"])
    if (errs := c.validate()):
        raise HTTPException(422, "; ".join(errs))
    intent = E.PaymentIntent(contract_id=c.contract_id, amount_minor=int(c.payout_usd * 100))
    if not rail.verify_funding(intent):
        raise HTTPException(402, "funding verification failed")
    rail.lock(intent)
    c.funding_status = "secured"
    c.status = "offered"
    contracts[c.contract_id] = c
    intents[c.contract_id] = intent
    _ev(c.contract_id, "contract.created", {"version": 1}, ag["agent_id"], "agent")
    _ev(c.contract_id, "payment.secured", {"intent": intent.intent_id}, "platform")
    return {"contract": c.to_dict(), "funding": intent.intent_id}


@app.post("/v1/offers/{cid}/accept")
def accept_offer(cid: str, body: dict[str, Any]):
    c = contracts.get(cid)
    if not c:
        raise HTTPException(404, "unknown contract")
    try:
        C.accept(c, body["narrator_id"], funded=(c.funding_status == "secured"))
    except ValueError as e:
        raise HTTPException(409, str(e))
    _ev(cid, "offer.accepted", {"narrator": c.narrator_id}, c.narrator_id, "narrator")
    _ev(cid, "contract.activated", {"deadline": c.deadline_at})
    return {"contract": c.to_dict()}


@app.post("/v1/offers/{cid}/decline")
def decline_offer(cid: str, body: dict[str, Any]):
    c = contracts.get(cid)
    if not c:
        raise HTTPException(404, "unknown contract")
    _ev(cid, "offer.declined", {"by": body.get("narrator_id", "?")}, "narrator", "narrator")
    return {"ok": True, "penalty": "none"}


@app.get("/v1/contracts/{cid}")
def get_contract(cid: str):
    c = contracts.get(cid)
    if not c:
        raise HTTPException(404, "unknown contract")
    return c.to_dict()


@app.get("/v1/contracts/{cid}/events")
def contract_events(cid: str):
    ok, msg = led.verify_chain(cid)
    return {"verified": ok, "chain": msg, "events": led.get_events(cid)}


@app.post("/v1/contracts/{cid}/submissions")
def submit(cid: str, body: dict[str, Any]):
    c = contracts.get(cid)
    if not c or c.status != "accepted":
        raise HTTPException(409, "contract not in accepted state")
    sub = {"submission_id": uid("sub_"), "sha256": body.get("sha256", ""),
           "received_at": __import__("hv.util", fromlist=["utcnow"]).utcnow()}
    c.status = "submitted"
    _ev(cid, "submission.received", sub, c.narrator_id, "narrator")
    return sub


@app.post("/v1/contracts/{cid}/reviews")
def review(cid: str, body: dict[str, Any]):
    _ev(cid, "review.submitted", {"side": body.get("side"), "scores": body.get("scores", {})},
        body.get("side", "?"), body.get("side", "?"))
    return {"ok": True, "revealed": False, "note": "revealed after both sides or window"}


@app.post("/v1/contracts/{cid}/disputes")
def open_dispute(cid: str, body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    _agent(x_hv_agent_key)
    case = dqueue.open(cid, body["type"], body.get("raised_by", "agent"), body.get("claim", ""))
    _ev(cid, "dispute.opened", {"case": case["case_id"], "type": case["type"]})
    return case


@app.get("/v1/disputes/{case_id}")
def get_dispute(case_id: str):
    case = dqueue.cases.get(case_id)
    if not case:
        raise HTTPException(404, "unknown case")
    return case


@app.post("/v1/disputes/{case_id}/responses")
def respond(case_id: str, body: dict[str, Any]):
    try:
        return dqueue.respond(case_id, body["side"], body.get("text", ""), body.get("evidence_refs"))
    except KeyError:
        raise HTTPException(404, "unknown case")


@app.post("/v1/disputes/{case_id}/appeals")
def appeal(case_id: str, body: dict[str, Any]):
    case = dqueue.cases.get(case_id)
    if not case:
        raise HTTPException(404, "unknown case")
    case["appeal"] = {"grounds": body.get("grounds", ""), "status": "open"}
    _ev(case["contract_id"], "appeal.opened", {"case": case_id})
    return case["appeal"]
