/** Per-vessel detail (AIS) — mirrors the aircraft DetailPane, shown when a
 *  vessel marker is clicked. Graceful "—" for missing fields (UX #4). */
import { flagForMmsi } from "../../lib/flags";
import { useStore } from "../../state/store";

function shipTypeName(t: number | null | undefined): string | null {
  if (t == null) return null;
  if (t === 30) return "Fishing";
  if (t === 36) return "Sailing";
  if (t === 37) return "Pleasure craft";
  if (t >= 40 && t < 50) return "High-speed craft";
  if (t === 50) return "Pilot vessel";
  if (t === 51) return "Search & rescue";
  if (t === 52) return "Tug";
  if (t === 53) return "Port tender";
  if (t === 55) return "Law enforcement";
  if (t >= 60 && t < 70) return "Passenger";
  if (t >= 70 && t < 80) return "Cargo";
  if (t >= 80 && t < 90) return "Tanker";
  return `Other (${t})`;
}

function Row({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{value ?? "—"}</span>
    </div>
  );
}

export function VesselDetailPane() {
  const mmsi = useStore((s) => s.selectedMmsi);
  const v = useStore((s) => (mmsi ? s.vessels[mmsi] : null));
  if (!v) return null;

  return (
    <aside className="detail-pane" aria-label="vessel detail">
      <header>
        <h2>🚢 {v.name ?? `MMSI ${v.mmsi}`}</h2>
        <button onClick={() => useStore.getState().selectVessel(null)} aria-label="close">×</button>
      </header>
      <Row label="MMSI" value={`${flagForMmsi(v.mmsi)} ${v.mmsi}`.trim()} />
      <Row label="Type" value={shipTypeName(v.shipType)} />
      <Row label="Speed" value={v.sogKt != null ? `${v.sogKt.toFixed(1)} kt` : null} />
      <Row label="Course" value={v.cogDeg != null ? `${v.cogDeg.toFixed(0)}°` : null} />
      <Row label="Position" value={`${v.lat.toFixed(4)}, ${v.lon.toFixed(4)}`} />
    </aside>
  );
}
