"""Series persistence: master + units survive restarts (SQLite).

Episode approval settles through the rail: no release without a locked
intent, and the released amount is transfer evidence, not just accounting.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class SeriesStore:
    def __init__(self, db_path: str = "data/hv-series.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS series (master_id TEXT PRIMARY KEY, doc TEXT)")
        conn.commit()
        conn.close()

    def _conn(self):
        return sqlite3.connect(str(self.db_path))

    def save(self, master: dict, series: dict):
        conn = self._conn()
        conn.execute("INSERT OR REPLACE INTO series VALUES (?, ?)",
                     (master["master_id"], json.dumps({"master": master, "series": series})))
        conn.commit()
        conn.close()

    def load(self, master_id: str) -> dict | None:
        conn = self._conn()
        row = conn.execute("SELECT doc FROM series WHERE master_id=?", (master_id,)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None


def approve_episode_with_release(entry: dict, episode: int, rail, intent) -> dict:
    """Approve only against a verified upload; settle through the rail."""
    from hv import series as SE
    unit = next(u for u in entry["series"]["units"] if u["episode"] == episode)
    if unit["status"] != "submitted" or not unit.get("upload_sha256"):
        raise ValueError("no verified upload — nothing to approve")
    tx = rail.release(intent, entry["master"]["narrator_id"])
    unit["status"] = "approved"
    unit["settlement"] = tx
    done = sum(1 for u in entry["series"]["units"] if u["status"] == "approved")
    if done == entry["series"]["episodes"]:
        entry["series"]["status"] = "completed"
    return {"episode": episode, "settlement": tx,
            "series_progress": f"{done}/{entry['series']['episodes']}"}
