# SOURCES — vendor docs imported 2026-10-08

| File | Source | License | Why kept |
|---|---|---|---|
| `qwen3-tts-readme.md` | QwenLM/Qwen3-TTS README (upstream) | Apache-2.0 | VoiceDesign/clone API shapes for demo TTS |
| `qwen3-asr-readme.md` | QwenLM/Qwen3-ASR README (upstream) | Apache-2.0 | ASR + ForcedAligner deploy commands, vLLM paths |

Refresh: re-curl upstream on model upgrades; never edit imported files
(exceptions live in `hv/` + `TECH-SPEC.md`).

## Cloud stack decision (Oct 2026)

| Need | Now (this box, no GPU) | Scale (GPU worker) |
|---|---|---|
| Transcription | Cloudflare Whisper Turbo ($0.000513/min, live) | Qwen3-ASR 0.6B vLLM (2000×rt) or 1.7B accuracy |
| Word timing | stub → Qwen3-ForcedAligner via vLLM pooling | ForcedAligner-0.6B, torch.compile batch |
| Voice description | stub shape | Qwen3.8-Omni-Flash API (DashScope/OpenAI-compatible; NO weights — API-only, do not plan local) |
| Demo TTS | none | Qwen3-TTS 1.7B (6GB VRAM) or Chatterbox |
| Agent harness media | — | Qwen-MM-Plugins (Apache-2.0, hybrid local+API) |

Qwen3.8-Omni-Flash is API-only (no GGUF, no checkpoint). Any "local Omni"
plan is fiction until weights release. Local alternative: Qwen3.8-27B
(vision, no unified audio) + split pipeline (local ASR + local VLM).
