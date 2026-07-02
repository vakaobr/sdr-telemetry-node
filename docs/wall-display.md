# Wall Display (TV / Kiosk Mode)

TV mode lives at **`http://<node-a>:8080/tv`** (or `/#tv`). Zero chrome, auto-rotating
panels (hero → map → stats, 12 s each), cursor hidden, OLED burn-in pixel-shift,
dark theme. An active emergency squawk forces the hero panel until the aircraft leaves.

## Option A — Smart TV browser
Open the URL in the TV's browser and use its full-screen mode. If the TV browser
struggles with the map panel, trim the rotation in `config.yaml`:
`ui: { tv_rotation: [hero, stats] }`.

## Option B — Raspberry Pi kiosk (any Pi + HDMI)
On a Pi OS (Desktop) install:

```bash
sudo apt install -y chromium-browser
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/sdr-kiosk.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=sdr-telemetry-kiosk
Exec=chromium-browser --kiosk --noerrdialogs --disable-infobars \
  --check-for-update-interval=31536000 http://tattoine-watcher.local:8080/tv
EOF
```

Disable screen blanking: `sudo raspi-config` → Display Options → Screen Blanking → No.

## Option C — Old tablet
Open the URL, "Add to Home Screen", use a kiosk/pinning app to keep it foreground,
and disable screen sleep while charging.

## Behavior notes
- WebSocket auto-reconnects (backoff to 15 s); a red pulsing dot bottom-right means
  the gateway is unreachable — the display self-heals when it returns.
- Panels and order come from `config.yaml` `ui.tv_rotation`; the satellite panel is
  added automatically when satellite capture ships (P10).
- 7-day soak expectation (M2 gate): no crash, no leak, no visual fault. Report
  anything else as a bug.
