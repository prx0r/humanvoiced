"""Autonomous rehearsal fleet: N contracts through the full loop, no human steps.

quote → create(fund) → offer → accept → submit → QC → [correction] →
approve → settle → receipt → reputation. Asserts every job settles with a
verified chain and 100% narrator payout. Explicit test environment:
isolated tmp DBs + simulated funding (never production paths).

Usage: python3 -m worker.fleet --n 10
"""
from __future__ import annotations

import argparse
import io
import struct
import sys
import tempfile
import wave

sys.path.insert(0, ".")

import api.app as A  # noqa: E402  module-level so rehearsals share it

SCRIPTS = [
    ("calm documentary narration about rivers", "standard"),
    ("energetic commercial for a local bakery", "standard"),
    ("slow horror story for a midnight episode", "standard"),
    (" measured explainer on how tides work", "proven"),
    ("warm children's story about a fox", "standard"),
    ("crisp news brief on the morning markets", "priority"),
    ("conversational travel guide to old towns", "standard"),
    ("documentary voiceover on bridge builders", "proven"),
    ("philosophy essay read slowly and clearly", "standard"),
    ("storytelling pilot with natural pauses", "standard"),
]


def make_wav(amp: int = 15000, secs: float = 2.0, sr: int = 48000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", amp) for _ in range(int(sr * secs))))
    return buf.getvalue()


def run_fleet(n: int = 10) -> dict:
    from fastapi.testclient import TestClient
    import hv.ledger as _led
    import hv.store as _st
    import hv.upload as _upl
    from hv.sessions import SessionStore

    tmp = tempfile.mkdtemp(prefix="hv-fleet-")
    A.DB = _st.Store(tmp + "/fleet.db")
    A.SESS = SessionStore(tmp + "/fleet-sess.db")
    A.led = _led.EventLedger(tmp + "/fleet-ev.db")
    _upl.RAW_DIR = tmp + "/audio"
    A.ALLOW_SIMULATED = True  # rehearsal is an explicit test environment
    A.AGENTS.clear()
    A.AGENTS["fleet"] = {"agent_id": "agent_fleet", "principal_id": "org_fleet",
                         "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    c = TestClient(A.app)
    H = {"X-HV-Agent-Key": "fleet"}

    results = []
    for i in range(n):
        text, tier = SCRIPTS[i % len(SCRIPTS)]
        script = (text + " ") * (40 + i * 5)
        nid = f"nar_fleet_{i:02d}"
        A.DB.save_narrator({"id": nid})
        tok = A.SESS.create("sub_" + nid, nid + "@fleet.test", nid)
        NH = {"X-HV-Session": tok}
        q = c.post("/v1/contracts/quote", json={"script_text": script, "tier": tier}, headers=H)
        assert q.status_code == 200, q.text
        r = c.post("/v1/contracts", json={"script_text": script, "tier": tier,
                                          "delivery_seconds": 7200,
                                          "narrator_ids": [nid]}, headers=H)
        assert r.status_code == 200, r.text
        cid, price = r.json()["contract"]["contract_id"], r.json()["price"]
        assert price["customer_price"] == price["narrator_payout"], "100% rule"
        a = c.post(f"/v1/offers/{cid}/accept", json={}, headers=NH)
        assert a.status_code == 200, a.text
        s = c.post(f"/v1/contracts/{cid}/submissions",
                   content=make_wav(amp=8000 + (i * 1200) % 12000, secs=1.0 + i * 0.2),
                   headers={**NH, "Content-Type": "audio/wav"})
        assert s.status_code == 200, s.text
        if i == n - 1:  # last job rehearses the correction round
            k = c.post(f"/v1/contracts/{cid}/corrections",
                       json={"passages": ["opening line"]}, headers=H)
            assert k.status_code == 200, k.text
            s2 = c.post(f"/v1/contracts/{cid}/submissions", content=make_wav(),
                        headers={**NH, "Content-Type": "audio/wav"})
            assert s2.status_code == 200, s2.text
        ap = c.post(f"/v1/contracts/{cid}/approve", json={}, headers=H)
        assert ap.status_code == 200, ap.text
        st = ap.json()["settlement"]
        rc = c.get(f"/v1/contracts/{cid}/receipt", headers=NH)
        assert rc.status_code == 200 and rc.json()["chain_verified"] is True
        rep = c.get(f"/v1/voices/{nid}/reputation").json()
        assert rep["completed"] == 1, rep
        pack_note = ""
        if i == 0:  # first job also rehearses the delivery pack (real transcribe)
            pk = c.post(f"/v1/contracts/{cid}/pack", json={"tier": "basic"}, headers=H)
            assert pk.status_code == 200, pk.text
            files = sorted(pk.json()["manifest"]["files"])
            assert "narration.wav" in files and "narration.mp3" in files
            pack_note = f" pack={files}"
        results.append({"job": i, "contract": cid, "payout_usd": price["narrator_payout"],
                        "settled_minor": st["amount_minor"],
                        "correction": i == n - 1})
        print(f"[{i + 1}/{n}] {cid} payout=${price['narrator_payout']:.2f} "
              f"settled={st['amount_minor']}c correction={i == n - 1} chain=ok{pack_note}", flush=True)
    total = round(sum(r["payout_usd"] for r in results), 2)
    print(f"FLEET OK: {n}/{n} settled, narrator total=${total:.2f} (100%), "
          f"reputation recorded on all {n} narrators.")
    _segmented_rehearsal(c, H)
    return {"settled": n, "total_usd": total, "results": results}


def _segmented_rehearsal(c, H):
    """One contract through modular capture: passages -> takes -> assembly."""
    nid = "nar_fleet_seg"
    A.DB.save_narrator({"id": nid})
    script = ("Beyond the mountains lay a city forgotten for centuries. "
              "Lanterns lit one by one along the empty streets. "
              "Nobody who entered ever spoke of what they found.")
    r = c.post("/v1/contracts", json={"script_text": script,
                                      "narrator_ids": [nid]}, headers=H)
    assert r.status_code == 200, r.text
    cid = r.json()["contract"]["contract_id"]
    segs = c.get(f"/v1/contracts/{cid}/segments", headers=H).json()["manifest"]["segments"]
    assert len(segs) == 3, segs
    tok = A.SESS.create("sub_" + nid, nid + "@fleet.test", nid)
    NH = {"X-HV-Session": tok}
    assert c.post(f"/v1/offers/{cid}/accept", json={}, headers=NH).status_code == 200
    for i, s in enumerate(segs):
        t = c.post(f"/v1/contracts/{cid}/segments/{s['id']}/takes",
                   content=make_wav(amp=10000 + i * 2000, secs=1.2),
                   headers={**NH, "Content-Type": "audio/wav"})
        assert t.status_code == 200, t.text
        a = c.post(f"/v1/contracts/{cid}/segments/{s['id']}/accept",
                   json={"sha256": t.json()["sha256"]}, headers=NH)
        assert a.status_code == 200
    asm = c.post(f"/v1/contracts/{cid}/assemble", json={}, headers=NH)
    assert asm.status_code == 200, asm.text
    assert len(asm.json()["edit_map"]) == 3
    assert c.post(f"/v1/contracts/{cid}/approve", json={}, headers=H).status_code == 200
    print(f"[seg] {cid} 3 passages -> takes -> master "
          f"{asm.json()['total_ms']:.0f}ms -> settled chain=ok", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()
    run_fleet(args.n)


if __name__ == "__main__":
    main()
