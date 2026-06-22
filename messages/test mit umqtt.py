from umqtt.simple import MQTTClient
import time
import json as JSON
from wlanZugriff import *

# mit Wlan verbinden
# connect_to_wlan()

# Verschiedene Display-Modes
DISPLAY_MODE_LIST = ["AN", "EINE_FARBE", "FLUGZEUG", "REGENBOGEN"]
display_mode = DISPLAY_MODE_LIST[0]

# MQTT broker (public test broker)
BROKER = "test.mosquitto.org"

CLIENT_ID = "micropython_test_client"
TOPIC = b"in-plane-sight"

def callback(topic, msg):
    print("Message received!")
    print("Topic:", TOPIC)
    print("Message:", msg)
    # msg = json.dumps(msg)
    try:
        msg = JSON.loads(msg)

        if msg["type"] == "change_display_mode":
                # beinhaltet mode einen gültigen Anzeige-Modus? <>
                # 0 = aus, keine Anzeige
                # 1 = fülle den gesamten Globus mit der aktuell gesetzten Farbe
                # 2 = Färbe den Globus mit $color ein und zeige einen roten Punkt für das Flugzeug
                # 3 = RGB Regenbogen-Farbspiel
                if msg["mode"] >= 0 and msg["mode"] <= 3:
                    display_mode = DISPLAY_MODE_LIST[msg["mode"]];
                    print("hier wird der Anzeige-Modus des HoloGlobe gesetzt auf Modus #", msg["mode"])
                else:
                    print("Fehlerhafter Modus übertrange von change_display_mode")
        elif msg["type"] == "change_PWM":
                if msg["mode"] >= 0 and msg["mode"] <= 1:
                    print("hier wird die Motorsteuerung des Picos angesprochen im Modus: ", msg["mode"])
                    print("die Parameter lauten: ", msg["rpm"])
        elif msg["type"] == "change_plane_position":
               print("hier wird die Flugzeug-Position gesetzt auf x:", msg["x"], " y:", msg["y"])
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