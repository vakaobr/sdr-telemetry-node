#!/usr/bin/env bash
# Node provisioning for sdr-telemetry-node (Raspberry Pi OS Bookworm, ARM64).
# Usage: sudo ./install-node.sh --role node-a|node-b [--uninstall]
# Idempotent: safe to re-run.
set -euo pipefail

ROLE=""
UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --role) ROLE="$2"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[[ "$ROLE" == "node-a" || "$ROLE" == "node-b" ]] || { echo "need --role node-a|node-b" >&2; exit 2; }
[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 2; }

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ $UNINSTALL -eq 1 ]]; then
  echo "==> uninstalling (role=$ROLE)"
  systemctl disable --now sdr-node-health.timer 2>/dev/null || true
  rm -f /etc/systemd/system/sdr-node-health.{service,timer} /usr/local/bin/sdr-node-health.sh
  rm -f /etc/modprobe.d/blacklist-rtlsdr-dvb.conf /etc/udev/rules.d/99-rtlsdr.rules
  systemctl daemon-reload
  udevadm control --reload-rules
  echo "==> done. Docker left installed (remove manually if desired)."
  exit 0
fi

echo "==> [1/5] blacklisting DVB kernel driver (would claim the SDR before userland)"
cat > /etc/modprobe.d/blacklist-rtlsdr-dvb.conf <<'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF
# unload now if already loaded (ignore errors: not loaded / in use until reboot)
modprobe -r dvb_usb_rtl28xxu 2>/dev/null || true

echo "==> [2/5] udev rules (RTL-SDR group access, stable by serial)"
install -m 0644 "$REPO_DIR/scripts/udev/99-rtlsdr.rules" /etc/udev/rules.d/99-rtlsdr.rules
udevadm control --reload-rules
udevadm trigger

echo "==> [3/5] docker engine + compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
SUDO_USER_NAME="${SUDO_USER:-}"
if [[ -n "$SUDO_USER_NAME" ]]; then
  usermod -aG docker "$SUDO_USER_NAME"
fi
systemctl enable --now docker

echo "==> [4/5] mosquitto-clients (host health publisher)"
apt-get update -qq && apt-get install -y -qq mosquitto-clients >/dev/null

echo "==> [5/5] node health publisher (systemd timer, 30 s)"
install -m 0755 "$REPO_DIR/scripts/node-health.sh" /usr/local/bin/sdr-node-health.sh
cat > /etc/systemd/system/sdr-node-health.service <<EOF
[Unit]
Description=Publish node health to MQTT (sdr-telemetry-node)
[Service]
Type=oneshot
Environment=NODE_NAME=$ROLE
Environment=MQTT_HOST=${MQTT_HOST:-127.0.0.1}
ExecStart=/usr/local/bin/sdr-node-health.sh
EOF
cat > /etc/systemd/system/sdr-node-health.timer <<'EOF'
[Unit]
Description=Node health publish every 30s
[Timer]
OnBootSec=60
OnUnitActiveSec=30
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now sdr-node-health.timer

echo "==> install complete (role=$ROLE)."
echo "    next: cd $REPO_DIR/docker/$ROLE && docker compose up -d"
echo "    note: re-login (or 'newgrp docker') for non-root docker access."
