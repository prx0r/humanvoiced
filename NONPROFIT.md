# HumanVoiced — nonprofit, crypto-native marketplace

Direction: UK CIC limited by guarantee (asset lock, social mission) — or a
nonprofit company limited by guarantee for flexibility. Zero commission:
narrators keep 100% of agreed fees; network/exchange/cash-out charges
disclosed separately; donations fund operations (never charitable/tax claims
without basis). Transparency page: aggregate fees, $0 commissions,
contributions, expenses, supported countries — no private worker data.

## Stablecoin rails (verified research, not yet integrations)

Primary: USDC on Base (cheap EVM, x402-native, escrow-compatible).
Second: USDC on Solana (low fees, x402 V2 documented). Research: TRON USDT
(TRC-20 cash-out compatibility; fees hurt micro-jobs; NOT Circle-native).
Recipient always chooses exact token+network. No silent bridging/swaps.

Corridors (provider-documented, each needs verification before activation):
Argentina (belo/Lemon USDT+USDC→ARS), Mexico (Bitso→SPEI MXN), Brazil
(Airtm USDC), Colombia/Peru/Chile (Airtm), Philippines (Coins.ph/PDAX/Airtm
→PHP/GCash/Maya). Vietnam/Thailand/Indonesia/Cambodia/India: restricted or
unverified — profiles yes, paid work no, until checked.

Pilots: Argentina + Mexico, then Philippines. Cambodia recruits, paid work
only after a verified cash-out route.

## Rules encoded in this repo

- Global profiles; paid bookings gated per country (`bookable_in`).
- Payout prefs at onboarding: later / stablecoin-wallet / local-currency.
- 100% fee to worker; minimum withdrawals + combined payouts.
- Noncustodial where possible (no unilateral control, no private-key custody).
- x402 = payment interface; escrow contract = conditional lock (USDC amount
  per contract, no double-spend, expiry refunds, dispute freeze). MSVault
  2-of-3 prototype only after economics/validation.
- Legal flags (not advice): FCA payment-services + Oct-2027 crypto regime;
  Stripe escrow approval; Cambodia/Indonesia/Thailand/India/Vietnam crypto
  payment limits; UK platform seller-reporting incl. zero-commission.

---
*Source: owner-supplied nonprofit/stablecoin thesis, saved 2026-10-08.
Image-badge lines omitted; prose, tables, flows and figures preserved.*
