# Qwen 3.8 Alibaba stack — full map (Oct 2026)

## Models (nine SKUs, three weight sets)

| SKU | Params | Context | In → out | Weights? | License | $/M in/out |
|---|---|---|---|---|---|---|
| qwen3.8-max (→0902) | 2.4T/95B | 1M | T+I+V→T | NO (2.4T-A95B text-only separate) | closed | 2/6 |
| qwen3.8-max-0902 | pinned 0902 | 1M | T+I+V→T | no | closed | 2/6 |
| qwen3.8-max-prime | max, fast tier | 1M | T+I+V→T | no | closed | 4/12 |
| qwen3.8-2.4T-A95B | 2.4T/95B | 262K→1M | T→T | YES (+FP8) | Max License ($50M floor) | 2/6 hosted |
| qwen3.8-flash | Flash-Next+prod | 1M | T+I+V→T | no | closed | 0.15/0.47 |
| qwen3.8-flash-next | 125B/6B+51B ngram | 262K→1M | T+I+V→T | YES (+FP8) | Community 1.0 (MaaS needs licence, NO floor) | — |
| qwen3.8-27b | 27B dense | 262K→1M | T+I+V→T | YES (+FP8) | Apache-2.0 | 0.50/3.00 |
| qwen3.8-omni-flash | undisclosed | 1M | T+I+A+V→T | NO | closed | 0.15/0.47 |
| omni-flash-realtime | — | — | +audio out | NO | closed | — |

Audio siblings: Qwen3-ASR 0.6B/1.7B + ForcedAligner 0.6B (open, Apache —
see qwen3-asr-readme.md), Qwen3-TTS 0.6B/1.7B (open, Apache), Qwen3-Omni
30B-A3B (vLLM-Omni staged serving).

## Platform (Alibaba Cloud Model Studio / DashScope)

- API: OpenAI-compatible (`compatible-mode/v1`), dashscope SDKs.
- Regions: Beijing + Singapore/Intl (keys NOT interchangeable).
- Billing: pay-as-you-go, Token Plan (personal/team), Coding Plan (fixed/mo).
  Qwen OAuth free tier dead since 2026-04-15.
- Plugins: official (code interpreter, Quark search — free limited time),
  third-party, custom. Model Studio Assistant API.
- Context caching: implicit + explicit (Flash $0.016/M read).

## Harnesses (open)

- Qwen Code (terminal agent, ACP, skills/subagents, VSCode/JetBrains).
- Qwen-MM-Plugins (Apache): skill + MCP per capability (core/api/search/
  video-memory/video-edit/blender/freecad), `uvx`-launched, `DASHSCOPE_API_KEY`
  for media ops. Works with Claude Code/Codex/Gemini CLI/OpenClaw/pi/opencode.
- Qwen-Live-Harness (open): realtime AV agents, task delegation to
  background harnesses, memory. Needs DashScope key + internet.

## Our mapping (HumanVoiced)

| Need | Pick | Why |
|---|---|---|
| Agent reasoning (API) | qwen3.8-flash ($0.15/M) | volume economics; Max-0902 only where measured failing |
| Voice description | qwen3.8-omni-flash API | audio in; no local alternative exists |
| Local/self-host | qwen3.8-27b (Apache-2.0) | only unrestricted commercial weights; laptop-quantizable |
| ASR/align (GPU box) | Qwen3-ASR + ForcedAligner, vLLM | day-0 support, torch.compile batch |
| Demo TTS (GPU box) | Qwen3-TTS 1.7B | Apache, 3-sec clone, NL direction |
| Media tools in harnesses | Qwen-MM-Plugins api profile | ffmpeg present; needs DASHSCOPE_API_KEY (not yet sealed) |
| AVOID | Flash-Next self-host for product | Community 1.0 MaaS clause triggers at ANY revenue |

Next keys to seal: `DASHSCOPE_API_KEY` (Singapore region) when spend approved.
