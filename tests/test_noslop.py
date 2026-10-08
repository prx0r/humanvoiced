"""NoSlop preflight: suggest-only, never gates, never rewrites."""
import sys
from unittest.mock import patch

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

import api.app as A

A.ALLOW_SIMULATED = True

import tempfile as _tf
_tmp = _tf.mkdtemp(prefix="hv-ns-")
import hv.ledger as _led
A.led = _led.EventLedger(_tmp + "/ev.db")
import hv.upload as _upl
_upl.RAW_DIR = _tmp + "/audio"


def _client(tmp_path):
    import hv.store as _st
    A.DB = _st.Store(str(tmp_path / "ns.db"))
    from hv.sessions import SessionStore
    A.SESS = SessionStore(str(tmp_path / "ns-sess.db"))
    A.AGENTS.clear()
    A.AGENTS["k1"] = {"agent_id": "ag1", "principal_id": "org1",
                      "max_job_minor": 10 ** 9, "max_daily_minor": 10 ** 9}
    return TestClient(A.app)


def test_preflight_off_by_default(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_n1"})
    r = c.post("/v1/contracts", json={"script_text": "hello world " * 40,
                                      "narrator_ids": ["nar_n1"]}, headers=H)
    assert r.status_code == 200
    assert "script_review" not in r.json()["contract"]


def test_preflight_suggest_only_never_gates(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_n2"})
    script = ("In conclusion, this tapestry of words is important. "
              "Hello world plain speech here. " * 10)
    r = c.post("/v1/contracts",
               json={"script_text": script, "narrator_ids": ["nar_n2"],
                     "script_review": "suggest_only"}, headers=H)
    assert r.status_code == 200, r.text  # funded regardless of findings
    doc = r.json()["contract"]
    rev = doc["script_review"]
    assert rev["mode"] == "suggest_only"
    assert "is_ai" not in rev and "confidence" not in rev  # no verdict surfaced
    assert doc["funding_status"] == "secured"  # never a gate
    assert doc["script_sha256"]  # script untouched, never rewritten


def test_preflight_unavailable_is_honest(tmp_path):
    c = _client(tmp_path)
    H = {"X-HV-Agent-Key": "k1"}
    A.DB.save_narrator({"id": "nar_n3"})
    with patch("hv.noslop._local_detect", return_value=None), \
         patch("hv.noslop._remote_detect", return_value=None):
        r = c.post("/v1/contracts",
                   json={"script_text": "hello world " * 40,
                         "narrator_ids": ["nar_n3"],
                         "script_review": "suggest_only"}, headers=H)
    assert r.status_code == 501
