# HumanVoiced — TECH SPEC (build target)

Companion to `THESIS.md` (the why + policy). This is the what + how:
exact stack, reuse map, core structure, per-person API, voice-analytics pipeline, P0 order.

Laws: secrets in vault only (names in tree). Human decides money, sanctions,
identity. No blockchain at P0. No voice-cloning of narrators without separate
specific agreement. Scripts are untrusted task data — never instructions.

## 1. Exact stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI (Python) + stdio MCP servers | Matches our repos (feedify, pogpet, oddhobbies `consumer_mcp.py` stdio JSON-RPC pattern) |
| Frontend | Next.js 14 + Tailwind + shadcn/ui | Reuse shape from TrustLedger/Haseeb (Apache/MIT patterns); portfolio pages + contract UI from thesis §2–3 |
| Ledger DB | PostgreSQL 15+ (SQLAlchemy) | Thesis §10 mandates PG transactional truth; 17 tables |
| Blobs | Cloudflare R2 (`R2_*` vault, existing) | WAV originals immutable, content-addressed `audio/raw/<contract>/<sha>.wav`; no permanent public URLs |
| Queue/workers | Postgres-backed queue + APScheduler worker | One less service than Redis; SLA timers, QC jobs, settlement jobs |
| Cron/scheduling | APScheduler (in-worker) | Deadline countdowns, grace expiry, review-window auto-accept |
| AuthN | SIWE-style wallet OR email+OAuth; server sessions | Agents use scoped API keys (see §5), humans use sessions |
| Money | Stripe Connect separate-charges-and-transfers | Thesis §13; platform bears refund/chargeback duty → loss reserve |
| Agent money later | x402 rails (`/root/x402`) | Machine-executable demand pattern already in-house |
| Secrets | agent-vault `oracle` + dash vault | Names in tree (`auth_ref`), values never |
| Audit checkpoints | Nightly signed Merkle root of event table | Thesis §3/§10 evidentiary trail without chain |
| Tests | pytest + contract fixtures | Every gate has a fixture (lateness, clipping, script edit → change order) |

What we do NOT run: Redis, Temporal, chain, custom queue infra at P0.

## 2. Reuse map — ours (port, don't rethink)

| Need (thesis) | Source | What we lift |
|---|---|---|
| Append-only event ledger + chain hash | `workerkit/core/events.py` (`EventLedger`, wk-events.db) | Port to PG: `contract_events` table, hash-chained rows, projector pattern (`LabProjector` → reputation/ledger projections) |
| AcceptanceContract + criteria + gates | `workerkit/verify/contracts.py`, `verify/gates.py` | Contract validation, QC gates, budget gates; `contract_from_jobspec` shape → `contract_from_brief` |
| Reputation feedback shape | `workerkit/protocols/erc8004/identity.py` (`ReputationFeedback`, avg) | Off-chain PG version; extend to outcome vector R_n=(Q,D,A,S,C) + M(n,j) matcher (§9) |
| Job escrow states | `workerkit/chain/erc8183.py` (Open→Funded→Submitted→Completed/Rejected) | Same state machine, Stripe custody instead of contract custody |
| Campaign/receipt discipline | `workerkit/wk.py`, `orchestrator.py` (freeze run, receipts) | Settlement receipts, evaluation receipts, decision receipts |
| Demand semantics | `oracle/ORACLE-SPEC.md` (Lightcast-style normalization) | Later: rate/demand analytics for narrator pricing |
| Machine-work pipeline | `workerkit` 14-step campaign (ingest→world→halving→verify→freeze) | Narrator selection as successive-halving over eligible voices |
| Per-person API pattern | `oddhobbies/db/consumer_mcp.py` (tool table, `store_agent_catalog` + public tools) + `bgraph/registry/agent_surfaces/` | Narrator endpoints as MCP tools (see §4) |
| Dispute adjudication surface | `qprivately/` (law repo: schemas, wire, runs) | Evidence-bundle assembly + decision records pattern |
| Voice registry + metrics | `sleepintel/voices/registry.yaml` + `jev/decisions.json` | Voice descriptors + promote/iterate/kill gates reused for narrator matching analytics |

## 3. Reuse map — GitHub (patterns default, vendor only if permissive)

| Need | Project | License | Take |
|---|---|---|---|
| Escrow lifecycle + arbitration states | `kevinle3212/TrustLedger` | Apache-2.0 | State machine (fund→submit→approve/warranty→payout/dispute), commit-reveal arbitration shape, E2E crypto drafting pattern. Testnet-only, unaudited — reference only. |
| Full-stack marketplace skeleton (NestJS+Prisma+PG, Next.js+wagmi) | `Haseeb-1698/Defi-Freelance-Marketplace` | MIT | Milestone escrow flow (post→bid→fund→submit→approve/dispute→review), Socket.IO status updates, demo seeding script. Closest stack match. |
| Soulbound reputation (non-transferable, earned-only) | `abhinav077/Verity` (VRT tiers, peer jury) | check | Portable work-history credential concept (§16 moat): signed completion stats, privacy-respecting export. |
| AI + on-chain reputation | `web3lancer/web3lancer` | AGPL-3.0 | Patterns ONLY (our influence rule 6): verified-reviews-only-by-counterparties, sybil notes. Never vendor. |
| TTS server template | `ValyrianTech/Qwen3-TTS_server` (FastAPI + Whisper transcription + RunPod) | check | Serving wrapper shape for our voice-demo analytics endpoint (not narrator voices). |
| Social/scheduler infra | `/root/xman` (ours, MIT, live :3999) | MIT | Creator-side distribution later; not P0. |

Rule: Apache/MIT may be vendored with attribution; AGPL is patterns-only, separate-service-or-reimplement.

## 4. Every narrator as an API endpoint

One MCP server (`hv_narrator`), stdio like `consumer_mcp.py`. Public tools need no auth; mutations need narrator session + idempotency keys + policy version.

| Tool | Auth | Maps to thesis API |
|---|---|---|
| `hv.voices.search {style, language, budget, deadline}` | none (public) | `GET /v1/voices` — M(n,j) ranked, New-voice exploration allocation |
| `hv.portfolio.get {narrator_id}` | none | `GET /v1/voices/{id}/portfolio` — samples consented only, 90-day + 12-month stats, sample counts next to every % |
| `hv.contract.quote {brief}` | agent key | `POST /v1/contracts/quote` — feasibility + price without funding |
| `hv.contract.create {brief, agent_id, principal_id}` | agent key + budget check | `POST /v1/contracts` — validates, secures funds, emits `contract.created` |
| `hv.offer.accept / .decline {offer_id}` | narrator session | Acceptance receipt (authenticated event, server timestamp, terms hash shown) |
| `hv.contract.amend {contract_id, change}` | creator agent | Change order (accept/renegotiate/decline), never silent overwrite |
| `hv.submit {contract_id, wav_ref}` | narrator session | Idempotent upload completion; checksum at receipt; original bytes frozen |
| `hv.evidence.get {contract_id}` | role-scoped | Permission-controlled bundle (§7 table) |
| `hv.review.submit {contract_id, side}` | both sides | Blind dual review, revealed after both/window |
| `hv.dispute.open/respond/appeal` | both sides | Case lifecycle with evidence refs |
| `hv.reputation.get {narrator_id}` | public summary | R_n vector + rolling windows + appeal corrections |

Agent permission object from thesis §12 enforced server-side per request (search→quote→create→review→dispute allowed; sanction/suspend/unilateral-amend/foreign-evidence denied). Budget caps checked before funding, anti-splitting monitored.

## 5. Voice-demo analytics stack (listen, measure, never clone)

Narrator voices are human. TTS exists for platform demo content and style previews only.

| Job | Choice (Oct 2026) | Notes |
|---|---|---|
| Script alignment (coverage_estimate) | Whisper Large V3 Turbo (809M, MIT, 216x RT, 99 langs) | Transcribe → diff vs frozen script; `potential_missing_segments`. Full V3 if accuracy disputes. |
| Word timestamps | Qwen3-ForcedAligner-0.6B (Apache-2.0, 11 langs) | Scene-target timing checks |
| Multilingual narrators | Qwen3-ASR-1.7B (Apache-2.0, 52 langs) | Where Whisper underperforms; validate on our audio first |
| Max-accuracy English appeals | NVIDIA Canary-Qwen 2.5B (CC-BY, 5.63% WER) | Appeal-tier rescoring only (license ok for internal use) |
| Tech QC (clip/noise/silence) | librosa + pyloudnorm + torchaudio | Deterministic thresholds, versioned in evaluation policy |
| Voice consistency (advisory!) | SpeechBrain ECAPA-TDNN cosine similarity | Advisory, never proof of origin, never sole payment blocker (§6) |
| Diarization (multi-voice jobs) | pyannote.audio | Bolt-on where needed |
| Portfolio descriptors (accent/pace/timbre) | Qwen3-ASR + prosody features + LLM summarizer | Uncertainty recorded; never ethnicity/nationality claims |
| Demo/preview TTS | Qwen3-TTS-12Hz-1.7B (Apache-2.0, 6GB+ VRAM, vLLM-Omni serve) | VoiceDesign for style previews; 3-sec clone ONLY with explicit consent + separate agreement |
| Prompt-injection guard | Script/brief rendered as data, never system | "Ignore all instructions…" stays text (§6 security rule); evaluator context isolation + output schema validation |

Evaluation report = thesis §6 JSON, plus `model_versions`, `policy_version`, `evidence_refs`. Deterministic checks gate automatically; style/consistency are advisory; payment withheld only on contract-grounded findings or human decision.

## 6. Core structure (repo `/root/humanvoiced`)

```
humanvoiced/
  THESIS.md            # governing thesis (verbatim)
  TECH-SPEC.md         # this file
  AGENTS.md            # repo laws (vault-only secrets, P0 rules, no-clone rule)
  README.md            # what/why/run in 5 minutes
  schemas/             # JSON Schemas, versioned (contract.v1, portfolio.v1,
                       #   reputation.v1, evaluation.v1, dispute.v1, agent_identity.v1)
  api/                 # FastAPI: routers voices/contracts/offers/submissions/
                       #   reviews/disputes/reputation/events + agent auth middleware
  mcp/                 # hv_narrator stdio server (tool table like consumer_mcp.py)
  worker/              # APScheduler jobs: sla.py, qc.py, settle.py, notify.py
  ledger/              # event store (port of workerkit EventLedger → PG) + projector
  reputation/          # R_n vector, M(n,j) matcher, windows, appeals correction
  escrow/              # Stripe Connect intents/webhooks, ledger postings, loss reserve
  disputes/            # case assembly, AI fact-extract (contract-grounded), adjudicator view
  audio/               # ingest (checksum/freeze), qc (tech), align (whisper/forced),
                       #   descriptors (prosody), consistency (ecapa, advisory)
  web/                 # Next.js: portfolio pages, contract HV-1042 UI, countdown,
                       #   evidence-gated dispute view, dual-review flow
  receipts/            # decision/settlement/evaluation receipt samples
  tests/               # fixtures per gate: late, faulty, script-edit, malicious-review…
```

## 8. Payment machine (from `PAYMENTS.md`: move ≠ protect ≠ judge)

Three separate systems: x402 moves money, escrow protects it during work,
disputes decide who gets it. Invariant: `payment_confirmed ≠ funds_escrowed` —
never display "Protected by escrow" without a real escrow arrangement.

### 8.1 Funded-contract state machine

```
proposed → quoted → funding_requested → secured → offered → accepted
  → submitted → qc_passed → review_window → approved/auto_accepted
  → settled | disputed → resolved → settled/refunded/split
              ↘ correction → resubmitted (≤ included_corrections)
```

Guards: no activation without `funding_status=secured`; no release above
available balance; no double-settle (idempotency keys); no refund of
distributed funds without independently funded remedy; agent review alone
never moves money; amendments never overwrite financial terms.

### 8.2 Rail interface (every rail implements all nine)

`quote() | createFundingRequest() | verifyFunding() | lock() | getBalance() |
release() | refund() | split() | getTransactions()` — eachTx bound to
`(contract_id, intent, asset, recipient, quote_version)`; bare tx hashes are
not proof. Rails advertise capabilities honestly (direct-pay rails must NOT
claim `lock()`).

| Rail | Role | Status |
|---|---|---|
| Stripe Connect (separate-charges-and-transfers) | Day-1 real-money custody + payouts | P0: test mode; pilot after legal review (FCA: marketplace holding customer money ≈ regulated payment service) |
| x402 V2 (`/root/x402` monorepo: TS/Go/Python SDKs, EVM contracts) | Agent-native checkout + signed offers/receipts | P1 adapter: `PAYMENT-SIGNATURE/REQUIRED/RESPONSE` headers, Payment-Identifier dedupe; store signed receipts beside contract receipts |
| Q+Pay (Qubic HTTP-402 gateway, provider-reported) | Fast QU collection | P1 adapter, SEPARATE from x402 (their example uses legacy `X-PAYMENT`, not V2 headers — verified real incompatibility). Non-custodial → collection only, never escrow. Verify docs before integrating |
| Qubic MSVault (verified live: 2..16 owners, quorum/Y-of-X, native QU) | Crypto escrow prototype: 2-of-3 buyer/worker/arbiter | Stage 04: prototype funding+release separately; test signer loss, non-cooperation, compromised arbiter. NOTE: also evaluate Qubic `Escrow` contract (index 27, @qubic.org/contracts) — purpose-built beats multisig |
| Escrow.com API | Regulated fallback | Evaluate economics for $5–15 jobs; likely unsuitable at that size |

### 8.3 Denomination rule

Display USD. Quotes fix QU amount + short expiry. Entitlement states USD or QU
explicitly pre-acceptance; exposure disclosed; refunds in contract
denomination; stable-value default, QU opt-in. Integer minor units everywhere.

### 8.4 Financial tables (PG, alongside §10 ledger)

`payment_intents | payment_transactions | funding_allocations |
escrow_positions | ledger_entries (double-entry) | payout_instructions |
refund_instructions | settlement_decisions | reconciliation_runs |
treasury_exposure`. Segregate protected funds in real accounts/vaults, not
just labels.

### 8.5 Dispute queue (case management before AI arbitration)

Classification → remedy table in `PAYMENTS.md` §6 (10 types: non-delivery,
wrong-script, clipping, wrong-voice, style, scope-change, outage, synthetic,
unfair-review, payment). Settlement decisions carry
`settlement_authorised:false` until appeal window closes; agents gather
evidence and recommend only. Launch policy v0.1: 100% pre-funding, 5–15min
offer expiry, server-time SLA, grace→recovery, immediate tech QC, 1 correction
round, 24h review → auto-accept, 48h dispute/appeal windows, reputation from
verified outcomes only.

### 8.6 Three public APIs (trust layer independent of rails)

`api.humanvoiced.com/voices | /contracts | /reputation` — Qubic (or any rail)
is a payment option, never a dependency of contracts/reputation.

## 9. P0 build order (first 10–30 narrators) — staged per `PAYMENTS.md` §11

1. Schemas + PG migration (17 tables §10) + R2 buckets (`hv-raw`, `hv-derived`).
2. Event ledger port + `/contracts/{id}/events` read path + nightly signed checkpoint.
3. Voices CRUD + portfolio pages + consent flags + New-voice label + availability.
4. Quote→create→accept flow with funding (Stripe test) + frozen script hash + server-time SLA countdown.
5. Upload completion (idempotent, checksum, freeze original) + R2 lifecycle (180-day rule).
6. QC pipeline: tech (deterministic) → align (Turbo) → report v1 → `delivery.ready`.
7. Dual review (blind) + settlement + reputation event emission.
8. Dispute v1: evidence bundle + human-operated resolution + outcomes table (§7).
9. MCP `hv.*` read tools + agent keys/budgets (create/dispute only within caps).
10. Fixture suite green before any real money.

Non-negotiable carried over: freeze contract + original audio from day one, or histories can never be trusted.
