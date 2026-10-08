"""Google sign-in for HumanVoiced — stdlib only, mirrored on pogpet auth.py.

Secrets come from env at runtime (injected from vault oracle:
GOOGLE_CLIENT_ID_HV / GOOGLE_CLIENT_SECRET_HV). Nothing with values lives
in the tree. When unset, /login explains instead of 500ing.
PUBLIC_BASE selects the callback host (humanvoiced.com once bought).
"""
from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
INFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPE = "openid email profile"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID_HV", "")


def client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET_HV", "")


def public_base() -> str:
    return os.environ.get("PUBLIC_BASE", "https://humanvoiced.pages.dev")


def configured() -> bool:
    return bool(client_id() and client_secret())


def redirect_uri() -> str:
    return f"{public_base().rstrip('/')}/api/auth/google/callback"


def authorize_url(state: str = "") -> str:
    q = urllib.parse.urlencode({
        "client_id": client_id(),
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPE,
        "state": state or secrets.token_urlsafe(24),
        "access_type": "online",
        "prompt": "select_account",
    })
    return f"{AUTH_URL}?{q}"


def _post(url: str, data: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"google token {e.code}: {e.read().decode('utf-8', 'replace')[:200]}") from None


def exchange(code: str) -> dict:
    """code -> Google profile {sub, email, name, picture}."""
    tok = _post(TOKEN_URL, {"code": code, "client_id": client_id(),
                            "client_secret": client_secret(), "redirect_uri": redirect_uri(),
                            "grant_type": "authorization_code"})
    if "access_token" not in tok:
        raise RuntimeError(f"no access_token: {json.dumps(tok)[:200]}")
    req = urllib.request.Request(INFO_URL)
    req.add_header("Authorization", f"Bearer {tok['access_token']}")
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())
