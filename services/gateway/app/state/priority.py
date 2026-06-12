"""Nearby-aircraft prioritization constants (FR-1.4).

Rule: ascending effective distance, where aircraft below LOW_ALT_FT get their
distance multiplied by LOW_ALT_WEIGHT — approach/departure traffic surfaces
ahead of equally-near overflights. Aircraft without a position sort last.

The ordering itself is applied by AircraftTable on wire payloads each cycle;
this module owns the tunables so the rule has exactly one home.
"""

LOW_ALT_FT = 10_000
LOW_ALT_WEIGHT = 0.5
