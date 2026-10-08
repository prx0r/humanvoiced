# HumanVoiced — quality contracts, pricing heatmaps, reference-based QC

## 1. What $0.05–$0.10 per second actually costs

| Finished recording | $0.05/sec | $0.10/sec |
| ------------------ | --------- | --------- |
| 15 seconds         | $0.75     | $1.50     |
| 1 minute           | $3        | $6        |
| 5 minutes          | $15       | $30       |
| 10 minutes         | $30       | $60       |
| 30 minutes         | $90       | $180      |
| 60 minutes         | $180      | $360      |

Still below professional reference rates (Voice123 non-union $350–$500 for
5–15 finished minutes; Bunny Studio from $25), but $30–$60 for 10 minutes
abandons the cheap everyday-narrator wedge. Keep flat per-second rates for
urgent clips, specialist performances and ads; use a declining curve for
longer narration (Bunny Studio principle: higher unit pricing on short
scripts, bulk discounts as size grows).

## 2. Adopted price curve (fitted to owner targets)

Owner targets: 10-second clip $2 · 10-minute video $10 · 30-minute video $20.

Fitted curve, t in finished-audio minutes:

\[ P(t) = 1.54 + 1.65\,t^{0.71} \]

| Length | Price |
| ------ | ----- |
| 10 sec | $1.97 |
| 1 min  | $3.17 |
| 5 min  | $6.78 |
| 10 min | $10.00 |
| 30 min | $20.00 |
| 60 min | $31.40 |

Volume discount is structural (exponent < 1). Minimum checkout $3.50 still
applies to single orders; batched clips keep unit price. Narrator share 75%.

### Heatmap bands (reputation-priced, automatically decided)

Quote returns a band, not a point: base from the curve × tier multiplier
(new 1.0× … proven 1.15× … specialist 1.3×), quoted as {low, base, high}.
No bidding, no negotiation — the band moves with verified history.

## 3. Reference-based quality contracts

The question is never "is this a good voiceover?" but "did this person
deliver what the buyer selected?" At booking, freeze the exact portfolio
sample + version (e.g. `sample_238_v2`). Compare delivery against it along
separate dimensions — never one collapsed score:

- Script accuracy (ASR + alignment): missing/incorrect lines with timestamps.
- Audio fidelity (signal metrics + speech-quality model): technical defects.
- Voice consistency (embeddings + acoustic comparison): flags changes; never
  proof of origin; cloning triggers provenance review, not auto-accusation.
- Delivery consistency (pace/pitch/pauses/prosody vs selected style).
- Creative suitability (audio-language evaluator + brief): advisory only.

Model notes (Oct 2026): WhisperX (transcription + word timestamps),
WeSpeaker (speaker embeddings, uncertainty-aware Sep-2026 updates),
DNSMOS/NISQA (perceptual quality, indicators not judges). Speaker-ID skill
≠ perceptual-similarity skill — keep them separate metrics.

Targeted corrections: isolate the passage, request a re-record, stitch a
derivative, rerun QC, retain the original privately. One bad sentence never
fails a whole recording.

## 4. Calibration previews

For new/large contracts: narrator records the first 15–20 seconds of the
actual script; creator approves it as the contract-specific performance
reference. Optional for repeats/shorts. Judging an hour against a 30-second
generic demo is the failure mode this prevents.

## 5. Career ladder + privacy

New Voice → Verified Voice → Proven Narrator → Specialist, on completed
quality work and reliability — never accent/gender/nationality prestige.
Scarcity premiums only where verified demand supports them. Voice embeddings
are biometric data (UK ICO voiceprint guidance): specific consent, restricted
access, no unrelated training, deletion honored.

## 6. Launch test

$10 ten-minute everyday narration beside the $11 budget offer: compare
conversion, effort, repeats, margin. Question answered empirically: cheapest
human voice, or easiest reliable hire at a fair price?

---
*Source: owner-supplied quality/pricing thesis, saved 2026-10-08. Image-badge
lines omitted; prose, tables, formulas and figures preserved. Curve in §2
fitted by the build (targets $2/$10/$20) — supersedes the earlier piecewise
P(t) for new quotes; old curve retained in git history.*
