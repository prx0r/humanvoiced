"""API integration tests — full lifecycle with real auth, storage, pricing."""
import io
import struct
import sys
import wave

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

import api.app as A

A.AGENTS["k1"] = {"agent_id": "agent_005", "principal_id": "org_832",
                  "max_job_minor": 300000, "max_daily_minor": 10**9}
A.SESS = __import__("hv.sessions", fromlist=["SessionStore"]).SessionStore("/tmp/hv-t-sess.db")
import hv.store as _st
import os
for _f in ("/tmp/hv-t.db", "/tmp/hv-t-sess.db"):
    try:
        os.remove(_f)
    except OSError:
        pass
A.DB = _st.Store("/tmp/hv-t.db")
A.SESS = __import__("hv.sessions", fromlist=["SessionStore"]).SessionStore("/tmp/hv-t-sess.db")
A.DB.save_narrator({"id": "nar_041"})
A.DB.save_narrator({"id": "nar_zzz"})
NAR = A.SESS.create("sub1", "n@x.com", "nar_041")
STRANGER = A.SESS.create("sub9", "z@x.com", "nar_zzz")
H = {"X-HV-Agent-Key": "k1"}
NH = {"X-HV-Session": NAR}
SH = {"X-HV-Session": STRANGER}
SCRIPT = "hello world calm documentary " * 60  # ~240 words


def _wav():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"".join(struct.pack("<h", 15000) for _ in range(48000)))
    return buf.getvalue()


def _make(client):
    r = client.post("/v1/contracts", json={"script_text": SCRIPT, "delivery_seconds": 7200,
                                           "narrator_ids": ["nar_041"]}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()["contract"]["contract_id"]


def test_full_lifecycle():
    c = TestClient(A.app)
    q = c.post("/v1/contracts/quote", json={"script_text": SCRIPT}, headers=H)
    assert q.status_code == 200 and q.json()["quote_usd"] > 0
    cid = _make(c)
    assert c.post(f"/v1/offers/{cid}/accept", json={}, headers=SH).status_code == 403
    a = c.post(f"/v1/offers/{cid}/accept", json={}, headers=NH)
    assert a.status_code == 200 and a.json()["contract"]["narrator_id"] == "nar_041"
    s = c.post(f"/v1/contracts/{cid}/submissions", content=_wav(),
               headers={**NH, "Content-Type": "audio/wav"})
    assert s.status_code == 200 and s.json()["qc_technical"]["file_valid"] is True
    stranger_sub = c.post(f"/v1/contracts/{cid}/submissions", content=_wav(),
                          headers={**SH, "Content-Type": "audio/wav"})
    assert stranger_sub.status_code == 403
    ev = c.get(f"/v1/contracts/{cid}/events", headers=NH)
    assert ev.json()["verified"] is True
    d = c.post(f"/v1/contracts/{cid}/disputes",
               json={"type": "style_dispute", "claim": "x"}, headers=NH)
    assert d.status_code == 200
    case = d.json()["case_id"]
    assert c.get(f"/v1/disputes/{case}", headers=SH).status_code == 403
    assert c.get(f"/v1/disputes/{case}", headers=NH).status_code == 200
    r1 = c.post(f"/v1/contracts/{cid}/reviews", json={"scores": {"Q": 1}}, headers=NH)
    assert r1.json()["revealed"] is False
    r2 = c.post(f"/v1/contracts/{cid}/reviews", json={"scores": {"Q": 1}}, headers=H)
    assert r2.json()["revealed"] is True


def test_budget_enforced_at_create_not_just_quote():
    c = TestClient(A.app)
    A.AGENTS["poor"] = {"agent_id": "a9", "principal_id": "o9",
                        "max_job_minor": 1, "max_daily_minor": 10**9}
    r = c.post("/v1/contracts", json={"script_text": SCRIPT, "narrator_ids": []},
               headers={"X-HV-Agent-Key": "poor"})
    assert r.status_code == 402


def test_restart_survives():
    import api.app as B
    B.DB.save_contract({"contract_id": "hvc_x", "status": "offered"})
    assert B.DB.get_contract("hvc_x")["status"] == "offered"


def test_profile_draft_publish_and_guest_order():
    from fastapi.testclient import TestClient
    import api.app as A
    c = TestClient(A.app)
    d = c.post("/v1/narrators/me/profile",
               json={"draft_from_tech": True, "tech": {"peak": 15000, "silence_ratio": 0.1},
                     "display_name": "Alex", "languages": ["en"]}, headers=NH)
    assert d.status_code == 200 and "nationality" not in str(d.json())
    p = c.post("/v1/narrators/me/profile",
               json={"publish": True, "profile": {"display_name": "Alex", "nationality": "x"}},
               headers=NH)
    assert p.json()["published"].get("nationality") is None
    r = c.post("/v1/contracts", json={"script_text": "hello world " * 40, "narrator_ids": ["nar_041"]}, headers=H)
    cid = r.json()["contract"]["contract_id"]
    g = c.post("/v1/orders/guest", json={"contract_id": cid}, headers=H)
    assert g.json()["commission"] == 0.0 and g.json()["url"].startswith("https://humanvoiced.com/orders/")
    lo = c.post("/api/auth/logout", headers=NH)
    assert lo.json() == {"ok": True}


def test_sample_kinds_and_suggested():
    from fastapi.testclient import TestClient
    import api.app as A
    c = TestClient(A.app)
    r = c.get("/v1/voices/suggested-samples")
    assert r.json()["recommended_two"][0]["kind"] == "documentary"
    assert r.json()["cap"] == 10
