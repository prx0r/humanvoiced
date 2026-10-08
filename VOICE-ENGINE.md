# HumanVoiced — Voice Intelligence Engine v1

Foundation: a machine-readable voice identity that gets more accurate with
every recording and completed job. 30 seconds in; structured profile out;
agents search in natural language and get explainable matches.

Core rule: four independent layers, never one embedding or one score —
acoustic measurements (measured), perceptual descriptions (AI-estimated,
subjective), confirmed capabilities (declared/verified), proven performance
(verified work only).

## Pipeline (independent, rerunnable stages)

record → preserve original → decode/QC → VAD → transcribe+align →
acoustic features → audio understanding → merge → validate → draft →
narrator review → publish → catalogue. Keyed by
`sample_sha256 + pipeline_version`; retry stages, never whole runs.

## Model stack (Oct 2026)

VAD: Silero (MIT, CPU). Transcription: Cloudflare Whisper large-v3-turbo
($0.000513/min) default; Qwen3-ASR multilingual option. Acoustic:
librosa/soundfile/FFmpeg/pitch tracker (no openSMILE — commercial trap).
Description: Gemini audio understanding / Qwen3-Omni captioner with the
constrained-extractor prompt (controlled vocab, time intervals, unknowns
allowed; never ethnicity/nationality/age/gender/personality/scores).

## Profile layers (35–45 fields, 7 groups)

Acoustic (measured, with uncertainty) · perceptual (controlled multi-label
vocab, graded) · language/accent (self-reported primary, AI tentative) ·
expressiveness per segment (audition passage parts) · recording quality
(retake signal, not a search penalty) · capabilities (declared/demonstrated/
verified) · work history (starts empty, verified only).

Provenance per field: value, source, model, evidence range, confidence type,
human_confirmed flag. Raw observations kept; public profile is a materialised
view. New models add runs; nothing silently rewrites identity.

## Search (3 stages)

Eligibility (language, category, length, availability, payout route — hard
gates, no score compensates) → soft suitability (perceptual 35, delivery 25,
pace/acoustic 15, category history 15, reliability 10; neutral for missing
history) → explained response (match reasons + uncertainties + sample +
profile + can_book). No unexplained talent scores.

Embeddings split: semantic (approved descriptions, pgvector later) vs
speaker (recognition-capable → biometric rules, ICO voiceprint guidance).
MVP: no speaker-identity embedding at signup; opt-in later with safeguards.

## Learning loop

Track shown → played → booked → approved → returned → rebooked, plus praised/
criticised characteristics. Exposure/price/position confound choice — controlled
exploration with consent before training rankers on it.

## Launch evaluation (30 voices × 20 briefs)

Top-5 recall, description agreement, narrator correction rate, booking
conversion, repeat rate, false-rejection rate. Manual evaluation beats
fine-tuning at this size.

## Milestone (DoD)

Authed narrator records in-browser → original stored privately, restart-safe
→ analysis produces validated structured data → descriptors grounded →
narrator edits/publishes → catalogue + search serve it → agent NL query
returns explainable matches → rerun with new model versions old records.

---
*Source: owner-supplied voice-engine thesis, saved 2026-10-08. Image-badge
lines omitted; prose, tables, schemas, flows and figures preserved.*
