#!/usr/bin/env bash

# Start script for the RasPi control app (exports env vars and runs uvicorn).
# Usage:
#   ./start.sh
#   DUMP1090_FILE_PATH=/tmp/aircraft.json ./start.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

export DUMP1090_FILE_PATH="${DUMP1090_FILE_PATH:-/tmp/aircraft.json}"
export DUMP1090_POLL_INTERVAL_S="${DUMP1090_POLL_INTERVAL_S:-1.0}"
export DUMP1090_BACKOFF_INITIAL_S="${DUMP1090_BACKOFF_INITIAL_S:-${DUMP1090_POLL_INTERVAL_S}}"
export DUMP1090_BACKOFF_MAX_S="${DUMP1090_BACKOFF_MAX_S:-15.0}"
export DUMP1090_BACKOFF_MULTIPLIER="${DUMP1090_BACKOFF_MULTIPLIER:-2.0}"

export GLOBE_MODE="${GLOBE_MODE:-udp}"
export GLOBE_HTTP_URL="${GLOBE_HTTP_URL:-http://192.168.4.1/aircraft}"
export GLOBE_HTTP_TIMEOUT_S="${GLOBE_HTTP_TIMEOUT_S:-1.0}"
export GLOBE_UDP_HOST="${GLOBE_UDP_HOST:-10.42.0.1}"
export GLOBE_UDP_PORT="${GLOBE_UDP_PORT:-5005}"

# Put in position of the system to show the correct distance to the aircrafts
export SYSTEM_LAT="${SYSTEM_LAT:-48.5756}"
export SYSTEM_LON="${SYSTEM_LON:-9.739}"

export PLANESPOTTERS_BASE_URL="${PLANESPOTTERS_BASE_URL:-https://api.planespotters.net/pub/photos/hex}"
export PLANESPOTTERS_TIMEOUT_S="${PLANESPOTTERS_TIMEOUT_S:-2.0}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-0}"

START_DUMP1090="${START_DUMP1090:-1}"
DUMP1090_CMD="${DUMP1090_CMD:-}"

if [[ "${START_DUMP1090}" == "1" ]]; then
  if [[ -z "${DUMP1090_CMD}" ]]; then
    DUMP1090_CMD="dump1090-fa"
  fi

  bash -lc "source ~/.bashrc 2>/dev/null || true; shopt -s expand_aliases; ${DUMP1090_CMD}" &
  DUMP1090_PID="$!"
  trap 'kill "${DUMP1090_PID}" 2>/dev/null || true' EXIT INT TERM
fi

if [[ "${RELOAD}" == "1" ]]; then
  if [[ "${START_DUMP1090}" == "1" ]]; then
    uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" --reload "$@"
  else
    exec uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" --reload "$@"
  fi
else
  if [[ "${START_DUMP1090}" == "1" ]]; then
    uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" "$@"
  else
    exec uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" "$@"
  fi
fi
