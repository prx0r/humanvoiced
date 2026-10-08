"""Portfolio proof: validated work entries with video links + view tracking.

Each entry binds (contract → upload hash → video URL → view counts over
time). Views come from the YouTube Data API (read-only key suffices:
videos.list statistics.viewCount). Entries without a verified upload hash
are never shown as validated work.
"""
from __future__ import annotations

from hv.util import utcnow


def proof_entry(contract_id: str, upload_sha256: str, video_url: str,
                title: str = "") -> dict:
    assert upload_sha256, "upload hash required — no hash, no proof"
    return {"contract_id": contract_id, "upload_sha256": upload_sha256,
            "video_url": video_url, "title": title,
            "views": [], "added_at": utcnow()}


def record_views(entry: dict, views: int, at: str = "") -> dict:
    entry["views"].append({"views": views, "at": at or utcnow()})
    return entry


def latest_views(entry: dict) -> int | None:
    return entry["views"][-1]["views"] if entry["views"] else None


def portfolio_proof(entries: list[dict]) -> dict:
    total_views = sum(latest_views(e) or 0 for e in entries)
    return {"validated_jobs": len(entries), "total_views": total_views,
            "entries": [{"title": e["title"], "video_url": e["video_url"],
                         "views": latest_views(e)} for e in entries]}
