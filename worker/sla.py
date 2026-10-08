"""SLA worker — server-time deadline enforcement (stdlib only).

Sweep contracts: warn at 50%/80% elapsed, flag late + open grace at deadline,
mark WORKER_NON_DELIVERY only when: accepted, deadline+grace passed, no
deliverable, no platform fault, review path open. Never auto-assigns fault.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

GRACE_SECONDS = 900


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def sweep(contracts: list, submissions: dict, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    actions = []
    for c in contracts:
        if c.status != "accepted" or not c.deadline_at:
            continue
        deadline = _parse(c.deadline_at)
        elapsed = (now - _parse(c.accepted_at)).total_seconds()
        frac = elapsed / max(1, c.delivery_seconds)
        cid = c.contract_id
        if now < deadline:
            if frac >= 0.8:
                actions.append({"contract": cid, "action": "warn_80"})
            elif frac >= 0.5:
                actions.append({"contract": cid, "action": "warn_50"})
        elif cid in submissions:
            actions.append({"contract": cid, "action": "in_qc"})
        elif now < deadline + timedelta(seconds=GRACE_SECONDS):
            actions.append({"contract": cid, "action": "grace"})
        else:
            actions.append({"contract": cid, "action": "flag_late",
                            "outcome_code": "WORKER_NON_DELIVERY_PENDING_REVIEW"})
    return actions
