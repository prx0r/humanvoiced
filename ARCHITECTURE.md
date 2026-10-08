# HumanVoiced — how it all works

## The loop (one narrator, one job)

```
record (browser mic → WAV encode) → upload (server hash, freeze)
  → Whisper transcript → AI draft → narrator review → publish
  → discoverable (/v1/voices, search, /@handle)
  → agent quote (server-priced) → funded contract → offer → accept
  → record job → upload → QC → approve/correct → settle → receipt
  → reputation event → portfolio proof (+video link, +views)
```

Series wrap episodes in a master agreement (mutual obligations, guaranteed
minimum, rail-settled per episode). Dubbing chains reviewer → narrator with
an 8-file package. Auditions let agents post sides and compare reads.

## Request paths (production)

- **Site** `humanvoiced.com` → Cloudflare Pages (static). No secrets, no backend.
- **API** `api.humanvoiced.com` → CF tunnel → this box :8801 (uvicorn,
  `hv-serve.sh` injects vault env at boot, nothing on disk). CORS locked to
  the site; session cookie scoped `.humanvoiced.com`.
- **Auth** Google OAuth (state-bound, single-use) → opaque SQLite session →
  HTTP-only Secure cookie (30d, revocable) or `X-HV-Session` header for agents.
- **Audio in** multipart WAV → size/type/frame validation → SHA freeze to disk
  (`audio/raw/<sha>.wav`, R2 layout reserved) → Whisper → transcript stored.
- **Money** quote (curve × tier heatmap) → budget gate → rail intent →
  lock → approve/correct/dispute → rail release/refund/split. Simulated rail
  refuses unless `HV_ALLOW_SIMULATED=1`. Stablecoin rails carry explicit
  capability flags; research rails cannot lock, by construction.
- **Disputes** deterministic flags (rule IDs) → assisted correction or human
  adjudication → signed settlement → appeal window → reputation update.
- **Discovery** eligibility gates → weighted match → explained reasons +
  uncertainties → match events recorded for the learning loop.

## Data

SQLite now (`hv.db`: contracts, intents, scripts, offers, narrators,
spend, uploads, cases, orders; `hv-events.db`: hash-chained envelope ledger;
`sessions`, `series` DBs), Postgres migration in `migrations/` when volume
demands. R2 `humanvoiced-audio` bucket created; object keys mirror disk.

## Provider chains (first available wins, never fails silently)

transcribe: CF Whisper → Qwen ASR → fal → stub. describe: DashScope Omni →
OpenRouter Omni → stub. translate: DashScope MT → chat fallback. synthesize:
fal Qwen3-TTS/Dia → self-host (needs keys/GPU). reason: DashScope Flash →
OpenRouter → local 27B. See `hv/providers.py` + `docs/vendor/`.

## Money rules

100% of agreed fee to narrator, 0% commission, processor/escrow costs shown
pre-pay and borne by buyer/platform, donations separate and never charitable
claims. Minimum withdrawals + combined payouts. No platform-held balances.

## What runs where

This box: API :8801, dash :8793, studio :7777/:7778, xman :3999, tunnels.
Vault `oracle`: all secrets. No keys in repo (audited). GPU work (align,
TTS, large ASR) waits on a GPU worker or hosted keys.
