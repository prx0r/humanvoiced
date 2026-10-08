"""API integration tests — full lifecycle through HTTP."""
import sys
sys.path.insert(0, ".")

from fastapi.testclient import TestClient

from api.app import AGENTS, HANDLES, SESS, app

AGENTS["k1"] = {"agent_id": "agent_005", "principal_id": "org_832", "max_job_minor": 3000}
NAR_TOKEN = SESS.create("sub_owner_1", "owner@example.com", "nar_041")
H = {"X-HV-Agent-Key": "k1"}
NH = {"X-HV-Session": NAR_TOKEN}
BRIEF = {"script_text": "hello world calm documentary", "payout_usd": 12,
         "delivery_seconds": 7200, "commercial_usage": "online_video"}


def test_full_lifecycle():
    c = TestClient(app)
    q = c.post("/v1/contracts/quote", json=BRIEF, headers=H)
    assert q.status_code == 200, q.text
    r = c.post("/v1/contracts", json=BRIEF, headers=H)
    assert r.status_code == 200, r.text
    cid = r.json()["contract"]["contract_id"]
    a = c.post(f"/v1/offers/{cid}/accept", json={}, headers=NH)
    assert a.status_code == 200, a.text
    assert a.json()["contract"]["deadline_at"] > a.json()["contract"]["accepted_at"]
    assert a.json()["contract"]["narrator_id"] == "nar_041"
    import struct
    import wave
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"".join(struct.pack("<h", 15000) for _ in range(48000)))
    s = c.post(f"/v1/contracts/{cid}/submissions", content=buf.getvalue(),
               headers={**NH, "Content-Type": "audio/wav"})
    assert s.status_code == 200, s.text
    assert s.json()["qc_technical"]["file_valid"] is True
    ev = c.get(f"/v1/contracts/{cid}/events")
    assert ev.json()["verified"] is True
    types = [e["event_type"] for e in ev.json()["events"]]
    assert types == ["contract.created", "payment.secured", "offer.accepted",
                     "contract.activated", "submission.received", "qc.completed"]
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
    d = c.post(f"/v1/offers/{cid}/decline", json={}, headers=NH)
    assert d.json() == {"ok": True, "penalty": "none"}
    bad = c.post(f"/v1/offers/{cid}/accept", json={})
    assert bad.status_code == 401  # no session, no accept
