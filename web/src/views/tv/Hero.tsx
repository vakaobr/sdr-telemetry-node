/** FlightWall hero panel — the product's face (FR-8.1). 10-ft typography. */
import { useRef } from "react";
import { sortedAircraft, useStore } from "../../state/store";
import { altitudeColor } from "../../components/Map/icons";
import { decorateRoute, flagForCountryName } from "../../lib/flags";
import { HeroSelector } from "./heroSelect";

function fmt(n: number | null | undefined, unit: string, digits = 0): string {
  return n != null ? `${n.toFixed(digits).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${unit}` : "—";
}

function cardinal(deg: number | null | undefined): string {
  if (deg == null) return "";
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return dirs[Math.round(deg / 45) % 8];
}

export function Hero() {
  const aircraft = useStore((s) => s.aircraft);
  const selectorRef = useRef(new HeroSelector());
  const hero = selectorRef.current.update(sortedAircraft(aircraft));

  if (!hero) {
    return (
      <div className="hero hero-empty">
        <div className="hero-listening">Listening to the sky…</div>
        <div className="hero-sub">no aircraft in range</div>
      </div>
    );
  }

  const e = hero.enrich;
  const emergency = hero.flags.includes("emergency");
  return (
    <div className={`hero${emergency ? " hero-emergency" : ""}`} key={hero.icao}>
      <div className="hero-callsign">{hero.callsign ?? hero.icao.toUpperCase()}</div>
      <div className="hero-type">
        {e?.typeName ?? e?.typeCode ?? "Unknown type"}
        {e?.operator ? <span className="hero-operator"> · {e.operator}</span> : null}
      </div>
      {e?.route && <div className="hero-route">{decorateRoute(e.route)}</div>}
      <div className="hero-grid">
        <div className="hero-stat">
          <span className="hero-label">Altitude</span>
          <span className="hero-value" style={{ color: altitudeColor(hero.altFt) }}>
            {hero.altFt === 0 ? "GROUND" : fmt(hero.altFt, " ft")}
          </span>
        </div>
        <div className="hero-stat">
          <span className="hero-label">Speed</span>
          <span className="hero-value">{fmt(hero.gsKt, " kt")}</span>
        </div>
        <div className="hero-stat">
          <span className="hero-label">Distance</span>
          <span className="hero-value">
            {fmt(hero.distanceKm, " km", 1)}
            <span className="hero-cardinal"> {cardinal(hero.bearingDeg)}</span>
          </span>
        </div>
        <div className="hero-stat">
          <span className="hero-label">{e?.registration ? "Registration" : "ICAO"}</span>
          <span className="hero-value">{e?.registration ?? hero.icao.toUpperCase()}</span>
        </div>
      </div>
      {e?.country && (
        <div className="hero-country">
          {flagForCountryName(e.country)} {e.country}
        </div>
      )}
      {emergency && <div className="hero-alert">⚠ EMERGENCY · SQUAWK {hero.squawk}</div>}
    </div>
  );
}
