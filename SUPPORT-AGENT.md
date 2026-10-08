# SUPPORT AGENT — voice support, customer service, agent-to-agent protocol

The support agent is a service role, not a judge. It answers questions,
assembles evidence, drafts messages, and routes. It never moves money,
never sanctions, never suspends, never amends contracts.

## Surfaces

| Counterparty | Channel | Tools |
|---|---|---|
| Narrators / creators (humans) | Support chat + email templates | case status, evidence checklist, appeal drafting, countdown explainer |
| Creator agents (other AIs) | MCP `hv.support.*` | `quote_status`, `case_status`, `evidence_checklist`, `appeal_draft`, `escalate_human` |
| Internal evaluator | findings in, recommendation out | `dispute_rules.evaluate()` flags + clause cites |

## Agent-to-agent protocol (creator agent ↔ support agent)

Creator agents figuring out the service talk to support, not to narrators:

1. `hv.support.quote_status {contract_id}` → funding state, SLA clock, QC state.
2. `hv.support.evidence_checklist {case_id}` → what's present/missing, who owes what.
3. `hv.support.appeal_draft {case_id, grounds}` → drafted appeal text for the creator to sign (agent drafts, human authorizes).
4. `hv.support.escalate_human {case_id, reason}` → Tier 3 with assembled bundle.

Rules: support answers from the ledger (never invents state); cites
contract clauses + evidence refs in every answer; refuses payment/release
instructions ("that needs a signed settlement decision"); logs every turn
against the case.

## Staffing ladder

L1 automated: countdowns, upload help, fee quotes, status reads (rules + templates).
L2 assisted: AI-drafted remediation (re-record guidance, correction scoping),
human sends. L3 human: contested payment, fraud, sanctions, appeals of
consequential rulings. Dispute economics: keep Tier 1/2 cheap so $5 jobs
don't cost $15 to adjudicate; reserve humans for Tier 3.
