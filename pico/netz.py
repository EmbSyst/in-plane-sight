"""netz.py - WLAN + MQTT. Schreibt empfangene Daten NUR in state.

Passt in die kooperative Hauptschleife:
  init()      einmal beim Boot (Globe steht -> kurzes Blockieren erlaubt)
  service()   pro Runde, NICHT-blockierend (ein check_msg, gedrosselt)

Faellt WLAN/MQTT weg, blockiert das die POV-Schleife NICHT: service() versucht
im Hintergrund (alle MQTT_RETRY_MS) einen Reconnect, ohne sleep. netz rechnet
selbst nichts an der Anzeige - es aktualisiert nur state (Punkte/Modus/Bildwahl).
"""

import time
import json

import network
from umqtt.simple import MQTTClient

import config
import state

# --- Modulzustand ----------------------------------------------------------
_wlan = None
_client = None
_connected = False
_next_check = 0
_next_ping = 0
_next_retry = 0


# --- eingehende Nachrichten -> state ---------------------------------------
def _on_message(topic, raw):
    """MQTT-Callback. Parst JSON und schreibt NUR in state (atomar)."""
    try:
        msg = json.loads(raw)
    except Exception as e:
        print("netz: JSON-Fehler:", e)
        return

    t = msg.get("type")
    if t == "set_points":
        pts = []                                  # neue Liste komplett bauen ...
        for p in msg.get("points", []):
            pts.append({
                "id":    p.get("id"),
                "lat":   p.get("lat", 0.0),
                "lon":   p.get("lon", 0.0),
                "color": p.get("color", [255, 0, 0]),
                "size":  p.get("size", 1),
            })
        state.points = pts                        # ... dann mit EINER Zuweisung aktiv
        print("netz: set_points ->", len(pts))

    elif t == "clear_points":
        state.points = []
        print("netz: clear_points")

    elif t in ("change_display_mode", "change_all_to_color"):
        if "color" in msg:
            state.mode_color = msg.get("color")
        if "value" in msg:                        # README-Variante
            state.mode_color = msg.get("value")
        state.display_mode = msg.get("mode", 1)   # change_all_to_color -> EINE_FARBE (1)
        print("netz: display_mode ->", state.display_mode, state.mode_color)

    elif t == "change_PWM":
        state.rpm_target = msg.get("rpm")
        print("netz: change_PWM rpm ->", state.rpm_target)

    elif t == "set_image":
        state.image_name = msg.get("name")
        print("netz: set_image ->", state.image_name)

    else:
        print("netz: unbekannter type:", t)


# --- Verbindungsaufbau ------------------------------------------------------
def _ensure_wlan_started():
    """WLAN-Interface aktivieren und connect() ausloesen (nicht-blockierend)."""
    global _wlan
    if _wlan is None:
        _wlan = network.WLAN(network.STA_IF)
        _wlan.active(True)
    if not _wlan.isconnected():
        try:
            _wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        except Exception as e:
            print("netz: WLAN connect Fehler:", e)


def _connect_mqtt():
    """MQTT verbinden + Topic abonnieren (kurzes Blockieren)."""
    global _client
    _client = MQTTClient(config.MQTT_CLIENT_ID, config.MQTT_BROKER,
                         port=config.MQTT_PORT, keepalive=config.MQTT_KEEPALIVE_S)
    _client.set_callback(_on_message)
    _client.connect()
    _client.subscribe(config.MQTT_TOPIC)
    print("netz: MQTT verbunden, Topic", config.MQTT_TOPIC)


def _mark_disconnected(now):
    global _connected, _next_retry
    _connected = False
    _next_retry = time.ticks_add(now, config.MQTT_RETRY_MS)
    try:
        _client.disconnect()
    except Exception:
        pass


def _service_reconnect(now):
    """Nicht-blockierender Reconnect, nur alle MQTT_RETRY_MS angestossen."""
    global _connected
    if time.ticks_diff(now, _next_retry) < 0:
        return
    _schedule_retry(now)
    if _wlan is None or not _wlan.isconnected():
        _ensure_wlan_started()                    # WLAN braucht ein paar Sekunden
        return                                    # -> erst beim naechsten Versuch MQTT
    try:
        _connect_mqtt()
        _connected = True
    except Exception as e:
        print("netz: MQTT-Reconnect fehlgeschlagen:", e)


def _schedule_retry(now):
    global _next_retry
    _next_retry = time.ticks_add(now, config.MQTT_RETRY_MS)


# --- oeffentliche Schnittstelle --------------------------------------------
def init():
    """Beim Boot aufrufen. Wartet kurz auf WLAN (Globe steht). Nie fatal."""
    global _connected
    _ensure_wlan_started()
    t = config.WIFI_TIMEOUT_S
    while _wlan is not None and not _wlan.isconnected() and t > 0:
        print("netz: warte auf WLAN...")
        time.sleep(1)
        t -= 1
    if _wlan is not None and _wlan.isconnected():
        print("netz: WLAN ok", _wlan.ifconfig()[0])
        try:
            _connect_mqtt()
            _connected = True
        except Exception as e:
            print("netz: MQTT-Connect fehlgeschlagen:", e)
            _connected = False
    else:
        print("netz: WLAN fehlgeschlagen - service() versucht es weiter")
        _connected = False


def service():
    """Pro Hauptschleifen-Runde aufrufen. Nicht-blockierend."""
    global _next_check, _next_ping
    now = time.ticks_ms()

    if not _connected:
        _service_reconnect(now)
        return

    # eingehende Nachrichten pruefen (gedrosselt, check_msg ist nicht-blockierend)
    if time.ticks_diff(now, _next_check) >= 0:
        _next_check = time.ticks_add(now, config.MQTT_CHECK_MS)
        try:
            _client.check_msg()
        except Exception as e:
            print("netz: Verbindung verloren (check):", e)
            _mark_disconnected(now)
            return

    # Keepalive-Ping, damit der Broker uns nicht kickt
    if time.ticks_diff(now, _next_ping) >= 0:
        _next_ping = time.ticks_add(now, config.MQTT_PING_MS)
        try:
            _client.ping()
        except Exception as e:
            print("netz: Verbindung verloren (ping):", e)
            _mark_disconnected(now)
