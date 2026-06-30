"""Child-process management for decoder lifecycles (ADR-004).

ChildProcess wraps an asyncio subprocess with stdout-derived heartbeat and
explicit SIGTERM/SIGKILL control. ProcessModeRunner adapts it to the FSM's
ModeRunner protocol by mapping a mode → command.

Heartbeat = time since the last stdout line. Real decoders (rtl_airband,
AIS-catcher, satdump) log continuously; a hung decoder stops emitting, which
the FSM watchdog detects. The supervisor runs as PID-namespace leader under
tini in the container so orphaned children are reaped.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

log = logging.getLogger("radio2.proc")


class ChildProcess:
    """One spawned decoder. Heartbeat tracks last stdout line."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._proc: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task | None = None
        self._last_line = 0.0
        self._lines = 0

    async def start(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        self._last_line = self._clock()
        self._lines = 0
        self._reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        assert self._proc and self._proc.stdout
        # Heartbeat = time since the last stdout *output*, read in chunks rather
        # than whole lines. rtl_airband's foreground (-f) display redraws in place
        # with ANSI cursor codes and no trailing newline, so a line-based reader
        # would see it as hung after startup and the watchdog would kill a healthy
        # decoder. Any bytes (a redraw, a log line) refresh the heartbeat.
        try:
            while True:
                chunk = await self._proc.stdout.read(4096)
                if not chunk:
                    break
                self._last_line = self._clock()
                self._lines += chunk.count(b"\n")
        finally:
            await self._proc.wait()  # reap → returncode set → alive() goes False

    def alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    def seconds_since_heartbeat(self) -> float:
        return self._clock() - self._last_line if self._proc else float("inf")

    @property
    def heartbeats(self) -> int:
        return self._lines

    def terminate(self) -> None:
        if self.alive():
            self._proc.terminate()  # SIGTERM

    def kill(self) -> None:
        if self.alive():
            self._proc.kill()  # SIGKILL

    async def wait(self) -> int | None:
        if self._proc:
            await self._proc.wait()
            return self._proc.returncode
        return None


class ProcessModeRunner:
    """Adapts ChildProcess to fsm.ModeRunner; one process at a time."""

    def __init__(
        self,
        command_for: Callable[[str], list[str]],
        *,
        clock: Callable[[], float] = time.monotonic,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command_for = command_for
        self._clock = clock
        self._env = env
        self._proc: ChildProcess | None = None
        self._mode: str | None = None

    async def start(self, mode: str) -> None:
        cmd = self._command_for(mode)
        log.info("starting decoder for mode %s: %s", mode, cmd[0] if cmd else "?")
        self._mode = mode
        self._proc = ChildProcess(clock=self._clock)
        await self._proc.start(cmd, env=self._env)

    async def stop(self) -> None:
        if self._proc:
            self._proc.terminate()

    async def kill(self) -> None:
        if self._proc:
            log.warning("SIGKILL escalation for mode %s", self._mode)
            self._proc.kill()

    def alive(self) -> bool:
        return self._proc.alive() if self._proc else False

    def seconds_since_heartbeat(self) -> float:
        return self._proc.seconds_since_heartbeat() if self._proc else float("inf")
