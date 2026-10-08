# web/ — static Pages site (no framework)

Source: `humanvoiced_frontend.zip` (stallshark bucket) + `contract.html`/`index.html`.
Preview concept renders included in the ZIP (not deployed).

- `onboard.html` + `studio.js` — Voice Studio: record → IndexedDB (`pending-onboarding`)
  survives OAuth → Google sign-in → upload → draft → edit → consent → publish.
  Status via `GET /api/auth/me`; `?demo=1` runs fully offline (localStorage).
- `portfolio.html` + `portfolio.js` — public portfolio `?h=handle`: playable
  consented samples, tags, verified-work counts, booking CTA.
- `brief.html` — creator brief explainer: script-only default, optional video,
  sync-to-picture, stage direction, paid custom auditions.
- `hv.css` — shared styling.
- `contract.html` — HV-1042 contract UI sketch (design-task buttons, not wired).
- `index.html` — landing stub.

Target: Next.js 14 + Tailwind + shadcn/ui (matches reuse set). Current static
pages are migratable 1:1. Dispute UI (`dispute.html`) not yet built.
