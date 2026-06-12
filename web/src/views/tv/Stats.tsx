/** Receiver stats panel for the TV rotation (FR-8.4 / task 6.5). */
import { useStore } from "../../state/store";

export function Stats() {
  const health = useStore((s) => s.health);
  const radio2 = useStore((s) => s.radio2);
  const a = health?.adsb;

  return (
    <div className="tv-stats">
      <div className="tv-stats-grid">
        <div className="tv-stat">
          <span className="tv-stat-value">{a?.aircraftCount ?? "—"}</span>
          <span className="tv-stat-label">aircraft now</span>
        </div>
        <div className="tv-stat">
          <span className="tv-stat-value">{a ? Math.round(a.msgRate) : "—"}</span>
          <span className="tv-stat-label">messages / s</span>
        </div>
        <div className="tv-stat">
          <span className="tv-stat-value">{a ? Math.round(a.maxRangeKm) : "—"}</span>
          <span className="tv-stat-label">max range km</span>
        </div>
        <div className="tv-stat">
          <span className="tv-stat-value tv-stat-radio">
            {radio2?.mode === "offline" ? "—" : (radio2?.mode ?? "—").toUpperCase()}
          </span>
          <span className="tv-stat-label">radio 2</span>
        </div>
      </div>
      {radio2?.nextPass && (
        <div className="tv-nextpass">
          📡 {radio2.nextPass.satellite} pass{" "}
          {new Date(radio2.nextPass.aos * 1000).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      )}
    </div>
  );
}
