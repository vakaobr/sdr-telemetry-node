/** Per-aircraft detail (FR-8.5) — graceful placeholders, never broken layout (UX #4). */
import { useStore } from "../../state/store";

function Row({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{value ?? "—"}</span>
    </div>
  );
}

export function DetailPane() {
  const icao = useStore((s) => s.selectedIcao);
  const ac = useStore((s) => (icao ? s.aircraft[icao] : null));
  if (!ac) return null;

  const e = ac.enrich;
  return (
    <aside className="detail-pane" aria-label="aircraft detail">
      <header>
        <h2>{ac.callsign ?? ac.icao}</h2>
        <button onClick={() => useStore.getState().select(null)} aria-label="close">×</button>
      </header>
      <Row label="ICAO" value={ac.icao.toUpperCase()} />
      <Row label="Registration" value={e?.registration} />
      <Row label="Type" value={e?.typeName ?? e?.typeCode} />
      <Row label="Operator" value={e?.operator} />
      <Row label="Route" value={e?.route} />
      <Row label="Altitude" value={ac.altFt != null ? `${ac.altFt.toLocaleString()} ft` : null} />
      <Row label="Ground speed" value={ac.gsKt != null ? `${Math.round(ac.gsKt)} kt` : null} />
      <Row
        label="Vertical rate"
        value={ac.vrFpm != null ? `${ac.vrFpm > 0 ? "+" : ""}${ac.vrFpm} fpm` : null}
      />
      <Row label="Squawk" value={ac.squawk} />
      <Row
        label="Distance"
        value={ac.distanceKm != null ? `${ac.distanceKm.toFixed(1)} km @ ${ac.bearingDeg?.toFixed(0)}°` : null}
      />
      <Row label="RSSI" value={ac.rssi != null ? `${ac.rssi.toFixed(1)} dBFS` : null} />
      {ac.flags.length > 0 && (
        <div className="detail-flags">{ac.flags.map((f) => <span key={f} className={`flag flag-${f}`}>{f}</span>)}</div>
      )}
    </aside>
  );
}
