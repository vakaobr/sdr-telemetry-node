/**
 * TV / kiosk mode (FR-8.4): zero chrome, auto-rotating panels, cursor hidden,
 * burn-in pixel-shift, emergency override. The wall display is the product.
 */
import { useEffect, useMemo, useState } from "react";
import { AircraftMap, type ReceiverInfo } from "../../components/Map/AircraftMap";
import { useStore } from "../../state/store";
import { Hero } from "./Hero";
import { Stats } from "./Stats";
import "./tv.css";

const PANEL_SECONDS = 12;
// burn-in guard: whole-canvas drift, cycled every minute (OLED-conscious, UX #5)
const SHIFTS = [
  [0, 0], [2, 1], [0, 2], [-2, 1], [-1, -1], [1, -2],
] as const;

export function TvView({ receiver }: { receiver: ReceiverInfo }) {
  const panels = useMemo(
    () => (receiver.tvRotation?.length ? receiver.tvRotation : ["hero", "map", "stats"]),
    [receiver.tvRotation],
  );
  const [idx, setIdx] = useState(0);
  const [shift, setShift] = useState(0);
  const connected = useStore((s) => s.connected);
  const alerts = useStore((s) => s.alerts);
  const aircraft = useStore((s) => s.aircraft);

  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % panels.length), PANEL_SECONDS * 1000);
    return () => clearInterval(t);
  }, [panels.length]);

  useEffect(() => {
    const t = setInterval(() => setShift((s) => (s + 1) % SHIFTS.length), 60_000);
    return () => clearInterval(t);
  }, []);

  // active emergency forces the hero panel (the only loud thing — UX #2)
  const emergencyLive = alerts.some(
    (a) => a.severity === "critical" && aircraft[a.icao] != null,
  );
  const panel = emergencyLive ? "hero" : panels[idx];
  const [dx, dy] = SHIFTS[shift];

  return (
    <div className="tv-root" style={{ transform: `translate(${dx}px, ${dy}px)` }}>
      {panel === "hero" && <Hero />}
      {panel === "map" && (
        <div className="tv-map">
          <AircraftMap receiver={receiver} />
        </div>
      )}
      {panel === "stats" && <Stats />}
      {/* satellite panel joins the rotation in P10 (ui.tv_rotation flag) */}
      <div className="tv-footer">
        <span className={`conn-dot ${connected ? "conn-ok" : "conn-down"}`} />
        <span className="tv-clock">
          {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
        <span className="tv-dots">
          {panels.map((p, i) => (
            <span key={p} className={`tv-dot${i === idx && !emergencyLive ? " tv-dot-on" : ""}`} />
          ))}
        </span>
      </div>
    </div>
  );
}
