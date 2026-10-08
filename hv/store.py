"""Transactional storage: contracts, intents, scripts, offers, narrators, spend.

Replaces in-memory dicts. Every mutation commits in one transaction.
Scripts stored by hash (content-addressed); terms reference them.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class Store:
    def __init__(self, db_path: str = "data/hv.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS contracts (id TEXT PRIMARY KEY, doc TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS intents (contract_id TEXT PRIMARY KEY, doc TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS scripts (sha256 TEXT PRIMARY KEY, text TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS offers (contract_id TEXT, narrator_id TEXT, PRIMARY KEY (contract_id, narrator_id))")
        conn.execute("CREATE TABLE IF NOT EXISTS narrators (id TEXT PRIMARY KEY, doc TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS spend (agent_id TEXT, day TEXT, amount_minor INT, PRIMARY KEY (agent_id, day))")
        conn.execute("CREATE TABLE IF NOT EXISTS uploads (sha256 TEXT PRIMARY KEY, contract_id TEXT, narrator_id TEXT, bytes INT, at REAL)")
        conn.execute("CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, doc TEXT)")
        conn.commit()
        conn.close()

    def _conn(self):
        return sqlite3.connect(str(self.db_path), timeout=30)

    def save_contract(self, c: dict):
        conn = self._conn()
        conn.execute("INSERT OR REPLACE INTO contracts VALUES (?, ?)", (c["contract_id"], json.dumps(c)))
        conn.commit()
        conn.close()

    def get_contract(self, cid: str) -> dict | None:
        conn = self._conn()
        row = conn.execute("SELECT doc FROM contracts WHERE id=?", (cid,)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None

    def save_intent(self, cid: str, intent: dict):
        conn = self._conn()
        conn.execute("INSERT OR REPLACE INTO intents VALUES (?, ?)", (cid, json.dumps(intent)))
        conn.commit()
        conn.close()

    def get_intent(self, cid: str) -> dict | None:
        conn = self._conn()
        row = conn.execute("SELECT doc FROM intents WHERE contract_id=?", (cid,)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None

    def save_script(self, text: str) -> str:
        from hv.util import sha256
        h = sha256(text)
        conn = self._conn()
        conn.execute("INSERT OR IGNORE INTO scripts VALUES (?, ?)", (h, text))
        conn.commit()
        conn.close()
        return h

    def get_script(self, sha: str) -> str | None:
        conn = self._conn()
        row = conn.execute("SELECT text FROM scripts WHERE sha256=?", (sha,)).fetchone()
        conn.close()
        return row[0] if row else None

    def offer_to(self, cid: str, narrator_ids: list[str]):
        conn = self._conn()
        conn.executemany("INSERT OR IGNORE INTO offers VALUES (?, ?)", [(cid, n) for n in narrator_ids])
        conn.commit()
        conn.close()

    def is_offered(self, cid: str, nid: str) -> bool:
        conn = self._conn()
        row = conn.execute("SELECT 1 FROM offers WHERE contract_id=? AND narrator_id=?", (cid, nid)).fetchone()
        conn.close()
        return row is not None

    def record_upload(self, sha: str, cid: str, nid: str, nbytes: int):
        conn = self._conn()
        conn.execute("INSERT OR IGNORE INTO uploads VALUES (?, ?, ?, ?, ?)", (sha, cid, nid, nbytes, time.time()))
        conn.commit()
        conn.close()

    def upload_owner(self, sha: str, cid: str) -> str | None:
        conn = self._conn()
        row = conn.execute("SELECT narrator_id FROM uploads WHERE sha256=? AND contract_id=?", (sha, cid)).fetchone()
        conn.close()
        return row[0] if row else None

    def add_spend(self, agent_id: str, day: str, amount_minor: int):
        conn = self._conn()
        conn.execute("INSERT INTO spend VALUES (?, ?, ?) ON CONFLICT(agent_id, day) DO UPDATE SET amount_minor=amount_minor+?", (agent_id, day, amount_minor, amount_minor))
        conn.commit()
        conn.close()

    def day_spend(self, agent_id: str, day: str) -> int:
        conn = self._conn()
        row = conn.execute("SELECT amount_minor FROM spend WHERE agent_id=? AND day=?", (agent_id, day)).fetchone()
        conn.close()
        return row[0] if row else 0

    def save_narrator(self, doc: dict):
        conn = self._conn()
        conn.execute("INSERT OR REPLACE INTO narrators VALUES (?, ?)", (doc["id"], json.dumps(doc)))
        conn.commit()
        conn.close()

    def get_narrator(self, nid: str) -> dict | None:
        conn = self._conn()
        row = conn.execute("SELECT doc FROM narrators WHERE id=?", (nid,)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None

    def save_case(self, doc: dict):
        conn = self._conn()
        conn.execute("INSERT OR REPLACE INTO cases VALUES (?, ?)", (doc["case_id"], json.dumps(doc)))
        conn.commit()
        conn.close()

    def get_case(self, case_id: str) -> dict | None:
        conn = self._conn()
        row = conn.execute("SELECT doc FROM cases WHERE id=?", (case_id,)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None

    def list_narrators(self) -> list[dict]:
        conn = self._conn()
        rows = conn.execute("SELECT doc FROM narrators").fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]
