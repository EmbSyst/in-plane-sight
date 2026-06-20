from umqtt.simple import MQTTClient
import time
import json as JSON
from wlanZugriff import *

# mit Wlan verbinden
connect_to_wlan()

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