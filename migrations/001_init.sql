-- HumanVoiced 001: core ledger tables (PG-first; SQLite-compatible subset noted).
-- Integer minor units for money. No floats for currency. UTC timestamps.
-- Event tables are append-only by policy (no UPDATE/DELETE grants in app role).

CREATE TABLE IF NOT EXISTS principals (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL DEFAULT 'org',
  display_name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL REFERENCES principals(id),
  permissions TEXT NOT NULL DEFAULT '[]',
  max_job_minor BIGINT NOT NULL DEFAULT 0,
  max_daily_minor BIGINT NOT NULL DEFAULT 0,
  max_monthly_minor BIGINT NOT NULL DEFAULT 0,
  allow_unattended_purchases BOOLEAN NOT NULL DEFAULT FALSE,
  allow_unattended_publication BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS narrators (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL DEFAULT '',
  availability TEXT NOT NULL DEFAULT 'offline',
  payout_identity_ref TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS voice_samples (
  id TEXT PRIMARY KEY,
  narrator_id TEXT NOT NULL REFERENCES narrators(id),
  r2_key TEXT NOT NULL,
  sha256 CHAR(64) NOT NULL,
  consented_public BOOLEAN NOT NULL DEFAULT FALSE,
  language TEXT NOT NULL DEFAULT '',
  style TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_proposals (
  id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL REFERENCES principals(id),
  agent_id TEXT NOT NULL REFERENCES agents(id),
  brief_sha256 CHAR(64) NOT NULL,
  brief_json TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contract_versions (
  contract_id TEXT NOT NULL,
  version INT NOT NULL,
  terms_json TEXT NOT NULL,
  terms_sha256 CHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (contract_id, version)
);

CREATE TABLE IF NOT EXISTS contract_acceptances (
  id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL,
  version INT NOT NULL,
  narrator_id TEXT NOT NULL REFERENCES narrators(id),
  accepted_at TIMESTAMPTZ NOT NULL,
  deadline_at TIMESTAMPTZ NOT NULL,
  terms_shown_sha256 CHAR(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS contract_events (
  seq BIGSERIAL PRIMARY KEY,
  event_id TEXT UNIQUE NOT NULL,
  contract_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL DEFAULT 'platform',
  actor_type TEXT NOT NULL DEFAULT 'system',
  payload TEXT NOT NULL DEFAULT '{}',
  payload_sha256 CHAR(64) NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  prev_sha256 TEXT NOT NULL DEFAULT '',
  event_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_contract ON contract_events(contract_id, seq);

CREATE TABLE IF NOT EXISTS submissions (
  id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL,
  version INT NOT NULL DEFAULT 1,
  r2_key TEXT NOT NULL,
  sha256 CHAR(64) NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  on_time BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS evaluation_reports (
  id TEXT PRIMARY KEY,
  submission_id TEXT NOT NULL REFERENCES submissions(id),
  contract_id TEXT NOT NULL,
  report_json TEXT NOT NULL,
  evaluation_version TEXT NOT NULL DEFAULT '1.0',
  policy_version TEXT NOT NULL DEFAULT 'qc-policy-0.1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dispute_cases (
  id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL,
  dtype TEXT NOT NULL,
  raised_by TEXT NOT NULL,
  claim TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',
  opened_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence_items (
  id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL,
  case_id TEXT REFERENCES dispute_cases(id),
  kind TEXT NOT NULL,
  r2_key TEXT NOT NULL DEFAULT '',
  sha256 CHAR(64) NOT NULL DEFAULT '',
  role_visibility TEXT NOT NULL DEFAULT 'adjudicator',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES dispute_cases(id),
  outcome TEXT NOT NULL,
  worker_share_bps INT NOT NULL,
  buyer_share_bps INT NOT NULL,
  evidence_root TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  decided_by TEXT NOT NULL,
  appeal_status TEXT NOT NULL DEFAULT 'open',
  settlement_authorised BOOLEAN NOT NULL DEFAULT FALSE,
  decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS appeals (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES dispute_cases(id),
  raised_by TEXT NOT NULL,
  grounds TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reputation_events (
  id TEXT PRIMARY KEY,
  narrator_id TEXT NOT NULL REFERENCES narrators(id),
  contract_id TEXT NOT NULL,
  verified BOOLEAN NOT NULL DEFAULT FALSE,
  worker_fault BOOLEAN NOT NULL DEFAULT FALSE,
  scores_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS financial_ledger (
  id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL,
  direction TEXT NOT NULL,
  account TEXT NOT NULL,
  amount_minor BIGINT NOT NULL,
  asset TEXT NOT NULL DEFAULT 'USD',
  authorising_decision TEXT NOT NULL DEFAULT '',
  external_tx TEXT NOT NULL DEFAULT '',
  idempotency_key TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS policy_versions (
  version TEXT PRIMARY KEY,
  terms_json TEXT NOT NULL,
  active_from TIMESTAMPTZ NOT NULL DEFAULT now()
);
