"""HumanVoiced API — FastAPI. Agent-native: principal+agent on every mutation.

Security model:
- Narrator mutations need X-HV-Session (Google login). Identity comes from
  the session, never the body. Offers are dispatched to specific narrators;
  only an offered narrator can accept.
- Agent mutations need X-HV-Agent-Key + budget. Prices are computed
  server-side from the frozen script (words → minutes → P(t) curve).
- Simulated rails work only with HV_ALLOW_SIMULATED=1 (dev default).
  Production must set 0, which refuses simulated funding outright.
- Contract reads (terms/events) are party-only: contract narrator, contract
  agent, or platform. Reviews are blind until both sides respond.
"""
from __future__ import annotations

import datetime as _dt
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

import sys
sys.path.insert(0, ".")
from hv import auth as hv_auth
from hv import contracts as C
from hv import disputes as D
from hv import escrow as E
from hv import ledger as L
from hv import pricing as P
from hv import reputation as R
from hv import series as SE
from hv import upload as UPL
from hv.sessions import SessionStore
from hv.store import Store
from hv.util import sha256, uid
from hv.util import utcnow as utcnow_now

POLICY_VERSION = "0.1"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOW_SIMULATED = os.getenv("HV_ALLOW_SIMULATED", "1") == "1"

app = FastAPI(title="HumanVoiced", version="0.1")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://humanvoiced.com", "https://www.humanvoiced.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _cookie_session(request, call_next):
    if not request.headers.get("x-hv-session"):
        tok = request.cookies.get("hv_session")
        if tok:
            request.scope["headers"] = [(k, v) for k, v in request.scope["headers"]
                                        if k != b"x-hv-session"] + [(b"x-hv-session", tok.encode())]
    return await call_next(request)

SESS = SessionStore(os.getenv("HV_SESSIONS_DB", "data/hv-sessions.db"))
DB = Store(os.getenv("HV_DB", "data/hv.db"))
led = L.EventLedger(os.getenv("HV_EVENTS_DB", "data/hv-events.db"))
rail = E.SimulatedRail()
reps: dict[str, R.ReputationVector] = {}
dqueue = D.DisputeQueue()
AGENTS: dict[str, dict] = {}
SERIES: dict[str, dict] = {}
STORE = None


def _store():
    global STORE
    if STORE is None:
        from hv.series_store import SeriesStore
        STORE = SeriesStore(os.getenv("HV_SERIES_DB", "data/hv-series.db"))
    return STORE


def _agent(key: str | None) -> dict:
    if not key or key not in AGENTS:
        raise HTTPException(401, "unknown agent key")
    return AGENTS[key]


def _narrator(x_hv_session: str | None) -> str:
    nid = SESS.narrator_for(x_hv_session or "")
    if not nid:
        raise HTTPException(401, "narrator session required")
    return nid


def _ev(cid: str, typ: str, payload: dict, actor="platform", atype="system"):
    return led.append(cid, typ, payload, actor, atype)


def _party_only(cid: str, nid: str | None, agent_id: str | None):
    c = DB.get_contract(cid)
    if not c:
        raise HTTPException(404, "unknown contract")
    if nid and nid == c.get("narrator_id"):
        return c
    if agent_id and agent_id == c.get("agent_id"):
        return c
    raise HTTPException(403, "not a party to this contract")


def _price_for(script_text: str, tier: str = "standard") -> dict:
    minutes = max(0.25, len(script_text.split()) / 150.0)
    return {"minutes": round(minutes, 2), **P.quote(minutes, tier=tier)}


# ---------- auth ----------

@app.get("/api/auth/google/start")
def google_start():
    if not hv_auth.configured():
        raise HTTPException(501, "sign-in not configured yet")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(hv_auth.authorize_url(SESS.issue_state()), status_code=302)


@app.get("/api/auth/google/callback")
def google_callback(code: str = "", state: str = ""):
    from fastapi.responses import JSONResponse
    if not code:
        raise HTTPException(400, "missing code")
    if not SESS.consume_state(state):
        raise HTTPException(400, "bad or expired state")
    try:
        profile = hv_auth.exchange(code)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    nid = "nar_" + (profile.get("sub") or "")[-8:]
    if not DB.get_narrator(nid):
        DB.save_narrator({"id": nid, "email": profile.get("email", ""),
                          "handle": "", "languages": [], "prefs": {},
                          "samples": [], "created": utcnow_now()})
    token = SESS.create(profile.get("sub", ""), profile.get("email", ""), nid)
    resp = JSONResponse({"narrator_id": nid, "email": profile.get("email")})
    resp.set_cookie("hv_session", token, httponly=True, secure=True,
                    samesite="lax", max_age=30 * 86400, path="/",
                    domain=".humanvoiced.com")
    return resp


@app.post("/api/auth/logout")
def logout(x_hv_session: str | None = Header(None)):
    if x_hv_session:
        SESS.revoke(x_hv_session)
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("hv_session", path="/")
    return resp


# ---------- narrators / voices ----------

@app.post("/v1/narrators/me/profile")
def my_profile(body: dict[str, Any], x_hv_session: str | None = Header(None)):
    from hv import profile_draft as _pd
    nid = _narrator(x_hv_session)
    doc = DB.get_narrator(nid) or {"id": nid}
    if body.get("publish"):
        pub = _pd.publish(doc, body.get("profile", {}))
        DB.save_narrator(doc)
        _ev(nid, "profile.published", {"handle": pub.get("display_name", "")}, nid, "narrator")
        return {"published": pub}
    if body.get("draft_from_tech"):
        draft = _pd.draft_from_sample(body.get("tech", {}), body,
                                      body.get("wpm"))
        doc["profile_draft"] = draft
        DB.save_narrator(doc)
        return {"draft": draft}
    doc.update({"handle": body.get("handle", doc.get("handle", "")),
                "languages": body.get("languages", doc.get("languages", [])),
                "prefs": body.get("prefs", doc.get("prefs", {}))})
    DB.save_narrator(doc)
    _ev(nid, "profile.updated", {"handle": doc["handle"]}, nid, "narrator")
    return doc


@app.post("/v1/narrators/me/sample")
async def my_sample(request: Request, x_hv_session: str | None = Header(None)):
    nid = _narrator(x_hv_session)
    body = await request.body()
    language = request.query_params.get("language", "en")
    if len(body) > MAX_UPLOAD_BYTES or len(body) < 44 or body[:4] != b"RIFF":
        raise HTTPException(422, "send WAV bytes under 50MB")
    receipt = UPL.store_upload(body, f"sample:{nid}:{language}")
    doc = DB.get_narrator(nid) or {"id": nid}
    doc.setdefault("samples", []).append({"sha256": receipt["sha256"],
                                          "language": language})
    if language not in doc.get("languages", []):
        doc["languages"] = doc.get("languages", []) + [language]
    DB.save_narrator(doc)
    _ev(nid, "sample.recorded", {"sha256": receipt["sha256"], "language": language}, nid, "narrator")
    return {"narrator_id": nid, "sample": receipt["sha256"], "language": language}


@app.get("/v1/voices")
def voices(style: str = "", language: str = ""):
    out = []
    for n in DB.list_narrators():
        if language and language not in n.get("languages", []):
            continue
        out.append({"id": n["id"], "handle": n.get("handle", ""),
                    "languages": n.get("languages", []),
                    "samples": len(n.get("samples", []))})
    return {"voices": out}


@app.post("/v1/orders/guest")
def guest_order(body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    """Guest checkout record: no buyer account; high-entropy order credential.
    Payout shows 100% to narrator, 0% commission (processor fees are platform cost)."""
    import secrets as _s
    import sqlite3 as _sq
    ag = _agent(x_hv_agent_key)
    c = DB.get_contract(body.get("contract_id", ""))
    if not c or c.get("agent_id") != ag["agent_id"]:
        raise HTTPException(403, "unknown or foreign contract")
    oid = "ord_" + _s.token_hex(8)
    cred = _s.token_urlsafe(24)
    conn = _sq.connect(str(DB.db_path), timeout=30)
    conn.execute("INSERT INTO orders VALUES (?, ?)", (oid, __import__("json").dumps(
        {"order_id": oid, "contract_id": c["contract_id"], "credential": sha256(cred),
         "narrator_payout": c["payout_usd"], "commission": 0.0})))
    conn.commit()
    conn.close()
    _ev(c["contract_id"], "order.created", {"order_id": oid}, ag["agent_id"], "agent")
    return {"order_id": oid, "url": f"https://humanvoiced.com/orders/{oid}",
            "access_credential": cred, "narrator_payout": c["payout_usd"],
            "commission": 0.0,
            "note": "store the credential securely; processor fees borne by platform"}


@app.post("/v1/voices/search")
def voices_search(body: dict[str, Any]):
    from hv import catalog as _cat
    catalog = []
    for n in DB.list_narrators():
        catalog.append({"voice_id": f"hv_voice_{n['id']}", "handle": n.get("handle", ""),
                        "languages": n.get("languages", []),
                        "capabilities": {"declared": n.get("prefs", {}).get("categories", []),
                                         "demonstrated": []},
                        "availability": {"accepting_offers": True, "max_minutes_per_job": 60},
                        "match_features": n.get("match_features", {}),
                        "reliability": n.get("reliability")})
    return {"matches": _cat.search(catalog, body, body.get("limit", 5))}


@app.get("/v1/voices/by-handle/{handle}")
def by_handle(handle: str):
    for n in DB.list_narrators():
        if n.get("handle", "").lower() == handle.lower().lstrip("@"):
            return portfolio(n["id"])
    raise HTTPException(404, "unknown handle")


@app.get("/v1/voices/{nid}/portfolio")
def portfolio(nid: str):
    n = DB.get_narrator(nid)
    if not n:
        raise HTTPException(404, "unknown narrator")
    r = reps.get(nid, R.ReputationVector(nid))
    return {"narrator_id": nid, "handle": n.get("handle", ""),
            "languages": n.get("languages", []), "samples": n.get("samples", []),
            "reputation": r.to_dict()}


@app.get("/v1/voices/{nid}/reputation")
def reputation(nid: str):
    return reps.get(nid, R.ReputationVector(nid)).to_dict()


# ---------- contracts ----------

def _quote_for(brief: dict, ag: dict) -> tuple[C.HVContract, dict]:
    script = brief.get("script_text", "")
    if not script.strip():
        raise HTTPException(422, "script_text required")
    priced = _price_for(script, brief.get("tier", "standard"))
    c = C.from_brief({**brief, "payout_usd": priced["narrator_payout"]},
                     script, ag["principal_id"], ag["agent_id"])
    errs = c.validate()
    if errs:
        raise HTTPException(422, "; ".join(errs))
    if priced["narrator_payout"] * 100 > ag["max_job_minor"]:
        raise HTTPException(402, "exceeds agent max_job budget")
    return c, priced


@app.post("/v1/contracts/quote")
def quote(brief: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    ag = _agent(x_hv_agent_key)
    c, priced = _quote_for(brief, ag)
    return {"quote_usd": priced["narrator_payout"], "customer_price": priced.get("customer_price"),
            "minutes": priced["minutes"], "delivery_seconds": c.delivery_seconds,
            "script_sha256": c.script_sha256, "policy_version": POLICY_VERSION}


@app.post("/v1/contracts")
def create(brief: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    from hv import globalx as _gx
    ag = _agent(x_hv_agent_key)
    country = (brief.get("narrator_country") or "").upper()
    if country:
        ok, why = _gx.bookable_in(country)
        if not ok:
            raise HTTPException(402, why)
    c, priced = _quote_for(brief, ag)
    today = _dt.date.today().isoformat()
    DB.add_spend(ag["agent_id"], today, int(priced["narrator_payout"] * 100))
    if DB.day_spend(ag["agent_id"], today) > ag.get("max_daily_minor", 10**12):
        raise HTTPException(402, "exceeds agent daily budget")
    script = brief.get("script_text", "")
    DB.save_script(script)
    if not ALLOW_SIMULATED:
        raise HTTPException(501, "simulated rail disabled — configure a real rail")
    intent = E.PaymentIntent(contract_id=c.contract_id, amount_minor=int(priced["narrator_payout"] * 100))
    if not rail.verify_funding(intent):
        raise HTTPException(402, "funding verification failed")
    rail.lock(intent)
    c.funding_status = "secured"
    c.status = "offered"
    DB.save_contract(c.to_dict())
    DB.save_intent(c.contract_id, {"intent_id": intent.intent_id,
                                  "amount_minor": intent.amount_minor,
                                  "idempotency_key": intent.idempotency_key})
    DB.offer_to(c.contract_id, brief.get("narrator_ids", []))
    _ev(c.contract_id, "contract.created", {"version": 1, "price": priced}, ag["agent_id"], "agent")
    _ev(c.contract_id, "payment.secured", {"intent": intent.intent_id}, "platform")
    return {"contract": DB.get_contract(c.contract_id), "funding": intent.intent_id,
            "price": priced}


@app.post("/v1/offers/{cid}/accept")
def accept_offer(cid: str, body: dict[str, Any], x_hv_session: str | None = Header(None)):
    nid = _narrator(x_hv_session)
    c = DB.get_contract(cid)
    if not c:
        raise HTTPException(404, "unknown contract")
    if not DB.is_offered(cid, nid):
        raise HTTPException(403, "offer was not dispatched to you")
    obj = C.HVContract(**{k: c[k] for k in C.HVContract().__dict__ if k in c})
    try:
        C.accept(obj, nid, funded=(c["funding_status"] == "secured"))
    except ValueError as e:
        raise HTTPException(409, str(e))
    c.update(obj.to_dict())
    DB.save_contract(c)
    _ev(cid, "offer.accepted", {"narrator": nid}, nid, "narrator")
    _ev(cid, "contract.activated", {"deadline": c["deadline_at"]})
    return {"contract": c}


@app.post("/v1/offers/{cid}/decline")
def decline_offer(cid: str, body: dict[str, Any], x_hv_session: str | None = Header(None)):
    nid = _narrator(x_hv_session)
    if not DB.get_contract(cid):
        raise HTTPException(404, "unknown contract")
    _ev(cid, "offer.declined", {"by": nid}, nid, "narrator")
    return {"ok": True, "penalty": "none"}


def _caller_ids(x_hv_session: str | None, x_hv_agent_key: str | None) -> tuple[str | None, str | None]:
    nid = SESS.narrator_for(x_hv_session or "") if x_hv_session else None
    ag = AGENTS.get(x_hv_agent_key or "", None) if x_hv_agent_key else None
    return nid, (ag["agent_id"] if ag else None)


@app.get("/v1/contracts/{cid}")
def get_contract(cid: str, x_hv_session: str | None = Header(None),
                 x_hv_agent_key: str | None = Header(None)):
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    return _party_only(cid, nid, aid)


@app.get("/v1/contracts/{cid}/events")
def contract_events(cid: str, x_hv_session: str | None = Header(None),
                     x_hv_agent_key: str | None = Header(None)):
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    _party_only(cid, nid, aid)
    ok, msg = led.verify_chain(cid)
    return {"verified": ok, "chain": msg, "events": led.get_events(cid)}


@app.post("/v1/contracts/{cid}/submissions")
async def submit(cid: str, request: Request, x_hv_session: str | None = Header(None)):
    import json as _json
    from pathlib import Path as _P
    nid = _narrator(x_hv_session)
    c = DB.get_contract(cid)
    if not c or c.get("narrator_id") != nid:
        raise HTTPException(403, "only the assigned narrator submits")
    if c.get("status") not in ("accepted", "in_correction"):
        raise HTTPException(409, "contract not awaiting submission")
    body: bytes = await request.body()
    ctype = request.headers.get("content-type", "")
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "upload exceeds 50MB")
    if ctype.startswith("audio/") or body[:4] == b"RIFF":
        try:
            receipt = UPL.store_upload(body, cid)
        except ValueError as e:
            raise HTTPException(422, str(e))
        DB.record_upload(receipt["sha256"], cid, nid, receipt["bytes"])
    else:
        try:
            payload = _json.loads(body or b"{}")
        except Exception:
            raise HTTPException(422, "send WAV bytes or JSON with sha256 of your upload")
        claimed = payload.get("sha256", "")
        owner = DB.upload_owner(claimed, cid) if claimed else None
        if not claimed or owner != nid:
            raise HTTPException(422, "unknown upload hash — upload your bytes first")
        if not _P(os.getenv("HV_AUDIO_DIR", "data/audio/raw"), claimed + ".wav").exists():
            raise HTTPException(422, "upload bytes missing server-side")
        receipt = {"sha256": claimed, "r2_key": f"audio/raw/{claimed}.wav",
                   "received_at": utcnow_now(), "contract_id": cid, "deduplicated": True}
    sub = {"submission_id": uid("sub_"), **receipt,
           "version": c.get("submission_version", 0) + 1}
    c["submission_version"] = sub["version"]
    c["status"] = "submitted"
    DB.save_contract(c)
    _ev(cid, "submission.received", sub, nid, "narrator")
    from hv import qc as _qc
    fpath = str(_P(os.getenv("HV_AUDIO_DIR", "data/audio/raw"), receipt["sha256"] + ".wav"))
    try:
        tech = _qc.tech_checks(fpath)
    except Exception as e:
        tech = {"file_valid": False, "error": str(e)[:100]}
    _ev(cid, "qc.completed", {"submission": sub["submission_id"], "technical": tech})
    sub["qc_technical"] = tech
    return sub


@app.post("/v1/contracts/{cid}/corrections")
def request_correction(cid: str, body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    ag = _agent(x_hv_agent_key)
    c = DB.get_contract(cid)
    if not c or c.get("agent_id") != ag["agent_id"]:
        raise HTTPException(403, "only the contracting agent requests corrections")
    if c.get("status") != "submitted":
        raise HTTPException(409, "nothing to correct")
    used = c.get("corrections_used", 0)
    if used >= c.get("included_corrections", 1):
        raise HTTPException(409, "correction rounds exhausted")
    c["corrections_used"] = used + 1
    c["status"] = "in_correction"
    DB.save_contract(c)
    _ev(cid, "correction.requested", {"passages": body.get("passages", [])}, ag["agent_id"], "agent")
    return {"ok": True, "status": "in_correction"}


@app.post("/v1/contracts/{cid}/reviews")
def review(cid: str, body: dict[str, Any], x_hv_session: str | None = Header(None),
           x_hv_agent_key: str | None = Header(None)):
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    c = DB.get_contract(cid)
    if not c:
        raise HTTPException(404, "unknown contract")
    side = None
    if nid and nid == c.get("narrator_id"):
        side = "narrator"
    elif aid and aid == c.get("agent_id"):
        side = "creator"
    if not side:
        raise HTTPException(403, "only contract parties review")
    c.setdefault("reviews", {})[side] = {"scores": body.get("scores", {}), "at": utcnow_now()}
    DB.save_contract(c)
    _ev(cid, "review.submitted", {"side": side}, nid or aid or "?", side)
    both = len(c["reviews"]) == 2
    return {"ok": True, "revealed": both, "note": "revealed after both sides or window"}


@app.post("/v1/contracts/{cid}/disputes")
def open_dispute(cid: str, body: dict[str, Any], x_hv_session: str | None = Header(None),
                 x_hv_agent_key: str | None = Header(None)):
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    c = DB.get_contract(cid)
    if not c:
        raise HTTPException(404, "unknown contract")
    if not ((nid and nid == c.get("narrator_id")) or (aid and aid == c.get("agent_id"))):
        raise HTTPException(403, "only contract parties dispute")
    case = dqueue.open(cid, body["type"], nid or aid or "?", body.get("claim", ""))
    DB.save_case(case)
    _ev(cid, "dispute.opened", {"case": case["case_id"], "type": case["type"]}, nid or aid or "?", "narrator" if nid else "agent")
    return case


@app.get("/v1/disputes/{case_id}")
def get_dispute(case_id: str, x_hv_session: str | None = Header(None),
                x_hv_agent_key: str | None = Header(None)):
    case = DB.get_case(case_id) or dqueue.cases.get(case_id)
    if not case:
        raise HTTPException(404, "unknown case")
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    _party_only(case["contract_id"], nid, aid)
    return case


@app.post("/v1/disputes/{case_id}/responses")
def respond(case_id: str, body: dict[str, Any], x_hv_session: str | None = Header(None),
            x_hv_agent_key: str | None = Header(None)):
    case = DB.get_case(case_id) or dqueue.cases.get(case_id)
    if not case:
        raise HTTPException(404, "unknown case")
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    _party_only(case["contract_id"], nid, aid)
    side = "narrator" if nid else "creator"
    out = dqueue.respond(case_id, side, body.get("text", ""), body.get("evidence_refs"))
    DB.save_case(dqueue.cases[case_id])
    return out


@app.post("/v1/disputes/{case_id}/appeals")
def appeal(case_id: str, body: dict[str, Any], x_hv_session: str | None = Header(None),
           x_hv_agent_key: str | None = Header(None)):
    case = DB.get_case(case_id) or dqueue.cases.get(case_id)
    if not case:
        raise HTTPException(404, "unknown case")
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    _party_only(case["contract_id"], nid, aid)
    case["appeal"] = {"grounds": body.get("grounds", ""), "status": "open"}
    DB.save_case(case)
    _ev(case["contract_id"], "appeal.opened", {"case": case_id})
    return case["appeal"]
