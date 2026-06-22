import network
import time

SSID = "embedded"
PASSWORD = "c384c8c3"
TIMEOUT = 100

def connect_to_wlan():
    timeout = TIMEOUT
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Verbinde mit WLAN...")
        wlan.connect(SSID, PASSWORD)

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
