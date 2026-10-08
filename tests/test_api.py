"""API integration tests — full lifecycle through HTTP."""
import sys
sys.path.insert(0, ".")

from fastapi.testclient import TestClient

from api.app import AGENTS, app

AGENTS["k1"] = {"agent_id": "agent_005", "principal_id": "org_832", "max_job_minor": 3000}
H = {"X-HV-Agent-Key": "k1"}
BRIEF = {"script_text": "hello world calm documentary", "payout_usd": 12,
         "delivery_seconds": 7200, "commercial_usage": "online_video"}


def test_full_lifecycle():
    c = TestClient(app)
    q = c.post("/v1/contracts/quote", json=BRIEF, headers=H)
    assert q.status_code == 200, q.text
    r = c.post("/v1/contracts", json=BRIEF, headers=H)
    assert r.status_code == 200, r.text
    cid = r.json()["contract"]["contract_id"]
    a = c.post(f"/v1/offers/{cid}/accept", json={"narrator_id": "nar_041"})
    assert a.status_code == 200, a.text
    assert a.json()["contract"]["deadline_at"] > a.json()["contract"]["accepted_at"]
    s = c.post(f"/v1/contracts/{cid}/submissions", json={"sha256": "a" * 64})
    assert s.status_code == 200, s.text
    ev = c.get(f"/v1/contracts/{cid}/events")
    assert ev.json()["verified"] is True
    types = [e["event_type"] for e in ev.json()["events"]]
    assert types == ["contract.created", "payment.secured", "offer.accepted",
                     "contract.activated", "submission.received"]
    d = c.post(f"/v1/contracts/{cid}/disputes",
               json={"type": "style_dispute", "claim": "not energetic"}, headers=H)
    assert d.status_code == 200
    assert d.json()["status"] == "open"


def test_budget_gate_and_decline_free():
    c = TestClient(app)
    big = dict(BRIEF, payout_usd=5000)
    assert c.post("/v1/contracts/quote", json=big, headers=H).status_code == 402
    r = c.post("/v1/contracts", json=BRIEF, headers=H)
    cid = r.json()["contract"]["contract_id"]
    d = c.post(f"/v1/offers/{cid}/decline", json={"narrator_id": "nar_9"})
    assert d.json() == {"ok": True, "penalty": "none"}
