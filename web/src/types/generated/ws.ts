/* AUTO-GENERATED from shared/schemas — do not edit. Run scripts/codegen.sh */

/**
 * WebSocket protocol between gateway and browser clients. Source of truth: 03_PROJECT_SPEC §3.1.
 */
export type WsMessages = ServerMessage | ClientMessage;
export type ServerMessage =
  | SnapshotMessage
  | AircraftDeltaMessage
  | VesselDeltaMessage
  | Radio2StatusMessage
  | AtcActivityMessage
  | InterestingMessage
  | PassUpdateMessage
  | SystemHealthMessage;
export type ClientMessage = SubscribeMessage | PingMessage;

export interface SnapshotMessage {
  type: "snapshot";
  ts: number;
  aircraft: Aircraft[];
  vessels: Vessel[];
  radio2: Radio2Status;
  latestPass: PassSummary | null;
  health: SystemHealth;
}
export interface Aircraft {
  icao: string;
  callsign?: string | null;
  lat?: number | null;
  lon?: number | null;
  altFt?: number | null;
  gsKt?: number | null;
  vrFpm?: number | null;
  track?: number | null;
  squawk?: string | null;
  distanceKm?: number | null;
  bearingDeg?: number | null;
  priority: number;
  flags: ("military" | "emergency" | "watchlist")[];
  enrich?: Enrichment | null;
  /**
   * @maxItems 100
   */
  trail: [number, number][];
  /**
   * unix seconds
   */
  lastSeen: number;
  rssi?: number | null;
}
export interface Enrichment {
  registration?: string | null;
  typeCode?: string | null;
  typeName?: string | null;
  operator?: string | null;
  country?: string | null;
  route?: string | null;
  photoUrl?: string | null;
}
export interface Vessel {
  mmsi: number;
  name?: string | null;
  lat: number;
  lon: number;
  sogKt?: number | null;
  cogDeg?: number | null;
  shipType?: number | null;
  lastSeen: number;
}
export interface Radio2Status {
  mode: "atc" | "ais" | "satellite" | "idle" | "faulted" | "offline";
  since: number;
  reason: "schedule" | "preempt" | "manual" | "fault" | "lwt";
  nextPass: NextPass | null;
  audioUrl: string | null;
  tleAgeDays: number;
}
export interface NextPass {
  satellite: string;
  aos: number;
  los: number;
  maxEl: number;
}
export interface PassSummary {
  id: number;
  satellite: string;
  aos: number;
  los: number;
  maxElevation: number;
  status: "scheduled" | "captured" | "decoded" | "failed";
  imageUrls: string[];
}
export interface SystemHealth {
  nodeA: NodeHealth;
  /**
   * null = offline (MQTT LWT fired)
   */
  nodeB: NodeHealth | null;
  adsb: AdsbHealth;
  dbOk: boolean;
}
export interface NodeHealth {
  ok: boolean;
  cpuPct: number;
  memMb: number;
  tempC: number;
  throttled: boolean;
  diskFreePct: number;
}
export interface AdsbHealth {
  ok: boolean;
  msgRate: number;
  aircraftCount: number;
  maxRangeKm: number;
}
export interface AircraftDeltaMessage {
  type: "aircraft_delta";
  ts: number;
  updated: Aircraft[];
  removed: string[];
}
export interface VesselDeltaMessage {
  type: "vessel_delta";
  ts: number;
  updated: Vessel[];
  removed: number[];
}
export interface Radio2StatusMessage {
  type: "radio2_status";
  ts: number;
  status: Radio2Status;
}
export interface AtcActivityMessage {
  type: "atc_activity";
  ts: number;
  channelMhz: number;
  active: boolean;
}
export interface InterestingMessage {
  type: "interesting";
  ts: number;
  icao: string;
  severity: "critical" | "notable";
  rule: string;
  callsign: string | null;
}
export interface PassUpdateMessage {
  type: "pass_update";
  ts: number;
  pass: PassSummary;
}
export interface SystemHealthMessage {
  type: "system_health";
  ts: number;
  health: SystemHealth;
}
export interface SubscribeMessage {
  type: "subscribe";
  topics: ("aircraft" | "vessels" | "radio2" | "system")[];
}
export interface PingMessage {
  type: "ping";
  ts: number;
}
