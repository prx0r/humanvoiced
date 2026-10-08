# HumanVoiced — payment backend to ship

Decision: sole trader. 0% fee. Free global signup. USD denomination.
First escrow: Stellar USDC via Trustless Work V1 (0.3%/release, milestones,
disputes with resolver; testnet first, mainnet only after stuck-fund,
audit-remediation and legal checks). x402 V2 (Coinbase-facilitated, Base)
for agent payments/donations — NOT escrow by itself. Stripe Connect only
where eligible (US-platform stablecoin payouts; not a global solution).
Solana USDC later. Qubic/Q+Pay later, once conditional settlement is proven.

Cash-out: MoneyGram Ramps (170+ countries incl. Cambodia per provider docs —
verify with a real small withdrawal), LOBSTR docs, belo/Lemon (AR), Bitso
(MX), Airtm (LATAM), Coins.ph/PDAX (PH). Each corridor verified before
marking bookable. No silent bridging: recipient picks exact token+network.

Fee display per checkout: narrator $X, commission $0, escrow fee ~0.3%,
network/on-ramp shown pre-pay, donation $0 default separate. Narrator
receives full agreed fee; provider/donation funds cover costs. No
platform-held withdrawal balances: escrow pays straight to nominated
wallet on completion.

Legal flags (not advice, needs solicitor before live escrow): FCA
payment-services + custody/arranging under Oct-2027 regime apply regardless
of nonprofit/smart-contract form if we control release/dispute keys;
Stripe account needs genuine business presence; HMRC platform reporting
may apply at 0%; Cambodia/ID/TH/IN/VN crypto-payment limits; sole trader
compatible with marketplace, not with unlicensed financial services.

Launch order: (1) global profiles, no wallet needed; (2) Trustless Work
testnet full scenarios incl. abandoned buyer + lost signer; (3) real
wallet-to-cash tests (KH/AR/PH); (4) limited mainnet, low caps, verified
settlements; (5) fiat on-ramp + x402. Milestone: one KH narrator, one
foreign buyer, one $10 USDC contract, verified delivery, release to own
wallet, tested cash-out.

---
*Source: owner-supplied payments-backend thesis, saved 2026-10-08.
Image-badge lines omitted; prose, tables, flows and figures preserved.*
