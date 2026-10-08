# Qwen/Alibaba API map (Oct 2026 — Intl/Singapore region unless noted)

Keys: `DASHSCOPE_API_KEY`, region-locked (Beijing ≠ Singapore). OpenAI-compatible
base where noted. All needs-DashScope-key items wait on spend approval.

## Realtime AV (our live-voice path)

- Model: `qwen3.8-omni-flash-realtime` (text+audio out, 113-lang ASR incl.
  `qwen3-asr-flash-realtime`, 36-lang TTS, voices e.g. Cherry/longalnglingxin,
  smooth_output, function calling, **remote MCP tools**, multichannel 1/2/4).
- WS: `wss://{wsid}.{region}.maas.aliyuncs.com/api-ws/v1/realtime?model=…`
  (`maas.qwencloudapi.com` Intl). PCM in 16k mono s16le; out 24k.
  VAD: server_vad | semantic_vad | manual. Events: session.*, input_audio_*,
  response.audio(.transcript).delta/done.
- WebRTC: SDP exchange POST, RTP media, DataChannel text, server-VAD only,
  echo-cancel/noise-reduction, allowlist-gated endpoint — needs AppServer proxy.
- Python SDK: `dashscope.audio.qwen_omni` (callbacks), AOQ also supported.
- Use for: live narrator auditions, spoken availability checks, voice support.

## Generation (studio backfill)

- Image: `qwen-image-3.0-pro` (prompt rewrite, natural-text render), `wan2.7-image-pro`
  (4K, 10 refs, sequential sets, thinking_mode). Sync + async.
- Video: `wan3.0-video` (30s, 4-modal refs, character consistency),
  `wan3.0-video-prime` (fast), `wan2.7-i2v/r2v/videoedit`, `vidu/*`
  (reference blend). $0.05–0.20/sec.
- TTS side: realtime voices above; batch TTS via Qwen3-TTS self-host.

## Language (dubbing pipeline)

- `qwen-mt-image-2.0`: 55-lang image text translation, layout-preserving,
  terminology/sensitive-word controls, domainHint (dubbing glossaries!).
- Realtime speech translation: `qwen3.5-livetranslate-flash-realtime` family.
- Text MT: standard Qwen chat models with translation prompts.

## Retrieval (search/discovery)

- `qwen3.7-text-embedding` (MTEB +20%, dims 256–2560), `qwen3-rerank`,
  `tongyi-embedding-vision-plus`. For approved-description semantic search
  (pgvector later; 30 voices don't need it yet).

## Agent platform

- Model Studio plugins (code interpreter, Quark search, custom), Assistant API.
- Qwen Code CLI + ACP; Qwen-MM-Plugins capabilities (core/api/search/
  video-memory/video-edit/blender/freecad) with `DASHSCOPE_API_KEY`.
- Qwen-Live-Harness: realtime AV agents, background delegation, memory
  (macOS now, Win/Linux coming; needs DashScope key + internet).

## Our mapping

| Need | API | Status |
|---|---|---|
| Live audition calls | omni-flash-realtime WS | needs key |
| Voice description at scale | omni-flash batch (text out) | needs key |
| Thumbnails/covers | qwen-image-3.0-pro | needs key |
| Dub visual assets | wan3.0-video / vidu refs | needs key |
| Subtitle translation | qwen-mt-image-2.0 (images) + chat MT | needs key |
| Description search vectors | qwen3.7-text-embedding | later |
| Everything above without keys | Cloudflare Whisper + local stubs | LIVE now |

Single blocker for all of it: one Singapore `DASHSCOPE_API_KEY`.
