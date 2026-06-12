/** Interactive layout: map + list + detail; responsive ≥360 px (FR-8.5). */
import { AtcPlayer } from "../../components/AtcPlayer";
import { Banner } from "../../components/Banner";
import { AircraftMap, type ReceiverInfo } from "../../components/Map/AircraftMap";
import { useStore } from "../../state/store";
import { AircraftList } from "./AircraftList";
import { DetailPane } from "./DetailPane";

export function InteractiveView({ receiver }: { receiver: ReceiverInfo }) {
  const connected = useStore((s) => s.connected);
  const health = useStore((s) => s.health);

  return (
    <div className="interactive-root">
      <header className="topbar">
        <h1>sdr-telemetry-node</h1>
        <div className="topbar-status">
          <AtcPlayer />
          {health && (
            <span className="stat">
              {health.adsb.aircraftCount} aircraft · {health.adsb.msgRate.toFixed(0)} msg/s ·
              max {health.adsb.maxRangeKm.toFixed(0)} km
            </span>
          )}
          <span
            className={`conn-dot ${connected ? "conn-ok" : "conn-down"}`}
            title={connected ? "live" : "reconnecting…"}
          />
        </div>
      </header>
      <Banner />
      <main className="content">
        <section className="map-pane">
          <AircraftMap receiver={receiver} />
        </section>
        <section className="side-pane">
          <AircraftList />
        </section>
        <DetailPane />
      </main>
    </div>
  );
}
