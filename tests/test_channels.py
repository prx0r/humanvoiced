"""Channels: same voice every episode, narrator still free to decline."""
import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

import api.app as A

A.ALLOW_SIMULATED = True

import tempfile as _tf
_tmp = _tf.mkdtemp(prefix="hv-ch-")
import hv.ledger as _led
A.led = _led.EventLedger(_tmp + "/ev.db")
import hv.upload as _upl
_upl.RAW_DIR = _tmp + "/audio"


def _client(tmp_path):
    import hv.store as _st
    A.DB = _st.Store(str(tmp_path / "ch.db"))
    from hv.sessions import SessionStore
    A.SESS = SessionStore(str(tmp_path / "ch-sess.db"))
    A.AGENTS.clear()
    A.AGENTS["k1"] = {"agent_id": "ag1", "principal_id": "org1",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    return TestClient(A.app)


def _channel(c, H, nid="nar_c1", **kw):
    A.DB.save_narrator({"id": nid})
    body = {"name": "History Weekly", "narrator_id": nid}
    body.update(kw)
    r = c.post("/v1/channels", json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()["channel"]


def test_channel_crud_scoped(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    assert c.post("/v1/channels", json={"name": "History Weekly", "narrator_id": "ghost"},
                  headers=H).status_code == 422
    A.DB.save_narrator({"id": "nar_c1"})
    assert c.post("/v1/channels", json={"name": "History Weekly", "narrator_id": "nar_c1",
                                        "preset_id": "nope"}, headers=H).status_code == 404
    ch = _channel(c, H, preset_id="natural-clean", direction="slow and dry")
    assert ch["preset_id"] == "natural-clean"
    assert len(c.get("/v1/channels", headers=H).json()["channels"]) == 1
    A.AGENTS["k2"] = {"agent_id": "ag2", "principal_id": "org2",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    H2 = {"X-HV-Agent-Key": "k2"}
    assert c.get("/v1/channels", headers=H2).json()["channels"] == []
    assert c.post(f"/v1/channels/{ch['id']}/rebook",
                  json={"script_text": "hello " * 40}, headers=H2).status_code == 404


def test_rebook_same_voice_same_sound(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    ch = _channel(c, H, preset_id="broadcast-presence")
    r = c.post(f"/v1/channels/{ch['id']}/rebook",
               json={"script_text": "episode fourteen words here " * 20}, headers=H)
    assert r.status_code == 200, r.text
    doc = r.json()["contract"]
    assert doc["channel_id"] == ch["id"]
    assert doc["channel_preset"] == "broadcast-presence"
    assert doc["funding_status"] == "secured"
    # offered to the saved narrator, who may still decline
    tok = A.SESS.create("sc", "c@x", "nar_c1")
    NH = {"X-HV-Session": tok}
    assert c.post(f"/v1/offers/{doc['contract_id']}/decline", json={},
                  headers=NH).status_code == 200
    assert c.post(f"/v1/offers/{doc['contract_id']}/accept", json={},
                  headers=NH).status_code == 403  # decline revoked it
    # second episode, accepted this time
    r2 = c.post(f"/v1/channels/{ch['id']}/rebook",
                json={"script_text": "episode fifteen words here " * 20}, headers=H)
    cid2 = r2.json()["contract"]["contract_id"]
    assert c.post(f"/v1/offers/{cid2}/accept", json={}, headers=NH).status_code == 200
