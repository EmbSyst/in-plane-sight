"""motor.py - Motor-PWM + zwei Taster (schneller/langsamer) mit Sanftanlauf.

Logik an die erprobte new_combine_test.py angelehnt (Sanftanlauf-Rampe,
Auto-Repeat). Bei Bedarf mit dieser Datei abgleichen.

change_PWM (MQTT, Web-UI): die gewuenschte rpm wird DIREKT in einen festen
duty_u16 umgerechnet (offen, keine Hall-Regelung, kein Hochregeln) und auf
RPM_DUTY_CAP begrenzt. Die zwei Hardware-Taster bleiben davon unberuehrt.
"""

import time
from machine import Pin, PWM

import config
import state


class Motor:
    def __init__(self):
        self.pwm = PWM(Pin(config.MOTOR_PIN))
        self.pwm.freq(config.MOTOR_FREQ)
        self.duty = 0
        self.target = 0
        self.btn_faster = Pin(config.BTN_FASTER, Pin.IN, Pin.PULL_UP)
        self.btn_slower = Pin(config.BTN_SLOWER, Pin.IN, Pin.PULL_UP)
        self._next_repeat = time.ticks_ms()
        self._last_rpm_ref = state.rpm_target      # letzte uebernommene change_PWM-Vorgabe
        self._apply()

    def _apply(self):
        self.pwm.duty_u16(self.duty)
        state.duty = self.duty

    @staticmethod
    def _rpm_setpoint(rt):
        """change_PWM-Nutzlast (state.rpm_target): rpm-Liste [v] (oder Skalar).
        Leer / None / 0 -> 0 (Motor aus)."""
        if rt is None:
            return 0
        if isinstance(rt, (list, tuple)):
            if not rt:
                return 0
            rt = rt[0]
        try:
            return float(rt)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _rpm_to_duty(rpm):
        """Feste, direkte Umrechnung rpm -> duty_u16 (offen, keine Regelung),
        begrenzt auf RPM_DUTY_CAP. rpm<=0 -> 0 (aus)."""
        if rpm <= 0:
            return 0
        duty = int(rpm * config.RPM_DUTY_PER_RPM)
        if duty > config.RPM_DUTY_CAP:
            return config.RPM_DUTY_CAP
        return duty

    def service(self):
        now = time.ticks_ms()

        # --- neue change_PWM-Vorgabe (Web-UI): rpm DIREKT -> festes duty ---
        # netz.py legt die rpm-Liste pro Nachricht neu an -> Referenzvergleich.
        # Kein Hochregeln, keine Hall-Rueckkopplung: target wird direkt gesetzt.
        rt = state.rpm_target
        if rt is not self._last_rpm_ref:
            self._last_rpm_ref = rt
            self.target = self._rpm_to_duty(self._rpm_setpoint(rt))

        # --- Taster mit Auto-Repeat (unveraendert; Pull-up -> gedrueckt = 0) ---
        if time.ticks_diff(now, self._next_repeat) >= 0:
            if not self.btn_faster.value():
                self.target = min(self.target + config.SPEED_STEP, 65535)
                self._next_repeat = time.ticks_add(now, config.REPEAT_MS)
            elif not self.btn_slower.value():
                self.target = max(self.target - config.SPEED_STEP, 0)
                self._next_repeat = time.ticks_add(now, config.REPEAT_MS)

        # --- Sanftanlauf / sanftes Bremsen Richtung target (unveraendert) ---
        if self.duty < self.target:
            self.duty = min(self.duty + config.RAMP_STEP, self.target)
        elif self.duty > self.target:
            self.duty = max(self.duty - config.RAMP_STEP, self.target)
        self._apply()
