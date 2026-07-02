/** Store reducer correctness + reconnect snapshot-merge semantics (P4 tests). */
import { beforeEach, expect, test } from "vitest";
import { sortedAircraft, useStore } from "./store";
import type { Aircraft, Radio2Status, ServerMessage, SystemHealth } from "../types/generated/ws";

const radio2: Radio2Status = {
  mode: "offline", since: 0, reason: "lwt", nextPass: null, audioUrl: null, tleAgeDays: 0,
};
const health: SystemHealth = {
  nodeA: { ok: true, cpuPct: 5, memMb: 300, tempC: 50, throttled: false, diskFreePct: 90 },
  nodeB: null,
  adsb: { ok: true, msgRate: 100, aircraftCount: 1, maxRangeKm: 100 },
  dbOk: true,
};

function plane(icao: string, priority = 0): Aircraft {
  return {
    icao, callsign: "TST", lat: 38.8, lon: -9.1, altFt: 10000, gsKt: 250, vrFpm: 0,
    track: 90, squawk: "2041", distanceKm: 10, bearingDeg: 180, priority,
    flags: [], enrich: null, trail: [[38.8, -9.1]], lastSeen: 1000, rssi: -20,
  };
}

function snapshot(...aircraft: Aircraft[]): ServerMessage {
  return { type: "snapshot", ts: 1000, aircraft, vessels: [], radio2, latestPass: null, health };
}

beforeEach(() => {
  useStore.setState({
    aircraft: {}, vessels: {}, radio2: null, health: null, latestPass: null,
    alerts: [], selectedIcao: null, connected: false, lastMessageTs: 0,
  });
});

test("snapshot replaces state authoritatively", () => {
  const apply = useStore.getState().applyServer;
  apply(snapshot(plane("aaaaaa"), plane("bbbbbb", 1)));
  expect(Object.keys(useStore.getState().aircraft)).toEqual(["aaaaaa", "bbbbbb"]);

  // reconnect scenario: a new snapshot must drop aircraft that vanished meanwhile
  apply(snapshot(plane("cccccc")));
  expect(Object.keys(useStore.getState().aircraft)).toEqual(["cccccc"]);
  expect(useStore.getState().radio2?.mode).toBe("offline");
  expect(useStore.getState().health?.adsb.ok).toBe(true);
});

test("aircraft_delta merges updates and removes", () => {
  const apply = useStore.getState().applyServer;
  apply(snapshot(plane("aaaaaa"), plane("bbbbbb", 1)));
  apply({
    type: "aircraft_delta", ts: 1001,
    updated: [{ ...plane("aaaaaa"), altFt: 12000 }],
    removed: ["bbbbbb"],
  });
  const s = useStore.getState();
  expect(s.aircraft["aaaaaa"].altFt).toBe(12000);
  expect(s.aircraft["bbbbbb"]).toBeUndefined();
  expect(s.lastMessageTs).toBe(1001);
});

test("selection cleared when selected aircraft is removed", () => {
  const apply = useStore.getState().applyServer;
  apply(snapshot(plane("aaaaaa")));
  useStore.getState().select("aaaaaa");
  apply({ type: "aircraft_delta", ts: 1001, updated: [], removed: ["aaaaaa"] });
  expect(useStore.getState().selectedIcao).toBeNull();
});

test("interesting alerts prepend and cap at 20", () => {
  const apply = useStore.getState().applyServer;
  for (let i = 0; i < 25; i++) {
    apply({
      type: "interesting", ts: i, icao: "aaaaaa",
      severity: i % 2 ? "critical" : "notable", rule: `r${i}`, callsign: null,
    });
  }
  const alerts = useStore.getState().alerts;
  expect(alerts).toHaveLength(20);
  expect(alerts[0].rule).toBe("r24"); // newest first
});

test("selecting a vessel clears aircraft selection and vice versa", () => {
  const { select, selectVessel } = useStore.getState();
  select("aaaaaa");
  expect(useStore.getState().selectedIcao).toBe("aaaaaa");
  selectVessel(12345);
  expect(useStore.getState().selectedMmsi).toBe(12345);
  expect(useStore.getState().selectedIcao).toBeNull(); // mutually exclusive
  select("bbbbbb");
  expect(useStore.getState().selectedMmsi).toBeNull();
});

test("removing the selected vessel clears its selection", () => {
  const apply = useStore.getState().applyServer;
  apply({
    type: "vessel_delta", ts: 1,
    updated: [{ mmsi: 999, name: "X", lat: 38, lon: -9, sogKt: null, cogDeg: null, shipType: null, lastSeen: 1 }],
    removed: [],
  });
  useStore.getState().selectVessel(999);
  apply({ type: "vessel_delta", ts: 2, updated: [], removed: [999] });
  expect(useStore.getState().selectedMmsi).toBeNull();
});

test("vessels-visible toggle persists to localStorage", () => {
  localStorage.removeItem("sdr.vesselsVisible");
  useStore.getState().setVesselsVisible(false);
  expect(useStore.getState().vesselsVisible).toBe(false);
  expect(localStorage.getItem("sdr.vesselsVisible")).toBe("0");
});

test("airspace overlay toggle persists to localStorage", () => {
  localStorage.removeItem("sdr.airspaceOverlay");
  useStore.getState().setAirspaceOverlay(true);
  expect(useStore.getState().airspaceOverlay).toBe(true);
  expect(localStorage.getItem("sdr.airspaceOverlay")).toBe("1");
  useStore.getState().setAirspaceOverlay(false);
  expect(localStorage.getItem("sdr.airspaceOverlay")).toBe("0");
});

test("sortedAircraft orders by priority", () => {
  const list = sortedAircraft({
    bbbbbb: plane("bbbbbb", 2),
    aaaaaa: plane("aaaaaa", 0),
    cccccc: plane("cccccc", 1),
  });
  expect(list.map((a) => a.icao)).toEqual(["aaaaaa", "cccccc", "bbbbbb"]);
});
