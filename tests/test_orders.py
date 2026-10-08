"""Orders: draft → buyer_authorized → funded. Agents propose, humans approve."""
import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

import api.app as A

A.ALLOW_SIMULATED = True

import tempfile as _tf
_tmp = _tf.mkdtemp(prefix="hv-ord-")
import hv.ledger as _led
A.led = _led.EventLedger(_tmp + "/ev.db")
import hv.upload as _upl
_upl.RAW_DIR = _tmp + "/audio"


def _client(tmp_path):
    import hv.store as _st
    A.DB = _st.Store(str(tmp_path / "o.db"))
    from hv.sessions import SessionStore
    A.SESS = SessionStore(str(tmp_path / "o-sess.db"))
    A.AGENTS.clear()
    A.AGENTS["k1"] = {"agent_id": "ag1", "principal_id": "org1",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    return TestClient(A.app)


def test_draft_approve_funds_and_offers(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_o1"})
    d = c.post("/v1/orders/draft", json={"script_text": "hello world " * 40,
                                         "narrator_ids": ["nar_o1"]}, headers=H)
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["status"] == "awaiting_buyer_approval"
    assert body["approval_url"].startswith("https://humanvoiced.com/order.html?o=hvo_")
    assert body["quote"]["narrator_payout_usd"] == body["quote"]["customer_price_usd"]
    # nothing funded, no contract yet
    assert A.DB.get_order(body["order_id"])["contract_id"] is None
    # token-gated terms view
    assert c.get(f"/v1/orders/{body['order_id']}").status_code == 404
    terms = c.get(f"/v1/orders/{body['order_id']}",
                  params={"t": body["approval_token"]}).json()
    assert terms["terms_hash"] == body["terms_hash"]
    # wrong hash refuses (terms changed)
    bad = c.post(f"/v1/orders/{body['order_id']}/approve",
                 json={"token": body["approval_token"], "terms_hash": "0" * 64})
    assert bad.status_code == 409
    # approval funds + offers
    ok = c.post(f"/v1/orders/{body['order_id']}/approve",
                json={"token": body["approval_token"], "terms_hash": body["terms_hash"]})
    assert ok.status_code == 200, ok.text
    cid = ok.json()["contract_id"]
    assert A.DB.get_contract(cid)["funding_status"] == "secured"
    assert A.DB.get_contract(cid)["status"] == "offered"
    # single-use
    again = c.post(f"/v1/orders/{body['order_id']}/approve",
                   json={"token": body["approval_token"], "terms_hash": body["terms_hash"]})
    assert again.status_code == 409
    # narrator can accept the offered contract
    tok = A.SESS.create("so", "o@x", "nar_o1")
    assert c.post(f"/v1/offers/{cid}/accept", json={},
                  headers={"X-HV-Session": tok}).status_code == 200
