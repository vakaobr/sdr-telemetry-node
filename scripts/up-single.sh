#!/usr/bin/env bash
# Single-node launcher (R3): all services on one host, one project/network.
# Merges node-a + node-b composes + the single-node CPU-pinning override.
# Env (RECEIVER_*, ICECAST_SOURCE_PASSWORD, OPENAIP/AISSTREAM keys) comes from
# docker/node-a/.env. config.yaml must set: nodes.mqtt_host=mosquitto,
# radio2.sdr_remote=null (local SDRs), radio2.atc.icecast_host=icecast.
set -euo pipefail
cd "$(dirname "$0")/.."

exec docker compose -p sdrnode \
  --env-file docker/node-a/.env \
  -f docker/node-a/compose.yml \
  -f docker/node-b/compose.yml \
  -f docker/single/compose.override.yml \
  up -d --build "$@"
