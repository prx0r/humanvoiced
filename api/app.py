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
# Simulated funding is NEVER production. Default off; set HV_ALLOW_SIMULATED=1
# explicitly only in dev/test. Production refuses simulated funding outright.
ALLOW_SIMULATED = os.getenv("HV_ALLOW_SIMULATED", "0") == "1"

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
    if not key:
        raise HTTPException(401, "unknown agent key")
    if key in AGENTS:
        return AGENTS[key]
    # Durable fallback: hashed keys survive restarts (raw keys never stored).
    doc = DB.get_agent(sha256(key))
    if not doc:
        raise HTTPException(401, "unknown agent key")
    AGENTS[key] = doc
    return doc


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


def _get_rep(nid: str) -> R.ReputationVector:
    """Reputation hydrated from the narrator doc (durable, survives restarts)."""
    doc = DB.get_narrator(nid) or {}
    saved = doc.get("reputation") or {}
    r = R.ReputationVector(nid)
    r.completed = int(saved.get("completed", 0))
    vec = saved.get("vector") or {}
    for d in R.DIMENSIONS:
        r.vector[d] = vec.get(d)
    r.verified_incidents = int(saved.get("verified_incidents", 0))
    r.appeals_won = int(saved.get("appeals_won", 0))
    reps[nid] = r
    return r


def _save_rep(nid: str, r: R.ReputationVector):
    doc = DB.get_narrator(nid) or {"id": nid}
    doc["reputation"] = {"completed": r.completed, "vector": dict(r.vector),
                         "verified_incidents": r.verified_incidents,
                         "appeals_won": r.appeals_won,
                         "model_version": r.model_version}
    DB.save_narrator(doc)
    reps[nid] = r


def _price_for(script_text: str, tier: str = "standard") -> dict:
    minutes = max(0.25, len(script_text.split()) / 150.0)
    return {"minutes": round(minutes, 2), **P.quote(minutes, tier=tier)}


# ---------- auth ----------

@app.get("/api/auth/google/start")
def google_start():
    if not hv_auth.configured():
        raise HTTPException(501, "sign-in not configured yet")
    from fastapi.responses import RedirectResponse
    state = SESS.issue_state()
    resp = RedirectResponse(hv_auth.authorize_url(state), status_code=302)
    # Bind the OAuth state to the initiating browser: callback must present
    # the same state both as query param and as cookie (CSRF protection).
    resp.set_cookie("hv_oauth", state, httponly=True, secure=True,
                    samesite="lax", max_age=600, path="/api/auth/google/callback")
    return resp


@app.get("/api/auth/google/callback")
def google_callback(request: Request, code: str = "", state: str = ""):
    from fastapi.responses import RedirectResponse
    if not code:
        raise HTTPException(400, "missing code")
    if not state or request.cookies.get("hv_oauth", "") != state:
        raise HTTPException(400, "state not initiated by this browser")
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
    resp = RedirectResponse("https://humanvoiced.com/onboard?login=ok", status_code=302)
    resp.set_cookie("hv_session", token, httponly=True, secure=True,
                    samesite="lax", max_age=30 * 86400, path="/",
                    domain=".humanvoiced.com")
    resp.delete_cookie("hv_oauth", path="/api/auth/google/callback")
    return resp


@app.post("/api/auth/logout")
def logout(x_hv_session: str | None = Header(None)):
    if x_hv_session:
        SESS.revoke(x_hv_session)
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("hv_session", path="/", domain=".humanvoiced.com")
    resp.delete_cookie("hv_session", path="/")  # legacy scope, if any
    return resp


@app.get("/api/auth/me")
def auth_me(request: Request, x_hv_session: str | None = Header(None)):
    """Durable signed-in status for page reloads (cookie or header session)."""
    tok = x_hv_session or request.cookies.get("hv_session", "")
    nid = SESS.narrator_for(tok)
    if not nid:
        from fastapi.responses import JSONResponse
        return JSONResponse({"authenticated": False}, status_code=401)
    doc = DB.get_narrator(nid) or {}
    return {"authenticated": True, "narrator_id": nid,
            "name": (doc.get("profile_published") or {}).get("display_name", ""),
            "email": doc.get("email", "")}


# ---------- narrators / voices ----------

@app.post("/v1/casting/search")
def casting_search(body: dict[str, Any]):
    from hv import casting as _c
    roles = [_c.role(body.get("project", ""), r.get("character", ""),
                     r.get("side_text", ""), r.get("voice_reqs", {}))
             for r in body.get("roles", [])]
    catalog = [{"voice_id": n["id"], "handle": n.get("handle", ""),
                "characters": n.get("characters", [])}
               for n in DB.list_narrators()]
    return {"cast": _c.cast_list(body.get("project", ""), roles, catalog)}


@app.post("/v1/contracts/{cid}/stage-direction")
def stage_direction(cid: str, body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    from hv import casting as _c
    ag = _agent(x_hv_agent_key)
    c = DB.get_contract(cid)
    if not c or c.get("agent_id") != ag["agent_id"]:
        raise HTTPException(403, "only the contracting agent directs")
    sd = _c.stage_direction(cid, body.get("notes", ""), body.get("scenes"))
    _ev(cid, "direction.attached", {"sha256": sd["sha256"]}, ag["agent_id"], "agent")
    return sd


@app.post("/v1/narrators/me/payout-prefs")
def payout_prefs(body: dict[str, Any], x_hv_session: str | None = Header(None)):
    from hv import stablecoin as _sc
    nid = _narrator(x_hv_session)
    doc = DB.get_narrator(nid) or {"id": nid}
    try:
        pref = _sc.set_prefs(doc, body.get("mode", "later"),
                             body.get("wallet", ""), body.get("currency", ""))
    except AssertionError as e:
        raise HTTPException(422, str(e))
    DB.save_narrator(doc)
    return {"payout_pref": pref}


@app.get("/v1/transparency")
def transparency():
    from hv import stablecoin as _sc
    t = _sc.Transparency()
    for kind, amount, country in DB.fin_sums():
        if kind == "fee":
            t.record_fee(amount / 100, country or "?")
        elif kind == "contribution":
            t.record_contribution(amount / 100)
        elif kind == "expense":
            t.record_expense(amount / 100, "")
    return t.public()
@app.get("/v1/narrators/me")
def my_profile_get(x_hv_session: str | None = Header(None)):
    nid = _narrator(x_hv_session)
    doc = DB.get_narrator(nid) or {"id": nid}
    return {"narrator_id": nid, "email": doc.get("email", ""),
            "handle": doc.get("handle", ""),
            "samples": len(doc.get("samples", [])),
            "published": bool(doc.get("profile_published"))}


@app.get("/v1/narrators/me/jobs")
def my_jobs(x_hv_session: str | None = Header(None)):
    """Talent home: offers to review, active jobs to record, recent payouts.
    No contract IDs typed by hand; everything actionable is linked."""
    from hv import pace as _pace
    nid = _narrator(x_hv_session)
    doc = DB.get_narrator(nid) or {"id": nid}
    offers = []
    for cid in DB.list_offers(nid):
        c = DB.get_contract(cid)
        if c and c.get("status") in ("offered", "proposed"):
            offers.append({"contract_id": cid, "payout_usd": c.get("payout_usd"),
                           "delivery_seconds": c.get("delivery_seconds"),
                           "deadline_at": c.get("deadline_at", "")})
    active, recent = [], []
    for c in DB.contracts_for_narrator(nid):
        row = {"contract_id": c["contract_id"], "payout_usd": c.get("payout_usd"),
               "status": c.get("status"), "deadline_at": c.get("deadline_at", ""),
               "settlement": c.get("settlement")}
        (active if c.get("status") in ("accepted", "in_correction", "submitted")
         else recent).append(row)
    recent = sorted(recent, key=lambda r: r["contract_id"], reverse=True)[:10]
    return {"offers": offers, "active": active, "recent": recent,
            "pace_wpm": _pace.narrator_wpm(doc),
            "published": bool(doc.get("profile_published")),
            "handle": doc.get("handle", "")}


@app.post("/v1/narrators/me/profile")
def my_profile(body: dict[str, Any], x_hv_session: str | None = Header(None)):
    from hv import profile_draft as _pd
    import re as _re
    nid = _narrator(x_hv_session)
    doc = DB.get_narrator(nid) or {"id": nid}
    if body.get("publish"):
        profile = dict(body.get("profile", {}))
        handle = (body.get("handle") or profile.get("handle") or doc.get("handle") or "").strip().lstrip("@")
        if not _re.fullmatch(r"[A-Za-z0-9_.-]{2,30}", handle or ""):
            raise HTTPException(422, "handle must be 2-30 chars: letters, numbers, _.-")
        for other in DB.list_narrators():
            if other.get("id") != nid and (other.get("handle", "") or "").lower() == handle.lower():
                raise HTTPException(409, "handle taken")
        doc["handle"] = handle
        # studio.js sends display names (e.g. "English") in the publish
        # profile but 2-letter codes in the pre-publish update. Only keep
        # code-shaped values so language filtering keeps working.
        if profile.get("languages") and all(
                isinstance(v, str) and _re.fullmatch(r"[A-Za-z]{2,3}", v.strip())
                for v in profile["languages"]):
            doc["languages"] = [v.strip().lower() for v in profile["languages"]]
        if profile.get("categories"):
            doc.setdefault("prefs", {})["categories"] = list(profile["categories"])
        profile["handle"] = handle
        pub = _pd.publish(doc, profile)
        raw_consent = body.get("consent_samples", [])
        if raw_consent == "latest":
            raw_consent = ["latest"]
        consent = set(raw_consent or [])
        if "latest" in consent:
            latest = (doc.get("samples", []) or [None])[-1]
            latest_sha = latest.get("sha256") if isinstance(latest, dict) else None
            consent.discard("latest")
            if latest_sha:
                consent.add(latest_sha)
        for s in doc.get("samples", []):
            if isinstance(s, dict):
                s["consented_public"] = s.get("sha256") in consent
        DB.save_narrator(doc)
        _ev(nid, "profile.published", {"handle": handle}, nid, "narrator")
        return {"published": pub}
    if body.get("draft_from_tech") or body.get("draft_from_sample"):
        latest = (doc.get("samples", []) or [{}])[-1]
        stored = latest.get("analysis", {}) if isinstance(latest, dict) else {}
        tech = {"peak": (stored.get("acoustic") or {}).get("peak", 0),
                "silence_ratio": 1 - (stored.get("acoustic") or {}).get("speech_fraction", 1),
                "clipping": bool((stored.get("acoustic") or {}).get("clipping_detected"))}
        draft = _pd.draft_from_sample(tech, body, None)
        draft["analysis_ref"] = latest.get("sha256") if isinstance(latest, dict) else ""
        doc["profile_draft"] = draft
        DB.save_narrator(doc)
        return {"draft": draft}
    doc.update({"handle": body.get("handle", doc.get("handle", "")),
                "languages": body.get("languages", doc.get("languages", [])),
                "prefs": body.get("prefs", doc.get("prefs", {}))})
    import re as _re
    if doc.get("handle") and not _re.fullmatch(r"[A-Za-z0-9_.-]{2,30}", doc["handle"]):
        raise HTTPException(422, "handle must be 2-30 chars: letters, numbers, _.-")
    DB.save_narrator(doc)
    _ev(nid, "profile.updated", {"handle": doc["handle"]}, nid, "narrator")
    return doc


def _analyze_sample(body: bytes, tx: dict) -> dict:
    """Real analysis on stored bytes: VAD + acoustic + transcript merge.
    Decodes complete 16-bit PCM frames and downmixes channels by averaging
    (see hv.audio.decode_wav_mono). Silent/empty audio never throws."""
    from hv import audio as _au
    try:
        frames, sr = _au.decode_wav_mono(body, max_seconds=120)
        return _au.analyze(frames, sr, tx.get("text", ""), "")
    except Exception as e:
        return {"error": str(e)[:100]}


@app.post("/v1/narrators/me/sample")
async def my_sample(request: Request, x_hv_session: str | None = Header(None)):
    from hv import transcribe as _tr
    nid = _narrator(x_hv_session)
    body = await request.body()
    language = request.query_params.get("language", "en")
    if len(body) > MAX_UPLOAD_BYTES or len(body) < 44 or body[:4] != b"RIFF":
        raise HTTPException(422, "send WAV bytes under 50MB")
    receipt = UPL.store_upload(body, f"sample:{nid}:{language}")
    try:
        tx = _tr.transcribe(body, language)
    except Exception as e:
        tx = {"text": "", "provider": "error", "note": str(e)[:100]}
    doc = DB.get_narrator(nid) or {"id": nid}
    kind = request.query_params.get("kind", "natural")
    existing = [s for s in doc.get("samples", [])
                if (s.get("sha256") if isinstance(s, dict) else s)]
    if len(existing) >= 11:
        raise HTTPException(409, "sample cap reached (1 base + 10 extras)")
    doc.setdefault("samples", []).append({"sha256": receipt["sha256"],
                                          "language": language, "kind": kind,
                                          "consented_public": False,
                                          "transcript_words": len(tx.get("text", "").split()),
                                          "analysis": _analyze_sample(body, tx)})
    if language not in doc.get("languages", []):
        doc["languages"] = doc.get("languages", []) + [language]
    from hv import pace as _pace
    _pace.record_sample(doc, len(tx.get("text", "").split()),
                        receipt.get("frames", 0) / max(1, receipt.get("sample_rate", 48000)))
    DB.save_narrator(doc)
    _ev(nid, "sample.recorded", {"sha256": receipt["sha256"], "language": language,
                                 "provider": tx.get("provider")}, nid, "narrator")
    return {"narrator_id": nid, "sample": receipt["sha256"], "language": language,
            "transcript": tx.get("text", ""), "transcript_provider": tx.get("provider")}


@app.get("/v1/voices")
def voices(style: str = "", language: str = ""):
    out = []
    for n in DB.list_narrators():
        if not n.get("profile_published"):
            continue  # unpublished profiles never appear in the public catalog
        if language and language not in n.get("languages", []):
            continue
        out.append({"id": n["id"], "handle": n.get("handle", ""),
                    "languages": n.get("languages", []),
                    "samples": len([s for s in n.get("samples", [])
                                    if isinstance(s, dict) and s.get("consented_public")])})
    return {"voices": out}


@app.get("/v1/payments/methods")
def pay_methods():
    from hv.payments import service as _s, adapters as _a
    svc = _s.PaymentService(None)
    for ad in (_a.StellarEscrow(), _a.X402Base(), _a.StripeConnect(), _a.Simulated()):
        svc.register(ad)
    return {"rails": svc.methods()}


@app.post("/v1/payments/quote")
def pay_quote(body: dict[str, Any]):
    from hv.payments import service as _s, adapters as _a
    svc = _s.PaymentService(None)
    for ad in (_a.StellarEscrow(), _a.X402Base(), _a.StripeConnect(), _a.Simulated()):
        svc.register(ad)
    return svc.quote({"payout_usd": float(body.get("payout_usd", 0))}, body.get("rail", "simulated"))


@app.get("/v1/demand/templates")
def demand_templates():
    from hv import demand as _d
    return {"templates": _d.TEMPLATES, "onboarding": _d.onboarding_tasks()}


@app.post("/v1/orders/guest")
def guest_order(body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    """Guest checkout: proven by funding intent, not by login. The intent
    idempotency key is the payment proof; agent key optional context."""
    import secrets as _s
    import sqlite3 as _sq
    c = DB.get_contract(body.get("contract_id", ""))
    if not c:
        raise HTTPException(404, "unknown contract")
    intent = DB.get_intent(c["contract_id"])
    if not intent or intent.get("intent_id") != body.get("funding_intent"):
        raise HTTPException(402, "no verified funding for this contract")
    ag = AGENTS.get(x_hv_agent_key or "", None)
    if ag and ag["agent_id"] != c.get("agent_id"):
        raise HTTPException(403, "foreign agent")
    oid = "ord_" + _s.token_hex(8)
    cred = _s.token_urlsafe(24)
    conn = _sq.connect(str(DB.db_path), timeout=30)
    conn.execute("INSERT INTO orders VALUES (?, ?)", (oid, __import__("json").dumps(
        {"order_id": oid, "contract_id": c["contract_id"], "credential": sha256(cred),
         "narrator_payout": c["payout_usd"], "commission": 0.0})))
    conn.commit()
    conn.close()
    _ev(c["contract_id"], "order.created", {"order_id": oid},
        (ag["agent_id"] if ag else "guest"), "agent" if ag else "guest")
    return {"order_id": oid, "url": f"https://humanvoiced.com/orders/{oid}",
            "access_credential": cred, "narrator_payout": c["payout_usd"],
            "commission": 0.0,
            "note": "store the credential securely; processor fees borne by platform"}


@app.post("/v1/voices/search")
def voices_search(body: dict[str, Any]):
    from hv import catalog as _cat
    prefs = body.get("preferences", {})
    catalog = []
    for n in DB.list_narrators():
        if not n.get("profile_published"):
            continue
        feats = dict(n.get("match_features", {}))
        if prefs.get("prosody") and prefs["prosody"] in str(feats.get("prosody", "")):
            feats["perceptual"] = min(1.0, feats.get("perceptual", 0.5) + 0.2)
        if prefs.get("energy") and prefs["energy"] == feats.get("energy"):
            feats["delivery"] = min(1.0, feats.get("delivery", 0.5) + 0.2)
        catalog.append({"voice_id": n["id"], "handle": n.get("handle", ""),
                        "languages": n.get("languages", []),
                        "capabilities": {"declared": n.get("prefs", {}).get("categories", []),
                                         "demonstrated": []},
                        "availability": {"accepting_offers": True, "max_minutes_per_job": 60},
                        "match_features": feats,
                        "reliability": n.get("reliability")})
    return {"matches": _cat.search(catalog, body, body.get("limit", 5))}


@app.get("/v1/voices/{nid}/sample")
def voice_sample(nid: str, sha: str = ""):
    from fastapi.responses import Response
    n = DB.get_narrator(nid)
    if not n:
        raise HTTPException(404, "unknown narrator")
    samples = [s for s in n.get("samples", [])
               if isinstance(s, dict) and s.get("consented_public")]
    if sha and not any(s.get("sha256") == sha for s in samples):
        raise HTTPException(403, "sample not public")
    target = sha or (samples[0]["sha256"] if samples else "")
    if not target:
        raise HTTPException(404, "no public samples")
    from pathlib import Path as _P
    f = _P(UPL.RAW_DIR, target + ".wav")
    if not f.exists():
        raise HTTPException(404, "audio missing")
    return Response(f.read_bytes(), media_type="audio/wav")


@app.get("/v1/voices/suggested-samples")
def suggested_samples():
    """Demand-led extras: which 2 (+up to 10) samples agents actually search.
    Base natural sample first; extras unlock template eligibility."""
    from hv import demand as _d
    return {"base": {"kind": "natural", "text": "Alex café passage (VOICE-DEMO.md Tier 1)",
                     "why": "casting baseline every buyer compares"},
            "recommended_two": [
                {"kind": "documentary", "why": "top agent query: calm measured narration"},
                {"kind": "commercial", "why": "second demand cluster: 30s ad reads"}],
            "further": [{"kind": t["id"], "why": t["brief"]} for t in _d.TEMPLATES
                        if t["id"] not in ("youtube-narration",)],
            "cap": 10}


CASTINGS: dict[str, dict] = {}


@app.post("/v1/casting")
def casting_create(body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    from hv import audition as _a
    ag = _agent(x_hv_agent_key)
    try:
        call = _a.casting_call(body.get("project", ""), body.get("role", ""),
                               body.get("side_text", ""), body.get("deadline_at", ""))
    except ValueError as e:
        raise HTTPException(422, str(e))
    CASTINGS[call["casting_id"]] = {**call, "agent_id": ag["agent_id"]}
    _ev(call["casting_id"], "casting.opened", {"role": call["role"]}, ag["agent_id"], "agent")
    return call


@app.post("/v1/casting/{cid}/submit")
async def casting_submit(cid: str, request: Request, x_hv_session: str | None = Header(None)):
    from hv import audition as _a
    nid = _narrator(x_hv_session)
    call = CASTINGS.get(cid)
    if not call:
        raise HTTPException(404, "unknown casting")
    body = await request.body()
    if len(body) < 44 or body[:4] != b"RIFF":
        raise HTTPException(422, "send WAV bytes")
    receipt = UPL.store_upload(body, f"audition:{cid}:{nid}")
    try:
        return _a.submit_read(call, nid, receipt["sha256"])
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/v1/casting/{cid}/compare")
def casting_compare(cid: str, x_hv_agent_key: str | None = Header(None)):
    from hv import audition as _a
    ag = _agent(x_hv_agent_key)
    call = CASTINGS.get(cid)
    if not call:
        raise HTTPException(404, "unknown casting")
    if call.get("agent_id") != ag["agent_id"]:
        raise HTTPException(403, "another agent's casting")
    return {"entries": _a.compare(call)}


@app.post("/v1/casting/{cid}/decide")
def casting_decide(cid: str, body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    from hv import audition as _a
    ag = _agent(x_hv_agent_key)
    call = CASTINGS.get(cid)
    if not call:
        raise HTTPException(404, "unknown casting")
    if call.get("agent_id") != ag["agent_id"]:
        raise HTTPException(403, "another agent's casting")
    try:
        out = _a.decide(call, body.get("winner_id", ""), body.get("notes", ""))
    except ValueError as e:
        raise HTTPException(422, str(e))
    _ev(cid, "casting.decided", {"winner": out["winner"]}, ag["agent_id"], "agent")
    return out


@app.post("/v1/agents/provision")
def provision_agent(body: dict[str, Any]):
    """Bootstrap agent keys. Gated by HV_ADMIN_TOKEN env (never default).
    Only the key hash is stored; the raw key is shown once at provision."""
    import secrets as _s
    admin = os.getenv("HV_ADMIN_TOKEN", "")
    if not admin or body.get("admin_token") != admin:
        raise HTTPException(403, "admin only")
    key = "hvag_" + _s.token_hex(16)
    AGENTS[key] = {"agent_id": body.get("agent_id", "agent_" + _s.token_hex(4)),
                   "principal_id": body.get("principal_id", ""),
                   "max_job_minor": int(body.get("max_job_minor", 3000)),
                   "max_daily_minor": int(body.get("max_daily_minor", 100000))}
    DB.save_agent(sha256(key), AGENTS[key])
    return {"agent_key": key, "agent_id": AGENTS[key]["agent_id"]}


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
    r = _get_rep(nid)
    pub = (n.get("profile_published") or {})
    pub_samples = []
    for s in n.get("samples", []):
        if not (isinstance(s, dict) and s.get("consented_public")):
            continue
        ac = (s.get("analysis") or {}).get("acoustic", {})
        pub_samples.append({"sha256": s.get("sha256"), "language": s.get("language"),
                            "kind": s.get("kind", "natural"),
                            "speech_fraction": ac.get("speech_fraction"),
                            "peak": ac.get("peak"),
                            "pause_median_ms": ac.get("pause_median_ms")})
    return {"narrator_id": nid, "handle": n.get("handle", ""),
            "languages": n.get("languages", []),
            "profile": {k: pub.get(k) for k in ("display_name", "bio", "categories")},
            "samples": pub_samples,
            "reputation": r.to_dict()}


@app.get("/v1/voices/{nid}/reputation")
def reputation(nid: str):
    return _get_rep(nid).to_dict()


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
    ag = _agent(x_hv_agent_key)
    doc, funding, priced = _create_funded(ag, brief)
    return {"contract": doc, "funding": funding, "price": priced}


def _create_funded(ag: dict, brief: dict[str, Any]) -> tuple[dict, str, dict]:
    """Shared funded-contract path for direct creates and channel rebooks."""
    from hv import globalx as _gx
    country = (brief.get("narrator_country") or "").upper()
    if country:
        ok, why = _gx.bookable_in(country)
        if not ok:
            raise HTTPException(402, why)
    c, priced = _quote_for(brief, ag)
    today = _dt.date.today().isoformat()
    if not DB.reserve_spend(ag["agent_id"], today, int(priced["narrator_payout"] * 100),
                            ag.get("max_daily_minor", 10**12)):
        raise HTTPException(402, "exceeds agent daily budget")
    script = brief.get("script_text", "")
    DB.save_script(script)
    from hv import brief as _br
    try:
        manifest = _br.compile(brief.get("brief") or {"mode": "script"}, script)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not ALLOW_SIMULATED:
        raise HTTPException(501, "simulated funding disabled — set HV_ALLOW_SIMULATED=1 only in dev/test; "
                                 "production requires a real protected-funding rail")
    intent = E.PaymentIntent(contract_id=c.contract_id, amount_minor=int(priced["narrator_payout"] * 100))
    if not rail.verify_funding(intent):
        raise HTTPException(402, "funding verification failed")
    rail.lock(intent)
    c.funding_status = "secured"
    c.status = "offered"
    doc = c.to_dict()
    doc["segment_manifest"] = manifest
    doc["segments_state"] = {s["id"]: {"takes": [], "accepted": None,
                                       "needs_retake": False, "retake_note": ""}
                             for s in manifest["segments"]}
    doc["session"] = {"takes": 0, "retakes": 0, "assemblies": 0,
                      "label": "HumanVoiced Verified Recording Session"}
    if brief.get("channel_id"):
        doc["channel_id"] = brief["channel_id"]
    if brief.get("channel_preset"):
        doc["channel_preset"] = brief["channel_preset"]
    DB.save_contract(doc)
    DB.save_intent(c.contract_id, {"intent_id": intent.intent_id,
                                  "amount_minor": intent.amount_minor,
                                  "idempotency_key": intent.idempotency_key})
    DB.offer_to(c.contract_id, brief.get("narrator_ids", []))
    _ev(c.contract_id, "contract.created", {"version": 1, "price": priced}, ag["agent_id"], "agent")
    _ev(c.contract_id, "payment.secured", {"intent": intent.intent_id}, "platform")
    return DB.get_contract(c.contract_id), intent.intent_id, priced


@app.post("/v1/offers/{cid}/accept")
def accept_offer(cid: str, body: dict[str, Any], x_hv_session: str | None = Header(None)):
    from hv import globalx as _gx
    nid = _narrator(x_hv_session)
    cur = DB.get_contract(cid)
    if not cur:
        raise HTTPException(404, "unknown contract")
    if not DB.is_offered(cid, nid):
        raise HTTPException(403, "offer was not dispatched to you")
    if cur.get("status") not in ("offered", "proposed"):
        raise HTTPException(409, "offer unavailable (taken or wrong state)")
    # Eligibility BEFORE the claim transaction (rechecked post-claim on the doc).
    ndoc = DB.get_narrator(nid) or {}
    ok, why = _gx.bookable_in((ndoc.get("country") or ""))
    if ndoc.get("country") and not ok:
        raise HTTPException(402, why)
    # Validate funding/state on a copy BEFORE claiming, so a validation
    # failure never strands a committed claim.
    obj = C.HVContract(**{k: cur[k] for k in C.HVContract().__dict__ if k in cur})
    try:
        C.accept(obj, nid, funded=(cur.get("funding_status") == "secured"))
    except ValueError as e:
        raise HTTPException(409, str(e))
    c = DB.accept_atomic(cid, nid, obj.to_dict())
    if not c:
        raise HTTPException(409, "offer unavailable (taken or wrong state)")
    _ev(cid, "offer.accepted", {"narrator": nid}, nid, "narrator")
    _ev(cid, "contract.activated", {"deadline": c["deadline_at"]})
    return {"contract": c}


@app.post("/v1/offers/{cid}/decline")
def decline_offer(cid: str, body: dict[str, Any], x_hv_session: str | None = Header(None)):
    nid = _narrator(x_hv_session)
    if not DB.get_contract(cid):
        raise HTTPException(404, "unknown contract")
    DB.decline_offer(cid, nid)
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


@app.get("/v1/contracts/{cid}/script")
def contract_script(cid: str, x_hv_session: str | None = Header(None),
                    x_hv_agent_key: str | None = Header(None)):
    """Frozen script text for the assigned reader. Party-only; hash must match.
    Offered narrators may read it to review the job before accepting."""
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    try:
        c = _party_only(cid, nid, aid)
    except Exception:
        c = None
        if nid and DB.is_offered(cid, nid):
            c = DB.get_contract(cid)
        if c is None:
            raise
    text = DB.get_script(c.get("script_sha256", "")) or ""
    return {"script_sha256": c.get("script_sha256"), "script_text": text}


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
        if not _P(UPL.RAW_DIR, claimed + ".wav").exists():
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
    fpath = str(_P(UPL.RAW_DIR, receipt["sha256"] + ".wav"))
    try:
        tech = _qc.tech_checks(fpath)
    except Exception as e:
        tech = {"file_valid": False, "error": str(e)[:100]}
    _ev(cid, "qc.completed", {"submission": sub["submission_id"], "technical": tech})
    sub["qc_technical"] = tech
    c["last_submission"] = sub  # persisted for approve/receipt (was response-only)
    DB.save_contract(c)
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


@app.post("/v1/contracts/{cid}/approve")
def approve(cid: str, body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    """Close the loop: agent approves → escrow releases → reputation recorded.
    Idempotent: re-approving a settled contract returns its receipt.
    Correctable defects 409 (use corrections); contested contracts 409 (resolve dispute)."""
    ag = _agent(x_hv_agent_key)
    c = DB.get_contract(cid)
    if not c or c.get("agent_id") != ag["agent_id"]:
        raise HTTPException(403, "only the contracting agent approves")
    if c.get("status") == "settled":
        return {"contract": c, "settlement": c.get("settlement"), "deduplicated": True}
    if c.get("status") != "submitted":
        raise HTTPException(409, "nothing to approve")
    for case in DB.cases_by_contract(cid):
        if case.get("status") in ("open", "decided") and not (
                (case.get("decision") or {}).get("settlement_authorised")):
            raise HTTPException(409, "dispute open — resolve before settlement")
    sub = c.get("last_submission") or {}
    tech = sub.get("qc_technical") or {}
    if not tech.get("file_valid"):
        raise HTTPException(422, "submission undecodable — request a correction round")
    if tech.get("clipping_detected") or not tech.get("noise_threshold_passed", True):
        raise HTTPException(409, "correctable audio defect — use the correction round")
    nid = c.get("narrator_id")
    stored = DB.get_intent(cid) or {}
    pi = E.PaymentIntent(intent_id=stored.get("intent_id", ""),
                        contract_id=cid,
                        amount_minor=int(stored.get("amount_minor",
                                                   int(c.get("payout_usd", 0) * 100))),
                        idempotency_key=stored.get("idempotency_key", uid("idem_")))
    if pi.intent_id not in rail.locked:
        rail.lock(pi)  # restart tolerance: re-establish the lock, then release
    try:
        rel = rail.release(pi, nid)
    except ValueError as e:
        raise HTTPException(409, str(e))
    late = False
    try:
        dl = _dt.datetime.strptime(c.get("deadline_at", ""), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=_dt.timezone.utc)
        late = _dt.datetime.now(_dt.timezone.utc) > dl
    except Exception:
        pass
    rep = _get_rep(nid)
    rep.record_outcome({"verified": True, "worker_fault": False,
                        "scores": {"Q": 1.0, "D": 0.0 if late else 1.0}})
    _save_rep(nid, rep)
    DB.record_fin("payout", rel["amount_minor"], "")
    c["status"] = "settled"
    c["settled_at"] = utcnow_now()
    c["settlement"] = {"to": rel["to"], "amount_minor": rel["amount_minor"],
                       "late": late, "intent_id": pi.intent_id}
    DB.save_contract(c)
    _ev(cid, "creator.approved", {}, ag["agent_id"], "agent")
    _ev(cid, "settlement.released", c["settlement"], "platform")
    _ev(cid, "reputation.updated", {"narrator": nid, "completed": rep.completed}, "platform")
    return {"contract": c, "settlement": c["settlement"]}


@app.get("/v1/contracts/{cid}/receipt")
def receipt(cid: str, x_hv_session: str | None = Header(None),
            x_hv_agent_key: str | None = Header(None)):
    """Settlement receipt: contract + funding + settlement + verified chain."""
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    c = _party_only(cid, nid, aid)
    if c.get("status") != "settled":
        raise HTTPException(409, "not settled yet")
    ok, chain = led.verify_chain(cid)
    return {"contract_id": cid, "payout_usd": c.get("payout_usd"),
            "narrator": c.get("narrator_id"), "settlement": c.get("settlement"),
            "funding": DB.get_intent(cid), "chain_verified": ok, "chain": chain,
            "policy_version": POLICY_VERSION}


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


# ---------- studio: presets + delivery packs ----------

def _resolve_preset(preset_id: str, ag: dict | None) -> dict:
    from hv import presets as _pr
    if preset_id in _pr.BUILTINS:
        return {"name": preset_id, **_pr.BUILTINS[preset_id]}
    if ag:
        for key in (preset_id, f"{ag['agent_id']}/{preset_id}"):
            doc = DB.get_preset(key)
            if doc and doc.get("owner") == ag["agent_id"]:
                return doc
    raise HTTPException(404, "unknown preset")


@app.post("/v1/studio/presets")
def create_preset(body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    """Save a channel sound preset. Namespaced per agent; builtins are read-only."""
    from hv import presets as _pr
    ag = _agent(x_hv_agent_key)
    errs = _pr.validate(body)
    if errs:
        raise HTTPException(422, "; ".join(errs))
    if body["name"] in _pr.BUILTINS:
        raise HTTPException(409, "builtin preset names are reserved")
    doc = {**_pr.normalize(body), "owner": ag["agent_id"]}
    doc["name"] = f"{ag['agent_id']}/{body['name']}"
    DB.save_preset(doc)
    _ev(doc["name"], "preset.saved", {"preset": doc["name"]}, ag["agent_id"], "agent")
    return {"preset": doc}


@app.get("/v1/studio/presets")
def list_presets(x_hv_agent_key: str | None = Header(None)):
    from hv import presets as _pr
    ag = _agent(x_hv_agent_key)
    own = [d for d in DB.list_presets() if d.get("owner") == ag["agent_id"]]
    return {"builtins": [{"name": k, **v} for k, v in _pr.BUILTINS.items()],
            "custom": own}


@app.get("/v1/studio/presets/{name:path}")
def get_preset(name: str, x_hv_agent_key: str | None = Header(None)):
    ag = _agent(x_hv_agent_key)
    return {"preset": _resolve_preset(name, ag)}


@app.post("/v1/studio/references")
async def upload_reference(request: Request, x_hv_agent_key: str | None = Header(None)):
    """Register a channel reference master: measured once, matched forever.
    WAV bytes; profile (bands + loudness) stored, audio kept for re-measure."""
    from hv import reference as _rf
    ag = _agent(x_hv_agent_key)
    body: bytes = await request.body()
    if len(body) > 25 * 1024 * 1024 or len(body) < 44 or body[:4] != b"RIFF":
        raise HTTPException(422, "send WAV bytes under 25MB")
    rid = "ref_" + sha256(body)[:12]
    rdir = os.path.join(os.getenv("HV_PACK_DIR", "data/packs"), "refs")
    os.makedirs(rdir, exist_ok=True)
    fpath = os.path.join(rdir, rid + ".wav")
    with open(fpath, "wb") as f:
        f.write(body)
    try:
        profile = _rf.measure_file(fpath)
    except Exception as e:
        raise HTTPException(422, f"could not measure reference: {e}"[:200])
    doc = {"id": rid, "owner": ag["agent_id"], "sha256": sha256(body),
           "profile": profile, "path": fpath}
    DB.save_ref(doc)
    _ev(rid, "reference.registered", {"lufs": profile.get("lufs")},
        ag["agent_id"], "agent")
    return {"reference": {k: doc[k] for k in ("id", "owner", "sha256", "profile")}}


@app.get("/v1/studio/references")
def list_references(x_hv_agent_key: str | None = Header(None)):
    ag = _agent(x_hv_agent_key)
    return {"references": [
        {k: d[k] for k in ("id", "owner", "sha256", "profile")}
        for d in DB.list_refs(ag["agent_id"])]}


def _transcribe_file(path: str, language: str = "en") -> dict:
    from hv import transcribe as _tr
    try:
        with open(path, "rb") as f:
            return _tr.transcribe(f.read(), language)
    except Exception as e:
        return {"text": "", "segments": [], "provider": "error",
                "note": str(e)[:100]}


def _run_mp3(wav_path: str, out_dir: str, stem: str) -> dict:
    from hv import processing as _proc
    mp3 = os.path.join(out_dir, stem + ".mp3")
    p = _proc._run(["ffmpeg", "-hide_banner", "-y", "-i", wav_path,
                    "-codec:a", "libmp3lame", "-b:a", "192k", mp3])
    if p.returncode != 0:
        raise _proc.ProcessingError("mp3 export failed: " + p.stderr[-300:])
    return {stem + ".wav": wav_path, stem + ".mp3": mp3,
            "measured": _proc.measure_loudness(wav_path)}


@app.post("/v1/contracts/{cid}/pack")
def build_pack(cid: str, body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    """Assemble the delivery pack: original (immutable) + basic master/MP3/SRT,
    optionally the studio upgrade under a channel preset. Processing fees are
    a separate HumanVoiced service line — narrator payout is never touched."""
    from hv import packages as _pk
    from hv import presets as _pr
    from hv import processing as _proc
    ag = _agent(x_hv_agent_key)
    c = DB.get_contract(cid)
    if not c or c.get("agent_id") != ag["agent_id"]:
        raise HTTPException(403, "only the contracting agent packs")
    if c.get("status") not in ("submitted", "settled"):
        raise HTTPException(409, "pack needs a submitted recording")
    tier = body.get("tier", "basic")
    if tier not in ("basic", "studio", "clean"):
        raise HTTPException(422, "tier must be basic, studio or clean")
    from hv import clean as _cl
    if tier == "clean":
        minutes = max(0.25, len((DB.get_script(c.get("script_sha256", "")) or "").split()) / 150.0)
        fee = {"tier": "clean",
               "processing_fee_usd": _cl.clean_quote_usd(minutes),
               "narrator_payout_change_usd": 0.0,
               "note": "VEED via fal.ai, passthrough usage cost billed separately"}
    else:
        fee = P.processing_quote(tier)
    preset = None
    if tier == "studio":
        if not ALLOW_SIMULATED:
            raise HTTPException(501, "studio billing needs a production rail; "
                                     "basic pack remains available")
        preset = _resolve_preset(body.get("preset_id") or c.get("channel_preset")
                                 or "natural-clean", ag)
    sub = c.get("last_submission") or {}
    sha = sub.get("sha256", "")
    from pathlib import Path as _P
    _cand = str(_P(UPL.RAW_DIR, sha + ".wav"))
    _mas = os.path.join(os.getenv("HV_PACK_DIR", "data/packs"), cid, "assembled.wav")
    src = _cand if sha and _P(_cand).exists() else _mas
    if not sha or not _P(src).exists():
        raise HTTPException(422, "original bytes missing server-side")
    out_dir = os.path.join(os.getenv("HV_PACK_DIR", "data/packs"), cid)
    try:
        assets = _proc.basic_pack(src, out_dir, target_lufs=_pr.REFERENCE_LUFS)
        tx = _transcribe_file(src)
        segments = tx.get("segments") or []
        srt = _proc.srt_from_segments(segments)
        if srt:
            spath = os.path.join(out_dir, "transcript.srt")
            with open(spath, "w") as f:
                f.write(srt)
            assets["transcript.srt"] = spath
        integrity = None
        ref_id = None
        if tier == "studio":
            from hv import reference as _rf
            ref_curve = None
            ref_id = body.get("reference_id") or preset.get("reference_id")
            if preset["name"] == "match-my-channel" and not ref_id:
                raise HTTPException(422, "match-my-channel needs reference_id")
            if ref_id:
                ref = DB.get_ref(ref_id)
                if not ref or ref.get("owner") != ag["agent_id"]:
                    raise HTTPException(404, "unknown reference")
                take_profile = _rf.measure_file(src)
                ref_curve = _rf.match_curve(take_profile["bands"],
                                            ref["profile"]["bands"])
            st = _proc.studio_master(src, out_dir, preset, ref_curve)
            assets.update(st)
            stx = _transcribe_file(st["studio.wav"])
            integrity = _proc.integrity_check(src, st["studio.wav"],
                                             tx.get("text", ""), stx.get("text", ""))
            if not integrity["passed"]:
                c["pack_review"] = "manual_review"
        if tier == "clean":
            try:
                prov = _cl.veed_clean(src, os.path.join(out_dir, "clean.wav"))
            except _cl.ProviderUnavailable as e:
                raise HTTPException(501, str(e))
            cp = _run_mp3(os.path.join(out_dir, "clean.wav"), out_dir, "clean")
            assets.update(cp)
            assets["chain"] = (f"veed/clean-audio target_lufs={prov['target_lufs']},"
                               "mp3-export")
            assets["provider"] = prov
            ctx = _transcribe_file(os.path.join(out_dir, "clean.wav"))
            integrity = _proc.integrity_check(src, os.path.join(out_dir, "clean.wav"),
                                              tx.get("text", ""), ctx.get("text", ""))
            if not integrity["passed"]:
                c["pack_review"] = "manual_review"
        manifest = _pk.build_manifest(c, sha, assets, tx.get("text", ""),
                                      segments, fee["processing_fee_usd"],
                                      tier, preset, integrity)
        manifest["source"] = "assembled_master" if (c.get("assembly") or {}).get(
            "master_sha256") == sha else "single_submission"
        manifest["edit_map"] = (c.get("assembly") or {}).get("edit_map", [])
        manifest["session"] = c.get("session") or {}
        if ref_id:
            manifest["reference_id"] = ref_id
        # A preset is settings + versions: engine, full chain, match flag.
        _pset = assets.get("preset") or {}
        _prov = assets.get("provider")
        manifest["processing"] = {
            "engine": _pset.get("engine") or _pr.ENGINE_VERSION,
            "chain": assets.get("chain", ""),
            "preset_settings": _pset or {"tier": tier},
            "reference_matched": bool(assets.get("reference_matched")),
            "denoise_backend": "afftdn" if not _prov else _prov.get("model", ""),
            "provider": _prov or {"provider": "local"},
        }
        if ref_id:
            manifest["reference_id"] = ref_id
        # original take(s) stay fetchable as evidence: resolve raw or assembled bytes
        _raw = str(_P(UPL.RAW_DIR, sha + ".wav"))
        _asm = os.path.join(os.getenv("HV_PACK_DIR", "data/packs"), cid, "assembled.wav")
        _opath = _raw if os.path.exists(_raw) else (_asm if os.path.exists(_asm) else "")
        if _opath:
            manifest["files"]["original.wav"] = {"sha256": sha,
                                                 "bytes": os.path.getsize(_opath)}
    except _proc.ProcessingError as e:
        raise HTTPException(502, str(e))
    for name, path in assets.items():
        if not isinstance(path, str) or not os.path.isfile(path):
            continue  # measured stats / chain descriptions, not deliverables
        DB.save_asset({"sha256": _proc.sha_file(path), "contract_id": cid,
                       "kind": name, "path": path})
    c["pack"] = {"tier": tier, "manifest": manifest,
                 "fee_usd": fee["processing_fee_usd"],
                 "fee_note": fee["note"]}
    DB.save_contract(c)
    _ev(cid, "pack.built", {"tier": tier, "fee_usd": fee["processing_fee_usd"],
                            "files": sorted(manifest["files"])}, ag["agent_id"], "agent")
    return {"manifest": manifest, "processing_fee": fee}


@app.get("/v1/contracts/{cid}/pack")
def get_pack(cid: str, x_hv_session: str | None = Header(None),
             x_hv_agent_key: str | None = Header(None)):
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    c = _party_only(cid, nid, aid)
    if not c.get("pack"):
        raise HTTPException(404, "no pack built yet")
    return c["pack"]


@app.get("/v1/contracts/{cid}/pack/download")
def download_asset(cid: str, asset: str = "", x_hv_session: str | None = Header(None),
                   x_hv_agent_key: str | None = Header(None)):
    from fastapi.responses import Response as _Resp
    from pathlib import Path as _P
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    c = _party_only(cid, nid, aid)
    pack = c.get("pack") or {}
    files = (pack.get("manifest") or {}).get("files") or {}
    if asset not in files:
        raise HTTPException(404, "unknown asset in this pack")
    # Party-scoped deliverables only: asset names come from the manifest,
    # never from free-form paths.
    if asset == "original.wav":
        cand = str(_P(UPL.RAW_DIR, pack["manifest"]["original_sha256"] + ".wav"))
        fpath = cand if os.path.exists(cand) else os.path.join(
            os.getenv("HV_PACK_DIR", "data/packs"), cid, "assembled.wav")
    else:
        fpath = os.path.join(os.getenv("HV_PACK_DIR", "data/packs"), cid, asset)
    if not os.path.exists(fpath):
        raise HTTPException(404, "asset bytes missing")
    media = "audio/wav" if asset.endswith(".wav") else (
        "audio/mpeg" if asset.endswith(".mp3") else "application/octet-stream")
    return _Resp(open(fpath, "rb").read(), media_type=media,
                 headers={"Content-Disposition": f"attachment; filename={asset}"})


# ---------- modular capture: passages, takes, assembly ----------

def _seg_state(c: dict, seg: str) -> dict:
    st = (c.get("segments_state") or {}).get(seg)
    if not st:
        raise HTTPException(404, "unknown segment")
    return st


def _can_read(cid: str, nid: str | None, aid: str | None) -> dict:
    """Party contract, or an offered narrator reviewing the job."""
    try:
        return _party_only(cid, nid, aid)
    except Exception:
        if nid and DB.is_offered(cid, nid):
            return DB.get_contract(cid)
        raise


@app.get("/v1/contracts/{cid}/segments")
def get_segments(cid: str, x_hv_session: str | None = Header(None),
                 x_hv_agent_key: str | None = Header(None)):
    from hv import pace as _pace
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    c = _can_read(cid, nid, aid)
    if not c:
        raise HTTPException(404, "unknown contract")
    wpm = _pace.narrator_wpm(DB.get_narrator(nid) or {}) if nid else _pace.DEFAULT_WPM
    segs = []
    for s in (c.get("segment_manifest") or {}).get("segments", []):
        segs.append({**s, "read": _pace.feasibility(s, wpm)})
    return {"manifest": c.get("segment_manifest"), "state": c.get("segments_state"),
            "passages": segs, "pace_wpm": wpm}


@app.post("/v1/contracts/{cid}/segments/{seg}/takes")
async def record_take(cid: str, seg: str, request: Request,
                      x_hv_session: str | None = Header(None)):
    """One passage take. Failed attempts are kept as capture evidence —
    a recording record, not a proof-of-humanity claim."""
    nid = _narrator(x_hv_session)
    c = DB.get_contract(cid)
    if not c or c.get("narrator_id") != nid:
        raise HTTPException(403, "only the assigned narrator records takes")
    if c.get("status") not in ("accepted", "in_correction"):
        raise HTTPException(409, "contract not recording")
    st = _seg_state(c, seg)
    body: bytes = await request.body()
    if len(body) > MAX_UPLOAD_BYTES or len(body) < 44 or body[:4] != b"RIFF":
        raise HTTPException(422, "send WAV bytes under 50MB")
    try:
        receipt = UPL.store_upload(body, f"take:{cid}:{seg}")
    except ValueError as e:
        raise HTTPException(422, str(e))
    DB.record_upload(receipt["sha256"], cid, nid, receipt["bytes"])
    take = {"sha256": receipt["sha256"], "bytes": receipt["bytes"],
            "attempt": len(st["takes"]) + 1, "at": utcnow_now()}
    st["takes"].append(take)
    st["needs_retake"] = False
    c.setdefault("session", {}).setdefault("takes", 0)
    c["session"]["takes"] += 1
    DB.save_contract(c)
    _ev(cid, "take.recorded", {"seg": seg, "attempt": take["attempt"],
                               "sha256": take["sha256"]}, nid, "narrator")
    return take


@app.post("/v1/contracts/{cid}/segments/{seg}/accept")
def accept_take(cid: str, seg: str, body: dict[str, Any],
                x_hv_session: str | None = Header(None)):
    nid = _narrator(x_hv_session)
    c = DB.get_contract(cid)
    if not c or c.get("narrator_id") != nid:
        raise HTTPException(403, "only the assigned narrator accepts takes")
    st = _seg_state(c, seg)
    sha = body.get("sha256", "")
    if not any(t["sha256"] == sha for t in st["takes"]):
        raise HTTPException(422, "unknown take for this passage")
    st["accepted"] = sha
    DB.save_contract(c)
    _ev(cid, "take.accepted", {"seg": seg, "sha256": sha}, nid, "narrator")
    return {"ok": True, "accepted": sha}


@app.post("/v1/contracts/{cid}/segments/{seg}/retake")
def flag_retake(cid: str, seg: str, body: dict[str, Any],
                x_hv_agent_key: str | None = Header(None)):
    ag = _agent(x_hv_agent_key)
    c = DB.get_contract(cid)
    if not c or c.get("agent_id") != ag["agent_id"]:
        raise HTTPException(403, "only the contracting agent flags retakes")
    st = _seg_state(c, seg)
    st["needs_retake"] = True
    st["retake_note"] = (body.get("note") or "")[:300]
    c.setdefault("session", {}).setdefault("retakes", 0)
    c["session"]["retakes"] += 1
    DB.save_contract(c)
    _ev(cid, "take.retake_requested", {"seg": seg, "note": st["retake_note"]},
        ag["agent_id"], "agent")
    return {"ok": True, "needs_retake": True}


@app.post("/v1/contracts/{cid}/assemble")
def assemble(cid: str, body: dict[str, Any],
             x_hv_session: str | None = Header(None),
             x_hv_agent_key: str | None = Header(None)):
    """Build the timeline master from accepted takes. Never time-stretches:
    hard-window overflow rejects with details for a shorter script/retake."""
    from hv import assembly as _as
    from hv import qc as _qc
    from pathlib import Path as _P
    nid, aid = _caller_ids(x_hv_session, x_hv_agent_key)
    c = DB.get_contract(cid)
    if not c:
        raise HTTPException(404, "unknown contract")
    if not ((nid and nid == c.get("narrator_id")) or (aid and aid == c.get("agent_id"))):
        raise HTTPException(403, "only contract parties assemble")
    if c.get("status") not in ("accepted", "in_correction"):
        raise HTTPException(409, "contract not recording")
    manifest = c.get("segment_manifest") or {"segments": []}
    state = c.get("segments_state") or {}
    missing = [s["id"] for s in manifest["segments"]
               if not (state.get(s["id"]) or {}).get("accepted")]
    if missing:
        raise HTTPException(409, "passages without accepted takes: " + ",".join(missing))
    take_paths = {}
    for s in manifest["segments"]:
        sha = state[s["id"]]["accepted"]
        fpath = str(_P(UPL.RAW_DIR, sha + ".wav"))
        if not _P(fpath).exists():
            raise HTTPException(422, f"take bytes missing for {s['id']}")
        take_paths[s["id"]] = fpath
    out_dir = os.path.join(os.getenv("HV_PACK_DIR", "data/packs"), cid)
    os.makedirs(out_dir, exist_ok=True)
    try:
        res = _as.assemble(manifest["segments"], take_paths,
                           os.path.join(out_dir, "assembled.wav"))
    except _as.AssemblyError as e:
        raise HTTPException(422, str(e))
    sub = {"submission_id": uid("sub_"), "sha256": res["master_sha256"],
           "bytes": os.path.getsize(res["path"]), "assembled": True,
           "version": c.get("submission_version", 0) + 1}
    c["submission_version"] = sub["version"]
    c["status"] = "submitted"
    c["assembly"] = res
    c.setdefault("session", {}).setdefault("assemblies", 0)
    c["session"]["assemblies"] += 1
    DB.save_contract(c)
    _ev(cid, "assembly.built", {"master": res["master_sha256"],
                                "total_ms": res["total_ms"],
                                "segments": len(res["edit_map"])},
        nid or aid or "?", "narrator" if nid else "agent")
    tech = _qc.tech_checks(res["path"])
    _ev(cid, "qc.completed", {"submission": sub["submission_id"], "technical": tech})
    sub["qc_technical"] = tech
    c["last_submission"] = sub
    DB.save_contract(c)
    return {"master": res["master_sha256"], "total_ms": res["total_ms"],
            "edit_map": res["edit_map"]}


@app.post("/v1/contracts/{cid}/direct")
def direct(cid: str, body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    """AI sound director: passage-level performance notes + production
    advice. Recommendations only — verify against ASR alignment and the
    original audio before any retake request or payment decision."""
    from hv import director as _dr
    ag = _agent(x_hv_agent_key)
    c = DB.get_contract(cid)
    if not c or c.get("agent_id") != ag["agent_id"]:
        raise HTTPException(403, "only the contracting agent directs")
    if c.get("status") not in ("submitted", "settled"):
        raise HTTPException(409, "nothing to review yet")
    script = DB.get_script(c.get("script_sha256", "")) or ""
    sub = c.get("last_submission") or {}
    sha = sub.get("sha256", "")
    from pathlib import Path as _P
    src = str(_P(UPL.RAW_DIR, sha + ".wav"))
    if not sha or not _P(src).exists():
        _mas = os.path.join(os.getenv("HV_PACK_DIR", "data/packs"), cid, "assembled.wav")
        src = _mas if os.path.exists(_mas) else ""
    if not src:
        raise HTTPException(422, "review audio missing server-side")
    tx = _transcribe_file(src)
    manifest = c.get("segment_manifest") or {"segments": []}
    acoustic = (sub.get("qc_technical") or {})
    try:
        review = _dr.direct(script, tx.get("text", ""), tx.get("segments") or [],
                            acoustic,
                            (manifest.get("direction") or {}).get("style", "")
                            if isinstance(manifest.get("direction"), dict)
                            else str(manifest.get("direction") or ""))
    except _dr.DirectorUnavailable as e:
        raise HTTPException(501, str(e))
    c["direction_review"] = review
    DB.save_contract(c)
    _ev(cid, "director.reviewed",
        {"accuracy": (review.get("performance_review") or {}).get("script_accuracy"),
         "issues": len((review.get("performance_review") or {}).get("suspected_issues", []))},
        ag["agent_id"], "agent")
    return review


# ---------- channels: the same voice, every episode ----------

@app.post("/v1/channels")
def create_channel(body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    """Save a channel voice: preferred narrator + preset + direction.
    A repeat relationship, not ownership: the narrator accepts or declines
    every offer, and nothing here permits cloning."""
    import re as _re
    ag = _agent(x_hv_agent_key)
    name = (body.get("name") or "").strip()
    if not _re.fullmatch(r"[A-Za-z0-9 _.-]{2,60}", name):
        raise HTTPException(422, "name must be 2-60 chars")
    nid = body.get("narrator_id", "")
    if not nid or not DB.get_narrator(nid):
        raise HTTPException(422, "unknown narrator_id")
    preset_id = body.get("preset_id")
    if preset_id:
        _resolve_preset(preset_id, ag)  # 404 when unknown
    ref_id = body.get("reference_id")
    if ref_id:
        ref = DB.get_ref(ref_id)
        if not ref or ref.get("owner") != ag["agent_id"]:
            raise HTTPException(404, "unknown reference")
    doc = {"id": "ch_" + uid()[:12], "owner_agent": ag["agent_id"],
           "name": name, "narrator_id": nid, "preset_id": preset_id,
           "reference_id": ref_id,
           "direction": (body.get("direction") or "")[:500],
           "created": utcnow_now()}
    DB.save_channel(doc)
    _ev(doc["id"], "channel.saved", {"narrator": nid, "preset": preset_id},
        ag["agent_id"], "agent")
    return {"channel": doc}


@app.get("/v1/channels")
def list_channels(x_hv_agent_key: str | None = Header(None)):
    ag = _agent(x_hv_agent_key)
    return {"channels": DB.list_channels(ag["agent_id"])}


@app.post("/v1/channels/{chid}/rebook")
def rebook(chid: str, body: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    """New episode, same voice: funded contract offered to the saved
    narrator with the channel's preset attached. They can still decline."""
    ag = _agent(x_hv_agent_key)
    ch = DB.get_channel(chid)
    if not ch or ch.get("owner_agent") != ag["agent_id"]:
        raise HTTPException(404, "unknown channel")
    script = body.get("script_text", "")
    if not script.strip():
        raise HTTPException(422, "script_text required")
    brief = {"script_text": script,
             "delivery_seconds": int(body.get("delivery_seconds", 7200)),
             "tier": body.get("tier", "standard"),
             "brief": body.get("brief") or {"mode": "script"},
             "narrator_ids": [ch["narrator_id"]],
             "channel_id": chid,
             "channel_preset": ch.get("preset_id")}
    if ch.get("direction") and isinstance(brief["brief"], dict):
        brief["brief"] = {**brief["brief"],
                          "direction": {"style": ch["direction"]}}
    doc, funding, priced = _create_funded(ag, brief)
    _ev(doc["contract_id"], "channel.rebooked",
        {"channel": chid, "narrator": ch["narrator_id"]}, ag["agent_id"], "agent")
    return {"contract": doc, "funding": funding, "price": priced,
            "channel": ch["name"]}


# ---------- orders: draft → buyer_authorized → funded (never agent-only) ----------

ORDER_TTL_SECONDS = 24 * 3600


def _order_terms(brief: dict, priced: dict, script: str) -> dict:
    import json as _j
    return {"script_sha256": sha256(script),
            "words": len(script.split()),
            "minutes": priced["minutes"],
            "narrator_payout_usd": priced["narrator_payout"],
            "customer_price_usd": priced.get("customer_price"),
            "delivery_seconds": priced.get("delivery_seconds"),
            "tier": priced.get("tier", "standard"),
            "commercial_usage": brief.get("commercial_usage", "online_video"),
            "included_corrections": 1,
            "review_window_seconds": 86400,
            "voice_cloning_allowed": False}


@app.post("/v1/orders/draft")
def draft_order(brief: dict[str, Any], x_hv_agent_key: str | None = Header(None)):
    """Agent proposes; nothing is funded. Returns terms + approval URL for
    the paying human. Funding happens only after buyer authorization."""
    import json as _j
    import secrets as _s
    ag = _agent(x_hv_agent_key)
    script = brief.get("script_text", "")
    c, priced = _quote_for(brief, ag)  # validates + budget-checks, reserves nothing
    terms = _order_terms(brief, {**priced,
                                 "delivery_seconds": c.delivery_seconds,
                                 "tier": brief.get("tier", "standard")}, script)
    token = _s.token_urlsafe(32)
    oid = "hvo_" + uid()[:12]
    now = _dt.datetime.now(_dt.timezone.utc)
    doc = {"order_id": oid, "status": "awaiting_buyer_approval",
           "agent_id": ag["agent_id"], "principal_id": ag["principal_id"],
           "brief": {k: brief.get(k) for k in ("script_text", "tier", "delivery_seconds",
                                              "narrator_ids", "brief", "commercial_usage")},
           "quote": terms, "terms_hash": sha256(_j.dumps(terms, sort_keys=True)),
           "token_hash": sha256(token),
           "budget": {"max_job_minor": ag["max_job_minor"],
                      "max_daily_minor": ag.get("max_daily_minor", 10 ** 12)},
           "expires_at": (now + _dt.timedelta(seconds=ORDER_TTL_SECONDS)).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "approval": None, "contract_id": None}
    DB.save_order(doc)
    _ev(oid, "order.drafted", {"terms_hash": doc["terms_hash"],
                               "total_usd": terms["customer_price_usd"]},
        ag["agent_id"], "agent")
    return {"order_id": oid, "status": doc["status"], "quote": terms,
            "terms_hash": doc["terms_hash"], "expires_at": doc["expires_at"],
            "approval_url": f"https://humanvoiced.com/order.html?o={oid}&t={token}",
            "approval_token": token,
            "note": "deliver the approval URL to the paying human privately; "
                    "nothing is funded until they approve"}


@app.get("/v1/orders/{oid}")
def get_order(oid: str, t: str = ""):
    """Approval-URL view: bearer token reveals the frozen terms. No token,
    no terms — order IDs alone disclose nothing."""
    o = DB.get_order(oid)
    if not o or o.get("token_hash") != sha256(t or ""):
        raise HTTPException(404, "unknown order")
    return {"order_id": oid, "status": o["status"], "quote": o["quote"],
            "terms_hash": o["terms_hash"], "expires_at": o["expires_at"],
            "approval": o.get("approval"),
            "contract_id": o.get("contract_id")}


@app.post("/v1/orders/{oid}/approve")
def approve_order(oid: str, body: dict[str, Any],
                  x_hv_session: str | None = Header(None)):
    """Buyer authorization: bearer token + frozen terms hash + expiry, then
    spend is reserved and the funded contract is created and offered.
    Server-enforced; agents cannot self-approve."""
    o = DB.get_order(oid)
    if not o or o.get("token_hash") != sha256(body.get("token", "")):
        raise HTTPException(404, "unknown order")
    if o["status"] != "awaiting_buyer_approval":
        raise HTTPException(409, "order already " + o["status"])
    if body.get("terms_hash") != o["terms_hash"]:
        raise HTTPException(409, "terms changed since draft — request a fresh order")
    try:
        exp = _dt.datetime.strptime(o["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=_dt.timezone.utc)
    except Exception:
        raise HTTPException(410, "order expired")
    if _dt.datetime.now(_dt.timezone.utc) > exp:
        o["status"] = "expired"
        DB.save_order(o)
        raise HTTPException(410, "order expired")
    ag = {"agent_id": o["agent_id"], "principal_id": o["principal_id"],
          "max_job_minor": o["budget"]["max_job_minor"],
          "max_daily_minor": o["budget"]["max_daily_minor"]}
    nid = SESS.narrator_for(x_hv_session or "") if x_hv_session else None
    doc, funding, priced = _create_funded(ag, o["brief"])
    now = utcnow_now()
    o["status"] = "authorized"
    o["approval"] = {"by": nid or "bearer-token-holder", "at": now,
                     "terms_hash": o["terms_hash"], "version": 1}
    o["contract_id"] = doc["contract_id"]
    o["funding"] = funding
    DB.save_order(o)
    _ev(oid, "order.authorized", {"by": o["approval"]["by"],
                                  "contract": doc["contract_id"]},
        nid or "buyer", "narrator" if nid else "buyer")
    return {"order_id": oid, "status": "authorized",
            "contract_id": doc["contract_id"], "funding": funding,
            "price": priced}
