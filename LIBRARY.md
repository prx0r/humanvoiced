# HumanVoiced — the ElevenLabs for real humans

I think you've landed on a much stronger product architecture: a searchable library of real human voices, with standardised pricing, instant booking, agent-based casting, and a verifiable history of every job.

The worker doesn't need to sell themselves, negotiate rates or learn audio engineering. They record their voice, choose what work they're willing to do, and start receiving offers.

The creator—or their AI agent—doesn't need to interview people. It listens to samples, chooses the right person, submits the job and gets back finished audio.

The key is to build the marketplace around voice IDs, just as speech-generation APIs do, except each ID represents an actual person.

## 1. The killer first wedge

Affordable human narration for faceless YouTube channels producing 5–15-minute videos.

Not advertising, audiobooks or character acting yet. Those will become additional products.

The initial proposition:

# HumanVoiced

### Real voices. On demand.

Browse 30 human voices, hear their natural recordings, and book a narrator from $1 per finished minute, plus a $1 job fee.

Quick clip

# $1.25

15 seconds · before single-order minimum

YouTube video

# $11

10 minutes

Long narration

# $41

60 minutes · volume pricing

Proposed entry-level customer prices, not validated market prices.

The strongest repeat-use case is an AI-assisted creator uploading three to seven videos a week. Their production agent already has the script and can commission narration without leaving its workflow.

Your first 30 narrators are effectively the initial voice library.

## 2. The exact 30-second audition

I researched established audition practices. Voice123 recommends samples of approximately 20–30 seconds and emphasises having distinct examples for narration, commercials, characters and other categories.

Traditional phonetic testing also uses passages such as The North Wind and the Sun to elicit pronunciation differences, but that is not optimised for a YouTube creator quickly deciding whether they like someone's voice.

I'd create our own standard text. Every narrator initially reads the same passage, making voices easy to compare.

HumanVoiced Natural Sample — English v1

Recommended

Approximately 30–35 seconds at a natural reading pace

Last Thursday morning, Alex walked into a little café beside the railway station. The rain had finally stopped, but the streets were still shining.

At seven forty-five, a woman in a bright blue jacket asked, "Have you heard the news?"

Alex laughed. "Not yet. What happened?"

By lunchtime, twenty-three people had gathered outside. Nobody quite knew what was going on, and that was the strange part.

Sometimes an ordinary day becomes a story you'll remember for years.

Read naturally. Don't perform or exaggerate an accent.

Copy script

This passage is designed to reveal several useful qualities in one short recording:

| Feature                        | What it tests                           |
| ------------------------------ | --------------------------------------- |
| Simple storytelling            | Natural narration cadence               |
| Questions and short replies    | Pitch variation and intonation          |
| "Thursday", "three", "shining" | Consonant articulation                  |
| Numbers and times              | Natural pronunciation patterns          |
| Long and short sentences       | Breath pacing and pauses                |
| Narrative ending               | Ability to close a thought convincingly |

It isn't scientifically phoneme-balanced or a complete measure of acting ability. But it's a useful standardised casting sample, which is what we need.

I'd add one optional 10-second unscripted prompt later: "Tell us something you enjoyed doing recently." This helps distinguish someone's natural conversational voice from their reading voice.

For Russian, Hindi, Spanish and other languages, use separately authored and reviewed native-language equivalents, not literal translations optimised for English phonetics.

Don't initially request five recordings. One sample should get someone onto the platform.

## 3. The real product is a library of bookable human voices

The ElevenLabs Voice Library already supports searching and filtering voices by language, accent, narration, social media, characters, education and advertisement use cases.

HumanVoiced can adopt that same discovery experience while adding the things synthetic voices don't need: live availability, delivery guarantees, work history and enforceable contracts.

A narrator portfolio should look something like this:

## Alex · British English

Accepting work

Conversational

Warm

Natural narration · Explainers · Storytelling

Voice samples

Demo profile

Natural voice

0:32

YouTube documentary

0:24

Energetic advertisement

0:18

Character: nervous inventor

0:16

Job success

98%

Completed

73

Typical delivery

4h

10-minute YouTube script

# $11

See booking flow

Fictional narrator, performance data and samples for layout illustration.

As someone completes jobs, their profile becomes more persuasive. The AI can suggest additional sample categories they would benefit from recording.

For instance, somebody with a great natural narrator voice might be invited to create a 20-second horror-story demonstration because actual customers have been searching for that style.

This creates a direct connection between demonstrated demand and workers improving their portfolios.

## 4. Onboarding: one recording, then choose what work you accept

After submitting the natural voice recording, show the narrator a short work-preferences screen.

What would you like to record?

Interactive onboarding prototype · Choose any

YouTube narration

Explainers, documentaries, storytelling

Shorts & social clips

15–90-second scripts

Organic promotional content

Unpaid-distribution promotional videos

Paid advertisements

Commercials with separate usage terms

Long-form readings

Longer narrated material

Characters & acting

Fictional voices and dialogue

Longest recording you'd accept

2 minutes

15 minutes

30 minutes

60 minutes

Standard guaranteed turnaround

2 hours

12 hours

24 hours

Copy preferences

I'd also include a separate, optional content-boundary selector for political messages, religious material, adult themes, profanity and sensitive subjects. Narrators can decline categories without a negative reliability event.

The onboarding should remain fast: these preferences can be completed after the profile is created.

## 5. Pricing — your $1-per-minute idea is good, with two adjustments

I particularly like removing price bidding.

Competitive bidding can drive people to offer increasingly low rates. Instead, HumanVoiced publishes a transparent schedule, and narrators choose whether they accept work at those rates.

We should distinguish two things:

1. Base pricing determined by the length of the script.
2. Premiums for demonstrated skill, scarce availability, difficult tasks and urgent delivery.

I'd start with this proposed customer price curve, before special premiums:

\[ P(t)= 1+\min(t,10)+0.75\max(0,\min(t,30)-10)+0.50\max(0,t-30) \]

Where \(t\) is quoted finished-audio minutes.

This gives your initial $1-per-minute pricing up to ten minutes, then volume discounts.

| Audio length | Base customer price |
| ------------ | ------------------- |
| 15 seconds   | $1.25               |
| 1 minute     | $2                  |
| 5 minutes    | $6                  |
| 10 minutes   | $11                 |
| 20 minutes   | $18.50              |
| 30 minutes   | $26                 |
| 60 minutes   | $41                 |

Adjustment one: minimum checkout. A standalone $1.25 job is too small once payment fees, moderation and recording setup are included. I'd charge at least $3.50 for an individual order. Keep the $1.25 unit price for batched clips that a narrator can record in one session.

Adjustment two: minimum effective pay. Long recordings sometimes require several hours of work per finished hour. Experienced audiobook narrators describe production ratios around two to four working hours per finished hour, depending on editing and complexity.

AI mastering reduces some post-production labour but not all human recording effort.

Therefore, the pricing engine should raise the payout or disallow an offer when it cannot meet the agreed minimum compensation for estimated work.

### Interactive pricing model

HumanVoiced rate simulator

Proposed pricing

Finished audio length

10 min

Narrator tier

Standard · 1×

Proven quality · 1.3×

Specialist or scarce skill · 1.8×

Priority delivery · 1.5×

Creator price

# $11.00

Narrator payout

# $8.25

Assumes a 75% narrator share of the calculated price, with a $2.25 minimum payout. Excludes any extra compensation needed to maintain an acceptable acceptable effective hourly rate. Platform margin must cover payment, audio-processing, support and dispute costs.

The price is fixed before acceptance. The narrator can reject an offer but cannot start a reverse auction.

Also, the quoted duration should derive from the frozen script's word count and an agreed reading pace. We shouldn't charge creators extra simply because a narrator speaks slowly.

### Why rarity pricing is interesting

Say a creator wants an English narration with a recognisable Russian accent, and the platform has only one qualified narrator available.

We could automatically raise the advertised payout for that particular type of job to attract supply.

But rarity must reflect actual unmet customer demand, not an assumption that one nationality or accent is inherently worth more.

A small initial marketplace could use these signals:

- Number of genuine paid orders requesting the capability.
- Number of qualified, available narrators.
- Quote-to-booking conversion.
- Jobs that could not be filled within their deadline.
- Observed fulfilment reliability.

Price surcharges should be disclosed in advance, and workers should see what they will earn. A proven narrator can additionally qualify for a higher service tier without having to negotiate individually.

## 6. Demand creates new narrator supply

This could become one of HumanVoiced's most distinctive features.

A creator's agent requests:

> I need an English-speaking narrator with a Russian accent for a 12-minute history video, delivered tonight.

There are no qualified available narrators.

Rather than simply returning an error, HumanVoiced should record unmet demand and start a recruitment workflow.

Agent requests a voice → Qualified narrator available? (Yes → Quote and dispatch contract) / (No → Record unmet demand → Enough verified demand? (No → Waitlist or suggest alternatives) / (Yes → Recruitment campaign → New applicants record samples → Voice QC and approval → Notify waiting customers))

(Original included a flowchart diagram expressing the above recruitment workflow.)

The recruitment agent could draft a targeted post:

> HumanVoiced is seeking people who speak English with a Russian accent for paid YouTube narration. Record a short sample to apply. Current jobs pay according to our published rate schedule.

Only describe actual funded work as an available job. Future or speculative demand should be clearly labelled as recruitment or a waitlist opportunity.

This creates a demand-responsive voice library without requiring thousands of dormant narrators.

## 7. Deterministic governance, with agents handling exceptions

I agree that disputes should start with a deterministic rules engine, not an LLM improvising a decision.

I'd split the system into three components.

Rules engine

Evaluates objective contractual facts: funding, deadline, upload receipt, cancellation status, agreed revisions and review-window expiry.

Governance agent

Analyses recording content, compares claims to the contract, finds evidence, explains applicable rules and recommends a resolution.

Human adjudicator

Handles disputed quality judgements, allegations of fraud, contested nonpayment, appeals and serious account sanctions.

### The rules should be explicit and versioned

For example:

| Rule ID   | Condition                                  | Action                                               |
| --------- | ------------------------------------------ | ---------------------------------------------------- |
| `PAY-001` | Funds not secured                          | Do not issue an actionable contract                  |
| `SLA-001` | Offer expires without acceptance           | Close offer; no worker penalty                       |
| `SLA-002` | Deadline missed                            | Notify, preserve logs, begin recovery                |
| `SLA-003` | Platform outage affects delivery           | Suspend affected deadline penalty                    |
| `QC-001`  | Uploaded file cannot decode                | Ask for replacement                                  |
| `QC-002`  | Speech alignment suggests missing passages | Flag exact passages for review                       |
| `REV-001` | Client changes locked script               | Require contract amendment                           |
| `PAY-002` | Valid delivery accepted                    | Authorise release                                    |
| `PAY-003` | Review period expires without objection    | Authorise release if contract policy permits         |
| `DIS-001` | Substantive dispute filed                  | Freeze affected settlement and escalate              |
| `REP-001` | Worker-attributable failure confirmed      | Update reliability after review rights are satisfied |

The agent cannot invent new rules. It can only supply evidence, classify issues and recommend the application of a published rule.

For financial disputes, a deterministic rule can authorise ordinary undisputed releases. But a disputed breach of contract, subjective performance failure or allegation of deception should not trigger an irreversible payout denial or public penalty without a meaningful review route.

### Example of a complete dispute

A narrator uploads a 10-minute recording 20 minutes late.

The contract shows a two-hour deadline. The accepted terms include a 15-minute grace period.

The machine finds:

```
{
  "rule": "SLA-002",
  "deadline_status": "missed",
  "late_seconds": 1200,
  "grace_seconds": 900,
  "original_file_received": true,
  "platform_outage": false,
  "finding": "late_submission",
  "fault_status": "pending_review",
  "action": "open_incident"
}
```

The worker is notified and may supply an explanation or challenge inaccurate records.

The customer service agent has a different job: help the parties understand the situation and propose an allowed remedy.

It can say:

> The recording arrived five minutes outside the agreed grace period. You can accept the late delivery, request the available contractual remedy, or ask for review.

It cannot just declare that the worker loses payment because it dislikes their explanation.

This makes governance predictable while keeping humans in control of consequential disputes.

## 8. Agent customer service and agent-to-agent support

I would make HumanVoiced's support agent part of the core API.

Imagine a creator's agent asking:

> What happens if the narrator misses the deadline? Can I request a different voice automatically?

HumanVoiced's agent answers from the exact contract, relevant policies and available API capabilities. It can then create a permitted fallback request.

For humans, the same agent supports voice-guided onboarding:

> "Your microphone has a lot of background noise. Try moving away from the fan and recording that sample again."

For developers and external agents, expose an MCP/OpenAPI interface with tools such as:

```
voices.search
voices.compare
voices.get_profile
pricing.quote
contracts.create
contracts.get_terms
contracts.get_status
contracts.request_amendment
submissions.get
quality.get_report
disputes.get_rules
disputes.open
support.ask
```

The support agent should use the same structured rules and official documentation as the backend, rather than providing answers from an uncontrolled conversational memory.

It should not receive unrestricted payout, refund or account-suspension authority.

### What a creator agent actually does

```
Agent: Find a warm British narrator
       for my 1,600-word script.

HumanVoiced:
       7 qualified voices available.
       3 within your 12-hour deadline.

Agent: Compare their narration samples.

HumanVoiced:
       Returns playable audio and
       explainable suitability rankings.

Agent: Book the best match under $25.

HumanVoiced:
       Contract funded and dispatched.

Narrator: Accepts, records, uploads.

HumanVoiced:
       Validates WAV, checks script,
       preserves original submission.

HumanVoiced:
       narration.ready webhook

Agent:
       Downloads approved audio,
       aligns scenes, renders video.

Creator:
       Reviews or authorises publishing.
```

This is where the ElevenLabs comparison really works. The caller can switch from synthetic speech to human speech with a similar abstract workflow, while accepting that human delivery is asynchronous.

## 9. Character voices become the second supply layer

After somebody records a natural sample, they can optionally add different performance profiles.

For instance:

One narrator, multiple bookable styles

Natural voice

Calm documentary

Comedy deadpan

Horror storyteller

Energetic announcer

Old wizard

Nervous inventor

Additional styles must be demonstrated by real recordings and selected by the narrator. They are not automatically claimed capabilities.

Each sample has its own style description, audio embedding, reliability history and suitable job categories, but all link back to the same person.

The matching system needs two distinct questions:

Who has the appropriate natural voice? Who can perform this particular character or style convincingly?

Those are not equivalent.

I'd avoid marketing unlicensed impersonations of recognisable celebrities or copyrighted characters. Original character voices are a much cleaner starting point.

And for advertisements, licensing needs to be separate from routine YouTube narration. Voices distinguishes broadcast/paid advertising from non-broadcast narration because usage, geographic reach and duration materially affect rates. So we should not automatically license a $2 organic narration clip for an unlimited global paid advertising campaign.

## 10. The launch product and growth loop

For the first 30 voices, I would focus on five functions:

| System      | What is essential at launch                                            |
| ----------- | ---------------------------------------------------------------------- |
| Onboarding  | Single standard read, audio check, email, consent                      |
| Portfolio   | Public sample, voice tags, work preferences, availability              |
| Marketplace | Browse, listen, fixed quote, book a narrator                           |
| Fulfilment  | Frozen contract, acceptance, delivery, quality checks                  |
| Governance  | Evidence preservation, deterministic timers, human-reviewed exceptions |

The natural progression is:

30 founding narrators → Public voice library → Creators hear real samples → Creators book and repeat → Performance history accumulates → Better agent matching → More completed orders → Identify missing voice capabilities → Recruit targeted new voices

(Original included a flowchart diagram expressing the above growth loop.)

I'd use the first batch of profiles to validate specific creator requests rather than recruiting endlessly. Ten narrators can be plenty if they cover the actual demand; a thousand narrators are not an asset if nobody gets paid.

### What I would prioritise for the next build

P0 — Complete immediately: Standard natural-voice audition; editable AI-generated profile; work preferences; public portfolio URLs; basic voice search; fixed pricing for YouTube narration; paid offers with accepted contract terms.

P1 — First real transactions: Payment protection; recording upload; audio QC; immutable evidence; deterministic resolution engine; completion webhook; mutual reviews.

P2 — After recurring orders: Extra voice styles, character samples, matching from reference audio, premium/specialist tiers, demand-based recruitment campaigns and full agent-to-agent support.

The exact first success criterion should be:

> A creator's AI writes a 10-minute script, finds a matching voice from the 30 real people, pays $11, receives a usable human recording, and automatically completes the video.

Then that creator buys the same narrator's voice again the following week.

One final distinction matters: YouTube does not categorically penalise synthetic voices. Its monetisation rules focus on repetitive, mass-produced and inauthentic content. HumanVoiced should sell superior human performance and creator relationships, not a guarantee of avoiding AI-content enforcement.

The strategic endgame: ElevenLabs lets developers select synthetic voices from a library. HumanVoiced lets developers select actual people from a comparable library—with price, availability, identity, contractual reliability and verified work history attached.

That combination is substantially more interesting than just a cheap voiceover marketplace. Save as .md

---
*Source: owner-supplied wedge document, saved verbatim 2026-10-08. Mermaid styling blocks and image-badge lines omitted; prose, tables, flows, figures and formulas preserved.*
