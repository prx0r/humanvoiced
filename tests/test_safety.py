"""Content policy + consent: tiers, prefs, acceptance, reports, review."""
import os
import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

import api.app as A

A.ALLOW_SIMULATED = True
os.environ["HV_ADMIN_TOKEN"] = "test-admin"

import tempfile as _tf
_tmp = _tf.mkdtemp(prefix="hv-sf-")
import hv.ledger as _led
A.led = _led.EventLedger(_tmp + "/ev.db")
import hv.upload as _upl
_upl.RAW_DIR = _tmp + "/audio"


def _client(tmp_path):
    import hv.store as _st
    A.DB = _st.Store(str(tmp_path / "sf.db"))
    from hv.sessions import SessionStore
    A.SESS = SessionStore(str(tmp_path / "sf-sess.db"))
    A.AGENTS.clear()
    A.AGENTS["k1"] = {"agent_id": "ag1", "principal_id": "org1",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    return TestClient(A.app)


def _mk(c, H, script, nids, **kw):
    A.DB.save_narrator({"id": nids[0]})
    body = {"script_text": script, "narrator_ids": nids}
    body.update(kw)
    return c.post("/v1/contracts", json=body, headers=H)


def test_tiers_and_prohibited_refused(tmp_path):
    from hv import content as _ct
    assert _ct.classify("A calm documentary about rivers.")["tier"] == "general"
    assert _ct.classify("What the fuck happened here?")["flags"] == ["strong_language"]
    doc = _ct.classify("An erotic audio story for your sexual gratification tonight.")
    assert doc["tier"] == "restricted"
    soft = _ct.classify("A documentary about sexual assault awareness and trials.")
    assert soft["tier"] == "mature"
    bad = _ct.classify("An intimate story about a young teen girl in bed.")
    assert bad["tier"] == "prohibited"
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    r = _mk(c, H, "An intimate story about a young teen girl in bed.", ["nar_x"])
    assert r.status_code == 422 and "prohibited" in r.text


def test_restricted_held_for_review(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_r1"})
    r = _mk(c, H, "An erotic audio story for your sexual gratification tonight.", ["nar_r1"])
    assert r.status_code == 200
    cid = r.json()["contract"]["contract_id"]
    doc = A.DB.get_contract(cid)
    assert doc["status"] == "needs_review" and doc["funding_status"] != "secured"
    assert r.json()["funding"] == ""
    tok = A.SESS.create("sr", "r@x", "nar_r1")
    assert c.post(f"/v1/offers/{cid}/accept", json={},
                  headers={"X-HV-Session": tok}).status_code in (403, 409)
    ad = {"admin_token": "test-admin", "contract_id": cid, "decision": "approve"}
    assert c.post("/v1/admin/review", json={**ad, "admin_token": "wrong"}).status_code == 403
    ok = c.post("/v1/admin/review", json=ad)
    assert ok.status_code == 200 and ok.json()["status"] == "offered"
    assert c.post(f"/v1/offers/{cid}/accept", json={},
                  headers={"X-HV-Session": tok}).status_code == 200


def test_prefs_filter_and_acceptance(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_ok"})
    A.DB.save_narrator({"id": "nar_no",
                        "prefs": {"content": {"horror": False}}})
    r = _mk(c, H, "A haunted gore house slasher story. " * 10, ["nar_ok", "nar_no"])
    assert r.status_code == 200
    cid = r.json()["contract"]["contract_id"]
    assert A.DB.is_offered(cid, "nar_ok") is True
    assert A.DB.is_offered(cid, "nar_no") is False  # opted out, never sees it
    tok = A.SESS.create("so", "o@x", "nar_ok")
    a = c.post(f"/v1/offers/{cid}/accept", json={}, headers={"X-HV-Session": tok})
    assert a.status_code == 200
    acc = a.json()["contract"]["talent_acceptance"]
    assert acc["accepted_by"] == "nar_ok" and acc["contract_version"] == 1
    assert len(acc["terms_sha256"]) == 64 and "voluntarily accept" in acc["statement"]


def test_report_blocks_settlement_until_cleared(tmp_path):
    import io, struct, wave
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_s1"})
    r = _mk(c, H, "hello world " * 40, ["nar_s1"])
    cid = r.json()["contract"]["contract_id"]
    tok = A.SESS.create("ss", "s@x", "nar_s1")
    NH = {"X-HV-Session": tok}
    c.post(f"/v1/offers/{cid}/accept", json={}, headers=NH)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"".join(struct.pack("<h", 15000) for _ in range(48000)))
    c.post(f"/v1/contracts/{cid}/submissions", content=buf.getvalue(),
           headers={**NH, "Content-Type": "audio/wav"})
    rep = c.post(f"/v1/contracts/{cid}/report",
                 json={"reason": "misrepresented", "detail": "script changed?"}, headers=NH)
    assert rep.status_code == 200
    assert c.post(f"/v1/contracts/{cid}/approve", json={}, headers=H).status_code == 409
    assert c.post(f"/v1/contracts/{cid}/pack", json={}, headers=H).status_code == 409
    clr = c.post("/v1/admin/review", json={"admin_token": "test-admin",
                                           "contract_id": cid, "decision": "clear"})
    assert clr.status_code == 200
    assert c.post(f"/v1/contracts/{cid}/approve", json={}, headers=H).status_code == 200


def test_exclusive_buyout_default(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_b1"})
    r = _mk(c, H, "hello world " * 40, ["nar_b1"])
    assert r.status_code == 200
    doc = r.json()["contract"]
    rights = doc["rights"]
    assert rights["model"] == "exclusive_commercial_buyout"
    assert rights["exclusive"] is True and rights["territory"] == "worldwide"
    assert rights["performer_resale"] is False and rights["platform_resale"] is False
    assert rights["portfolio_use"] is False and rights["ai_training"] is False
    assert rights["covers"] == "approved_deliverables_only"
    # order terms carry the model too
    d = c.post("/v1/orders/draft", json={"script_text": "hello world " * 40,
                                         "narrator_ids": ["nar_b1"]}, headers=H)
    assert d.json()["quote"]["rights_model"] == "exclusive_commercial_buyout"
    assert d.json()["quote"]["exclusive_to_buyer"] is True
