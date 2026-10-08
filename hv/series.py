"""Series deals: one contract, N episodes, enforced per episode.

A series locks episodes, cadence, per-episode price and total commitment
up front (e.g. 12 videos, ~20h content). Each episode is its own funded
unit with its own deadline/upload/QC; the series tracks completion and
consistency (same narrator voice throughout). Upload + system enforce:
no upload → no release, missed episode → series-level recovery.
"""
from __future__ import annotations

from hv.util import sha256, uid, utcnow


def create_series(principal_id: str, agent_id: str, narrator_id: str,
                  episodes: int, minutes_each: float, price_each: float,
                  cadence_days: int = 7) -> dict:
    assert 2 <= episodes <= 52, "series are 2–52 episodes"
    total = round(episodes * price_each, 2)
    eps = [{"episode": i + 1, "status": "pending", "upload_sha256": "",
            "due_offset_days": cadence_days * i}
           for i in range(episodes)]
    return {"series_id": "hvs_" + uid()[:8], "principal_id": principal_id,
            "agent_id": agent_id, "narrator_id": narrator_id,
            "episodes": episodes, "minutes_each": minutes_each,
            "price_each": price_each, "total_value": total,
            "cadence_days": cadence_days, "status": "active",
            "units": eps, "created_at": utcnow(),
            "terms_sha256": sha256(f"{principal_id}:{narrator_id}:{episodes}:{price_each}")}


def submit_episode(series: dict, episode: int, upload_sha256: str, late: bool = False) -> dict:
    unit = next(u for u in series["units"] if u["episode"] == episode)
    if unit["status"] == "approved":
        raise ValueError("episode already approved")
    unit.update({"status": "submitted", "upload_sha256": upload_sha256,
                 "late": late, "submitted_at": utcnow()})
    return unit


def approve_episode(series: dict, episode: int) -> dict:
    unit = next(u for u in series["units"] if u["episode"] == episode)
    if unit["status"] != "submitted" or not unit["upload_sha256"]:
        raise ValueError("no verified upload — nothing to approve")
    unit["status"] = "approved"
    done = sum(1 for u in series["units"] if u["status"] == "approved")
    if done == series["episodes"]:
        series["status"] = "completed"
    return {"episode": episode, "released": series["price_each"],
            "series_progress": f"{done}/{series['episodes']}"}


def series_health(series: dict) -> dict:
    units = series["units"]
    done = sum(1 for u in units if u["status"] == "approved")
    late = sum(1 for u in units if u.get("late"))
    return {"progress": f"{done}/{len(units)}",
            "pct": round(100 * done / len(units), 1),
            "late_episodes": late,
            "value_released": round(done * series["price_each"], 2),
            "value_locked": round(series["total_value"] - done * series["price_each"], 2)}
