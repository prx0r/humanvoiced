# HumanVoiced — Payment, Escrow & Dispute Infrastructure

The research suggests we should combine Upwork's funded-contract protections, Fiverr's resolution process, and x402's agent-native payments, with Qubic providing an optional fast settlement rail.

But there's an important distinction:

x402 moves money. Escrow protects money while work is being performed. Dispute resolution determines who is entitled to it.

These are three separate systems. HumanVoiced needs all three.

## 1. What successful marketplaces actually do

| Marketplace  | Mechanism worth copying                                                                        | What HumanVoiced should do                            |
| ------------ | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Upwork       | Fund the milestone before work begins; release after acceptance or expiry of the review period | Every accepted narration must be fully funded         |
| Fiverr       | Structured resolution centre for extensions, cancellations and refunds                         | Let both parties propose resolution before escalating |
| Bunny Studio | Voice-specific corrections, approval and automatic completion                                  | Distinguish recording errors from creative changes    |

Upwork's current fixed-price system gives customers 14 days to approve submitted work or request changes, after which funds can be released automatically. Its escrow-related disputes involve mediation and, where applicable, further arbitration.

Fiverr's Resolution Center allows structured requests between buyers and sellers, generally providing 48 hours to respond. It also supports extensions, cancellation requests and partial refunds.

Bunny Studio illustrates why voiceover work needs specialist rules: corrections attributable to the original instructions are treated differently from new creative requests.

### What I would use for HumanVoiced

Because most narration jobs will be small and urgent, we shouldn't copy Upwork's entire 14-day review cycle.

My proposed starting policy:

- Payment: secured before a narrator can accept.
- Delivery: deadline agreed before acceptance.
- Automated QC: begins immediately after upload.
- Creator review: 24 hours after a technically valid submission.
- Corrections: one included round for objectively identifiable mistakes.
- Disputes: freeze affected settlement and preserve evidence.
- No response: automatic acceptance after the review window, subject to defined exceptions.
- Final resolution: payment, refund or agreed split.

These are proposed platform rules, not contractual terms already in force.

## 2. x402 + Qubic Pay: what actually exists

I found Q+Pay, which is directly relevant.

It advertises Qubic-native HTTP 402 payments, a QPAY smart contract, invoice links, API paywalls, wallet-based checkout and signed webhooks.

Q+Pay

Qubic-native payment gateway

Advertised live service

| Protocol                  | HTTP 402-style payment flow                             |
| ------------------------- | ------------------------------------------------------- |
| Asset                     | QUBIC (QU)                                              |
| Advertised processing fee | 0.75% or 100 QU minimum                                 |
| Settlement                | Direct to merchant wallet                               |
| Escrow                    | Not established by its documented standard payment flow |

Provider-reported features and rates, not independently audited guarantees.

The crucial finding is that Q+Pay describes itself as non-custodial: funds move directly from the buyer to the merchant, and Q+Pay does not hold or freeze them.

That makes it useful for collecting HumanVoiced payments, but not a replacement for escrow.

Similarly, the official x402 protocol primarily defines how a service requests, verifies and settles an HTTP payment. It doesn't automatically manage a contract lasting several hours, a quality dispute or conditional worker payouts.

We therefore need a distinct funded-contract engine, regardless of which payment rail is used.

## 3. Qubic does have a possible escrow building block

This is the most promising Qubic-specific discovery: MSVault.

Qubic lists MSVault as a live multisignature smart contract supporting shared control of native QU funds, including configurable approval thresholds such as two of three signers.

Conceptually, a HumanVoiced contract could use:

Proposed 2-of-3 funding arrangement

Customer (Agent's principal) + Narrator (Human worker) + Arbiter (Independent authority) → Funded QU vault (Requires two authorised approvals to release) → Worker paid (Buyer + worker) / Refund (Worker + arbiter, or buyer + arbiter) / Dispute (Arbiter joins one side)

Conceptual approval paths, not an audited or deployed HumanVoiced escrow contract.

The governance design would be:

- Buyer and worker can voluntarily agree to release funds.
- If they disagree, the arbiter can approve the appropriate release with either party.
- HumanVoiced records the evidence and resolution off-chain.
- The vault handles the actual movement of funds.

There are important caveats. MSVault is a general multisig, not a purpose-built narration escrow. An automatic 24-hour payout, unilateral deadline refund or programmable split settlement is not guaranteed by the basic 2-of-3 mechanism. Its exact transaction permissions, vault provisioning costs and suitability for many tiny contracts require testing.

Also, Qubic smart contracts are not deployed like ordinary EVM contracts. New contracts require integration into the network's core, governance approval and an IPO process. So building a brand-new Qubic escrow contract is a substantially larger project than adding a Solidity contract to an EVM chain.

### Three implementation options

| Option                           | Benefits                                            | Main limitation                                    | Recommendation                               |
| -------------------------------- | --------------------------------------------------- | -------------------------------------------------- | -------------------------------------------- |
| Q+Pay direct payments            | Already documented, fast, useful for agent checkout | Does not lock funds for a job                      | Use for payment collection where appropriate |
| Qubic MSVault                    | Existing on-chain shared control                    | Requires multiple signatures and a custom workflow | Prototype for crypto escrow                  |
| Licensed escrow/payment provider | Established custody and dispute processes           | Fees, verification and country restrictions        | Evaluate for initial real-money protection   |

A dedicated provider such as Escrow.com offers a documented escrow API and regulated custody. However, its onboarding and economics may be unsuitable for frequent $5–$15 narration contracts; that needs explicit provider confirmation.

### One compatibility issue we must fix

Q+Pay's published example labels itself x402 V2 but shows a legacy-style `X-PAYMENT` submission. Official x402 V2 specifies `PAYMENT-SIGNATURE`, `PAYMENT-REQUIRED` and `PAYMENT-RESPONSE` headers.

Therefore, we should use a Q+Pay-specific payment adapter, rather than assume that any standard x402 client can transparently pay a Qubic endpoint.

That lets us support official x402 integrations and Qubic payments without coupling the job engine to one gateway's implementation.

## 4. The complete payment architecture

I would make HumanVoiced payment-rail agnostic at the backend, while allowing agents to pay through x402 and Qubic.

Creator or AI agent → Quote + fixed contract terms → Payment rail (x402 stablecoin / Q+Pay-Qubic / Fiat marketplace provider) → Verify funding assurance → Funds protected for work? (No → Do not activate contract) → Offer to narrators → Narrator accepts → Submit original WAV → AI quality checks → Outcome (Approved / Rejected-and-resolved / Disputed) → Authorise worker payout / Refund buyer / Hold pending adjudication → Pay / refund / split

(Original included a flowchart diagram expressing the above payment architecture.)

### Define a common payment interface

Every payment rail implements the same conceptual capabilities:

| Operation                | Purpose                                  |
| ------------------------ | ---------------------------------------- |
| `quote()`                | Determine exact cost, asset and expiry   |
| `createFundingRequest()` | Obtain payment instructions              |
| `verifyFunding()`        | Confirm independently that funds arrived |
| `lock()`                 | Confirm conditional protection of funds  |
| `getBalance()`           | Reconcile available and committed funds  |
| `release()`              | Pay narrator after resolution            |
| `refund()`               | Return eligible buyer funds              |
| `split()`                | Execute an agreed partial payment        |
| `getTransactions()`      | Supply verifiable settlement evidence    |

These are our own proposed interfaces, not universal functions supplied by x402 or Q+Pay.

A rail must advertise its capabilities. Q+Pay's ordinary direct-payment flow, for example, cannot truthfully advertise conditional locking.

This is an important invariant:

`payment_confirmed ≠ funds_escrowed`

The platform should never display "Protected by escrow" unless an actual supported escrow arrangement exists.

### The on-chain payment flow

For a cryptocurrency-funded job:

1. An agent requests a quote for an exact script version.
2. HumanVoiced returns an amount and expiration.
3. The agent funds the job through a supported route.
4. The payment adapter independently verifies chain settlement.
5. The escrow or authorised holding mechanism confirms the amount is protected.
6. Only then may the narrator accept.
7. On approval, HumanVoiced instructs the authorised release process.
8. Settlement reconciliation completes the job.

A payment transaction must be bound to a unique `contract_id`, payment intent, asset, expected recipient and quote version. Never use a bare transaction hash as sufficient proof.

### x402-specific features worth using

The current x402 protocol has two particularly relevant extensions:

Payment-Identifier: lets clients retry payment requests without inadvertently creating duplicate charges, when supported by the implementation.

Signed Offers & Receipts: provides portable cryptographic evidence of payment terms and successful HTTP interactions.

We can store those alongside the HumanVoiced contract receipt.

However, an x402 receipt proving a paid HTTP request does not itself prove that a narrator later fulfilled a separate agreement. Those remain distinct pieces of evidence.

## 5. The biggest crypto design problem: denomination and volatility

Suppose an AI agent purchases a narration priced at $20 and funds it using QUBIC.

We have to decide whether the contract promises:

- A fixed quantity of QU; or
- A fixed USD-equivalent amount.

Those are not interchangeable.

If QU changes significantly in value while a long job is underway, someone bears that risk.

My proposed approach:

| Setting                | Recommended policy                                       |
| ---------------------- | -------------------------------------------------------- |
| Display price          | USD                                                      |
| Quote                  | Fixed QU amount with short validity period               |
| Funding                | Confirm exact asset amount on-chain                      |
| Narrator entitlement   | Explicit USD amount or QU quantity before acceptance     |
| Exchange-rate exposure | Disclose who bears it                                    |
| Refunds                | Default to the contract's agreed denomination            |
| Settlement             | Preserve exact chain amount, USD valuation and timestamp |

For everyday workers, I would strongly prefer stable-value earnings, with optional QUBIC payouts for those who actually want them.

Otherwise, someone attracted by a $10 narration job might finish the work and discover their crypto payout is worth materially less.

Do not silently convert QUBIC or promise USD protection unless a properly supported conversion, hedging or treasury mechanism exists.

For the early crypto product, a fixed-QU contract with an obvious USD estimate is operationally simpler. It should be explicitly opt-in.

## 6. How crypto-native labour marketplaces handle disputes

A highly relevant comparison is LaborX.

Its published gig contract design contains the customer's and freelancer's wallet addresses, job deadline and locked funds. Following submission, payment can be released. For disputes, a designated arbiter can take control of releasing funds and allocate them between parties.

This is the important lesson:

The blockchain doesn't judge whether a recording was good. It enforces the financial outcome produced by an agreed resolution mechanism.

HumanVoiced should keep that separation.

The ideal trust flow is:

`Contract evidence → objective analysis → party responses → adjudication → signed settlement instruction → payment rail`

A dispute decision should contain:

```
{
  "decision_id": "dec_001",
  "contract_id": "hvc_1042",
  "contract_version": 1,
  "outcome": "partial_payment",
  "worker_share_bps": 7000,
  "buyer_share_bps": 3000,
  "evidence_root": "sha256:...",
  "policy_version": "1.0",
  "decided_by": "human_reviewer",
  "appeal_status": "open",
  "settlement_authorised": false
}
```

Notice the final field: a decision should not immediately transfer funds when a protected appeal window applies.

It becomes settlement-authorised only after the policy's required conditions are met.

### Proposed dispute classification

| Dispute type                       | Initial assessment                             | Remedy                                  |
| ---------------------------------- | ---------------------------------------------- | --------------------------------------- |
| No audio delivered                 | Server timestamps                              | Reassign/refund, worker incident review |
| Wrong script read                  | Speech-to-script alignment                     | Correction or refund                    |
| Audio clipping/noise               | Measured technical thresholds                  | Correction                              |
| Wrong narrator/voice               | Compare agreed selected profile and provenance | Review and remedy                       |
| Style disagreement                 | Human assessment against original brief        | Revision/approval decision              |
| Client changes brief               | Compare contract versions                      | Requote or cancel without worker fault  |
| Upload service outage              | Internal infrastructure logs                   | Extend deadline, no worker penalty      |
| Synthetic audio presented as human | Provenance, challenge and human review         | Remedy and possible account action      |
| Unfair review                      | Compare claim to contract and evidence         | Correct rating and protect payout       |
| Disputed payment/refund            | Financial ledger and settlement records        | Hold and adjudicate                     |

I'd implement a small case-management queue before any sophisticated AI arbitration.

Agents can gather evidence, find relevant clauses, compare timelines and recommend outcomes. They shouldn't independently seize funds or issue permanent reputational sanctions.

## 7. The accounting system must be separate from blockchain settlement

This is non-negotiable. Every contract needs a financial ledger.

A wallet balance is not sufficient, because HumanVoiced needs to distinguish uncommitted balances, active-job obligations, pending payouts, refunds and platform revenue.

### Required financial tables

| Table                  | Function                                          |
| ---------------------- | ------------------------------------------------- |
| `payment_intents`      | Quoted amount, rail, recipient and expiry         |
| `payment_transactions` | Blockchain or payment-provider settlement records |
| `funding_allocations`  | Funds committed to specific contracts             |
| `escrow_positions`     | Custodian/vault, locked amount and beneficiaries   |
| `ledger_entries`       | Double-entry accounting movements                 |
| `payout_instructions`  | Approved payments to narrators                    |
| `refund_instructions`  | Approved returns to buyers                        |
| `settlement_decisions` | Contractual authorisation to release              |
| `reconciliation_runs`  | Compare internal ledger with external balances    |
| `treasury_exposure`    | Asset-denominated balances and currency risk      |

Use integer monetary units, not floating-point amounts.

Each movement gets an immutable record with its source and destination, currency, amount, contract, authorising decision, external transaction identifier and idempotency key.

### Essential invariants

- Never activate a paid job without confirmed, sufficiently protected funding.
- Never release more than the contract's available balance.
- Never pay the same settlement instruction twice.
- Never issue a refund against funds already distributed unless an independently funded remedy exists.
- Never allow an agent's negative review alone to move money.
- Never recognise a pending payment as confirmed settlement.
- Never use a contract amendment to overwrite previously agreed financial terms.
- Never permit platform operating expenses to consume protected customer funds.

The final point requires the underlying account/vault structure and legal arrangements to actually segregate protected funds. A database label isn't enough.

## 8. Full governance and evidence structure

For every contract, preserve the following objects:

Contract evidence bundle

```
contracts/{contract_id}/
  contract/
    original-request.json
    accepted-terms.json
    contract-hashes.json
    acceptance-receipts.json

  payments/
    funding-receipt.json
    settlement-transactions.json
    ledger-snapshot.json

  production/
    original-script.txt
    original-upload.wav
    upload-receipts.json
    processed-audio.wav
    alignment.json
    qc-report.json

  communications/
    directions.json
    amendments.json
    revision-requests.json

  governance/
    client-review.json
    narrator-review.json
    dispute-evidence.json
    decision.json
    appeal.json

  audit/
    event-log.jsonl
    evidence-manifest.json
    signatures.json
```

The object storage should be private, versioned and encrypted. Hash every original artifact on receipt. Keep access logs and prohibit silent evidence modification.

For the blockchain, store at most an appropriately designed commitment to contract or settlement data. Don't publish scripts, recordings, identities or detailed disputes on-chain. Even hashes of sensitive content require privacy consideration.

Use a retention schedule with legal holds, deletion procedures and access controls. The purpose is tamper-evident evidence, not permanent surveillance.

## 9. Dispute rules I'd adopt for launch

Proposed contract policy

Version 0.1

| Funding           | 100% secured before dispatch               |
| ----------------- | ------------------------------------------ |
| Offer expiry      | 5–15 minutes, configurable                 |
| Deadline          | Starts at confirmed acceptance             |
| Late submission   | Grace period, then evidence-based recovery |
| QC                | Immediate automated technical analysis     |
| Correction        | One included round for mistakes            |
| Customer review   | 24 hours after valid submission            |
| Dispute response  | 48 hours, with exceptions                  |
| Appeal            | 48 hours after a consequential ruling      |
| Public reputation | Only verified final outcomes               |

Illustrative operational deadlines. Formal terms must account for consumer rights, fair notice, payment arrangements and applicable law.

The dispute resolution system needs a written explanation of each decision, the supporting evidence, the applicable contract clause and a mechanism to contest mistakes.

I'd also include a very important customer-abuse protection: if an agent receives an approved recording and later attempts to obtain a refund using criteria absent from the original contract, that behaviour becomes part of the buyer's own reliability history.

For small jobs, HumanVoiced may sometimes rationally reimburse a customer from its own operating funds while still paying a compliant narrator. That is a customer-service expense, not a reason to manipulate the worker's contract.

## 10. Legal structure: the biggest prerequisite

Here is the main reason not to deploy self-custodied customer escrows casually.

The UK's FCA explicitly warns that an online marketplace receiving customer money before transferring it to sellers may be carrying on regulated payment services. It also requires certain UK cryptoasset service businesses to register before operating, depending on their activities.

A 2-of-3 multisig is not automatically exempt from regulation merely because it is on-chain.

For HumanVoiced, there are three possible business/legal structures to evaluate:

| Model                                   | Description                                                                                | Consideration                                                                            |
| --------------------------------------- | ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| Marketplace with regulated payments     | HumanVoiced connects customers and narrators; a qualified provider handles protected funds | Best starting point for an open marketplace                                              |
| Merchant of record / managed production | HumanVoiced sells narration to creators and contracts narrators as suppliers               | Different legal and operational responsibilities; not a magic exemption                  |
| Crypto-native escrow                    | On-chain conditional funding and controlled release                                        | Strong technical programmability, but requires contract, custody and regulatory analysis |

I would design the software to support all three but choose one legally reviewed model for the first live transactions.

A provider's fraud, KYC and payout infrastructure can save far more work than its fees cost at the earliest stage.

Also, actual financial escrow, contractual guarantees and merely delaying a payout are different things. We should describe the protection offered to users accurately.

## 11. Recommended implementation order

Given HumanVoiced is still recruiting its first narrators, I'd split the build into four deliverable stages.

# 01

Contracts and evidence

Versioned job contracts, server-side deadlines, immutable submissions, audit events and manual adjudication. Use simulated payments until the chosen funding arrangement is approved.

# 02

Payment adapters

Implement x402 V2 and a separate Q+Pay adapter. Support signed receipts, idempotent invoice settlement and financial reconciliation. No job activation unless the selected arrangement protects the funding.

# 03

Controlled real-money pilot

Use a compliant payment setup, carefully selected jurisdictions, small contracts and manually reviewed disputes. Test worker and creator payouts, refunds, chargebacks and exceptional cases.

# 04

Qubic escrow integration

Prototype MSVault funding and release separately, then test whether Q+Pay payment flows can interact with it. A vault is usable only if transaction permissions, recovery paths, human adjudication and settlement economics work in practice.

### Tests that must pass before real funds

The backend should have automated integration tests for simultaneous acceptance by multiple narrators, repeated x402 payments, duplicated provider webhooks, failed funding, partial funding, payouts during an open dispute, double-refund attempts, changed scripts after acceptance, expired invoices, platform upload outages, arbiter unavailability and rejected payment transactions.

For MSVault, also test signer loss, conflicting transaction proposals, two parties refusing to cooperate and a faulty or compromised arbitration signer.

Remember that a multisig accepts any permitted combination of signatures; it doesn't inherently know which party deserves a refund. Its signer arrangements, permitted destinations and governance controls must account for that trust model.

## 12. One final recommendation: separate the settlement layer from the trust layer

This matters for the broader vision.

HumanVoiced could eventually provide three public APIs:

| API                              | Service                                          |
| -------------------------------- | ------------------------------------------------ |
| `api.humanvoiced.com/voices`     | Search and contract verified narrators           |
| `api.humanvoiced.com/contracts`  | Execute and verify human-service agreements      |
| `api.humanvoiced.com/reputation` | Query permissioned, evidence-backed work history |

That way Qubic can become a preferred native payment option without restricting creators using ordinary accounts, stablecoins or other wallets.

The x402 signed-offer and receipt extensions are particularly interesting here because they support portable, verifiable records of transactions. HumanVoiced could extend that idea to actual human-service fulfilment receipts, supported by its own signed contract and submission records.

## Recommended end-state

## HumanVoiced Trust Engine

One contract lifecycle, independent of how the customer pays.

```
Agent requests human work
       ↓
Contract + quote locked
       ↓
Payment protected
       ↓
Human accepts
       ↓
Human submits evidence
       ↓
Independent QC + review
       ↓
Approve / correct / dispute
       ↓
Authorised fund release
       ↓
Signed completion receipt
       ↓
Reputation updated
       ↓
Agent resumes workflow
```

The next thing I would implement is the payment-state machine and immutable contract ledger—not a new Qubic smart contract yet.

That gives us the machinery for real transactions and disputes while preserving the ability to integrate x402, Q+Pay, MSVault and ordinary marketplace payment methods.

The distinctive infrastructure here is not just a system for paying people with crypto. It's a system where AI agents can commission human work, humans can trust that payment is protected, and neither party can arbitrarily rewrite the agreement after the work has been done.

---
*Source: owner-supplied research document, saved verbatim 2026-10-08. Mermaid styling blocks and image-badge lines from the source are omitted; all prose, tables, flows and figures are preserved.*
