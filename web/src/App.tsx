/**
 * App shell: fetch receiver config once, start the WS client, render the
 * interactive view. TV mode joins as a second view in Phase 6.
 */
import { useEffect, useState } from "react";
import type { ReceiverInfo } from "./components/Map/AircraftMap";
import { useStore } from "./state/store";
import { InteractiveView } from "./views/interactive/InteractiveView";
import { TvView } from "./views/tv/TvView";
import { WsClient } from "./ws/client";

function isTvMode(): boolean {
  return window.location.pathname === "/tv" || window.location.hash === "#tv";
}

export function App() {
  const [receiver, setReceiver] = useState<ReceiverInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/config")
      .then((r) => {
        if (!r.ok) throw new Error(`config: HTTP ${r.status}`);
        return r.json();
      })
      .then((cfg) => {
        if (!cancelled) {
          setReceiver({
            lat: cfg.receiver.lat,
            lon: cfg.receiver.lon,
            rangeRingsKm: cfg.ui?.rangeRingsKm ?? [50, 100, 150],
            tvRotation: cfg.ui?.tvRotation,
          });
        }
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const { applyServer, setConnected } = useStore.getState();
    const client = new WsClient({ onMessage: applyServer, onConnected: setConnected });
    client.start();
    return () => client.stop();
  }, []);

  if (error) {
    return <main className="boot-msg">gateway unreachable: {error} — retrying on reload</main>;
  }
  if (!receiver) {
    return <main className="boot-msg">connecting…</main>;
  }
  return isTvMode() ? <TvView receiver={receiver} /> : <InteractiveView receiver={receiver} />;
}
