"""state.py - gemeinsamer Zustand ('Whiteboard'). Nur Daten, keine Logik.

Regel: Leser duerfen halb geschriebene Daten nie sehen. 'points' und der
Framebuffer-Tausch werden daher atomar referenziert (fertig bauen, dann mit
EINER Zuweisung aktiv setzen).
"""

# rpm -> display
period_us     = 0       # gemessene Drehperiode (EMA, us); 0 = steht
last_pulse_us = 0       # Zeitpunkt des letzten Hall-Pulses (ticks_us)
seq           = 0       # zaehlt Umdrehungen hoch (fuer GC-Timing)

# netz -> display / motor  (von netz.py geschrieben, atomar)
points        = []      # Liste von {id, lat, lon, color, size}
display_mode  = None    # z.B. Index/Name aus change_display_mode
mode_color    = [255, 255, 255]   # Farbe fuer EINE_FARBE-Modus
rpm_target    = None    # gewuenschte Drehzahl vom Backend (change_PWM)
image_name    = None    # gewuenschtes Bild (set_image)

# motor -> info
duty          = 0       # aktuelle Motor-Drehzahl (duty_u16)
