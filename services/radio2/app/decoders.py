"""Mode → decoder command table.

Phase 8 wires ATC (rtl_airband). AIS (P9) and satellite (P10) configs land on
their milestones. Tests and the simulated supervisor inject a fake
`command_for` pointing at the scripted fake decoder, so the FSM/proc path is
exercised for real without RF.
"""

from __future__ import annotations

from collections.abc import Callable

from app.config import Radio2Config

ATC_CONF_PATH = "/run/rtl_airband.conf"  # written at boot by main.render + write


def real_command_for(cfg: Radio2Config, serial: str) -> Callable[[str], list[str]]:
    """Build a mode→argv function bound to config + the SDR-2 serial."""

    def command_for(mode: str) -> list[str]:
        if mode == "atc":
            # -f foreground (stdout heartbeat), -e errors→stderr; config written
            # at boot by main from cfg.radio2.atc (see rtl_airband.render_config)
            return ["rtl_airband", "-f", "-e", "-c", ATC_CONF_PATH]
        if mode == "ais":
            return ["AIS-catcher", "-d", serial, "-N", "8100", "-v"]
        if mode == "satellite":
            # record-then-decode wrapper (P10); placeholder argv for now
            return ["satdump-record", serial]
        raise ValueError(f"no decoder command for mode {mode!r}")

    return command_for
