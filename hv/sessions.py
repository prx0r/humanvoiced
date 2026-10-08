"""Login sessions: OAuth state binding + narrator identity for mutations.

Google `state` is bound at login start and consumed once at callback —
no reuse, 10-minute expiry. Session tokens are opaque, SQLite-persisted
(survive restarts), and map to exactly one narrator_id. Mutations take
identity from the session, never from the request body.
"""
from __future__ import annotations

import secrets
import sqlite3
import time
from pathlib import Path

STATE_TTL = 600


class SessionStore:
    def __init__(self, db_path: str = "data/hv-sessions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS oauth_state (state TEXT PRIMARY KEY, created REAL)")
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, sub TEXT, email TEXT, narrator_id TEXT, created REAL)")
        conn.commit()
        conn.close()

    def _conn(self):
        return sqlite3.connect(str(self.db_path))

    def issue_state(self) -> str:
        st = secrets.token_urlsafe(24)
        conn = self._conn()
        conn.execute("INSERT INTO oauth_state VALUES (?, ?)", (st, time.time()))
        conn.commit()
        conn.close()
        return st

    def consume_state(self, state: str) -> bool:
        conn = self._conn()
        row = conn.execute("SELECT created FROM oauth_state WHERE state=?", (state,)).fetchone()
        if not row:
            conn.close()
            return False
        conn.execute("DELETE FROM oauth_state WHERE state=?", (state,))
        conn.commit()
        conn.close()
        return (time.time() - row[0]) <= STATE_TTL

    def create(self, sub: str, email: str, narrator_id: str) -> str:
        tok = secrets.token_urlsafe(32)
        conn = self._conn()
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                     (tok, sub, email, narrator_id, time.time()))
        conn.commit()
        conn.close()
        return tok

    def narrator_for(self, token: str) -> str | None:
        conn = self._conn()
        row = conn.execute("SELECT narrator_id FROM sessions WHERE token=?", (token,)).fetchone()
        conn.close()
        return row[0] if row else None
