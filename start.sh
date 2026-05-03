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

// Put in position of the system on the map
export SYSTEM_LAT=49.121479
export SYSTEM_LON=9.211960

export PLANESPOTTERS_BASE_URL="${PLANESPOTTERS_BASE_URL:-https://api.planespotters.net/pub/photos/hex}"
export PLANESPOTTERS_TIMEOUT_S="${PLANESPOTTERS_TIMEOUT_S:-2.0}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-0}"

START_DUMP1090="${START_DUMP1090:-0}"
DUMP1090_CMD="${DUMP1090_CMD:-}"

if [[ "${START_DUMP1090}" == "1" ]]; then
  if [[ -z "${DUMP1090_CMD}" ]]; then
    DUMP1090_CMD="/home/pi/Projekt/dump1090-fa/dump1090 --device-type hackrf --write-json /tmp --interactive-show-distance"
    if [[ -n "${SYSTEM_LAT:-}" && -n "${SYSTEM_LON:-}" ]]; then
      DUMP1090_CMD="${DUMP1090_CMD} --lat ${SYSTEM_LAT} --lon ${SYSTEM_LON}"
    fi
  fi

  bash -lc "${DUMP1090_CMD}" &
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
