"""Append-only contract event ledger — port of workerkit EventLedger.

Scope key is contract_id. Hash chain is per-contract: each event binds
(event_id, contract_id, type, payload, server timestamp, prev hash).
verify_chain() recomputes every link; any edit breaks the chain.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hv.util import sha256, uid, utcnow


class EventLedger:
    def __init__(self, db_path: str = "data/hv-events.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contract_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE,
                contract_id TEXT,
                event_type TEXT,
                actor TEXT,
                actor_type TEXT,
                payload TEXT,
                payload_sha256 TEXT,
                recorded_at TEXT,
                prev_sha256 TEXT,
                event_sha256 TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_contract ON contract_events(contract_id, seq)")
        conn.commit()
        conn.close()

    def _conn(self):
        return sqlite3.connect(str(self.db_path))

    def append(self, contract_id: str, event_type: str, payload: dict,
               actor: str = "platform", actor_type: str = "system") -> str:
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            event_id = uid("evt_")
            now = utcnow()
            payload_json = json.dumps(payload, sort_keys=True)
            row = conn.execute(
                "SELECT event_sha256 FROM contract_events WHERE contract_id=? ORDER BY seq DESC LIMIT 1",
                (contract_id,)).fetchone()
            prev_hash = row[0] if row else ""
            event_hash = sha256(":".join([event_id, contract_id, event_type, actor,
                                          actor_type, payload_json, now, prev_hash]))
            conn.execute(
                """INSERT INTO contract_events
                   (event_id, contract_id, event_type, actor, actor_type, payload,
                    payload_sha256, recorded_at, prev_sha256, event_sha256)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, contract_id, event_type, actor, actor_type, payload_json,
                 sha256(payload_json), now, prev_hash, event_hash))
            conn.commit()
        finally:
            conn.close()
        return event_id

    def get_events(self, contract_id: str) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT event_id, event_type, actor, actor_type, payload, payload_sha256,"
            " recorded_at, prev_sha256, event_sha256 FROM contract_events"
            " WHERE contract_id=? ORDER BY seq", (contract_id,)).fetchall()
        conn.close()
        keys = ["event_id", "event_type", "actor", "actor_type", "payload",
                "payload_sha256", "recorded_at", "prev_sha256", "event_sha256"]
        out = []
        for r in rows:
            d = dict(zip(keys, r))
            d["payload"] = json.loads(d["payload"])
            out.append(d)
        return out

    def verify_chain(self, contract_id: str) -> tuple[bool, str]:
        events = self.get_events(contract_id)
        prev = ""
        for e in events:
            if e["prev_sha256"] != prev:
                return False, f"link broken at {e['event_id']}"
            payload_json = json.dumps(e["payload"], sort_keys=True)
            expect = sha256(":".join([e["event_id"], contract_id, e["event_type"],
                                      e["actor"], e["actor_type"], payload_json,
                                      e["recorded_at"], e["prev_sha256"]]))
            if expect != e["event_sha256"]:
                return False, f"hash mismatch at {e['event_id']}"
            prev = e["event_sha256"]
        return True, f"ok ({len(events)} events)"
