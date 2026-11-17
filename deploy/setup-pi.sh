#!/usr/bin/env bash
# Richtet einen frischen Raspberry Pi 5 (Ubuntu 24.04) komplett für In Plane Sight ein:
# dump1090-fa (HackRF), Backend-Service, Autologin + Sway-Kiosk.
# Aufruf als normaler Benutzer (NICHT mit sudo) aus dem geklonten Repo:
#   ./deploy/setup-pi.sh
# Idempotent: kann gefahrlos erneut ausgeführt werden.
set -euo pipefail

[[ $EUID -ne 0 ]] || { echo "Bitte ohne sudo starten (sudo wird intern genutzt)."; exit 1; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="$(id -un)"
DUMP1090_DIR="${DUMP1090_DIR:-$HOME/Projekt/dump1090-fa}"
SYSTEM_LAT="${SYSTEM_LAT:-49.12194}"
SYSTEM_LON="${SYSTEM_LON:-9.21111}"

echo "==> Pakete installieren"
sudo apt-get update
sudo apt-get install -y git python3-venv build-essential pkg-config \
  libncurses-dev libhackrf-dev hackrf sway
snap list chromium >/dev/null 2>&1 || sudo snap install chromium
# HackRF-USB-Zugriff ohne root (udev-Regel aus dem hackrf-Paket nutzt plugdev)
sudo usermod -aG plugdev "$RUN_USER"

echo "==> dump1090-fa bauen (HackRF)"
if [[ ! -d "$DUMP1090_DIR/.git" ]]; then
  mkdir -p "$(dirname "$DUMP1090_DIR")"
  git clone https://github.com/flightaware/dump1090 "$DUMP1090_DIR"
fi
make -C "$DUMP1090_DIR" RTLSDR=no BLADERF=no LIMESDR=no SOAPYSDR=no HACKRF=yes

echo "==> Python-Umgebung fürs Backend"
[[ -d "$REPO_DIR/.venv" ]] || python3 -m venv "$REPO_DIR/.venv"
"$REPO_DIR/.venv/bin/pip" install -r "$REPO_DIR/backend/requirements.txt"
chmod +x "$REPO_DIR/start.sh"

echo "==> systemd-Services"
sudo tee /etc/systemd/system/dump1090.service >/dev/null <<EOF
[Unit]
Description=dump1090-fa ADS-B Decoder (HackRF) -> /tmp/aircraft.json
After=network.target

[Service]
User=$RUN_USER
SupplementaryGroups=plugdev
ExecStart=$DUMP1090_DIR/dump1090 --device-type hackrf --write-json /tmp --lat $SYSTEM_LAT --lon $SYSTEM_LON --quiet
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/backend.service >/dev/null <<EOF
[Unit]
Description=In Plane Sight Backend (FastAPI)
Wants=network-online.target
After=network-online.target dump1090.service

[Service]
User=$RUN_USER
WorkingDirectory=$REPO_DIR
Environment=SYSTEM_LAT=$SYSTEM_LAT
Environment=SYSTEM_LON=$SYSTEM_LON
ExecStart=$REPO_DIR/start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now dump1090.service backend.service

echo "==> Autologin auf tty1 + Kiosk-Boot"
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/override.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $RUN_USER --noclear %I \$TERM
EOF
sudo systemctl set-default multi-user.target

echo "==> Sway-Konfiguration"
mkdir -p "$HOME/.config/sway"
cat > "$HOME/.config/sway/config" <<'EOF'
# Bildschirm und Touch-Matrix um 180 Grad drehen
output * transform 180
input type:touch {
    calibration_matrix -1 0 1 0 -1 1
}

# Hintergrund (blau) und Kiosk-Optik (keine Ränder)
output * bg #0000AA solid_color
default_border none
hide_edge_borders both

# Alt+F4 beendet Sway -> Textkonsole (Wartung)
bindsym Mod1+F4 exit

# Start des Frontends
exec bash -c "sleep 10 && /snap/bin/chromium --enable-features=UseOzonePlatform --ozone-platform=wayland --kiosk --noerrdialogs --disable-infobars http://localhost:8000"
EOF

if ! grep -q 'exec sway' "$HOME/.bash_profile" 2>/dev/null; then
  cat >> "$HOME/.bash_profile" <<'EOF'
[[ -f ~/.bashrc ]] && . ~/.bashrc
if [[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]]; then
    exec sway
fi
EOF
fi

echo
echo "Fertig. Prüfen mit:"
echo "  systemctl status dump1090.service backend.service"
echo "  curl -s localhost:8000/api/aircraft | head"
echo "Danach: sudo reboot  (startet in den Kiosk-Modus)"
