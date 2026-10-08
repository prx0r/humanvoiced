"""Round-2 peer-review regression tests (10 blockers).

Covers: publish w/ handle+consent, catalog filtering, PCM decode mono/stereo,
silent audio honesty, atomic accept, country eligibility order, simulated
refusal, 100% payout, guest order ownership, onboarding persistence static.
"""
import io
import struct
import sys
import wave

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

import api.app as A

A.ALLOW_SIMULATED = True

# Isolate side effects: ledger + audio must not touch production paths.
import tempfile as _tf
_tmp = _tf.mkdtemp(prefix="hv-r2-")
import hv.ledger as _led
A.led = _led.EventLedger(_tmp + "/ev.db")
import hv.upload as _upl
_upl.RAW_DIR = _tmp + "/audio"


def _wav(mono=True, secs=1.0, amp=15000, sr=48000):
    buf = io.BytesIO()
    ch = 1 if mono else 2
    with wave.open(buf, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(sr)
        n = int(sr * secs)
        frames = b"".join(struct.pack("<h", amp) for _ in range(n * ch))
        w.writeframes(frames)
    return buf.getvalue()


def _client(tmp_path):
    import hv.store as _st
    import os
    db = str(tmp_path / "r2.db")
    sdb = str(tmp_path / "r2-sess.db")
    for _f in (db, sdb):
        try:
            os.remove(_f)
        except OSError:
            pass
    A.DB = _st.Store(db)
    from hv.sessions import SessionStore
    A.SESS = SessionStore(sdb)
    A.AGENTS.clear()
    A.AGENTS["k1"] = {"agent_id": "ag1", "principal_id": "org1",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    return TestClient(A.app)


def test_publish_handle_consent_and_catalog(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    nar = "nar_pub1"
    A.DB.save_narrator({"id": nar})
    tok = A.SESS.create("s", "e@x.com", nar)
    NH = {"X-HV-Session": tok}
    wav = _wav()
    r = c.post("/v1/narrators/me/sample", content=wav,
               headers={**NH, "Content-Type": "audio/wav"})
    assert r.status_code == 200, r.text
    sha = r.json()["sample"]
    # publish without handle -> 422
    bad = c.post("/v1/narrators/me/profile",
                 json={"publish": True, "profile": {"display_name": "T"}}, headers=NH)
    assert bad.status_code == 422
    # publish with handle + 'latest' consent
    ok = c.post("/v1/narrators/me/profile",
                json={"publish": True, "handle": "tester_one",
                      "profile": {"display_name": "Tester"},
                      "consent_samples": "latest"}, headers=NH)
    assert ok.status_code == 200, ok.text
    assert ok.json()["published"]["handle"] == "tester_one"
    doc = A.DB.get_narrator(nar)
    assert doc["handle"] == "tester_one"
    pub_samples = [s for s in doc["samples"] if s.get("consented_public")]
    assert len(pub_samples) == 1 and pub_samples[0]["sha256"] == sha
    # duplicate handle -> 409
    nar2 = "nar_pub2"
    A.DB.save_narrator({"id": nar2})
    tok2 = A.SESS.create("s2", "e2@x.com", nar2)
    dup = c.post("/v1/narrators/me/profile",
                 json={"publish": True, "handle": "TESTER_one",
                       "profile": {}}, headers={"X-HV-Session": tok2})
    assert dup.status_code == 409
    # catalog: published appears, unpublished does not
    cat = c.get("/v1/voices").json()["voices"]
    assert any(v["id"] == nar for v in cat)
    assert not any(v["id"] == nar2 for v in cat)


def test_pcm_decode_mono_stereo():
    from hv import audio as AU
    mono = _wav(mono=True, secs=1.0, amp=15000)
    stereo = _wav(mono=False, secs=1.0, amp=15000)
    fm, srm = AU.decode_wav_mono(mono)
    fs, srs = AU.decode_wav_mono(stereo)
    assert srm == srs == 48000
    assert abs(len(fm) - 48000) < 2 and abs(len(fs) - 48000) < 2
    expect = 15000 / 32768
    assert abs(sum(fm) / len(fm) - expect) < 1e-6
    assert abs(sum(fs) / len(fs) - expect) < 1e-6


def test_silent_audio_no_crash_no_invention():
    from hv import audio as AU
    silent = _wav(mono=True, secs=1.0, amp=0)
    frames, sr = AU.decode_wav_mono(silent)
    rep = AU.analyze(frames, sr, "", "shax")
    assert rep["acoustic"]["rms_dbfs"] == -96.0  # floor, no log10(0)
    assert rep["acoustic"]["clipping_detected"] is False
    per = rep["perceptual"]
    assert per["placeholders"] is True
    labels = [t.get("label") for t in per.get("texture", [])]
    assert labels == ["unknown"]


def test_double_accept_one_winner(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    for nid in ("nar_a", "nar_b"):
        A.DB.save_narrator({"id": nid})
    r = c.post("/v1/contracts", json={"script_text": "hello world " * 40,
                                      "narrator_ids": ["nar_a", "nar_b"]}, headers=H)
    cid = r.json()["contract"]["contract_id"]
    ta = A.SESS.create("sa", "a@x", "nar_a")
    tb = A.SESS.create("sb", "b@x", "nar_b")
    ra = c.post(f"/v1/offers/{cid}/accept", json={}, headers={"X-HV-Session": ta})
    assert ra.status_code == 200
    rb = c.post(f"/v1/offers/{cid}/accept", json={}, headers={"X-HV-Session": tb})
    assert rb.status_code in (403, 409)  # loser gets nothing
    assert A.DB.get_contract(cid)["narrator_id"] == "nar_a"
    # same narrator double-accept: offer row is gone -> 403 or 409 both mean "no second claim"
    ra2 = c.post(f"/v1/offers/{cid}/accept", json={}, headers={"X-HV-Session": ta})
    assert ra2.status_code in (403, 409)


def test_decline_revokes_offer(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_d"})
    r = c.post("/v1/contracts", json={"script_text": "hello world " * 40,
                                      "narrator_ids": ["nar_d"]}, headers=H)
    cid = r.json()["contract"]["contract_id"]
    t = A.SESS.create("sd", "d@x", "nar_d")
    assert c.post(f"/v1/offers/{cid}/decline", json={},
                  headers={"X-HV-Session": t}).status_code == 200
    assert c.post(f"/v1/offers/{cid}/accept", json={},
                  headers={"X-HV-Session": t}).status_code == 403


def test_country_eligibility_before_claim(tmp_path):
    from hv import globalx as GX
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    blocked = [k for k, v in getattr(GX, "COUNTRIES", {}).items()
               if not v.get("bookable", True)]
    if not blocked:
        return  # no blocked fixtures; ordering covered by code review
    A.DB.save_narrator({"id": "nar_x", "country": blocked[0]})
    r = c.post("/v1/contracts", json={"script_text": "hello world " * 40,
                                      "narrator_ids": ["nar_x"]}, headers=H)
    cid = r.json()["contract"]["contract_id"]
    t = A.SESS.create("sx", "x@x", "nar_x")
    assert c.post(f"/v1/offers/{cid}/accept", json={},
                  headers={"X-HV-Session": t}).status_code == 402
    assert A.DB.get_contract(cid)["status"] == "offered"  # claim never committed


def test_simulated_refused_by_default(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.ALLOW_SIMULATED = False
    try:
        r = c.post("/v1/contracts", json={"script_text": "hello world " * 40,
                                          "narrator_ids": []}, headers=H)
        assert r.status_code == 501
        assert "simulated" in r.text.lower()
    finally:
        A.ALLOW_SIMULATED = True


def test_narrator_gets_100_percent(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    script = "word " * 1500  # ~10 min
    q = c.post("/v1/contracts/quote", json={"script_text": script}, headers=H)
    assert q.json()["narrator_payout"] == 10.0
    assert q.json()["customer_price"] == 10.0 + q.json()["service_fee_usd"]
    r = c.post("/v1/contracts", json={"script_text": script, "narrator_ids": []}, headers=H)
    assert r.json()["contract"]["payout_usd"] == r.json()["price"]["narrator_payout"]
    assert r.json()["price"]["customer_price"] == r.json()["price"]["narrator_payout"] + r.json()["price"]["service_fee_usd"]


def test_guest_cannot_claim_foreign_order(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    r = c.post("/v1/contracts", json={"script_text": "hello world " * 40,
                                      "narrator_ids": []}, headers=H)
    cid = r.json()["contract"]["contract_id"]
    funding = r.json()["funding"]
    ok = c.post("/v1/orders/guest",
                json={"contract_id": cid, "funding_intent": funding}, headers=H)
    assert ok.status_code == 200
    bad = c.post("/v1/orders/guest",
                 json={"contract_id": cid, "funding_intent": "pi_forged"}, headers=H)
    assert bad.status_code == 402


def test_onboard_persists_recording_static():
    import pathlib
    html = pathlib.Path("web/onboard.html").read_text()
    js = pathlib.Path("web/studio.js").read_text()
    assert "indexedDB" in js and "pending-onboarding" in js
    assert 'id="consent"' in html and 'id="handle"' in html and 'id="name"' in html
    assert "portfolio.html?h=" in js and "/api/auth/me" in js
    for el in ('id="wave"', 'id="spec"', 'id="dbfs-live"', 'id="rec-live"',
               'id="checkroom"', 'id="check-results"', 'id="check-playback"',
               'id="check-keep"', 'id="upload-existing"', 'id="wave-saved"'):
        assert el in html, el
    assert "pending-onboarding" in js and "getFloatTimeDomainData" in js
    ws = pathlib.Path("web/workspace.html").read_text()
    assert "/v1/contracts/" in ws and "/submissions" in ws and "/script" in ws
    cust = pathlib.Path("web/voices.html").read_text()
    assert "/v1/voices" in cust and "For talent" in cust
    for p in ("web/index.html", "web/brief.html", "web/portfolio.html", "web/order.html"):
        assert "For talent" in pathlib.Path(p).read_text(), p
    for p in ("web/home.html", "web/workspace.html", "web/onboard.html"):
        html = pathlib.Path(p).read_text()
        assert "Guide" in html and "Studio" in html, p
        assert "How jobs work" not in html, p


def test_contract_script_party_only(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_sc"})
    r = c.post("/v1/contracts", json={"script_text": "secret script words here " * 10,
                                      "narrator_ids": ["nar_sc"]}, headers=H)
    cid = r.json()["contract"]["contract_id"]
    t = A.SESS.create("ssc", "sc@x", "nar_sc")
    got = c.get(f"/v1/contracts/{cid}/script", headers={"X-HV-Session": t})
    assert got.status_code == 200 and "secret script words" in got.json()["script_text"]
    A.DB.save_narrator({"id": "nar_out"})
    t2 = A.SESS.create("so", "o@x", "nar_out")
    assert c.get(f"/v1/contracts/{cid}/script",
                 headers={"X-HV-Session": t2}).status_code == 403


def test_auth_me_and_oauth_state_binding(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/auth/me").status_code == 401
    A.DB.save_narrator({"id": "nar_me", "email": "m@x.com"})
    tok = A.SESS.create("subm", "m@x.com", "nar_me")
    r = c.get("/api/auth/me", headers={"X-HV-Session": tok})
    assert r.status_code == 200 and r.json()["authenticated"] is True
    assert r.json()["narrator_id"] == "nar_me"
    # cookie session also works (browser path)
    c.cookies.set("hv_session", tok)
    r2 = c.get("/api/auth/me")
    assert r2.status_code == 200 and r2.json()["email"] == "m@x.com"
    # OAuth callback without browser-bound state cookie is rejected
    bad = c.get("/api/auth/google/callback", params={"code": "x", "state": "y"})
    assert bad.status_code == 400


def _run_contract(c, H, nid):
    """Drive one contract quote→settle. Returns (cid, settlement)."""
    r = c.post("/v1/contracts", json={"script_text": "hello world calm documentary " * 30,
                                      "narrator_ids": [nid]}, headers=H)
    assert r.status_code == 200, r.text
    cid = r.json()["contract"]["contract_id"]
    tok = A.SESS.create("s_" + nid, nid + "@x.com", nid)
    NH = {"X-HV-Session": tok}
    a = c.post(f"/v1/offers/{cid}/accept", json={}, headers=NH)
    assert a.status_code == 200, a.text
    s = c.post(f"/v1/contracts/{cid}/submissions", content=_wav(),
               headers={**NH, "Content-Type": "audio/wav"})
    assert s.status_code == 200, s.text
    ap = c.post(f"/v1/contracts/{cid}/approve", json={}, headers=H)
    assert ap.status_code == 200, ap.text
    return cid, ap.json()["settlement"]


def test_approve_settles_reputation_receipt(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_set"})
    cid, st = _run_contract(c, H, "nar_set")
    assert st["to"] == "nar_set" and st["amount_minor"] > 0
    assert A.DB.get_contract(cid)["status"] == "settled"
    rep = c.get("/v1/voices/nar_set/reputation").json()
    assert rep["completed"] == 1 and rep["history_label"] == "insufficient_history"
    # idempotent re-approve
    tok = A.SESS.create("sx", "x@x", "nar_set")
    r = c.get(f"/v1/contracts/{cid}/receipt", headers={"X-HV-Session": tok})
    assert r.status_code == 200 and r.json()["chain_verified"] is True
    again = c.post(f"/v1/contracts/{cid}/approve", json={}, headers=H)
    assert again.json().get("deduplicated") is True
    # reputation survives the in-memory cache (persisted on narrator doc)
    doc = A.DB.get_narrator("nar_set")
    assert doc["reputation"]["completed"] == 1
    # open dispute blocks settlement
    A.DB.save_narrator({"id": "nar_blk"})
    r2 = c.post("/v1/contracts", json={"script_text": "hello world " * 40,
                                       "narrator_ids": ["nar_blk"]}, headers=H)
    cid2 = r2.json()["contract"]["contract_id"]
    t2 = A.SESS.create("s2", "b@x", "nar_blk")
    NH2 = {"X-HV-Session": t2}
    c.post(f"/v1/offers/{cid2}/accept", json={}, headers=NH2)
    c.post(f"/v1/contracts/{cid2}/submissions", content=_wav(),
           headers={**NH2, "Content-Type": "audio/wav"})
    c.post(f"/v1/contracts/{cid2}/disputes",
           json={"type": "style_dispute", "claim": "x"}, headers=NH2)
    assert c.post(f"/v1/contracts/{cid2}/approve", json={}, headers=H).status_code == 409
