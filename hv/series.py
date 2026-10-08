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


# --- Master agreement: mutual enforcement (SERIES.md §4) ---

def master_agreement(principal_id: str, agent_id: str, narrator_id: str,
                     episodes: int, max_words_per_episode: int,
                     price_each: float, minimum_guaranteed: int,
                     contract_weeks: int = 8, delivery_sla_hours: int = 24,
                     rights: dict | None = None) -> dict:
    """Master terms: creator owes scripts+funding+minimum; narrator owes
    capacity+acceptance+delivery. Neither side enforceable by lock-in —
    cancellation settles on the guaranteed minimum."""
    assert 0 < minimum_guaranteed <= episodes, "guarantee within series size"
    return {"master_id": "hvm_" + uid()[:8], "principal_id": principal_id,
            "agent_id": agent_id, "narrator_id": narrator_id,
            "episodes": episodes, "max_words_per_episode": max_words_per_episode,
            "price_each": price_each, "minimum_guaranteed": minimum_guaranteed,
            "contract_weeks": contract_weeks, "delivery_sla_hours": delivery_sla_hours,
            "rights": rights or {"online_video_commercial_use": True,
                                 "portfolio_attribution": True,
                                 "voice_cloning": False},
            "scripts_supplied": 0, "status": "active", "created_at": utcnow()}


def creator_supply_script(master: dict, episode: int, late: bool = False) -> dict:
    """Creator supplies script: narrator deadline starts now; late supply
    shifts the deadline with no worker penalty."""
    master["scripts_supplied"] += 1
    return {"episode": episode, "script supplied": True,
            "deadline_shifted": late, "worker_penalty": "none"}


def settle_termination(master: dict, completed_episodes: int) -> dict:
    """Creator stops commissioning: honour guaranteed minimum or terminate."""
    owed = max(0, master["minimum_guaranteed"] - completed_episodes)
    return {"completed": completed_episodes,
            "guaranteed_minimum": master["minimum_guaranteed"],
            "termination_owed_episodes": owed,
            "termination_value": round(owed * master["price_each"], 2)}


# --- Verification levels (SERIES.md §3) ---

LEVELS = ("platform", "publication", "channel")


def verify_publication(contract_ok: bool, video_url: str, channel_match: bool,
                       creator_confirmed: bool, oauth_channel: bool = False,
                       confidential: bool = False) -> dict:
    """platform → publication → channel. Confidential work strengthens the
    internal score without public exposure."""
    if not contract_ok:
        return {"level": None, "display": "unverified"}
    if oauth_channel and channel_match and creator_confirmed:
        level = "channel"
    elif video_url and channel_match and creator_confirmed:
        level = "publication"
    else:
        level = "platform"
    return {"level": level,
            "display": "Verified channel collaboration" if level == "channel"
            else "Published work" if level == "publication"
            else "Verified recording",
            "public": not confidential}

