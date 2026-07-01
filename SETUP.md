# In Plane Sight – Hardware & System Setup

Dieses Dokument beschreibt die physische Einrichtung für das "In Plane Sight"-Projekt. Es umfasst den Aufbau des Kiosk-Displays am Raspberry Pi 5 sowie die Konfiguration und Nutzung des Holo-Globes (Raspberry Pi Pico).

---

## 1. Hardware-Verkabelung

### Raspberry Pi (Main Controller)
* Der Raspberry Pi 5 ist im Touchgehäuse verbaut und braucht eine Stromversorgung über das weiße Netzkabel von Raspberry. Dieses muss am USB-C-Port des Raspberry Pi 5 angeschlossen werden.
* Der HackRF-One muss über eine USB-Kabel an einen der freien USB-Ports am Raspberry Pi 5 angeschlossen werden.
* Die Antenne muss zusätzlich am Antennen-Port des HackRF-One angeschlossen werden.

### Holo-Globe (Pico Controller)
* Das Kaltgeräte-Kabel muss am Sockel des Holo-Globes angeschlossen werden. Danach kann der Schalter am Sockel des Holo-Globes betätigt werden.
* Der Raspberry Pi Pico 2W braucht zudem eine zusätzliche 5V Stromversorgung über dessen Micro-USB-Port. Diese kann über ein 5V USB-Netzteil oder über einen Laptop erfolgen.

---

## 2. Betriebssystem des Raspberry Pi 5

Da das System ein DSI-Display nutzt und Ubuntu 24.04 zum Einsatz kommt, verwenden wir **Sway** als ressourcenschonenden, ausbruchsicheren Kiosk-Fenstermanager, damit während der Nutzung nicht aus dem Frontent "ausgebrochen" werden kann.

Das System startet nach dem Einstecken der Stromversorgung automatisch, loggt sich automatisch ein (Informationen zu Benutzername und Passwort in der schriftlichen Dokumentation) und aktiviert die Hintergrundprozesse des Raspberry Pi 5. 

Vor dem ersten Start sollte über den in Punkt 5 beschriebenen Prozess aus dem Kiosk-Modus ausgebrochen werden und im Repo des Projekts einmal der aktuelle Status des Projekts zur Sicherheit gepullt werden.

```bash
cd /home/pi/Projekt/backend/in-plane-sight
git pull 
```


## 3. WLAN Konfiguration

Es ist wichtig, dass beide Raspberry Pi 5 und Raspberry Pi Pico 2W im gleichen WLAN verbunden sind. Ansonsten kann der Datenaustausch über MQTT nicht erfolgen.

### 3.1 WLAN Konfiguration des Raspberry Pi 5

Um die Konfiguration des WLANs im Raspberry Pi 5 zu ändern, ist folgender Weg z.B. möglich: 
1. Zuerst wie in Punkt 5 beschrieben aus dem Kiosk-Modus ausbrechen.
2. Danach ist die Konfiguration über das Terminal wie folgt möglich:


WLAN-Netzwerke in der Nähe anzeigen:

```bash
nmcli device wifi list
```
Mit einem WLAN-Netzwerk verbinden:

```bash
sudo nmcli device wifi connect MEINE-SSID password MEIN-PASSWORT
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

In der Datei `config.py` des Pico muss die Konfiguration des WLANs geändert werden.

Folgende Netzwerke sind aktuell hinterlegt:

```python
WIFI_NETWORKS = [
    ("embedded", "c384c8c3"),
    ("in-plane-sight", "planespotter"),
]
```

Diese können bei Bedarf geändert werden.

## 4. Benutzung des Holo-Globes

### 4.1 Drehung des Holo-Globes

Vor dem ersten Start des Holo-Globes sollten natürlich alle Steckverbindungen auf der Platine im Holo-Globe überprüft werden. Hierzu bitte den Stromlaufplan bzw. die Dokumentation des Holo-Globes ansehen.

Danach kann die Drehbewegung des Holo-Globes entweder durch kurzes Halten der grünen Taste an dem Sockel des Holo-Globes, oder durch Auswählen der "400" Umdrehungen im Frontend des Raspiberry Pi 5 auf dem Touchdisplay durchgeführt werden.

Gegebenenfalls muss die Drehbewegung durch einen kleine Schubs initiiert werden. 

über das Halten der grünen oder roten Taste am Sockel des Holo-Globes kann die Drehbewegung stufenlos verstellt werden bzw. der Globe auch wieder gestoppt werden.

### 4.2 Lichtmodi des Holo-Globes

Danach kann der Lichtmodus des Holo-Globes durch die Frontend des Raspiberry Pi 5 auf dem Touchdisplay geändert werden.

Standardmäßig ist die Weltkarte aktiv und kann durch das Frontend in verschiedene Beleuchtungsmodi geändert werden.

## 5. Wartung & Troubleshooting

### Den Kiosk-Modus verlassen
Wenn du Wartungsarbeiten am System durchführen musst:
1. Eine physische Tastatur an den Raspberry Pi anschließen.
2. `Alt + F4` drücken, um Sway zu beenden und in die ungedrehte Textkonsole zu gelangen.
3. Hier können Befehle ausgeführt oder Logs geprüft werden.
4. Mit `sudo reboot` startet das System wieder regulär in den Kiosk-Modus.
