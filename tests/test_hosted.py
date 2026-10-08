"""Hosted providers + director: honest gating, mocked runs."""
import io
import os
import struct
import sys
import wave
from unittest.mock import patch

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

import api.app as A

A.ALLOW_SIMULATED = True

import tempfile as _tf
_tmp = _tf.mkdtemp(prefix="hv-host-")
import hv.ledger as _led
A.led = _led.EventLedger(_tmp + "/ev.db")
import hv.upload as _upl
_upl.RAW_DIR = _tmp + "/audio"

TX = {"text": "hello world", "segments": [], "provider": "test-stub"}


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
    os.environ["HV_PACK_DIR"] = str(tmp_path / "packs")
    A.DB = _st.Store(str(tmp_path / "h.db"))
    from hv.sessions import SessionStore
    A.SESS = SessionStore(str(tmp_path / "h-sess.db"))
    A.AGENTS.clear()
    A.AGENTS["k1"] = {"agent_id": "ag1", "principal_id": "org1",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    return TestClient(A.app)


def _submitted(c, H, nid="nar_h1"):
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


def test_clean_tier_needs_fal_key(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    cid, _ = _submitted(c, H)
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FAL_KEY", None)
        with patch("hv.transcribe.transcribe", return_value=dict(TX)):
            r = c.post(f"/v1/contracts/{cid}/pack", json={"tier": "clean"}, headers=H)
    assert r.status_code == 501 and "FAL_KEY" in r.text


def test_clean_tier_mocked_run(tmp_path):
    from hv import clean as _cl
    assert _cl.clean_quote_usd(10) == 0.125  # 10 min at $0.0125
    assert _cl.clean_quote_usd(0.2) == 0.0125  # 1-minute minimum
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    cid, NH = _submitted(c, H, "nar_h2")
    before = A.DB.get_contract(cid)["payout_usd"]

    def fake_veed(src, dst, **kw):
        import shutil
        shutil.copy(src, dst)
        return {"provider": "veed-fal", "model": "veed/clean-audio",
                "target_lufs": -19.0, "request_id": "req_test"}

    with patch("hv.transcribe.transcribe", return_value=dict(TX)), \
         patch("hv.clean.veed_clean", side_effect=fake_veed):
        os.environ["FAL_KEY"] = "test-key"
        try:
            r = c.post(f"/v1/contracts/{cid}/pack", json={"tier": "clean"}, headers=H)
        finally:
            os.environ.pop("FAL_KEY", None)
    assert r.status_code == 200, r.text
    m = r.json()["manifest"]
    assert "clean.wav" in m["files"] and "clean.mp3" in m["files"]
    assert m["processing"]["provider"]["model"] == "veed/clean-audio"
    assert m["processing_fee_usd"] > 0
    assert A.DB.get_contract(cid)["payout_usd"] == before  # narrator untouched
    dl = c.get(f"/v1/contracts/{cid}/pack/download", params={"asset": "clean.wav"},
               headers=NH)
    assert dl.status_code == 200


def test_director_needs_key_and_contract_shape(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    cid, _ = _submitted(c, H, "nar_h3")
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DASHSCOPE_API_KEY", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        r = c.post(f"/v1/contracts/{cid}/direct", json={}, headers=H)
    assert r.status_code == 501
    fake = {"performance_review": {"script_accuracy": "review_required",
                                  "suspected_issues": [{"passage": "p01", "issue": "x",
                                                        "recommended_action": "accept"}],
                                  "overall": "fine"},
            "production_advice": {"mastering_preset": "natural-clean",
                                  "preserve_breaths": True,
                                  "restoration_strength": "light", "notes": ""},
            "uncertainty": []}
    with patch("hv.transcribe.transcribe", return_value=dict(TX)), \
         patch("hv.director.direct", return_value={**fake, "provider": "test",
                                                   "verify": "v"}):
        r2 = c.post(f"/v1/contracts/{cid}/direct", json={}, headers=H)
    assert r2.status_code == 200
    body = r2.json()
    assert body["performance_review"]["script_accuracy"] == "review_required"
    assert "verify" in body
    assert A.DB.get_contract(cid)["direction_review"]["provider"] == "test"
