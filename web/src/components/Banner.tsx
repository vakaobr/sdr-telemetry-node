/**
 * Interesting-aircraft banner (FR-8.6, story B1).
 * CRITICAL (emergency) persists while the aircraft is tracked;
 * NOTABLE (military/watchlist) auto-hides after 30 s.
 */
import { useEffect, useState } from "react";
import { useStore } from "../state/store";

const NOTABLE_TTL_S = 30;

export function Banner() {
  const alerts = useStore((s) => s.alerts);
  const aircraft = useStore((s) => s.aircraft);
  const select = useStore((s) => s.select);
  const [, forceTick] = useState(0);

  // re-evaluate visibility every 5 s so notable alerts age out
  useEffect(() => {
    const t = setInterval(() => forceTick((n) => n + 1), 5000);
    return () => clearInterval(t);
  }, []);

  const now = Math.floor(Date.now() / 1000);
  const alert = alerts.find((a) =>
    a.severity === "critical" ? aircraft[a.icao] != null : now - a.ts < NOTABLE_TTL_S,
  );
  if (!alert) return null;

  return (
    <button
      className={`banner banner-${alert.severity}`}
      onClick={() => select(alert.icao)}
      aria-label={`${alert.severity} alert`}
    >
      <span className="banner-badge">{alert.severity === "critical" ? "EMERGENCY" : "NOTABLE"}</span>
      <span className="banner-text">
        {alert.callsign ?? alert.icao.toUpperCase()} — {alert.rule}
      </span>
    </button>
  );
}
