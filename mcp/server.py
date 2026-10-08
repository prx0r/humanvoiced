"""hv_narrator MCP server — stdio JSON-RPC 2.0. Read tools live first.

Mutations (create/accept/submit/dispute) arrive with agent keys + idempotency
in later milestones; the tool table already reserves their names.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from hv import reputation as R

TOOLS = [
    {"name": "hv.voices.search", "description": "Ranked narrator search (M(n,j)); New voices get exploration allocation"},
    {"name": "hv.portfolio.get", "description": "Public portfolio: consented samples, windowed stats with sample counts"},
    {"name": "hv.reputation.get", "description": "R_n outcome vector (Q,D,A,S,C) + windows + appeals"},
    {"name": "hv.contract.get", "description": "Frozen contract terms + hashes + status"},
    {"name": "hv.contract.events", "description": "Append-only lifecycle history for a contract"},
]


def handle(method: str, params: dict) -> dict:
    if method == "tools/list":
        return {"tools": TOOLS}
    if method != "tools/call":
        return {"error": "unknown method"}
    name, args = params.get("name"), params.get("arguments", {})
    if name == "hv.reputation.get":
        r = R.ReputationVector(args.get("narrator_id", "nar_demo"))
        return {"result": r.to_dict()}
    if name == "hv.voices.search":
        feats = args.get("features", {"VoiceFit": 0.8, "Reliability": 0.7,
                                      "Availability": 1.0, "PriceFit": 0.9, "Preferences": 0.8})
        return {"result": {"match": R.match_score(feats), "weights": R.MATCH_WEIGHTS}}
    return {"error": f"tool {name} reserved for funded milestone"}


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
