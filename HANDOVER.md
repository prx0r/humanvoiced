# HANDOVER — HumanVoiced (fresh agent start here)

Date: 2026-10-08. Repo: `prx0r/humanvoiced` (public), main branch.
Live: https://humanvoiced.com (Pages) + https://api.humanvoiced.com (this box :8801).

## Run it

```bash
./hv-serve.sh            # API :8801, vault-injected env, nothing on disk
python3 -m pytest tests/ -q   # 60+ tests, must stay green
```

Deploy site: `wrangler pages deploy web --project-name humanvoiced`
(CF token + account from vault `oracle`).

## State of the world

- 20 theses saved verbatim (THESIS/PAYMENTS/LIBRARY/DUBBING/SERIES/QUALITY/
  VOICE-ENGINE/GLOBAL/MVP/NONPROFIT/LAUNCH/WEDGE/DEMAND/GOLD + specs).
- Backend: FastAPI + SQLite (`data/`), hash-chained ledger, sessions+cookies,
  server-side pricing (curve `1.54+1.65t^0.71`, heatmaps), escrow rails with
  honesty gates, disputes with rule IDs, series, localisation, casting,
  auditions, stablecoin prefs, transparency, demand templates.
- Audio: upload→freeze→CF Whisper→analysis→draft→publish→catalogue+search.
  No GPU here; hosted swaps spec'd in `docs/vendor/`.
- Frontend: landing, onboard (record + WAV encode + live spectrogram + mic
  advice + draft/review/publish flow), dynamic portfolio (?h=), all on Pages.
- Tests: pytest, GitHub Actions CI green. No secrets in git (audited).

## Secrets (vault `oracle`, NEVER tree/chat)

DASHSCOPE_API_KEY (needs console activation), GOOGLE_CLIENT_ID/SECRET_HV
(needs redirect URI), X_*, social passwords, CF/R2/TELNYX, MESHY_* (ask
before spend), SERPAPI. OPENROUTER was wrong key — retired. R2 S3 sets dead
— mint fresh for object upload. FAL_KEY + OPENROUTER_API_KEY missing.

## Gotchas learned the hard way

- Edit tool: always Read before Edit/Write; decorator-eating bug — after
  inserting before `@app.*` lines, verify the decorator survived.
- pkill -f matches your own shell — use bracket trick `[p]attern`.
- setsid launches die with short tool timeouts — verify in a later call.
- SQLite :memory: is per-connection — tests use tmp files.
- Cloudflare Pages custom domains need manual DNS (doesn't auto-wire).
- Tunnel ingress edits need full ingress list resubmitted.
- Dash (agentcom, separate repo /root/influence): reconcile-on-read melts
  CPU — TTL cache + WAL + locks + run_logs cap already applied.

## Next (owner's direction)

1. Google redirect URI (owner click) → first real narrator onboard.
2. DASHSCOPE_API_KEY activation → Omni describe live.
3. FAL_KEY → demo TTS.
4. Trustless Work testnet → real escrow.
5. R2 S3 keys → object upload off disk.
6. Next.js migration, PG deploy, Stripe-test wiring.

## 2026-10-08 late session (onboarding incident)

Owner recorded + authed and landed back on a dead page: recording lost
(navigation wiped memory), no signed-in state shown. Root causes fixed:
login-first step order, `?login=ok` banner, `GET /v1/narrators/me` session
endpoint, cookie already spanned `.humanvoiced.com`. Lesson for next agent:
any cross-navigation flow must persist artifacts (server draft or storage)
and render auth state on load — never trust in-memory JS across OAuth.
