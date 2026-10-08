"""hv_narrator MCP server — stdio JSON-RPC 2.0 over the REAL engine.

Search ranks published narrators, quotes price server-side, and drafts
return an approval URL for the paying human — the agent proposes, the
human approves, the narrator accepts. Agent keys validate against the
same hashed store as the HTTP API (durable across restarts).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from hv import reputation as R
from hv.ledger import EventLedger
from hv.store import Store
from hv.util import sha256, uid

DB = Store(os.getenv("HV_DB", "data/hv.db"))
LED = EventLedger(os.getenv("HV_EVENTS_DB", "data/hv-events.db"))

TOOLS = [
    {"name": "hv.voices.search",
     "description": "Ranked search over published narrators; new voices get exploration allocation"},
    {"name": "hv.pricing.quote",
     "description": "Server-side quote from frozen script word count; narrator gets 100%"},
    {"name": "hv.contract.draft",
     "description": "Draft order (nothing funded) + approval URL for the paying human"},
    {"name": "hv.contract.status",
     "description": "Contract state + receipt for the contracting agent"},
    {"name": "hv.reputation.get",
     "description": "R_n outcome vector (Q,D,A,S,C) + windows + appeals"},
    {"name": "hv.disputes.get_rules",
     "description": "Published rule IDs (PAY/SLA/QC/REV/DIS/REP) — agents cite, never invent"},
    {"name": "hv.casting.search",
     "description": "Multi-role cast list: roles with sides matched to character profiles"},
]
COMING = ["hv.voices.compare", "hv.portfolio.get", "hv.contract.events",
          "hv.support.ask"]


def _agent(args: dict) -> dict:
    import datetime as _dt
    key = args.get("agent_key", "")
    doc = DB.get_agent(sha256(key)) if key else None
    if not doc:
        raise ValueError("unknown agent key")
    return doc


def _quote(script: str, tier: str, ag: dict) -> dict:
    from hv import pricing as _p
    minutes = max(0.25, len(script.split()) / 150.0)
    q = _p.quote(minutes, tier=tier)
    if q["customer_price"] * 100 > ag["max_job_minor"]:
        raise ValueError("exceeds agent max_job budget")
    return {"minutes": round(minutes, 2), **q}


def handle(method: str, params: dict) -> dict:
    if method == "tools/list":
        return {"tools": TOOLS}
    if method != "tools/call":
        return {"error": "unknown method"}
    name, args = params.get("name"), params.get("arguments", {})
    try:
        if name == "hv.voices.search":
            from hv import catalog as _cat
            body = {"job": args.get("job", {}),
                    "preferences": args.get("preferences", {}),
                    "limit": args.get("limit", 5)}
            catalog = []
            for n in DB.list_narrators():
                if not n.get("profile_published"):
                    continue
                catalog.append({"voice_id": n["id"], "handle": n.get("handle", ""),
                                "languages": n.get("languages", []),
                                "capabilities": {"declared": n.get("prefs", {}).get("categories", []),
                                                 "demonstrated": []},
                                "availability": {"accepting_offers": True,
                                                 "max_minutes_per_job": 60},
                                "match_features": n.get("match_features", {}),
                                "reliability": n.get("reliability")})
            return {"result": {"matches": _cat.search(catalog, body, body["limit"])}}
        if name == "hv.pricing.quote":
            ag = _agent(args)
            script = args.get("script_text", "")
            if not script.strip():
                return {"error": "script_text required"}
            return {"result": _quote(script, args.get("tier", "standard"), ag)}
        if name == "hv.contract.draft":
            import datetime as _dt
            import secrets as _s
            ag = _agent(args)
            script = args.get("script_text", "")
            if not script.strip():
                return {"error": "script_text required"}
            priced = _quote(script, args.get("tier", "standard"), ag)
            terms = {"script_sha256": sha256(script),
                     "words": len(script.split()), "minutes": priced["minutes"],
                     "narrator_payout_usd": priced["narrator_payout"],
                     "customer_price_usd": priced.get("customer_price"),
                     "delivery_seconds": int(args.get("delivery_seconds", 7200)),
                     "tier": args.get("tier", "standard"),
                     "included_corrections": 1, "voice_cloning_allowed": False}
            token = _s.token_urlsafe(32)
            oid = "hvo_" + uid()[:12]
            now = _dt.datetime.now(_dt.timezone.utc)
            exp = (now + _dt.timedelta(seconds=24 * 3600)).strftime("%Y-%m-%dT%H:%M:%SZ")
            DB.save_order({"order_id": oid, "status": "awaiting_buyer_approval",
                           "agent_id": ag["agent_id"], "principal_id": ag["principal_id"],
                           "brief": {"script_text": script,
                                     "tier": args.get("tier", "standard"),
                                     "delivery_seconds": terms["delivery_seconds"],
                                     "narrator_ids": args.get("narrator_ids", [])},
                           "quote": terms,
                           "terms_hash": sha256(json.dumps(terms, sort_keys=True)),
                           "token_hash": sha256(token),
                           "budget": {"max_job_minor": ag["max_job_minor"],
                                      "max_daily_minor": ag.get("max_daily_minor", 10 ** 12)},
                           "expires_at": exp,
                           "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "approval": None, "contract_id": None})
            LED.append(oid, "order.drafted", {"via": "mcp"}, ag["agent_id"], "agent")
            return {"result": {
                "order_id": oid, "quote": terms,
                "approval_url": f"https://humanvoiced.com/order.html?o={oid}&t={token}",
                "note": "nothing funded — the paying human approves at the URL"}}
        if name == "hv.contract.status":
            ag = _agent(args)
            c = DB.get_contract(args.get("contract_id", ""))
            if not c or c.get("agent_id") != ag["agent_id"]:
                return {"error": "unknown contract for this agent"}
            return {"result": {"contract_id": c["contract_id"], "status": c.get("status"),
                               "narrator_id": c.get("narrator_id"),
                               "settlement": c.get("settlement"),
                               "pack": bool(c.get("pack"))}}
        if name == "hv.reputation.get":
            nid = args.get("narrator_id", "")
            doc = DB.get_narrator(nid) or {}
            saved = doc.get("reputation") or {}
            r = R.ReputationVector(nid)
            r.completed = int(saved.get("completed", 0))
            for d in R.DIMENSIONS:
                r.vector[d] = (saved.get("vector") or {}).get(d)
            return {"result": r.to_dict()}
        if name == "hv.disputes.get_rules":
            from hv import dispute_rules as _dr
            return {"result": _dr.RULES}
        if name == "hv.casting.search":
            from hv import casting as _c
            roles = [_c.role(args.get("project", ""), r.get("character", ""),
                             r.get("side_text", ""), r.get("voice_reqs", {}))
                     for r in args.get("roles", [])]
            return {"result": _c.cast_list(args.get("project", ""), roles,
                                           args.get("catalog", []))}
        if name in COMING:
            return {"error": f"tool {name} tracked, not yet implemented"}
        return {"error": f"unknown tool {name}"}
    except ValueError as e:
        return {"error": str(e)}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle(req.get("method", ""), req.get("params", {}))
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": res}) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": str(e)[:200]}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
