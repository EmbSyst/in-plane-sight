"""motor.py - Motor-PWM + zwei Taster (schneller/langsamer) mit Sanftanlauf.

Logik an die erprobte new_combine_test.py angelehnt (Sanftanlauf-Rampe,
Auto-Repeat). Bei Bedarf mit dieser Datei abgleichen.
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
        self._apply()

    def _apply(self):
        self.pwm.duty_u16(self.duty)
        state.duty = self.duty

    def service(self):
        now = time.ticks_ms()
        # Taster mit Auto-Repeat (Pull-up -> gedrueckt = 0)
        if time.ticks_diff(now, self._next_repeat) >= 0:
            if not self.btn_faster.value():
                self.target = min(self.target + config.SPEED_STEP, 65535)
                self._next_repeat = time.ticks_add(now, config.REPEAT_MS)
            elif not self.btn_slower.value():
                self.target = max(self.target - config.SPEED_STEP, 0)
                self._next_repeat = time.ticks_add(now, config.REPEAT_MS)
        # Sanftanlauf / sanftes Bremsen Richtung target
        if self.duty < self.target:
            self.duty = min(self.duty + config.RAMP_STEP, self.target)
        elif self.duty > self.target:
            self.duty = max(self.duty - config.RAMP_STEP, self.target)
        self._apply()
