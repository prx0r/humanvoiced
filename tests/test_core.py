"""Fixture suite: the gates that must hold before real money."""
import json
import sqlite3
import wave

import pytest

from hv import contracts as C
from hv import disputes as D
from hv import escrow as E
from hv import ledger as L
from hv import qc
from hv import reputation as R


def test_ledger_chain_and_tamper(tmp_path):
    led = L.EventLedger(str(tmp_path / "e.db"))
    led.append("hvc_1", "contract.created", {"v": 1})
    led.append("hvc_1", "offer.accepted", {"by": "nar_1"})
    ok, _ = led.verify_chain("hvc_1")
    assert ok
    conn = sqlite3.connect(str(tmp_path / "e.db"))
    conn.execute("UPDATE contract_events SET payload='{\"v\": 2}' WHERE event_type='contract.created'")
    conn.commit()
    conn.close()
    ok, msg = led.verify_chain("hvc_1")
    assert not ok


def test_accept_requires_funding():
    c = C.from_brief({"payout_usd": 12, "delivery_seconds": 7200}, "hello world", "org_1", "agent_1")
    assert c.validate() == []
    with pytest.raises(ValueError):
        C.accept(c, "nar_1", funded=False)
    C.accept(c, "nar_1", funded=True)
    assert c.status == "accepted" and c.funding_status == "secured"
    assert c.deadline_at > c.accepted_at


def test_script_edit_is_amendment_not_overwrite():
    c = C.from_brief({"payout_usd": 12}, "v1 script", "org_1", "agent_1")
    C.accept(c, "nar_1", funded=True)
    old_hash = c.script_sha256
    nxt = C.amend(c, {"script_sha256": "0" * 64})
    assert nxt.version == 2 and nxt.status == "proposed"
    assert c.script_sha256 == old_hash  # original untouched


def test_late_submit_flagged_by_qc(tmp_path):
    wav = str(tmp_path / "s.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        import struct
        w.writeframes(b"".join(struct.pack("<h", 15000) for _ in range(48000)))
    rep = qc.evaluate("sub_1", "hvc_1", wav, "hello world", "hello world")
    assert rep["recommendation"] == "approve"
    assert rep["requires_human_review"] is False
    bad = qc.evaluate("sub_2", "hvc_1", wav, "hello world entirely different script here", "hello world")
    assert bad["script_alignment"]["coverage_estimate"] < 0.9


def test_double_settle_and_over_release_blocked():
    rail = E.SimulatedRail()
    it = E.PaymentIntent(contract_id="hvc_1", amount_minor=1200)
    assert rail.verify_funding(it)
    rail.lock(it)
    rail.release(it, "nar_1")
    assert rail.balances["nar_1"] == 1200
    with pytest.raises(ValueError):
        rail.release(it, "nar_1")  # duplicate instruction
    it2 = E.PaymentIntent(contract_id="hvc_2", amount_minor=500)
    rail.lock(it2)
    with pytest.raises(ValueError):
        rail.refund(it2)
        rail.refund(it2)  # double refund


def test_reputation_recovers_and_new_voice_label():
    r = R.ReputationVector("nar_1")
    assert r.history_label == "new_voice"
    r.record_outcome({"verified": False, "scores": {"Q": 0.1}})  # unverified: ignored
    assert r.completed == 0
    r.record_outcome({"verified": True, "worker_fault": True, "scores": {"Q": 0.4, "D": 0.2}})
    assert r.verified_incidents == 1
    for _ in range(5):
        r.record_outcome({"verified": True, "scores": {"Q": 0.95, "D": 1.0}})
    assert r.vector["D"] > 0.8  # repeated success restores confidence
    assert 0 < R.match_score({"VoiceFit": 1, "Reliability": 1, "Availability": 1, "PriceFit": 1, "Preferences": 1}) <= 1


def test_dispute_shares_and_appeal_window():
    q = D.DisputeQueue()
    case = q.open("hvc_1", "style_dispute", "creator", "not energetic enough")
    q.respond(case["case_id"], "narrator", "contract said calm documentary")
    with pytest.raises(AssertionError):
        q.decide(case["case_id"], "partial_payment", 6000, 3000, "sha", "1.0")  # bad split
    q.decide(case["case_id"], "partial_payment", 7000, 3000, "sha256:abc", "1.0")
    assert q.cases[case["case_id"]]["decision"]["settlement_authorised"] is False
    q.close_appeal_window(case["case_id"])
    assert q.cases[case["case_id"]]["decision"]["settlement_authorised"] is True
