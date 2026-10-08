"""Unified provider map: audio engine, translation, analysis.

Chains resolve first-available credentials; every call degrades to the
local stub rather than failing. Spend only happens on explicit provider
selection with keys present.
"""
from __future__ import annotations

import os

PROVIDERS = {
    "transcribe": [
        ("cf-whisper-turbo", "Cloudflare Workers AI, $0.000513/min, live, no extra key"),
        ("qwen3-asr", "DashScope/self-host GPU box, needs DASHSCOPE_API_KEY or CUDA"),
        ("fal-whisper", "fal.ai, needs FAL_KEY"),
    ],
    "describe": [
        ("dashscope-omni-flash", "qwen3.8-omni-flash, needs DASHSCOPE_API_KEY + console activation"),
        ("openrouter-omni-flash", "qwen/qwen3.8-omni-flash via OpenRouter, needs OPENROUTER_API_KEY"),
        ("stub", "controlled-JSON shape, always available"),
    ],
    "translate": [
        ("qwen-mt", "DashScope qwen-mt-*/image-2.0, terminology controls, needs key"),
        ("chat-mt", "any chat model with glossary prompt, no extra key beyond chat"),
    ],
    "synthesize": [
        ("fal-qwen3tts", "Qwen3-TTS custom/clone endpoints, needs FAL_KEY"),
        ("fal-dia", "multi-speaker dialogue sides, needs FAL_KEY"),
        ("selfhost-qwen3tts", "1.7B, 6GB VRAM, Apache-2.0"),
    ],
    "realtime": [
        ("dashscope-omni-realtime", "WS/WebRTC, 16k-in/24k-out, VAD, MCP tools, needs key+activation"),
    ],
    "reason": [
        ("dashscope-flash", "qwen3.8-flash $0.15/M, needs key+activation"),
        ("openrouter-flash", "same via OpenRouter, needs OPENROUTER_API_KEY"),
        ("local-27b", "Qwen3.8-27B Apache-2.0, own hardware"),
    ],
}


def available() -> dict:
    """What runs right now, no guessing."""
    has_ds = bool(os.environ.get("DASHSCOPE_API_KEY"))
    has_or = bool(os.environ.get("OPENROUTER_API_KEY"))
    has_fal = bool(os.environ.get("FAL_KEY"))
    return {"transcribe": "cf-whisper-turbo",
            "describe": "dashscope-omni-flash" if has_ds else ("openrouter-omni-flash" if has_or else "stub"),
            "translate": "dashscope-qwen-mt" if has_ds else "chat-mt",
            "synthesize": "fal-qwen3tts" if has_fal else "none (needs FAL_KEY)",
            "realtime": "dashscope-omni-realtime" if has_ds else "none (needs DASHSCOPE_API_KEY)",
            "reason": "dashscope-flash" if has_ds else ("openrouter-flash" if has_or else "local-27b"),
            "notes": "DashScope models also need console activation (Model Studio service enablement)"}
