# The gold (Oct 2026): what each pipe is actually for

Verified live: OpenRouter key works (467 models).

## OpenRouter — reasoning + Omni text-side, NOT audio IO

Has all six Qwen3.8 text models (Max-Prime, Omni-Flash, Max-0902, Flash,
27B, 2.4T) + a free nemotron omni. Has NO Whisper/transcription/TTS
models — only `openai/gpt-audio(-mini)`. So: use OpenRouter for agent
reasoning (Flash $0.15/M), matching explanations, dispute drafting —
never for transcription.

## fal.ai — the whole audio menu, one SDK pattern, needs FAL_KEY

Whisper STT · MiniMax Speech-02-HD/Turbo + voice clone ($1.50/clone) ·
**Qwen3-TTS custom-voice + clone-voice endpoints** · Dia dialogue TTS
(multi-speaker `[S1]/[S2]`) · Chatterbox · Tada · Lux 48kHz · IndexTTS.
Same `fal.subscribe(endpoint, {input})` shape everywhere; `FAL_KEY` env.
No key in vault yet — single blocker.

## The stack that falls out

| Job | Pick | Why |
|---|---|---|
| Transcription | Cloudflare Whisper Turbo (live) | $0.0005/min, no key needed beyond CF |
| Voice description | OpenRouter `qwen/qwen3.8-omni-flash` | live key, text I/O today |
| Demo/reference TTS + voice design | fal Qwen3-TTS endpoints | zero GPU, same SDK as everything else |
| Dialogue previews | fal Dia | multi-speaker sides for casting |
| Agent reasoning | OpenRouter Flash / Max-0902 | measured escalation only |
| Fallback STT | fal Whisper | same pattern, no new integration |

Missing keys: `FAL_KEY`, `DASHSCOPE_API_KEY`. Everything else runs now.
