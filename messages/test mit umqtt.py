from umqtt.simple import MQTTClient
import time
import json as JSON

import network

TIMEOUT = 100

SSID = "embedded"
PASSWORD = "c384c8c3"

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

if not wlan.isconnected():
    print("Verbinde mit WLAN...")
    wlan.connect(SSID, PASSWORD)

    timeout = TIMEOUT
    while not wlan.isconnected() and timeout > 0:
        print("Warte auf Verbindung...")
        time.sleep(1)
        timeout -= 1

if wlan.isconnected():
    print("Verbunden!")
    print("Netzwerk-Konfiguration:", wlan.ifconfig())
else:
    print("Verbindung fehlgeschlagen")
    sys.exit(-1)
    
# MQTT broker (public test broker)
BROKER = "test.mosquitto.org"

CLIENT_ID = "micropython_test_client"
TOPIC = b"hello/world"

def callback(topic, msg):
    print("Message received!")
    print("Topic:", TOPIC)
    print("Message:", msg)
    # msg = json.dumps(msg)
    try:
        msg = JSON.loads(msg)

        if msg["type"] == "change_all_to_color":
                print("hier wird der gesamte LED-Streifen auf Wert", msg["value"], "gesetzt")
        elif msg["type"] == "change_display_mode":
                print("hier wird der Anzeige Modus des Globe festgelegt", msg["value"])
                # 0 = aus, keine Anzeige
                # 1 = fülle den gesamten Globus mit der aktuell gesetzten Farbe
        else:
                print("Nachrichtenformat nicht erkannt")
    except Exception as e:
        print("Fehler beim JSON-Umwandeln: ", e)
    
client = MQTTClient("micropython_client", BROKER)

client.set_callback(callback)
client.connect()

client.subscribe(TOPIC)

print("Subscribed to:", TOPIC)

while True:
    client.check_msg()  # non-blocking check
    time.sleep(1)