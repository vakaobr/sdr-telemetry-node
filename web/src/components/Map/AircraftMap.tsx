/**
 * Live Leaflet map — canvas renderer, imperative marker management.
 *
 * React renders the container once; aircraft markers/trails are synced
 * directly against Leaflet layers per store update (no per-aircraft React
 * re-render at 1 Hz — NFR-9 on Pi/TV-class browsers, ADR-008).
 */
import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useStore } from "../../state/store";
import type { Aircraft } from "../../types/generated/ws";
import { iconHtml, sizeForZoom } from "./icons";
import "./map.css";

export interface ReceiverInfo {
  lat: number;
  lon: number;
  rangeRingsKm: number[];
  tvRotation?: string[];
}

function aircraftIcon(ac: Aircraft, selected: boolean, sizePx: number): L.DivIcon {
  return L.divIcon({
    className: "",
    html: iconHtml(ac, { sizePx, selected }),
    iconSize: [sizePx, sizePx],
    iconAnchor: [sizePx / 2, sizePx / 2],
  });
}

export function AircraftMap({ receiver }: { receiver: ReceiverInfo }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Map<string, L.Marker>>(new Map());
  const trailsRef = useRef<Map<string, L.Polyline>>(new Map());

  // map bootstrap — once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      center: [receiver.lat, receiver.lon],
      zoom: 9,
      renderer: L.canvas(),
      zoomControl: true,
      attributionControl: false,
    });
    L.tileLayer("/tiles/{z}/{x}/{y}.png", { maxZoom: 12, minZoom: 5 }).addTo(map);

    // receiver + range rings
    L.circleMarker([receiver.lat, receiver.lon], {
      radius: 6, color: "#7dd3fc", fillOpacity: 1,
    }).addTo(map);
    for (const km of receiver.rangeRingsKm) {
      L.circle([receiver.lat, receiver.lon], {
        radius: km * 1000, color: "#334155", weight: 1, fill: false, dashArray: "4 6",
      }).addTo(map);
    }
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // receiver is fetched once before mount — bootstrap deps intentionally empty
  }, []);

  // aircraft sync — subscribe to store outside React's render cycle
  useEffect(() => {
    let lastSelected: string | null = null;
    const sync = () => {
      const map = mapRef.current;
      if (!map) return;
      const sizePx = sizeForZoom(map.getZoom());
      const { aircraft, selectedIcao, select } = useStore.getState();

      // selection changed → pan to the aircraft (tar1090-style)
      if (selectedIcao && selectedIcao !== lastSelected) {
        const sel = aircraft[selectedIcao];
        if (sel?.lat != null && sel.lon != null) {
          map.panTo([sel.lat, sel.lon], { animate: true });
        }
      }
      lastSelected = selectedIcao;
      const markers = markersRef.current;
      const trails = trailsRef.current;

      for (const [icao, marker] of markers) {
        if (!aircraft[icao] || aircraft[icao].lat == null) {
          marker.remove();
          markers.delete(icao);
          trails.get(icao)?.remove();
          trails.delete(icao);
        }
      }
      for (const ac of Object.values(aircraft)) {
        if (ac.lat == null || ac.lon == null) continue;
        const pos: L.LatLngExpression = [ac.lat, ac.lon];
        const selected = ac.icao === selectedIcao;
        let m = markers.get(ac.icao);
        if (!m) {
          m = L.marker(pos, { icon: aircraftIcon(ac, selected, sizePx), keyboard: false });
          m.on("click", () => select(ac.icao));
          m.addTo(map);
          markers.set(ac.icao, m);
        } else {
          m.setLatLng(pos);
          m.setIcon(aircraftIcon(ac, selected, sizePx));
        }
        const trailPts = ac.trail as unknown as [number, number][];
        let t = trails.get(ac.icao);
        if (!t) {
          t = L.polyline(trailPts, { color: "#38bdf8", weight: 1.5, opacity: 0.6 });
          t.addTo(map);
          trails.set(ac.icao, t);
        } else {
          t.setLatLngs(trailPts);
        }
      }
    };
    sync();
    const unsub = useStore.subscribe(sync);
    // re-render icons at the new size when the zoom level settles
    mapRef.current?.on("zoomend", sync);
    return () => {
      mapRef.current?.off("zoomend", sync);
      unsub();
    };
  }, []);

  return <div ref={containerRef} className="map-container" data-testid="aircraft-map" />;
}
