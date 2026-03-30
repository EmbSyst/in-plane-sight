# In Plane Sight

## Kurzbeschreibung

In diesem Projekt wollen wir ein ADS-B-basiertes Flugzeug-Tracking-System entwickeln, das nicht nur Positionsdaten empfängt und verarbeitet, sondern ein Flugzeug auch physisch über eine Pan/Tilt-Mechanik „anzeigt“.

Die geplante Pipeline sieht so aus:

- Empfang von ADS-B-Signalen auf 1090 MHz
- Erfassung der Rohdaten über einen SDR-Empfänger
- Demodulation und Decoding der Datenpakete
- Extraktion von Position und Höhe des Flugzeugs
- Berechnung von Azimut und Elevation relativ zur eigenen Basisstation
- Umwandlung dieser Werte in PWM-Steuersignale
- Ansteuerung von zwei Servos für Pan und Tilt
- Physischer Zeiger richtet sich auf das Flugzeug aus

Das Repository befindet sich aktuell noch in einer frühen Phase und dient zunächst dazu, die geplante Struktur, den technischen Ablauf und die nächsten Entwicklungsschritte festzuhalten.
