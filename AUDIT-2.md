# AUDIT-2 — full codebase audit (2026-10-08, post-onboarding-fix)

## What's real (ran it)

- Onboarding loop: record → upload (server hash) → Whisper → draft → publish
  → catalogue/search, e2e-tested live with synthetic speech (perfect transcript).
- Auth: Google OAuth (state-bound), sessions (expiry/revoke), HTTP-only cookie
  spanning apex+api, logout. Login-first order; `?login=ok` banner; `/me` endpoint.
- Money: server-side pricing, budget gates, atomic claims, SQLite persistence,
  simulated rail gated, stablecoin rails honest, fee math tested.
- Governance: envelope-hashed ledger, rule-ID disputes, blind reviews, appeals,
  mutual series enforcement, verification ladder, consent-gated audio, XSS fixed.
- Discovery: 3-stage explained search, casting calls, auditions, demand templates.
- Live: Pages site + :8801 API via tunnel, 62 tests, CI green, no secrets in git.

## What's stubbed (honest list)

- ASR/describe: CF Whisper live; Omni/Qwen-hosted behind keys/activation.
- Escrow: simulated + interface shapes; Trustless Work = research only.
- TTS/demo media: no GPU, no FAL_KEY — nothing generates audio here.
- R2 objects: bucket exists, S3 keys dead — disk primary.
- Next.js/PG/Stripe-test: spec'd, not built.

## Top risks

1. Single box, no backups, no process supervisor (all setsid/nohup).
2. Reconcile-class cost lives in influence/dash, not here — but same pattern
   risk if QC ever blocks requests (it doesn't; sync short calls only).
3. Google OAuth untested with a real account (redirect registered, not clicked).
4. No rate limiting on API (abuse: upload/storage costs).
5. Whisper cost per upload (~$0.00026) unbounded without quotas.

## DEV PLAN (ordered)

1. Owner: Google login click-through → narrator #1 → verify live. (human)
2. Rate limits + upload quotas per session/IP.
3. Process supervision (systemd units for api/dash/studio) + DB backups to R2.
4. DASHSCOPE activation → Omni describe live on samples.
5. FAL_KEY → demo TTS for casting sides.
6. Trustless Work testnet: fund/lock/release/refund rehearsal on testnet USDC.
7. R2 S3 keys → object upload off disk.
8. Next.js portfolio/onboard migration (SEO, polish).
9. PG migration when job volume justifies.
10. Stripe-test checkout wiring (needs account eligibility decision).
