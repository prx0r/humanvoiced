"""MCP over the real engine: search, quote, draft, status."""
import sys

sys.path.insert(0, ".")

import importlib.util as _ilu
import os

sys.path.insert(0, ".")

from hv.ledger import EventLedger
from hv.store import Store
from hv.util import sha256


def _load_local_server():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        "mcp", "server.py")
    spec = _ilu.spec_from_file_location("hv_mcp_server", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load_local_server()


def _db(tmp_path):
    import tempfile
    d = tempfile.mkdtemp(prefix="hv-mcp-")
    M.DB = Store(d + "/m.db")
    M.LED = EventLedger(d + "/e.db")
    M.DB.save_agent(sha256("key1"), {"agent_id": "ag1", "principal_id": "org1",
                                     "max_job_minor": 10 ** 9,
                                     "max_daily_minor": 10 ** 9})
    return M.DB


def _call(name, args):
    return M.handle("tools/call", {"name": name, "arguments": args})


def test_tools_list_and_auth(tmp_path):
    _db(tmp_path)
    names = [t["name"] for t in M.handle("tools/list", {})["tools"]]
    assert "hv.contract.draft" in names and "hv.pricing.quote" in names
    assert "error" in _call("hv.pricing.quote", {"script_text": "hi there",
                                                 "agent_key": "bogus"})
    assert M.handle("nope", {}) == {"error": "unknown method"}


def test_search_quote_draft_status(tmp_path):
    DB = _db(tmp_path)
    DB.save_narrator({"id": "nar_m1", "handle": "marta", "languages": ["en"],
                      "profile_published": {"display_name": "Marta"},
                      "samples": [], "prefs": {}})
    DB.save_narrator({"id": "nar_hid", "handle": "ghost"})
    s = _call("hv.voices.search", {"job": {"language": "en"}, "limit": 5})
    ids = [m["voice_id"] for m in s["result"]["matches"]]
    assert ids == ["nar_m1"]  # unpublished excluded
    q = _call("hv.pricing.quote", {"script_text": "word " * 1500, "agent_key": "key1"})
    assert q["result"]["narrator_payout"] == 10.0
    assert q["result"]["customer_price"] == 10.0 + q["result"]["service_fee_usd"]
    d = _call("hv.contract.draft", {"script_text": "hello world " * 40,
                                    "narrator_ids": ["nar_m1"], "agent_key": "key1"})
    assert d["result"]["approval_url"].startswith("https://humanvoiced.com/order.html")
    assert DB.get_order(d["result"]["order_id"])["status"] == "awaiting_buyer_approval"
    st = _call("hv.contract.status", {"contract_id": "hvc_nope", "agent_key": "key1"})
    assert "error" in st
    rep = _call("hv.reputation.get", {"narrator_id": "nar_m1"})
    assert rep["result"]["history_label"] == "new_voice"


def test_portfolio_readout_and_compare(tmp_path):
    DB = _db(tmp_path)
    DB.save_narrator({"id": "nar_p1", "handle": "pia", "languages": ["en"],
                      "profile_published": {"display_name": "Pia", "bio": "Warm reads"},
                      "samples": [{"sha256": "a" * 64, "kind": "natural",
                                   "language": "en", "consented_public": True},
                                  {"sha256": "b" * 64, "kind": "secret",
                                   "consented_public": False}],
                      "prefs": {"categories": ["storytelling"]},
                      "reputation": {"completed": 3, "vector": {"Q": 0.9},
                                     "verified_incidents": 0, "appeals_won": 0}})
    DB.save_narrator({"id": "nar_hidden", "handle": "ghost"})
    p = _call("hv.portfolio.get", {"handle": "pia"})
    assert p["result"]["display_name"] == "Pia"
    assert len(p["result"]["samples"]) == 1  # private sample excluded
    assert p["result"]["samples"][0]["play_url"].endswith("a" * 64)
    assert p["result"]["reputation"]["completed"] == 3
    assert "error" in _call("hv.portfolio.get", {"handle": "ghost"})
    cmp_ = _call("hv.voices.compare", {"narrator_ids": ["nar_p1", "nar_hidden"],
                                       "preferences": {}})
    assert [c["narrator_id"] for c in cmp_["result"]["compared"]] == ["nar_p1"]
    assert cmp_["result"]["compared"][0]["samples"] == 1
