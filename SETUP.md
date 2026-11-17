# In Plane Sight – Hardware & System Setup

Dieses Dokument beschreibt die physische Einrichtung für das "In Plane Sight"-Projekt. Es umfasst den Aufbau des Kiosk-Displays am Raspberry Pi 5 sowie die Konfiguration und Nutzung des Holo-Globes (Raspberry Pi Pico).

---

## 1. Hardware-Verkabelung

### Raspberry Pi (Main Controller)
* Der Raspberry Pi 5 ist im Touchgehäuse verbaut und braucht eine Stromversorgung über das weiße Netzkabel von Raspberry. Dieses muss am USB-C-Port des Raspberry Pi 5 angeschlossen werden.
* Der HackRF-One muss über ein Micro-USB auf USB-Kabel an einen der freien USB-Ports am Raspberry Pi 5 angeschlossen werden.
* Die Antenne muss zusätzlich am Antennen-Port des HackRF-One angeschlossen werden.

### Holo-Globe (Pico Controller)
* Das Kaltgeräte-Kabel muss am Sockel des Holo-Globes angeschlossen werden. Danach kann der Netz-Schalter am Sockel des Holo-Globes betätigt werden.
* Der Raspberry Pi Pico 2W braucht zudem eine zusätzliche 5V Stromversorgung über dessen Micro-USB-Port. Diese kann über ein 5V USB-Netzteil oder über einen Laptop erfolgen.

---

## 2. Betriebssystem des Raspberry Pi 5

Da das System ein DSI-Display nutzt und Ubuntu 24.04 zum Einsatz kommt, verwenden wir **Sway** als ressourcenschonenden, ausbruchsicheren Kiosk-Fenstermanager, damit während der Nutzung nicht aus dem Frontent "ausgebrochen" werden kann.

Das System startet nach dem Einstecken der Stromversorgung automatisch, loggt sich automatisch ein (Benutzername `hologlobe`, Passwort `hologlobe`) und aktiviert die Hintergrundprozesse des Raspberry Pi 5. 

Vor dem ersten Start sollte über den in Punkt 5 beschriebenen Prozess aus dem Kiosk-Modus ausgebrochen werden und im Repo des Projekts einmal der aktuelle Status des Projekts zur Sicherheit gepullt werden.

```bash
cd /home/hologlobe/Projekt/backend/in-plane-sight
git pull 
```


### 2.1 Neuinstallation (z.B. nach SD-Karten-Defekt)

1. Mit dem Raspberry Pi Imager **Ubuntu Desktop 24.04 LTS (64-bit)** auf eine neue SD-Karte flashen, booten, Benutzer `hologlobe` (Passwort `hologlobe`) anlegen und WLAN verbinden.
2. Repo klonen und Setup-Skript ausführen (als `hologlobe`, **ohne** sudo):

```bash
git clone https://github.com/EmbSyst/in-plane-sight.git /home/hologlobe/Projekt/backend/in-plane-sight
cd /home/hologlobe/Projekt/backend/in-plane-sight
./deploy/setup-pi.sh            # optional: SYSTEM_LAT=... SYSTEM_LON=... ./deploy/setup-pi.sh
sudo reboot
```

Das Skript installiert und richtet ein: `dump1090-fa` mit HackRF-Unterstützung (`dump1090.service`, schreibt `/tmp/aircraft.json`), das Backend (`backend.service`), den Autologin auf tty1 sowie Sway + Chromium im Kiosk-Modus.

## 3. WLAN Konfiguration

Der Raspberry Pi 5 spannt mit seinem **eingebauten WLAN** einen eigenen Hotspot auf (`in-plane-sight` / `planespotter`, Pi = `10.42.0.1`) und betreibt darauf den **lokalen MQTT-Broker** (Mosquitto). Der Pico verbindet sich nur mit diesem Hotspot – es muss kein fremdes Netzwerk konfiguriert werden.

Für Internet (Flugzeugfotos, `git pull`) nutzt der Pi einen **USB-WLAN-Stick**. Ohne Internet läuft alles außer den Fotos weiter (dann Platzhalterbild).

Hotspot und Broker richtet `deploy/setup-pi.sh` ein. Wichtig: Den USB-Stick **vor** dem Skript einstecken und damit ins Internet verbinden, denn das eingebaute WLAN wird vom Skript zum Hotspot umgestellt (eine bestehende WLAN-Verbindung darauf bricht ab).

### 3.1 WLAN Konfiguration des Raspberry Pi 5

Um die Konfiguration des WLANs im Raspberry Pi 5 zu ändern, ist folgender Weg z.B. möglich: 
1. Zuerst wie in Punkt 5 beschrieben aus dem Kiosk-Modus ausbrechen.
2. Danach ist die Konfiguration über das Terminal wie folgt möglich:


WLAN-Netzwerke in der Nähe anzeigen:

```bash
nmcli device wifi list
```
Mit einem WLAN-Netzwerk verbinden – immer über den **USB-Stick** (Interface-Name aus `nmcli device`, meist `wlx…`), nicht über das eingebaute WLAN (das ist der Hotspot):

```bash
sudo nmcli device wifi connect MEINE-SSID password MEIN-PASSWORT ifname <usb-stick-interface>
```
Überprüfen ob die Verbindung erfolgreich war:

```bash
nmcli connection show --active
```

Auch ist es möglich, die Konfiguration über das normale, graphische Interface des Raspberry Pi 5 zu ändern. Hierzu sind folgende Schritte notwendig:

1. Ausbrechen aus dem Kioskmodus (siehe Punkt 5).
2. Umstellen auf graphische Benutzeroberfläche mit folgendem Befehl:

```bash
sudo systemctl set-default graphical.target
```
Danach rebooten:

```bash
sudo reboot
```
Danach ist die Konfiguration über das normale, graphische Interface des Raspberry Pi 5 möglich.

Umstellen auf den Kiosk-Modus mit folgendem Befehl:

```bash
sudo systemctl set-default multi-user.target
sudo reboot
```


### 3.2 WLAN Konfiguration des Raspberry Pi Pico 2W

Um die WLAN-Konfiguration des Raspberry Pi Pico 2W zu ändern, bitte wie folgt vorgehen:

Normalerweise ist nichts zu tun: Der Pico verbindet sich mit dem Hotspot des Pi. In `config.py` steht:

```python
WIFI_NETWORKS = [
    ("in-plane-sight", "planespotter"),
]
MQTT_BROKER = "10.42.0.1"
```

Werden SSID/Passwort des Hotspots geändert (`HOTSPOT_SSID=... HOTSPOT_PASS=... ./deploy/setup-pi.sh`), müssen sie hier ebenfalls angepasst und `config.py` neu auf den Pico geladen werden.

## 4. Benutzung des Holo-Globes

### 4.1 Drehung des Holo-Globes

Vor dem ersten Start des Holo-Globes sollten natürlich alle Steckverbindungen auf der Platine im Holo-Globe überprüft werden. Hierzu bitte den Stromlaufplan bzw. die Dokumentation des Holo-Globes ansehen.

Danach kann die Drehbewegung des Holo-Globes entweder durch kurzes Halten des grünen Tasters an dem Sockel des Holo-Globes, oder durch Auswählen der "400" Umdrehungen im Frontend des Raspiberry Pi 5 auf dem Touchdisplay durchgeführt werden.

Gegebenenfalls muss die Drehbewegung durch einen kleine Schubs initiiert werden. 

über das Halten des grünen oder roten Tasters am Sockel des Holo-Globes kann die Drehbewegung stufenlos verstellt werden bzw. der Globe auch wieder gestoppt werden.

### 4.2 Lichtmodi des Holo-Globes

Danach kann der Lichtmodus des Holo-Globes durch die Frontend des Raspiberry Pi 5 auf dem Touchdisplay geändert werden.

Standardmäßig ist die Weltkarte aktiv und kann durch das Frontend in verschiedene Beleuchtungsmodi geändert werden.

## 5. Wartung & Troubleshooting

### Den Kiosk-Modus verlassen
Wenn du Wartungsarbeiten am System durchführen musst:
1. Eine physische Tastatur an den Raspberry Pi anschließen.
2. `Alt + F4` drücken, um Sway zu beenden und in die ungedrehte Textkonsole zu gelangen.
3. Hier können Befehle ausgeführt oder Logs geprüft werden (z.B. `ifconfig` um IP-Adresse zu überprüfen für eine ssh-Verbindung).
4. Mit `sudo reboot` startet das System wieder regulär in den Kiosk-Modus.
