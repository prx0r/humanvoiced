"""Delivery packs: the agent-native production bundle.

A pack references the immutable original plus derived assets, each
content-addressed, with a manifest an editing agent can ingest without
opening a ZIP: script hash, rights, loudness, provenance, processing
settings and versions. Reproducible from (original sha, settings, versions).
"""
from __future__ import annotations

from hv import processing as _p
from hv.util import utcnow

MANIFEST_VERSION = "pack-manifest-0.1"


def build_manifest(contract: dict, original_sha: str, assets: dict,
                   transcript: str, segments: list[dict],
                   processing_fee_usd: float, tier: str,
                   preset: dict | None = None,
                   integrity: dict | None = None) -> dict:
    files = {}
    for name, path in assets.items():
        if not isinstance(path, str):
            continue
        if not __import__("os").path.isfile(path):
            continue  # measured stats / chain descriptions, not deliverables
        files[name] = {"sha256": _p.sha_file(path),
                       "bytes": __import__("os").path.getsize(path)}
    return {"manifest_version": MANIFEST_VERSION,
            "contract_id": contract["contract_id"],
            "narrator_id": contract.get("narrator_id"),
            "script_sha256": contract.get("script_sha256"),
            "original_sha256": original_sha,
            "tier": tier,
            "preset": preset["name"] if preset else None,
            "files": files,
            "loudness": assets.get("measured") or {},
            "transcript_words": len(transcript.split()),
            "segments": len(segments),
            "integrity": integrity or {},
            "rights": {"commercial_usage": contract.get("commercial_usage", "online_video"),
                       "voice_cloning_allowed": False,
                       "enhancement_consent": "processing_only_no_cloning"},
            "processing_fee_usd": processing_fee_usd,
            "narrator_payout_usd": contract.get("payout_usd"),
            "service_fee_usd": contract.get("service_fee_usd", 0.0),
            "ffmpeg": _p.ffmpeg_version(),
            "built_at": utcnow()}
