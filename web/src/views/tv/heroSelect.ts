/**
 * Hero selection with hysteresis (FR-8.1, P6 anti-flap requirement).
 *
 * The hero is the priority-0 aircraft — but two aircraft trading p0 every
 * second would make the wall display flap. Rules:
 *  - no current hero → take p0 immediately
 *  - current hero gone (or lost its position) → take p0 immediately
 *  - an EMERGENCY-flagged aircraft → takes over immediately (UX: only loud thing)
 *  - otherwise a challenger must hold p0 for STABLE_UPDATES consecutive
 *    updates before it replaces the current hero
 */
import type { Aircraft } from "../../types/generated/ws";

export const STABLE_UPDATES = 3;

export class HeroSelector {
  private current: string | null = null;
  private challenger: string | null = null;
  private challengerStreak = 0;

  /** Feed the priority-sorted aircraft list; returns the hero (or null). */
  update(sorted: Aircraft[]): Aircraft | null {
    const candidate = sorted.find((a) => a.lat != null) ?? null;
    const byIcao = new Map(sorted.map((a) => [a.icao, a]));

    const emergency = sorted.find((a) => a.flags.includes("emergency") && a.lat != null);
    if (emergency) {
      this.current = emergency.icao;
      this.challenger = null;
      this.challengerStreak = 0;
      return emergency;
    }

    const currentAc = this.current ? byIcao.get(this.current) : undefined;
    if (!currentAc || currentAc.lat == null) {
      this.current = candidate?.icao ?? null;
      this.challenger = null;
      this.challengerStreak = 0;
      return candidate;
    }

    if (candidate && candidate.icao !== this.current) {
      if (this.challenger === candidate.icao) {
        this.challengerStreak += 1;
      } else {
        this.challenger = candidate.icao;
        this.challengerStreak = 1;
      }
      if (this.challengerStreak >= STABLE_UPDATES) {
        this.current = candidate.icao;
        this.challenger = null;
        this.challengerStreak = 0;
        return candidate;
      }
    } else {
      this.challenger = null;
      this.challengerStreak = 0;
    }
    return currentAc;
  }
}
