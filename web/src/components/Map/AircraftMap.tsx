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
import type { Aircraft, Vessel } from "../../types/generated/ws";
import { flagForMmsi } from "../../lib/flags";
import { iconHtml, sizeForZoom } from "./icons";
import "./map.css";

function vesselIcon(v: Vessel, selected: boolean): L.DivIcon {
  // teal chevron pointing along course-over-ground; distinct from aircraft
  const rot = v.cogDeg ?? 0;
  return L.divIcon({
    className: "",
    html: `<div class="vessel-icon${selected ? " vessel-selected" : ""}" style="transform: rotate(${rot}deg)">▲</div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

export interface ReceiverInfo {
  lat: number;
  lon: number;
  rangeRingsKm: number[];
  tvRotation?: string[];
  airspaceAvailable?: boolean; // gateway has an OpenAIP key (R2)
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
  const vesselsRef = useRef<Map<number, L.Marker>>(new Map());
  const airspaceRef = useRef<L.TileLayer | null>(null);
  const airspaceOn = useStore((s) => s.airspaceOverlay);

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
    L.tileLayer("/tiles/{z}/{x}/{y}.png", {
      maxZoom: 12,
      minZoom: 5,
      className: "base-tiles", // dark filter scoped to this layer only (see map.css)
    }).addTo(map);

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
    let lastSelectedMmsi: number | null = null;
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

      // vessels (AIS) — distinct teal ship markers; clickable, toggleable layer
      const { vessels, vesselsVisible, selectedMmsi, selectVessel } = useStore.getState();
      if (selectedMmsi && selectedMmsi !== lastSelectedMmsi) {
        const sv = vessels[selectedMmsi];
        if (sv) map.panTo([sv.lat, sv.lon], { animate: true });
      }
      lastSelectedMmsi = selectedMmsi;
      const vmarkers = vesselsRef.current;
      for (const [mmsi, marker] of vmarkers) {
        if (!vesselsVisible || !vessels[mmsi]) {
          marker.remove();
          vmarkers.delete(mmsi);
        }
      }
      if (vesselsVisible) {
        for (const v of Object.values(vessels)) {
          const pos: L.LatLngExpression = [v.lat, v.lon];
          const selected = v.mmsi === selectedMmsi;
          let m = vmarkers.get(v.mmsi);
          if (!m) {
            m = L.marker(pos, {
              icon: vesselIcon(v, selected),
              keyboard: false,
              zIndexOffset: -1000,
            });
            m.bindTooltip(`${flagForMmsi(v.mmsi)} ${v.name ?? v.mmsi}`.trim(), {
              direction: "top",
            });
            m.on("click", () => selectVessel(v.mmsi));
            m.addTo(map);
            vmarkers.set(v.mmsi, m);
          } else {
            m.setLatLng(pos);
            m.setIcon(vesselIcon(v, selected));
          }
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

  // OpenAIP airspace overlay (R2) — add/remove on toggle; gateway-proxied so the
  // API key stays server-side, region-cached so it works offline after first view
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const show = airspaceOn && receiver.airspaceAvailable;
    if (show && !airspaceRef.current) {
      airspaceRef.current = L.tileLayer("/tiles/openaip/{z}/{x}/{y}.png", {
        maxZoom: 14,
        opacity: 1, // native OpenAIP colors; visibility boosted via CSS (map.css)
        className: "airspace-tiles",
        // sits in the tile pane: above the base map, below aircraft markers
      });
      airspaceRef.current.addTo(map);
    } else if (!show && airspaceRef.current) {
      airspaceRef.current.remove();
      airspaceRef.current = null;
    }
  }, [airspaceOn, receiver.airspaceAvailable]);

  return <div ref={containerRef} className="map-container" data-testid="aircraft-map" />;
}
