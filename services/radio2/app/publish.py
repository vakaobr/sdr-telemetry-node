"""MQTT publish + command consumer for radio2 (03_ARCHITECTURE §5, ADR-002).

Publishes retained state (radio2/mode, radio2/pass/next, radio2/health) so the
gateway re-learns instantly on reconnect, with a Last-Will on radio2/health so
Node-A detects Node-B offline within keepalive. Consumes radio2/cmd for manual
overrides. Publisher is a Protocol so the supervisor can be driven by a fake in
tests with no broker.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Protocol

import paho.mqtt.client as mqtt

from app.scheduler.passes import Pass

log = logging.getLogger("radio2.publish")


class Publisher(Protocol):
    def mode(self, mode: str, reason: str, ts: int) -> None: ...
    def next_pass(self, p: Pass | None, ts: int) -> None: ...
    def health(
        self, *, ok: bool, decoder: str | None, uptime_s: int, tle_age_days: float | None, ts: int
    ) -> None: ...


class FakePublisher:
    """Records published state for tests."""

    def __init__(self) -> None:
        self.modes: list[dict] = []
        self.passes: list[dict] = []
        self.healths: list[dict] = []

    def mode(self, mode: str, reason: str, ts: int) -> None:
        self.modes.append({"mode": mode, "reason": reason, "ts": ts})

    def next_pass(self, p: Pass | None, ts: int) -> None:
        self.passes.append({"satellite": p.satellite if p else None, "ts": ts})

    def health(self, *, ok, decoder, uptime_s, tle_age_days, ts) -> None:
        self.healths.append({"ok": ok, "decoder": decoder, "ts": ts})


class PahoPublisher:
    """Real MQTT publisher + radio2/cmd consumer."""

    def __init__(self, host: str, port: int = 1883) -> None:
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="radio2")
        self._host, self._port = host, port
        self._on_cmd: Callable[[dict], None] | None = None
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        # Last-Will: if radio2 drops, Node-A sees offline within keepalive
        self._client.will_set(
            "radio2/health",
            json.dumps({"ts": 0, "ok": False, "reason": "offline"}),
            qos=1,
            retain=True,
        )

    def set_command_handler(self, handler: Callable[[dict], None]) -> None:
        self._on_cmd = handler

    def start(self) -> None:
        self._client.connect_async(self._host, self._port)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, client: mqtt.Client, *_a) -> None:
        log.info("mqtt connected to %s:%d", self._host, self._port)
        client.subscribe("radio2/cmd", qos=1)

    def _on_message(self, _c, _u, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload)
        except (ValueError, UnicodeDecodeError):
            return
        if msg.topic == "radio2/cmd" and isinstance(payload, dict) and self._on_cmd:
            self._on_cmd(payload)

    def _pub(self, topic: str, payload: dict, retain: bool = True) -> None:
        self._client.publish(topic, json.dumps(payload), qos=1, retain=retain)

    def mode(self, mode: str, reason: str, ts: int) -> None:
        self._pub("radio2/mode", {"ts": ts, "mode": mode, "since": ts, "reason": reason})

    def next_pass(self, p: Pass | None, ts: int) -> None:
        self._pub(
            "radio2/pass/next",
            {
                "ts": ts,
                "satellite": p.satellite if p else None,
                "aos": p.aos if p else None,
                "los": p.los if p else None,
                "maxEl": p.max_el if p else None,
            },
        )

    def health(self, *, ok, decoder, uptime_s, tle_age_days, ts) -> None:
        self._pub(
            "radio2/health",
            {
                "ts": ts,
                "ok": ok,
                "decoder": decoder,
                "uptimeS": uptime_s,
                "tleAgeDays": tle_age_days,
            },
        )


def now_s() -> int:
    return int(time.time())
