"""
Service layer (data sources and network integrations).

Modules:
- dump1090: fetch and normalize aircraft data
- globe: forward selected aircraft data to the microcontroller
- system_position: resolve the system's own lat/lon (env or GPSD)
"""

from . import system_position
