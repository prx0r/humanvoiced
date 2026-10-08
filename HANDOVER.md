# HANDOVER — HumanVoiced (fresh agent start here)

Date: 2026-10-08. Repo: `prx0r/humanvoiced`, main branch.
Live: https://humanvoiced.com (Pages) + https://api.humanvoiced.com (this box :8801).

## Run it

```bash
./hv-serve.sh            # API :8801, vault-injected env, nothing on disk
python3 -m pytest tests/ -q   # 109 tests, must stay green
python3 -m worker.fleet --n 10  # autonomous rehearsal (isolated tmp DBs)
python3 -m worker.benchmark A_DIR B_DIR --out OUT/  # blind A/B harness
```

Deploy site: `wrangler pages deploy web --project-name humanvoiced`
(CF token + account from vault `oracle`).
Push: owner asked for direct pushes this session (`git push origin main`).

## What this is now

Agent-directed recording + production system, not a voiceover marketplace:
agent/creator submits script → passages → human records takes on phone →
assembly → Clean/Studio packs → agent downloads. Narrator gets 100% of
payout; buyer pays payout + $1 service fee + pays processing separately.

Two site sections, one API: customer pages (index, voices, brief,
portfolio, order) and talent pages (home, workspace studio, onboard).
Spanish landing live (`?lang=es`); UI strings in `web/i18n/`.

## State of the world

- Full loop wired: quote → draft order → buyer approval (session-required)
  → fund → offer → accept (signed statement) → takes → assemble → approve →
  settle → receipt + durable reputation. 109 tests green, CI fixed (needs
  numpy/scipy), fleet proves 10/10 + segmented rehearsal autonomously.
- Money: server pricing (curve + $1 fee + $5 cue floor), atomic budgets,
  simulated rail (test only, default off), honest hosted adapters
  (veed/fal needs FAL_KEY — stored, never used without owner OK).
- Production: basic + studio (ride/deesser/ref-match) + clean tiers,
  channel presets + match-my-channel, delivery packs with manifests,
  director advisories, capture QC, dispute rules, series, localisation.
- Trust: content tiers (prohibited/refused, restricted/held for review,
  mature/prefs-filtered), talent content prefs, acceptance records,
  safety reports block settle+pack, exclusive-buyout rights by default.
- MCP: 9 real tools over stdio (`python3 mcp/server.py`) + `POST /mcp`
  (origin-checked). NOTE: local `mcp/` dir collides with installed MCP
  SDK package — run by file path, never `python -m`; tests load by path.

## Secrets (vault `oracle` + `.env`, NEVER git)

`.env` (0600, git-ignored): DASHSCOPE_API_KEY, GOOGLE_CLIENT_ID_HV,
GOOGLE_CLIENT_SECRET_HV, FAL_KEY (stored, owner approval required before
any fal call). Vault adds: CLOUDFLARE_*, R2_S3_*, SERPAPI, social/X keys.
Missing/not-found: HV_ADMIN_TOKEN (admin review endpoints inert in prod),
OPENROUTER_API_KEY, real payment keys, AUPHONIC_KEY, ELEVENLABS_KEY.

## Gotchas learned the hard way

- Edit tool: never call with identical old/new — it glues lines. Always
  `ast.parse` api/app.py after edits; indent inside try-blocks is 8 spaces.
- Tests share the `api.app` module: each file rebinds A.DB/A.led to tmp.
  `UPL.RAW_DIR` is the single audio source of truth — never getenv it twice.
- `from hv import X` inside functions (repo style); `uid()` hex lengths
  matter for guest/intent entropy claims.
- pkill -f matches own shell — use bracket trick `[u]vicorn`.
- Pages clean URLs: `/onboard.html?login=ok` 308s to `/onboard?login=ok`
  (query survives); callback redirects to clean URLs directly.
- Favicon caches hard — bump `?v=N` on change.
- Kaggle: KILLED for now. Two errored kernels (pip builds); 29.95 GPU-h
  remain; PI token in ~/.kaggle. Recon clones archived at
  `/root/recon/` + `s3://stallshark/recon/`.
- R2 stallshark holds: humanvoiced_frontend.zip, engtest/ (30s real-speech
  engine test: studio +7.5dB SNR), recon archive.

## Next (owner's direction)

1. Narrator #1 (30s phone clip → publish) — unlocks all live verification.
2. Real-money decision: Stripe corridor + keys, or manual pilots.
3. FAL_KEY spend approval → first VEED-vs-local blind test.
4. 5–10 faceless creators willing to trial weekly scripts (paid pilots only).
5. Legal review before launch (checkout, performer licence, payments).
6. iPhone Safari + Android Chrome pass (mic, decode, waveform perf).
7. studio.humanvoiced.com DNS deferred (paths serve both flows today).
8. Adult vertical: parked, separate operation if ever (safety layer holds).
