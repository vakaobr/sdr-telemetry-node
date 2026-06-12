/* AUTO-GENERATED from shared/schemas — do not edit. Run scripts/codegen.sh */

/**
 * MQTT topic payloads. Topic tree: 03_ARCHITECTURE §5. All payloads carry ts (unix s); consumers are idempotent (QoS 1 = at-least-once).
 */
export type MqttPayloads =
  | Radio2Mode
  | Radio2PassNext
  | Radio2Health
  | Radio2Command
  | AtcActivity
  | AisVessel
  | SatellitePassEvent
  | SysHealth
  | AdsbInteresting;

/**
 * topic: radio2/mode (retained, QoS1)
 */
export interface Radio2Mode {
  ts: number;
  mode: "atc" | "ais" | "satellite" | "idle" | "faulted";
  since: number;
  reason: "schedule" | "preempt" | "manual" | "fault" | "boot";
  pid?: number | null;
}
/**
 * topic: radio2/pass/next (retained, QoS1); payload may be null-equivalent via satellite:null when no pass scheduled
 */
export interface Radio2PassNext {
  ts: number;
  satellite: string | null;
  aos: number | null;
  los: number | null;
  maxEl: number | null;
}
/**
 * topic: radio2/health (retained, QoS1, LWT sets ok:false reason:offline)
 */
export interface Radio2Health {
  ts: number;
  ok: boolean;
  decoder?: string | null;
  uptimeS?: number | null;
  reason?: string | null;
  tleAgeDays?: number | null;
}
/**
 * topic: radio2/cmd (QoS1, not retained) — gateway-issued manual override
 */
export interface Radio2Command {
  ts: number;
  mode: "atc" | "ais" | "satellite" | "idle" | "auto";
  durationS?: number | null;
  force?: boolean;
}
/**
 * topic: atc/activity (QoS0)
 */
export interface AtcActivity {
  ts: number;
  channelMhz: number;
  active: boolean;
}
/**
 * topic: ais/vessel (QoS0)
 */
export interface AisVessel {
  ts: number;
  mmsi: number;
  lat: number;
  lon: number;
  sogKt?: number | null;
  cogDeg?: number | null;
  name?: string | null;
  shipType?: number | null;
}
/**
 * topic: satellite/pass/event (QoS1)
 */
export interface SatellitePassEvent {
  ts: number;
  passId: number;
  satellite: string;
  status: "scheduled" | "capturing" | "captured" | "decoding" | "decoded" | "failed";
  images?: string[];
  note?: string | null;
}
/**
 * topic: sys/{node}/health (retained, QoS1, LWT sets ok:false)
 */
export interface SysHealth {
  ts: number;
  ok: boolean;
  cpuPct: number;
  memMb: number;
  tempC: number;
  throttled: boolean;
  diskFreePct: number;
}
/**
 * topic: adsb/interesting (QoS1)
 */
export interface AdsbInteresting {
  ts: number;
  icao: string;
  severity: "critical" | "notable";
  rule: string;
  callsign?: string | null;
}
