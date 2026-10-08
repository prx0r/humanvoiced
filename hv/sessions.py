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
SESSION_TTL = 30 * 86400


class SessionStore:
    def __init__(self, db_path: str = "data/hv-sessions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS oauth_state (state TEXT PRIMARY KEY, created REAL)")
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, sub TEXT, email TEXT, narrator_id TEXT, created REAL)")
        conn.execute("CREATE TABLE IF NOT EXISTS oauth_next (state TEXT PRIMARY KEY, next TEXT)")
        conn.commit()
        conn.close()

    def _conn(self):
        return sqlite3.connect(str(self.db_path))

    def issue_state(self, next_url: str = "") -> str:
        st = secrets.token_urlsafe(24)
        conn = self._conn()
        conn.execute("INSERT INTO oauth_state VALUES (?, ?)", (st, time.time()))
        if next_url.startswith("/") and "://" not in next_url:
            conn.execute("INSERT OR REPLACE INTO oauth_next VALUES (?, ?)", (st, next_url[:200]))
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

    def pop_next(self, state: str) -> str:
        conn = self._conn()
        row = conn.execute("SELECT next FROM oauth_next WHERE state=?", (state,)).fetchone()
        conn.execute("DELETE FROM oauth_next WHERE state=?", (state,))
        conn.commit()
        conn.close()
        return row[0] if row else ""

    def create(self, sub: str, email: str, narrator_id: str) -> str:
        tok = secrets.token_urlsafe(32)
        conn = self._conn()
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                     (tok, sub, email, narrator_id, time.time()))
        conn.commit()
        conn.close()
        return tok

    def narrator_for(self, token: str) -> str | None:
        import time as _t
        conn = self._conn()
        row = conn.execute("SELECT narrator_id, created FROM sessions WHERE token=?", (token,)).fetchone()
        conn.close()
        if not row:
            return None
        if _t.time() - row[1] > SESSION_TTL:
            self.revoke(token)
            return None
        return row[0]

    def revoke(self, token: str):
        conn = self._conn()
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit()
        conn.close()
