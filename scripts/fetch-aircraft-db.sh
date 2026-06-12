#!/usr/bin/env bash
# Download the offline aircraft database (tar1090-db) to the gateway data dir.
# Run at install and re-run any time to refresh; the gateway re-imports on
# boot when the file changes. Downloaded at install time → we redistribute
# nothing (license posture per 02_CODE_RESEARCH open Q6).
set -euo pipefail

DEST="${1:-/opt/sdr-telemetry-node/data/aircraft.csv.gz}"
URL="https://raw.githubusercontent.com/wiedehopf/tar1090-db/csv/aircraft.csv.gz"

mkdir -p "$(dirname "$DEST")"
echo "==> downloading aircraft DB → $DEST"
curl -fsSL --retry 3 -o "$DEST.tmp" "$URL"
mv "$DEST.tmp" "$DEST"
size=$(du -h "$DEST" | cut -f1)
echo "==> done ($size). Gateway imports it on next restart (one-time ~60 s on a Pi 3B)."
