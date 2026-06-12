"""Mode → decoder command table.

Phase 7 ships the command shapes; the real decoder configs (rtl_airband
channels, AIS-catcher device, satdump pipeline) are finalized when each mode
lands on hardware (P8 ATC, P9 AIS, P10 satellite). Tests and the simulated
supervisor inject a fake `command_for` pointing at the scripted fake decoder,
so the FSM/proc path is exercised for real without RF.
"""

from __future__ import annotations

from app.config import Radio2Config


def real_command_for(cfg: Radio2Config, serial: str) -> callable:
    """Build a mode→argv function bound to config + the SDR-2 serial."""

    def command_for(mode: str) -> list[str]:
        if mode == "atc":
            # rtl_airband reads a generated config (written in P8)
            return ["rtl_airband", "-f", "-c", "/run/rtl_airband.conf"]
        if mode == "ais":
            return ["AIS-catcher", "-d", serial, "-N", "8100", "-v"]
        if mode == "satellite":
            # record-then-decode wrapper (P10); placeholder argv for now
            return ["satdump-record", serial]
        raise ValueError(f"no decoder command for mode {mode!r}")

    return command_for
