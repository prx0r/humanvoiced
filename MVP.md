# HumanVoiced MVP — 100% human-owned earnings

Positioning: run by a human, with the help of AI. Real voices. Real
people. Real work. 100% of the agreed job fee to the narrator, 0%
platform commission, supported by voluntary contributions.

## Legality summary

Google signup, AI-assisted portfolios, zero commission, voluntary
contributions, guest checkout and crypto payments are not inherently
unlawful. The regulated line is holding customer money and releasing it
to workers: UK FCA treats marketplace collection-and-pass-through as
potentially regulated payment services (offence to operate unauthorised);
Stripe's Sep-2026 restricted-business policy puts escrow services under
additional approval. So: separate marketplace/contract engine from actual
payment/custody. No self-operated escrow without authorisation; no
"legally protected escrow" claims without a real arrangement.

Also noted: Stripe account country matters (Cambodia unsupported, UK is);
UK platform seller-reporting to HMRC may apply even at zero commission;
UK consumer law needs fair cancellation/refund terms; FCA crypto custody
registration is separate from merely accepting crypto.

## MVP scope

1. Narrator onboarding: record 30s BEFORE sign-in; Google attaches it to
   the new account. AI fills a private draft profile (name from Google,
   declared languages, suggested accent/character/pace/quality/categories/
   bio/tags with confidence + model version; never nationality/ethnicity/
   gender/age as fact). Narrator reviews, edits, publishes.
2. Guest booking: no buyer account. Narrator $X, commission $0, payout $X
   (processor fees are platform expense). Stripe Checkout
   (`customer_creation=if_required`); private order link
   `humanvoiced.com/orders/ord_123` with high-entropy credential, email
   receipt, no analytics/referrer leakage. Pseudonymous to narrator/workers;
   not anonymous to processors/regulators.
3. Money: narrator gets 100% of agreed fee. Donations ("Support
   HumanVoiced", never charitable/tax claims, needs provider approval)
   fund fees, storage, AI, refunds. Operating reserve segregated from
   narrator funds — never touch owed money for expenses.
4. Escrow paths: Stripe Connect separate-charges-and-transfers (needs
   provider approval of delayed settlement; authorisations ≠ escrow,
   ~7-day windows); crypto 2-of-3 (buyer/narrator/arbiter) via MSVault
   prototype after validation. MVP: Stripe test mode + simulated crypto.
5. Release sequence: (1) voice library, (2) guest booking, (3) live fiat
   with approved provider, (4) agent-native crypto.

Pipeline: voice_samples → voice_analysis_jobs → ai_profile_drafts →
narrator_reviewed_profiles → public_voice_catalogue → agent_search_api.

First screens: Record Your Voice, Review Your AI Profile, Your Public
Portfolio. Success: friend records, gets discovered, delivers, gets paid.

---
*Source: owner-supplied MVP thesis, saved 2026-10-08. Image-badge lines
omitted; prose, tables, flows and figures preserved.*
