#!/usr/bin/env bash

# Start script for the RasPi control app (exports env vars and runs uvicorn).
# Usage:
#   ./start.sh
#   DUMP1090_URL=... GLOBE_MODE=udp ./start.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

export DUMP1090_URL="${DUMP1090_URL:-http://127.0.0.1:8080/data/aircraft.json}"
export DUMP1090_POLL_INTERVAL_S="${DUMP1090_POLL_INTERVAL_S:-1.0}"
export DUMP1090_BACKOFF_INITIAL_S="${DUMP1090_BACKOFF_INITIAL_S:-${DUMP1090_POLL_INTERVAL_S}}"
export DUMP1090_BACKOFF_MAX_S="${DUMP1090_BACKOFF_MAX_S:-15.0}"
export DUMP1090_BACKOFF_MULTIPLIER="${DUMP1090_BACKOFF_MULTIPLIER:-2.0}"

export GLOBE_MODE="${GLOBE_MODE:-disabled}"
export GLOBE_HTTP_URL="${GLOBE_HTTP_URL:-http://192.168.4.1/aircraft}"
export GLOBE_HTTP_TIMEOUT_S="${GLOBE_HTTP_TIMEOUT_S:-1.0}"
export GLOBE_UDP_HOST="${GLOBE_UDP_HOST:-192.168.4.1}"
export GLOBE_UDP_PORT="${GLOBE_UDP_PORT:-4210}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-0}"

if [[ "${RELOAD}" == "1" ]]; then
  exec uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" --reload "$@"
else
  exec uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" "$@"
fi

