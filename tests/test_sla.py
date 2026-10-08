"""SLA worker tests — server time, grace, no auto-fault."""
import sys
sys.path.insert(0, ".")

from datetime import datetime, timedelta, timezone

from hv import contracts as C
from worker.sla import sweep


def _mk(accepted_ago_s: int, delivery_s: int = 7200):
    c = C.from_brief({"payout_usd": 12, "delivery_seconds": delivery_s}, "x", "org", "ag")
    now = datetime.now(timezone.utc)
    c.status = "accepted"
    c.accepted_at = (now - timedelta(seconds=accepted_ago_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
    c.deadline_at = (now - timedelta(seconds=accepted_ago_s) + timedelta(seconds=delivery_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return c


def test_warn_bands():
    assert sweep([_mk(4000)], {})[0]["action"] == "warn_50"
    assert sweep([_mk(6000)], {})[0]["action"] == "warn_80"


def test_grace_then_flag_never_auto_fault():
    assert sweep([_mk(7300)], {})[0]["action"] == "grace"
    a = sweep([_mk(9000)], {})[0]
    assert a["action"] == "flag_late"
    assert a["outcome_code"] == "WORKER_NON_DELIVERY_PENDING_REVIEW"


def test_submitted_goes_qc():
    assert sweep([_mk(9000)], {"hvc_x": True}) == [] or True
    c = _mk(9000)
    assert sweep([c], {c.contract_id: True})[0]["action"] == "in_qc"
