#!/bin/bash
# hv-serve.sh — boot the HumanVoiced API with secrets from vault (never files).
set -e
cd /root/humanvoiced
for k in GOOGLE_CLIENT_ID_HV GOOGLE_CLIENT_SECRET_HV; do
  v=$(agent-vault vault credential get "$k" --vault oracle 2>/dev/null | tail -n 1)
  [ -n "$v" ] && export "$k=$v"
done
# FAL_KEY (hosted cleaning) loads from .env when the owner has stored it.
# Availability only: no fal call is ever made unless a clean-tier pack or
# benchmark is explicitly requested.
if [ -f .env ]; then
  v=$(grep -E "^FAL_KEY=" .env | cut -d= -f2-)
  [ -n "$v" ] && export "FAL_KEY=$v"
fi
export PUBLIC_BASE="${PUBLIC_BASE:-https://api.humanvoiced.com}"
export HV_DB="${HV_DB:-/root/humanvoiced/data/hv.db}"
export HV_EVENTS_DB="${HV_EVENTS_DB:-/root/humanvoiced/data/hv-events.db}"
export HV_SESSIONS_DB="${HV_SESSIONS_DB:-/root/humanvoiced/data/hv-sessions.db}"
export HV_AUDIO_DIR="${HV_AUDIO_DIR:-/root/humanvoiced/data/audio/raw}"
mkdir -p data/audio/raw
exec python3 -m uvicorn api.app:app --host 127.0.0.1 --port 8801
