"""Modular capture: briefs, takes, assembly, provenance."""
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
_tmp = _tf.mkdtemp(prefix="hv-seg-")
import hv.ledger as _led
A.led = _led.EventLedger(_tmp + "/ev.db")
import hv.upload as _upl
_upl.RAW_DIR = _tmp + "/audio"

TX = {"text": "hello world", "segments": [], "provider": "test-stub"}


def _wav(secs=1.0, amp=12000, sr=48000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", amp) for _ in range(int(sr * secs))))
    return buf.getvalue()


def _client(tmp_path):
    import hv.store as _st
    import os
    os.environ["HV_PACK_DIR"] = str(tmp_path / "packs")
    A.DB = _st.Store(str(tmp_path / "s.db"))
    from hv.sessions import SessionStore
    A.SESS = SessionStore(str(tmp_path / "s-sess.db"))
    A.AGENTS.clear()
    A.AGENTS["k1"] = {"agent_id": "ag1", "principal_id": "org1",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    return TestClient(A.app)


def test_brief_compile_modes():
    from hv import brief as _b
    m = _b.compile({"mode": "script"}, "Hello world. This is a second sentence!")
    assert len(m["segments"]) == 2 and m["segments"][0]["timing"] == "soft"
    assert m["segments"][1]["target_start_ms"] >= m["segments"][0]["target_end_ms"]
    sb = _b.compile({"mode": "storyboard",
                     "segments": [{"id": "a", "script": "Hi there."}]}, "")
    assert sb["segments"][0]["direction"] == ""
    try:
        _b.compile({"mode": "timed", "segments": [
            {"id": "h", "script": "word " * 100, "timing": "hard",
             "target_start_ms": 0, "target_end_ms": 500}]}, "")
        assert False
    except ValueError as e:
        assert "hard window" in str(e)
    try:
        _b.compile({"mode": "nope"}, "x")
        assert False
    except ValueError:
        pass


def _seg_contract(c, H, nid="nar_s1", brief=None):
    A.DB.save_narrator({"id": nid})
    body = {"script_text": "First passage here. Second passage here. Third one here.",
            "narrator_ids": [nid]}
    if brief:
        body["brief"] = brief
    r = c.post("/v1/contracts", json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()["contract"]["contract_id"]


def _take(c, cid, seg, NH, wav=None):
    return c.post(f"/v1/contracts/{cid}/segments/{seg}/takes", content=wav or _wav(),
                  headers={**NH, "Content-Type": "audio/wav"})


def test_takes_accept_retake_assemble(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    cid = _seg_contract(c, H)
    segs = c.get(f"/v1/contracts/{cid}/segments", headers=H).json()
    assert len(segs["manifest"]["segments"]) == 3
    tok = A.SESS.create("ss1", "s1@x", "nar_s1")
    NH = {"X-HV-Session": tok}
    a = c.post(f"/v1/offers/{cid}/accept", json={}, headers=NH)
    assert a.status_code == 200
    # full takes flow per passage: two takes, accept second
    for s in segs["manifest"]["segments"]:
        t1 = _take(c, cid, s["id"], NH)
        assert t1.status_code == 200
        t2 = _take(c, cid, s["id"], NH, _wav(amp=9000))
        assert t2.json()["attempt"] == 2
        acc = c.post(f"/v1/contracts/{cid}/segments/{s['id']}/accept",
                     json={"sha256": t2.json()["sha256"]}, headers=NH)
        assert acc.status_code == 200
    # agent flags a retake on passage 1, narrator re-records + accepts
    seg0 = segs["manifest"]["segments"][0]["id"]
    assert c.post(f"/v1/contracts/{cid}/segments/{seg0}/retake",
                  json={"note": "plosive"}, headers=H).status_code == 200
    t3 = _take(c, cid, seg0, NH, _wav(amp=14000))
    c.post(f"/v1/contracts/{cid}/segments/{seg0}/accept",
           json={"sha256": t3.json()["sha256"]}, headers=NH)
    asm = c.post(f"/v1/contracts/{cid}/assemble", json={}, headers=NH)
    assert asm.status_code == 200, asm.text
    body = asm.json()
    assert len(body["edit_map"]) == 3 and body["total_ms"] > 2000
    assert A.DB.get_contract(cid)["status"] == "submitted"
    assert A.DB.get_contract(cid)["session"]["takes"] == 7
    # approve + pack from the assembled master
    assert c.post(f"/v1/contracts/{cid}/approve", json={}, headers=H).status_code == 200
    with patch("hv.transcribe.transcribe", return_value=dict(TX)):
        pk = c.post(f"/v1/contracts/{cid}/pack", json={"tier": "basic"}, headers=H)
    m = pk.json()["manifest"]
    assert m["source"] == "assembled_master" and len(m["edit_map"]) == 3
    assert m["session"]["label"] == "HumanVoiced Verified Recording Session"
    assert "original.wav" in m["files"]


def test_assemble_missing_and_overflow(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    cid = _seg_contract(c, H, "nar_s2")
    tok = A.SESS.create("ss2", "s2@x", "nar_s2")
    NH = {"X-HV-Session": tok}
    c.post(f"/v1/offers/{cid}/accept", json={}, headers=NH)
    assert c.post(f"/v1/contracts/{cid}/assemble", json={}, headers=NH).status_code == 409
    # hard-window overflow: 2s take into a 1500ms window
    # (passes the 1.5x estimate guard at brief time, fails on real audio)
    cid2 = _seg_contract(c, H, "nar_s3", {"mode": "timed", "segments": [
        {"id": "h", "script": "Short line here.", "timing": "hard",
         "target_start_ms": 0, "target_end_ms": 1500}]})
    t3 = A.SESS.create("ss3", "s3@x", "nar_s3")
    NH3 = {"X-HV-Session": t3}
    c.post(f"/v1/offers/{cid2}/accept", json={}, headers=NH3)
    tk = _take(c, cid2, "h", NH3, _wav(secs=2.0))
    assert tk.status_code == 200
    c.post(f"/v1/contracts/{cid2}/segments/h/accept",
           json={"sha256": tk.json()["sha256"]}, headers=NH3)
    ov = c.post(f"/v1/contracts/{cid2}/assemble", json={}, headers=NH3)
    assert ov.status_code == 422 and "hard window" in ov.text


def test_takes_auth_and_denoise_backend(tmp_path):
    from hv import processing as _p
    assert _p.denoise_backend() == "none"  # no torch on this box
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    cid = _seg_contract(c, H, "nar_s4")
    seg = c.get(f"/v1/contracts/{cid}/segments", headers=H).json()["manifest"]["segments"][0]["id"]
    A.DB.save_narrator({"id": "nar_out"})
    to = A.SESS.create("so", "o@x", "nar_out")
    bad = c.post(f"/v1/contracts/{cid}/segments/{seg}/takes", content=_wav(),
                 headers={"X-HV-Session": to, "Content-Type": "audio/wav"})
    assert bad.status_code == 403  # stranger cannot record
    assert c.get(f"/v1/contracts/{cid}/segments",
                 headers={"X-HV-Session": to}).status_code == 403


def test_assembly_deterministic():
    import tempfile, os
    from hv import assembly as _as
    d = tempfile.mkdtemp()
    p1 = os.path.join(d, "a.wav")
    p2 = os.path.join(d, "b.wav")
    open(p1, "wb").write(_wav(secs=1.0, amp=10000))
    open(p2, "wb").write(_wav(secs=1.0, amp=16000))
    segs = [{"id": "a", "timing": "soft", "target_start_ms": 0, "target_end_ms": None},
            {"id": "b", "timing": "soft", "target_start_ms": None, "target_end_ms": None}]
    r1 = _as.assemble(segs, {"a": p1, "b": p2}, os.path.join(d, "m1.wav"))
    r2 = _as.assemble(segs, {"a": p1, "b": p2}, os.path.join(d, "m2.wav"))
    assert r1["master_sha256"] == r2["master_sha256"]
    assert r1["total_ms"] > 2000  # two 1s takes + breathing room
