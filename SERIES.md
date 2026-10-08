# HumanVoiced — the recurring channel marketplace

I think this is the strongest wedge we've identified. Instead of selling one-off voiceovers, HumanVoiced helps ordinary people become the recurring voices of YouTube channels.

A creator isn't really looking for someone to read one script. They're looking for someone they can depend on for their next 10, 20 or 100 videos.

And for the narrator, that completely changes the appeal:

> Become the voice of a YouTube channel. Get paid for every episode. Build a verified portfolio of published work.

The product becomes a combination of a human voice library, a recurring-work marketplace and an agent-managed production system.

## 1. The three types of work

| Contract          | Example                     | Purpose                |
| ----------------- | --------------------------- | ---------------------- |
| One-off recording | $11 for one 10-minute video | Try someone out        |
| Series contract   | 15 videos over 8 weeks      | Recurring paid work    |
| Channel voice     | Ongoing weekly releases     | Long-term relationship |

The ideal customer progression is:

Hear sample → commission trial → book a series → retain as channel narrator.

The creator's AI agent manages all of this. The narrator just receives scripts, records them and builds a portfolio.

Importantly, Upwork already demonstrates the basic payment-protection structure: a fixed-price contract can be divided into individually funded milestones, with each deliverable submitted for review before payout. HumanVoiced can specialise that mechanism for episode-based production.

## 2. The series contract

EXAMPLE SERIES AGREEMENT

## Narrator for 15 YouTube Episodes

Recurring

The Curious History Channel

Episodes

# 15

Target audio

# 150 min

Narrator earnings

# $120

Creator total

# $165

Episode commitment

15 milestones

Approximately 10 minutes per episode, scripts supplied during the 8-week contract.

Each accepted episode must be delivered within 24 hours of receiving the final approved script.

The creator funds each active episode in advance and agrees to the series cancellation terms.

Illustrative $11 customer price and $8 narrator payout per episode. Real prices must account for recording effort, contract duration, work guarantees and processing costs.

One scale distinction matters: 15 ten-minute episodes are 2.5 hours of finished audio, not 20 hours. A contract covering 20 hours of finished narration would involve 1,200 recorded minutes and should be priced very differently.

I'd make every contract specify both total word-count limits and estimated finished-audio duration.

## 3. The portfolio becomes the worker's most valuable asset

Imagine the public profile after somebody has spent six months on HumanVoiced.

## Alex Morgan

British English · Natural storytelling

Verified work history

Accepting series offers

Published videos

## 38

Completed contracts

## 5

On-time delivery

## 98%

Selected published work

The History Channel — Medieval Mysteries

12-episode narration contract · Completed

Verified

1.2M example views

Space Explained — Weekly Episodes

16-episode narration contract · Completed

Verified

825K example views

Illustrative profile. Names, episodes, thumbnails, statistics and verification badges are mock data.

That is much more compelling than "I've completed 38 orders."

The narrator can say:

> "I'm the voice of two channels. I've narrated 38 published videos. Here are the videos and my verified completion record."

### How we verify published work

YouTube's Data API provides video IDs, titles, channel IDs, descriptions and view counts. Its `videos.list` endpoint can retrieve these details without asking the narrator to fabricate screenshots.

I'd implement three verification levels:

| Level                | Evidence                                             | Profile display                |
| -------------------- | ---------------------------------------------------- | ------------------------------ |
| Platform verified    | HumanVoiced contract and delivered WAV               | Verified recording             |
| Publication verified | Video URL, matching channel and creator confirmation | Published work                 |
| Channel verified     | Creator connects their YouTube account through OAuth | Verified channel collaboration |

For every completed recording, we already possess the original submitted WAV, its checksum, the accepted script and the contract. We can associate those with the final published video's ID.

That connection is much stronger than letting anybody paste a YouTube URL into a portfolio.

The narrator needs permission to publicly claim or display commissioned work, particularly for confidential projects. A verified private contract can still strengthen their internal reliability score without exposing the customer.

### Automatically track views

We can periodically retrieve public video statistics and show something like:

Example portfolio impact

# 2,430,000

Combined views across attributed videos

Views of videos featuring the narrator, not views caused by the narration. Last synchronised: example only.

This is technically feasible, but YouTube's API policies matter. Unauthorised public statistics generally cannot be stored for more than 30 days without refreshing; authorised statistics have different retention conditions. Displayed figures must remain current and properly contextualised.

Also, from August 24, 2026, YouTube changed how video starts count toward public view counts, so raw views shouldn't be represented as a comparable measure of narrator performance across all periods.

If a channel connects its account, we can optionally retrieve more useful private analytics, such as watch time, through the authorised YouTube Analytics API.

I would keep views as portfolio proof, not as the main quality score. A narrator can perform brilliantly on a video that receives 200 views, or poorly on one that receives a million.

## 4. Strict enforcement needs to be mutual

This is the biggest structural decision.

A 15-episode agreement creates obligations for both parties. It cannot just be a mechanism for penalising a narrator who fails to deliver.

The creator must actually provide scripts, secure episode funding and honour whatever volume of work it guarantees.

The narrator must reserve the agreed capacity, accept valid scripts within that arrangement and deliver completed audio on time.

### Master agreement + episode contracts

Series Master Contract → Episode 1 → Episode 2 → Episode 3–15. Funded + Script Locked → Narrator Records → QC + Approval → Worker Paid → Published Video Linked → Portfolio Updated.

(Original included a flowchart diagram expressing the above master/episode structure.)

The master agreement specifies the overall relationship:

- Number of committed episodes and maximum total words.
- Contract period, release schedule and delivery guarantees.
- Narrator payout, pricing tiers and any volume discount.
- Minimum guaranteed paid work versus merely estimated demand.
- Usage rights, optional public credits and portfolio permissions.
- Correction, cancellation, replacement and termination rules.
- Payment protection and the selected funding mechanism.

Each episode then has its own immutable script, deadline, submission and approval record.

Upwork's milestone system is a useful precedent, but its standard approach requires funding one active milestone at a time.

For HumanVoiced, we can add a series-level minimum commitment so a worker who reserves capacity isn't left without compensation if the creator stops supplying scripts.

### Example contract policy

| Event                                       | Proposed rule                                                            |
| ------------------------------------------- | ------------------------------------------------------------------------ |
| Creator supplies the script on schedule     | Narrator's response obligation begins according to the agreed terms      |
| Creator supplies it late                    | Narrator's deadline shifts; no automatic worker penalty                  |
| Narrator misses a valid deadline            | Recovery process, backup options and a verified incident review          |
| Narrator submits the wrong text             | Correct the affected passages                                            |
| Creator changes the script                  | New version and potentially an adjusted payout                           |
| Creator cancels after work begins           | Pay for completed work and applicable agreed cancellation compensation   |
| Creator stops commissioning episodes        | Honour the guaranteed minimum or agreed termination settlement           |
| Narrator withdraws from series              | Apply notice, transition and cancellation terms, with genuine exceptions |
| Creator doesn't publish a completed episode | Narrator still gets paid for the accepted work                           |

This last rule is important. The worker sells the recording, not the promise that the creator will publish it.

The platform can enforce payment, deadlines, access, eligibility, contract state and reputation rules. It cannot physically compel someone to record ten future scripts. Longer-term commitments therefore need proportionate cancellation remedies and replacement arrangements—not indefinite lock-in or automatic cash fines.

## 5. Agent-native recurring contracts

The creator's agent should be able to manage an entire series without manual oversight, provided the creator has authorised the budget and terms.

Example:

```
{
  "contract_type": "series",
  "channel_id": "yt_123",
  "narrator_id": "voice_alex",
  "episodes": 15,
  "max_words_per_episode": 1500,
  "schedule": {
    "episodes_per_week": 2,
    "contract_weeks": 8
  },
  "delivery_sla_hours": 24,
  "pricing": {
    "customer_usd_per_episode": 11,
    "narrator_usd_per_episode": 8,
    "minimum_guaranteed_episodes": 10
  },
  "rights": {
    "online_video_commercial_use": true,
    "portfolio_attribution": true,
    "voice_cloning": false
  }
}
```

The exact script doesn't need to exist when the master agreement is signed. It is frozen when each new episode is commissioned.

The API could expose:

```
POST /v1/series
GET  /v1/series/{id}
POST /v1/series/{id}/episodes
GET  /v1/series/{id}/progress
POST /v1/episodes/{id}/submissions
POST /v1/episodes/{id}/publication
GET  /v1/voices/{id}/verified-work
```

Agent requests human work → Contract + quote locked → Payment protected → Human accepts → Human submits evidence → Independent QC + review → Approve / correct / dispute → Authorised fund release → Signed completion receipt → Reputation updated → Agent resumes workflow.

(Trust-engine sequence from the payments thesis, reused for series episodes.)

A failed episode should not automatically terminate the whole series. The contract should define correction rights, fallback narrator rules and thresholds for terminating the ongoing relationship.

For payments, the x402/Qubic adapters we've discussed can be integrated per episode, but a confirmed payment isn't automatically escrow. A true series guarantee requires protected funds or another enforceable and financially supported commitment.

## 6. Portfolio proof could create a second growth engine

I especially like the possibility that every new published video advertises the worker's skills.

The creator could optionally include:

> Narration by Alex — HumanVoiced.com/@alex

That link is a proposed URL, not a verified live profile.

Now a narrator's previous work can bring future customers.

And a creator might discover someone whose voice they love while watching an unrelated video, click their profile and book them for an entire series.

The platform could also generate a concise verified-work credential that the narrator can share outside HumanVoiced:

Verified HumanVoiced Work History

Completed 15-episode narration contract

150 finished audio minutes delivered

14 of 15 episodes delivered on time

12 publicly attributed YouTube releases

Illustrative evidence-backed credential, not an actual completed contract.

That work history is a portable asset, rather than reputation trapped inside a private star-rating system.

## 7. The job board becomes a channel casting board

Instead of displaying a million tiny $2 jobs, I would make recurring opportunities the prominent category.

## Open channel opportunities

Illustrative

History Documentary Channel

Series

British English · Calm storytelling · 2 videos/week

$8 per episode to narrator

12 episodes · Up to $96

12-week project

Science Explainer Channel

Series

Indian English · Conversational · 3 videos/week

$10 per episode to narrator

15 episodes · Up to $150

5-week project

Horror Stories Channel

Trial → Series

Any English accent · Atmospheric storytelling

$12 per episode to narrator

One paid trial, then potential 10-episode agreement

Flexible

Fictional opportunities for product design; no actual jobs are being offered.

For each opening, an agent searches existing profiles, listens to the natural voice samples and sends invitations. Workers can also express interest themselves.

And because the agent understands the job requirements, it could explain:

> You're a strong match for this documentary channel because your reading pace and tone align with its brief. The contract requires two ten-minute narrations each week.

This is considerably more accessible than asking ordinary people to write professional proposals and compete in an open bidding market.

## 8. The actual first go-to-market strategy

I'd reposition the worker-facing headline around recurring jobs.

Old: Get paid to read aloud.

New: Become the voice of a YouTube channel.

The second has greater aspiration while retaining the simplicity of the work.

I would launch with two customer products:

Try a voice: commission one affordable episode.

Hire for a series: select a narrator, specify 4–15 episodes, agree on volume and timelines, and fund the agreed commitments.

Don't require creators to guarantee 15 videos on their first transaction. Make it easy to upgrade a successful first recording into a series.

### The first 30 days

| Stage                      | What to validate                                            |
| -------------------------- | ----------------------------------------------------------- |
| 30 narrator profiles       | Can agents meaningfully distinguish and match their voices? |
| 10 paid trials             | Do creators prefer the result enough to pay?                |
| 3 series agreements        | Will customers commit to repeat orders?                     |
| 20 completed recordings    | Can the platform meet delivery and quality obligations?     |
| 10 linked published videos | Can we turn deliveries into verifiable portfolios?          |

At this stage, manually help match narrators where necessary. The agent interface and contract data model should exist, but fully autonomous casting can improve gradually.

## 9. What I would prioritise in the next build

I would add three linked resources to the current MVP:

`Voice Portfolio → Channel Contract → Episode Milestones`

And three high-priority capabilities:

1. Series contract creation. The creator's agent specifies number of episodes, cadence, maximum script length, price, funding and guarantees.
2. Episode delivery and enforcement. Each episode has its own script, deadline, original WAV, deterministic QC, payment and dispute record.
3. Published-work verification. Videos are linked to completed episodes, and the narrator's portfolio gains consented verified credits and current performance metadata.

There's no need for complex ML pricing, character voice synthesis or on-chain smart-contract deployment to prove this. Those can come later.

The most interesting metric might become contracted future narration volume: how much genuinely guaranteed, appropriately funded work has been secured for humans on the platform.

That is far more meaningful than the number of registered voices.

The big idea is that HumanVoiced doesn't merely sell voiceovers. It lets ordinary people acquire a recurring role in an AI-powered content production system—and build a verified career history from every piece of work they complete.

---
*Source: owner-supplied series thesis, saved verbatim 2026-10-08. Image-badge lines omitted; prose, tables, flows, figures and schemas preserved.*
