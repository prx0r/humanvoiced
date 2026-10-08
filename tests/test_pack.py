"""Delivery-pack + studio-preset tests: honest processing, separate fees."""
import io
import struct
import sys
import wave
from unittest.mock import patch

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

import api.app as A

A.ALLOW_SIMULATED = True

import tempfile as _tf
_tmp = _tf.mkdtemp(prefix="hv-pack-")
import hv.ledger as _led
A.led = _led.EventLedger(_tmp + "/ev.db")
import hv.upload as _upl
_upl.RAW_DIR = _tmp + "/audio"

TX = {"text": "hello world calm documentary test",
      "segments": [{"start": 0.0, "end": 1.0, "text": "hello world"},
                   {"start": 1.0, "end": 2.0, "text": "calm documentary test"}],
      "provider": "test-stub"}


def _wav(secs=2.0, amp=12000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"".join(struct.pack("<h", amp) for _ in range(int(48000 * secs))))
    return buf.getvalue()


def _client(tmp_path):
    import hv.store as _st
    import os
    os.environ["HV_PACK_DIR"] = str(tmp_path / "packs")
    A.DB = _st.Store(str(tmp_path / "p.db"))
    from hv.sessions import SessionStore
    A.SESS = SessionStore(str(tmp_path / "p-sess.db"))
    A.AGENTS.clear()
    A.AGENTS["k1"] = {"agent_id": "ag1", "principal_id": "org1",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    return TestClient(A.app)


def _submitted(c, H, nid="nar_p1"):
    A.DB.save_narrator({"id": nid})
    r = c.post("/v1/contracts", json={"script_text": "hello world " * 40,
                                      "narrator_ids": [nid]}, headers=H)
    cid = r.json()["contract"]["contract_id"]
    tok = A.SESS.create("s_" + nid, nid + "@x.com", nid)
    NH = {"X-HV-Session": tok}
    c.post(f"/v1/offers/{cid}/accept", json={}, headers=NH)
    s = c.post(f"/v1/contracts/{cid}/submissions", content=_wav(),
               headers={**NH, "Content-Type": "audio/wav"})
    assert s.status_code == 200, s.text
    return cid, NH


def test_preset_crud_and_validation(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    r = c.get("/v1/studio/presets", headers=H)
    assert "calm-documentary" in [p["name"] for p in r.json()["builtins"]]
    bad = c.post("/v1/studio/presets", json={"name": "x", "denoise_db": 99}, headers=H)
    assert bad.status_code == 422
    clash = c.post("/v1/studio/presets", json={"name": "calm-documentary"}, headers=H)
    assert clash.status_code == 409
    ok = c.post("/v1/studio/presets",
                json={"name": "history.show", "target_lufs": -19,
                      "denoise_db": 10, "compression": "medium", "eq": "warm"},
                headers=H)
    assert ok.status_code == 200
    assert ok.json()["preset"]["name"] == "ag1/history.show"
    got = c.get("/v1/studio/presets/ag1/history.show", headers=H)
    assert got.json()["preset"]["compression"] == "medium"
    assert c.get("/v1/studio/presets/nope", headers=H).status_code == 404


def test_basic_pack_free_and_payout_untouched(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    cid, NH = _submitted(c, H)
    before = A.DB.get_contract(cid)["payout_usd"]
    with patch("hv.transcribe.transcribe", return_value=dict(TX)):
        r = c.post(f"/v1/contracts/{cid}/pack", json={"tier": "basic"}, headers=H)
    assert r.status_code == 200, r.text
    m = r.json()["manifest"]
    assert set(("narration.wav", "narration.mp3", "transcript.srt")) <= set(m["files"])
    assert m["processing_fee_usd"] == 0.0
    assert m["narrator_payout_usd"] == before
    assert m["rights"]["voice_cloning_allowed"] is False
    assert m["loudness"].get("input_i") is not None
    after = A.DB.get_contract(cid)["payout_usd"]
    assert after == before  # processing never deducts narrator pay
    g = c.get(f"/v1/contracts/{cid}/pack", headers=NH)
    assert g.status_code == 200 and g.json()["tier"] == "basic"


def test_studio_pack_fee_separate_and_integrity(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    cid, NH = _submitted(c, H, "nar_p2")
    before = A.DB.get_contract(cid)["payout_usd"]
    with patch("hv.transcribe.transcribe", return_value=dict(TX)):
        r = c.post(f"/v1/contracts/{cid}/pack",
                   json={"tier": "studio", "preset_id": "calm-documentary"}, headers=H)
    assert r.status_code == 200, r.text
    fee = r.json()["processing_fee"]
    assert fee["processing_fee_usd"] == 3.00
    assert fee["narrator_payout_change_usd"] == 0.0
    m = r.json()["manifest"]
    assert "studio.wav" in m["files"] and m["preset"] == "calm-documentary"
    assert m["integrity"]["passed"] is True
    assert A.DB.get_contract(cid)["payout_usd"] == before
    dl = c.get(f"/v1/contracts/{cid}/pack/download", params={"asset": "narration.mp3"},
               headers=NH)
    assert dl.status_code == 200 and dl.headers["content-type"] == "audio/mpeg"
    assert len(dl.content) > 1000
    assert c.get(f"/v1/contracts/{cid}/pack/download", params={"asset": "../../x"},
                 headers=NH).status_code == 404


def test_studio_refused_without_simulated_and_stranger_blocked(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    cid, _ = _submitted(c, H, "nar_p3")
    A.ALLOW_SIMULATED = False
    try:
        with patch("hv.transcribe.transcribe", return_value=dict(TX)):
            r = c.post(f"/v1/contracts/{cid}/pack", json={"tier": "studio"}, headers=H)
        assert r.status_code == 501
    finally:
        A.ALLOW_SIMULATED = True
    A.DB.save_narrator({"id": "nar_str"})
    st = A.SESS.create("ss", "s@x.com", "nar_str")
    assert c.get(f"/v1/contracts/{cid}/pack",
                 headers={"X-HV-Session": st}).status_code == 403


def test_pack_needs_submission(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_p4"})
    r = c.post("/v1/contracts", json={"script_text": "hello world " * 40,
                                      "narrator_ids": ["nar_p4"]}, headers=H)
    cid = r.json()["contract"]["contract_id"]
    assert c.post(f"/v1/contracts/{cid}/pack", json={}, headers=H).status_code == 409


def test_capture_qc_and_srt_units():
    from hv import capture_qc as _q
    from hv import processing as _p
    clean = [0.0] * 4800 + [0.25 * (-1) ** i for i in range(48000)]
    m = _q.measure(clean, 48000)
    assert m["clipping_detected"] is False and m["advisory_only"] is True
    assert _q.advise(m) == ["Sounds good. Start recording."]
    clip = [1.0] * 4800
    assert "clipping" in _q.measure(clip, 48000)["flags"]
    srt = _p.srt_from_segments([{"start": 61.5, "end": 63.25, "text": "hi there"}])
    assert srt.startswith("1\n00:01:01,500 --> 00:01:03,250\nhi there")
    assert _p.srt_from_segments([]) == ""
