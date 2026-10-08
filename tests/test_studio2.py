"""Studio v2: creator presets, reference matching, benchmark harness."""
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
_tmp = _tf.mkdtemp(prefix="hv-st2-")
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
    import os
    os.environ["HV_PACK_DIR"] = str(tmp_path / "packs")
    A.DB = _st.Store(str(tmp_path / "v2.db"))
    from hv.sessions import SessionStore
    A.SESS = SessionStore(str(tmp_path / "v2-sess.db"))
    A.AGENTS.clear()
    A.AGENTS["k1"] = {"agent_id": "ag1", "principal_id": "org1",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    return TestClient(A.app)


def _submitted(c, H, nid="nar_v1"):
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


def test_creator_four_and_aliases(tmp_path):
    from hv import presets as _pr
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    names = [p["name"] for p in c.get("/v1/studio/presets", headers=H).json()["builtins"]]
    for want in ("natural-clean", "broadcast-presence", "intimate-story",
                 "match-my-channel", "calm-documentary"):
        assert want in names
    # alias resolves with new engine fields
    r = c.get("/v1/studio/presets/calm-documentary", headers=H).json()["preset"]
    assert r["engine"] == _pr.ENGINE_VERSION and r["ride"] is True
    assert c.get("/v1/studio/presets/nope", headers=H).status_code == 404


def test_reference_register_and_match(tmp_path):
    from hv import reference as _rf
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    up = c.post("/v1/studio/references", content=_wav(secs=3.0),
                headers={**H, "Content-Type": "audio/wav"})
    assert up.status_code == 200, up.text
    ref = up.json()["reference"]
    assert set(ref["profile"]["bands"]) == {"125", "250", "500", "1000",
                                            "2000", "4000", "8000"}
    assert ref["profile"]["bands"]["1000"] == 0.0  # normalized
    assert c.get("/v1/studio/references", headers=H).json()["references"]
    # match-my-channel without a reference is refused
    cid, _ = _submitted(c, H)
    with patch("hv.transcribe.transcribe", return_value=dict(TX)):
        no = c.post(f"/v1/contracts/{cid}/pack",
                    json={"tier": "studio", "preset_id": "match-my-channel"}, headers=H)
    assert no.status_code == 422
    # with reference: matched, capped, recorded
    with patch("hv.transcribe.transcribe", return_value=dict(TX)):
        ok = c.post(f"/v1/contracts/{cid}/pack",
                    json={"tier": "studio", "preset_id": "match-my-channel",
                          "reference_id": ref["id"]}, headers=H)
    assert ok.status_code == 200, ok.text
    m = ok.json()["manifest"]
    assert m["reference_id"] == ref["id"]
    assert m["processing"]["reference_matched"] is True
    assert "firequalizer" in m["processing"]["chain"]
    assert m["processing"]["engine"] == "hv-studio-0.2"
    # stranger's reference is invisible
    A.AGENTS["k2"] = {"agent_id": "ag2", "principal_id": "org2",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    with patch("hv.transcribe.transcribe", return_value=dict(TX)):
        foreign = c.post(f"/v1/contracts/{cid}/pack",
                         json={"tier": "studio", "preset_id": "match-my-channel",
                               "reference_id": ref["id"]},
                         headers={"X-HV-Agent-Key": "k2"})
    assert foreign.status_code in (403, 404)


def test_match_curve_capped():
    from hv import reference as _rf
    take = {f: -10.0 for f in _rf.BANDS}
    ref = {f: 50.0 for f in _rf.BANDS}
    curve = _rf.match_curve(take, ref)
    assert curve.count("entry(") == 7
    assert ",6.0)" in curve and ",-6.0)" not in curve  # capped at +6
    flat = _rf.match_curve(take, {f: -10.0 for f in _rf.BANDS})
    assert ",0.0)" in flat


def test_studio_chain_has_ride_and_deess(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    cid, _ = _submitted(c, H, "nar_v2")
    with patch("hv.transcribe.transcribe", return_value=dict(TX)):
        r = c.post(f"/v1/contracts/{cid}/pack",
                   json={"tier": "studio", "preset_id": "broadcast-presence"},
                   headers=H)
    assert r.status_code == 200, r.text
    chain = r.json()["manifest"]["processing"]["chain"]
    assert "dynaudnorm" in chain and "deesser" in chain and "afftdn" in chain
    assert "loudnorm" in chain and "limiter" in chain
    assert "reverb" not in chain and "aecho" not in chain


def test_benchmark_harness(tmp_path):
    import os
    from worker import benchmark as _b
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    open(a / "clip.wav", "wb").write(_wav())
    open(b / "clip.wav", "wb").write(_wav(amp=6000))
    out = _b.compare(str(a), str(b), str(tmp_path / "bench"), "ours", "ref")
    assert len(out["rows"]) == 1
    assert out["rows"][0]["snr_delta"] is not None
    blind = os.listdir(str(tmp_path / "bench" / "blind"))
    assert len(blind) == 2 and os.path.exists(str(tmp_path / "bench" / "key.json"))
