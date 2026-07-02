"""MQTT bridge: paho thread → asyncio, with last-known-state for snapshots.

Subscribes to the cross-node topics (03_ARCHITECTURE §5). Retained messages
re-populate state instantly on (re)connect — restart-safe by construction.
Bus loss never touches the ADS-B path; it only freezes Node-B freshness.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import paho.mqtt.client as mqtt

from app.config import Config
from app.models.generated_ws import NodeHealth, Radio2Status

log = logging.getLogger("gateway.bus")

NODE_HEALTH_STALE_S = 90  # health is republished every 30 s; 3 misses = offline


class MqttBridge:
    """Maintains retained-state mirrors and forwards events to an asyncio queue."""

    def __init__(self, config: Config) -> None:
        self._cfg = config
        self._loop: asyncio.AbstractEventLoop | None = None
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)

        # last-known retained state
        self._radio2_mode: dict | None = None
        self._radio2_pass: dict | None = None
        self._radio2_health: dict | None = None
        self._node_health: dict[str, dict] = {}

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id="gateway", clean_session=True
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self.connected = False

    # -- lifecycle --------------------------------------------------------

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._client.connect_async(self._cfg.nodes.mqtt_host, self._cfg.nodes.mqtt_port)
        self._client.loop_start()  # paho-owned thread

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def publish(self, topic: str, payload: dict, retain: bool = False, qos: int = 1) -> None:
        self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    # -- paho thread callbacks ---------------------------------------------

    def _on_connect(self, client: mqtt.Client, *_args: Any) -> None:
        self.connected = True
        log.info("mqtt connected to %s", self._cfg.nodes.mqtt_host)
        for topic in (
            "radio2/#",
            "sys/+/health",
            "atc/activity",
            "ais/vessel",
            "satellite/pass/event",
            "adsb/interesting",
        ):
            client.subscribe(topic, qos=1)

    def _on_message(self, _c: mqtt.Client, _u: Any, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload)
        except (ValueError, UnicodeDecodeError):
            log.warning("unparseable payload on %s", msg.topic)
            return
        if not isinstance(payload, dict):
            return

        # state mirrors (retained topics)
        if msg.topic == "radio2/mode":
            self._radio2_mode = payload
        elif msg.topic == "radio2/pass/next":
            self._radio2_pass = payload
        elif msg.topic == "radio2/health":
            self._radio2_health = payload
        elif msg.topic.startswith("sys/") and msg.topic.endswith("/health"):
            self._node_health[msg.topic.split("/")[1]] = payload

        # event forwarding to the asyncio side
        if self._loop is not None:
            event = {"topic": msg.topic, "payload": payload}
            self._loop.call_soon_threadsafe(self._enqueue, event)

    def _enqueue(self, event: dict) -> None:
        try:
            self.events.put_nowait(event)
        except asyncio.QueueFull:
            log.warning("event queue full — dropping %s", event["topic"])

    # -- snapshot state accessors (async side) ------------------------------

    def radio2_status(self) -> Radio2Status:
        """Merge retained radio2 topics into the WS Radio2Status shape."""
        now = int(time.time())
        health, mode = self._radio2_health, self._radio2_mode
        offline = (
            health is None
            or health.get("ok") is False
            or (health.get("ts", 0) < now - NODE_HEALTH_STALE_S)
        )
        if offline or mode is None:
            return Radio2Status.model_validate(
                {
                    "mode": "offline",
                    "since": (health or {}).get("ts", 0),
                    "reason": "lwt",
                    "nextPass": None,
                    "audioUrl": None,
                    "tleAgeDays": (health or {}).get("tleAgeDays") or 0,
                }
            )
        next_pass = None
        if self._radio2_pass and self._radio2_pass.get("satellite"):
            p = self._radio2_pass
            next_pass = {
                "satellite": p["satellite"],
                "aos": p["aos"],
                "los": p["los"],
                "maxEl": p["maxEl"],
            }
        audio_url = self._cfg.radio2.atc.icecast_url if mode.get("mode") == "atc" else None
        return Radio2Status.model_validate(
            {
                "mode": mode.get("mode", "idle"),
                "since": mode.get("since", now),
                "reason": mode.get("reason", "schedule"),
                "nextPass": next_pass,
                "audioUrl": audio_url,
                "tleAgeDays": health.get("tleAgeDays") or 0,
            }
        )

    def node_health(self, node: str) -> NodeHealth | None:
        """None = never seen or stale (LWT-equivalent via ts staleness)."""
        h = self._node_health.get(node)
        if not h or h.get("ts", 0) < int(time.time()) - NODE_HEALTH_STALE_S:
            return None
        if not h.get("ok", False):
            return None
        return NodeHealth.model_validate(
            {
                "ok": True,
                "cpuPct": h.get("cpuPct", 0),
                "memMb": h.get("memMb", 0),
                "tempC": h.get("tempC", 0),
                "throttled": h.get("throttled", False),
                "diskFreePct": h.get("diskFreePct", 0),
            }
        )
