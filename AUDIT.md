# HumanVoiced — repository audit (2026-10-08, commit `d1e351d`+)

Method: test suite executed (62 passed), all public endpoints probed live,
git history + secret scan reviewed. Status words mean: LIVE (running in
production now), WIRED (code + tests, deploy pending or partial), SCAFFOLD
(shape exists, needs work), DOC (thesis/spec only).

## Modules

| Module | Status | Evidence |
|---|---|---|
| contracts / ledger / reputation / escrow core | WIRED | 62 tests; chain-hash + envelope verified |
| FastAPI lifecycle (quote→settle) | LIVE | api.humanvoiced.com serves; auth + budgets enforced |
| Sessions (expiry, revoke, cookie) | LIVE | tested incl. 401 paths |
| Upload (server hash, 50MB cap, ownership) | LIVE | e2e WAV tested |
| QC tech checks on real bytes | WIRED | real-WAV tests; ASR stub until GPU/hosted |
| Transcription (CF Whisper) | LIVE | verified e2e, perfect transcript |
| Pricing curve + heatmaps | WIRED | exact-fit tests |
| Disputes (rules, queue, appeals) | WIRED | human-review gates tested |
| Series + master agreements | WIRED | mutual-enforcement tests |
| Localisation (quals, chains, SRT) | WIRED | tests |
| Auditions | WIRED | tests |
| Casting (roles/sides/stage) | WIRED | tests |
| Voice engine (pipeline/catalog/search) | WIRED | tests; ASR/describe stubs shaped for hosted swap |
| AB harness | WIRED | tests |
| Stablecoin rails + prefs + transparency | WIRED | research rails refuse to lock (tested) |
| Payments backend (service/quotes/adapters) | WIRED | simulated + honesty tests; Trustless Work = shape only |
| MCP server | WIRED | stdio smoke-tested |
| Google OAuth | WIRED | code complete; needs console redirect URI to go live |
| Onboarding pages | LIVE | humanvoiced.com/onboard serves; full loop tested headlessly |
| Portfolio pages | LIVE | dynamic ?h= profiles serve |
| Site (Pages) | LIVE | 200s on apex/www/portfolio/contract/onboard |

## Known gaps (not hidden)

1. No real narrator yet (DB empty by design) — first Google login untested
   until redirect URI is registered.
2. ASR/describe stubs — hosted swap spec'd, keys pending (DASHSCOPE activation, FAL_KEY).
3. Trustless Work = interface shape, no chain calls; MSVault = prototype only.
4. R2 object upload needs fresh dashboard S3 keys (stored sets dead).
5. Next.js migration, PG deploy, Stripe-test wiring — spec'd, not built.
6. No GPU on this box — alignment/TTS/large-ASR need a GPU worker.

## Secrets audit 2026-10-08

No `.env`/`.db`/tokens tracked. No key-pattern matches in tree or full
`git log -S` history. Vault holds: DASHSCOPE_API_KEY, GOOGLE_*, X_*, social
passwords, CF/R2/TELNYX, MESHY_*, SERPAPI. OPENROUTER key retired (was wrong
service). OPENCODE vault copy stale (401) — auth.json is truth.
