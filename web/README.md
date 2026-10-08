# web/ — portfolio + contract + dispute UI

Target: Next.js 14 + Tailwind + shadcn/ui (matches reuse set).
Current: static prototype pages below, same copy/structure, migratable 1:1.

- `portfolio.html` — narrator portfolio (§2): samples (consent-gated), 90-day +
  12-month stats with sample counts, New-voice label, availability.
- `contract.html` — HV-1042 contract UI (§3): payout, deadline countdown
  (server time), criteria, accept/decline/counteroffer (design-task buttons).
- `dispute.html` — evidence-gated case view (§7): relevant evidence only,
  both-sides responses, written decision + appeal window.
