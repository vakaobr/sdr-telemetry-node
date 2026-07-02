/** Priority-ordered live aircraft list (FR-8.5). */
import { sortedAircraft, useStore } from "../../state/store";
import type { Aircraft } from "../../types/generated/ws";

function fmtAlt(a: Aircraft): string {
  if (a.altFt == null) return "—";
  if (a.altFt === 0) return "GND";
  return `${a.altFt.toLocaleString()} ft`;
}

export function AircraftList() {
  const aircraft = useStore((s) => s.aircraft);
  const selected = useStore((s) => s.selectedIcao);
  const select = useStore((s) => s.select);
  const list = sortedAircraft(aircraft);

  if (list.length === 0) {
    return <div className="list-empty">Listening… no aircraft in range</div>;
  }

  return (
    <ul className="ac-list" aria-label="live aircraft">
      {list.map((a) => (
        <li
          key={a.icao}
          className={`ac-row${a.icao === selected ? " row-selected" : ""}${a.flags.length ? " row-flagged" : ""}`}
          onClick={() => select(a.icao === selected ? null : a.icao)}
        >
          <span className="ac-callsign">{a.callsign ?? a.icao}</span>
          <span className="ac-type">{a.enrich?.typeCode ?? ""}</span>
          <span className="ac-alt">{fmtAlt(a)}</span>
          <span className="ac-dist">{a.distanceKm != null ? `${a.distanceKm.toFixed(0)} km` : "—"}</span>
        </li>
      ))}
    </ul>
  );
}
