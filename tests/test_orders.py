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
    assert body["quote"]["customer_price_usd"] == body["quote"]["narrator_payout_usd"] + body["quote"]["service_fee_usd"]
    # nothing funded, no contract yet
    assert A.DB.get_order(body["order_id"])["contract_id"] is None
    # token-gated terms view
    assert c.get(f"/v1/orders/{body['order_id']}").status_code == 404
    terms = c.get(f"/v1/orders/{body['order_id']}",
                  params={"t": body["approval_token"]}).json()
    assert terms["terms_hash"] == body["terms_hash"]
    # wrong hash refuses (terms changed)
    A.DB.save_narrator({"id": "buyer_0", "email": "buyer0@x.com"})
    bt0 = A.SESS.create("sb0", "buyer0@x.com", "buyer_0")
    bad = c.post(f"/v1/orders/{body['order_id']}/approve",
                 json={"token": body["approval_token"], "terms_hash": "0" * 64},
                 headers={"X-HV-Session": bt0})
    assert bad.status_code == 409
    # approval needs a signed-in buyer, not just the bearer link
    anon = c.post(f"/v1/orders/{body['order_id']}/approve",
                  json={"token": body["approval_token"], "terms_hash": body["terms_hash"]})
    assert anon.status_code == 401
    A.DB.save_narrator({"id": "buyer_1", "email": "buyer@x.com"})
    bt = A.SESS.create("sb", "buyer@x.com", "buyer_1")
    BH = {"X-HV-Session": bt}
    # approval funds + offers
    ok = c.post(f"/v1/orders/{body['order_id']}/approve",
                json={"token": body["approval_token"], "terms_hash": body["terms_hash"]},
                headers=BH)
    assert ok.status_code == 200, ok.text
    assert ok.json()["contract_id"]
    assert A.DB.get_order(body["order_id"])["approval"]["by"] == "buyer_1"
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


def test_cue_mode_floor_and_rights(tmp_path):
    from hv import brief as _br
    m = _br.compile({"mode": "cue", "segments": [
        {"id": "r1", "cue": "Surprised gasp, then a laugh.",
         "context": "comedy sketch", "variations": 3}]}, "")
    assert m["segments"][0]["is_cue"] is True
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_cue"})
    r = c.post("/v1/orders/draft",
               json={"script_text": "Surprised gasp, then a laugh.",
                     "narrator_ids": ["nar_cue"],
                     "brief": {"mode": "cue", "segments": [
                         {"id": "r1", "cue": "Surprised gasp, then a laugh."}]}},
               headers=H)
    assert r.status_code == 200, r.text
    q = r.json()["quote"]
    assert q["narrator_payout_usd"] == 5.00  # cue floor, not word math
    assert "rights_statement" in q and "vocal identity" in q["rights_statement"]
    A.DB.save_narrator({"id": "buyer_2", "email": "b2@x.com"})
    bt = A.SESS.create("sb2", "b2@x.com", "buyer_2")
    ok = c.post(f"/v1/orders/{r.json()['order_id']}/approve",
                json={"token": r.json()["approval_token"],
                      "terms_hash": r.json()["terms_hash"]},
                headers={"X-HV-Session": bt})
    assert ok.status_code == 200
    doc = A.DB.get_contract(ok.json()["contract_id"])
    assert doc["rights"]["ai_training"] is False
    assert doc["segment_manifest"]["mode"] == "cue"


def test_session_quote_and_draft(tmp_path):
    c = _client(tmp_path)
    A.DB.save_narrator({"id": "buyer_3", "email": "b3@x.com"})
    bt = A.SESS.create("sb3", "b3@x.com", "buyer_3")
    BH = {"X-HV-Session": bt}
    assert c.post("/v1/contracts/quote", json={"script_text": "hello " * 40}).status_code == 401
    q = c.post("/v1/contracts/quote", json={"script_text": "hello " * 40}, headers=BH)
    assert q.status_code == 200 and q.json()["customer_price"] > 0
    A.DB.save_narrator({"id": "nar_d1"})
    d = c.post("/v1/orders/draft", json={"script_text": "hello " * 40,
                                         "narrator_ids": ["nar_d1"]}, headers=BH)
    assert d.status_code == 200
    assert d.json()["approval_url"].startswith("https://humanvoiced.com/order.html")


def test_remote_mcp_and_oauth_next(tmp_path):
    c = _client(tmp_path)
    bad = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1,
                               "method": "tools/list", "params": {}},
                 headers={"Origin": "https://evil.example"})
    assert bad.status_code == 403
    ok = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1,
                              "method": "tools/list", "params": {}})
    assert ok.status_code == 200
    assert "hv.contract.draft" in [t["name"] for t in ok.json()["result"]["tools"]]
    assert c.post("/mcp", json={"id": 1, "method": "tools/list", "params": {}}).status_code == 422
    st = A.SESS.issue_state("/order.html?o=hvo_1&t=x")
    assert A.SESS.pop_next(st) == "/order.html?o=hvo_1&t=x"
    st2 = A.SESS.issue_state("https://evil.example/x")
    assert A.SESS.pop_next(st2) == ""  # absolute URLs never stored
