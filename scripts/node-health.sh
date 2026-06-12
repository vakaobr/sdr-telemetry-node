#!/usr/bin/env bash
# Publish node health to MQTT (retained). Gateway treats ts older than 90 s as offline.
# Schema: shared/schemas/mqtt.schema.json#SysHealth
set -euo pipefail

NODE_NAME="${NODE_NAME:-node-a}"
MQTT_HOST="${MQTT_HOST:-127.0.0.1}"

ts=$(date +%s)

# CPU % over a 1 s window from /proc/stat
read -r _ u1 n1 s1 i1 rest < /proc/stat
sleep 1
read -r _ u2 n2 s2 i2 rest < /proc/stat
busy=$(( (u2+n2+s2) - (u1+n1+s1) ))
total=$(( busy + (i2-i1) ))
cpu_pct=$(( total > 0 ? 100*busy/total : 0 ))

mem_mb=$(awk '/MemAvailable/ {avail=$2} /MemTotal/ {tot=$2} END {printf "%d", (tot-avail)/1024}' /proc/meminfo)

temp_c=0
throttled=false
if command -v vcgencmd >/dev/null 2>&1; then
  temp_c=$(vcgencmd measure_temp | grep -oE '[0-9]+\.[0-9]+' || echo 0)
  tflags=$(vcgencmd get_throttled | cut -d= -f2)
  [[ "$tflags" != "0x0" ]] && throttled=true
fi

disk_free_pct=$(df --output=pcent / | tail -1 | tr -dc '0-9')
disk_free_pct=$((100 - disk_free_pct))

payload=$(printf '{"ts":%s,"ok":true,"cpuPct":%s,"memMb":%s,"tempC":%s,"throttled":%s,"diskFreePct":%s}' \
  "$ts" "$cpu_pct" "$mem_mb" "$temp_c" "$throttled" "$disk_free_pct")

mosquitto_pub -h "$MQTT_HOST" -t "sys/${NODE_NAME}/health" -r -q 1 -m "$payload"
