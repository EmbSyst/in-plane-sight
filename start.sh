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

export GLOBE_MODE="${GLOBE_MODE:-mqtt}"
export GLOBE_MQTT_HOST="${GLOBE_MQTT_HOST:-test.mosquitto.org}"
export GLOBE_MQTT_PORT="${GLOBE_MQTT_PORT:-1883}"
export GLOBE_MQTT_TOPIC="${GLOBE_MQTT_TOPIC:-in-plane-sight}"
export GLOBE_MQTT_QOS="${GLOBE_MQTT_QOS:-0}"
export GLOBE_MQTT_RETAIN="${GLOBE_MQTT_RETAIN:-0}"
export GLOBE_DUMMY_X="${GLOBE_DUMMY_X:-0}"
export GLOBE_DUMMY_Y="${GLOBE_DUMMY_Y:-0}"

# Hier die aktuelle Position des Systems eintragen zur korrekten Berechnung der Distanz. 
# Aktuelle Koordinaten entsprechen Hochschule Heilbronn, Techcampus
export SYSTEM_LAT="${SYSTEM_LAT:-49.12194}"
export SYSTEM_LON="${SYSTEM_LON:-9.21111}"

export PLANESPOTTERS_BASE_URL="${PLANESPOTTERS_BASE_URL:-https://api.planespotters.net/pub/photos/hex}"
export PLANESPOTTERS_TIMEOUT_S="${PLANESPOTTERS_TIMEOUT_S:-2.0}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-0}"

if [[ "${RELOAD}" == "1" ]]; then
  exec uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" --reload "$@"
else
  exec uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" "$@"
fi
