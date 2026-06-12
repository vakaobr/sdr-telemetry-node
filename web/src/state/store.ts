/**
 * Central client state, fed exclusively by WS messages (03_ARCHITECTURE §2).
 * One reducer (`applyServer`) maps every ServerMessage onto the store —
 * the only write path, so reconnect/snapshot semantics live in one place.
 */
import { create } from "zustand";
import type {
  Aircraft,
  Radio2Status,
  PassSummary,
  ServerMessage,
  SystemHealth,
  Vessel,
} from "../types/generated/ws";

export interface InterestingAlert {
  ts: number;
  icao: string;
  severity: "critical" | "notable";
  rule: string;
  callsign: string | null;
}

export interface AppState {
  connected: boolean;
  lastMessageTs: number;
  aircraft: Record<string, Aircraft>;
  vessels: Record<number, Vessel>;
  radio2: Radio2Status | null;
  health: SystemHealth | null;
  latestPass: PassSummary | null;
  alerts: InterestingAlert[]; // newest first, capped
  selectedIcao: string | null;
  selectedMmsi: number | null; // selected vessel (mutually exclusive w/ aircraft)
  atcActive: boolean; // squelch-open pulse (FR-5.3)
  atcActiveTs: number;
  airspaceOverlay: boolean; // OpenAIP overlay toggle (R2), persisted per device
  vesselsVisible: boolean; // AIS layer toggle, persisted per device

  setConnected: (c: boolean) => void;
  applyServer: (msg: ServerMessage) => void;
  select: (icao: string | null) => void;
  selectVessel: (mmsi: number | null) => void;
  setAirspaceOverlay: (on: boolean) => void;
  setVesselsVisible: (on: boolean) => void;
}

const MAX_ALERTS = 20;
const AIRSPACE_KEY = "sdr.airspaceOverlay";
const VESSELS_KEY = "sdr.vesselsVisible";

function loadBoolPref(key: string): boolean {
  try {
    const v = localStorage.getItem(key);
    return v === null ? true : v === "1"; // on by default; respects explicit toggle-off
  } catch {
    return true;
  }
}

export const useStore = create<AppState>((set) => ({
  connected: false,
  lastMessageTs: 0,
  aircraft: {},
  vessels: {},
  radio2: null,
  health: null,
  latestPass: null,
  alerts: [],
  selectedIcao: null,
  selectedMmsi: null,
  atcActive: false,
  atcActiveTs: 0,
  airspaceOverlay: loadBoolPref(AIRSPACE_KEY),
  vesselsVisible: loadBoolPref(VESSELS_KEY),

  setConnected: (c) => set({ connected: c }),
  select: (icao) => set({ selectedIcao: icao, selectedMmsi: null }),
  selectVessel: (mmsi) => set({ selectedMmsi: mmsi, selectedIcao: null }),
  setVesselsVisible: (on) => {
    try {
      localStorage.setItem(VESSELS_KEY, on ? "1" : "0");
    } catch {
      /* no storage */
    }
    set({ vesselsVisible: on });
  },
  setAirspaceOverlay: (on) => {
    try {
      localStorage.setItem(AIRSPACE_KEY, on ? "1" : "0");
    } catch {
      /* private mode / no storage — keep in memory only */
    }
    set({ airspaceOverlay: on });
  },

  applyServer: (msg) =>
    set((s) => {
      switch (msg.type) {
        case "snapshot": {
          // authoritative replace — this is what makes reconnect safe
          const aircraft: Record<string, Aircraft> = {};
          for (const a of msg.aircraft) aircraft[a.icao] = a;
          const vessels: Record<number, Vessel> = {};
          for (const v of msg.vessels) vessels[v.mmsi] = v;
          return {
            lastMessageTs: msg.ts,
            aircraft,
            vessels,
            radio2: msg.radio2,
            health: msg.health,
            latestPass: msg.latestPass,
          };
        }
        case "aircraft_delta": {
          const aircraft = { ...s.aircraft };
          for (const a of msg.updated) aircraft[a.icao] = a;
          for (const icao of msg.removed) delete aircraft[icao];
          const selectedIcao =
            s.selectedIcao && !aircraft[s.selectedIcao] ? null : s.selectedIcao;
          return { lastMessageTs: msg.ts, aircraft, selectedIcao };
        }
        case "vessel_delta": {
          const vessels = { ...s.vessels };
          for (const v of msg.updated) vessels[v.mmsi] = v;
          for (const mmsi of msg.removed) delete vessels[mmsi];
          const selectedMmsi =
            s.selectedMmsi && !vessels[s.selectedMmsi] ? null : s.selectedMmsi;
          return { lastMessageTs: msg.ts, vessels, selectedMmsi };
        }
        case "radio2_status":
          return { lastMessageTs: msg.ts, radio2: msg.status };
        case "system_health":
          return { lastMessageTs: msg.ts, health: msg.health };
        case "pass_update":
          return { lastMessageTs: msg.ts, latestPass: msg.pass };
        case "interesting": {
          const alert: InterestingAlert = {
            ts: msg.ts,
            icao: msg.icao,
            severity: msg.severity,
            rule: msg.rule,
            callsign: msg.callsign,
          };
          return {
            lastMessageTs: msg.ts,
            alerts: [alert, ...s.alerts].slice(0, MAX_ALERTS),
          };
        }
        case "atc_activity":
          return { lastMessageTs: msg.ts, atcActive: msg.active, atcActiveTs: msg.ts };
        default:
          return {};
      }
    }),
}));

/** Priority-sorted aircraft list (selector helper). */
export function sortedAircraft(aircraft: Record<string, Aircraft>): Aircraft[] {
  return Object.values(aircraft).sort((a, b) => a.priority - b.priority);
}
