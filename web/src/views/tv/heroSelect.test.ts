import { expect, test } from "vitest";
import { HeroSelector, STABLE_UPDATES } from "./heroSelect";
import type { Aircraft } from "../../types/generated/ws";

function plane(icao: string, priority: number, extra: Partial<Aircraft> = {}): Aircraft {
  return {
    icao, callsign: icao.toUpperCase(), lat: 38.8, lon: -9.1, altFt: 10000,
    gsKt: 250, vrFpm: 0, track: 90, squawk: "2041", distanceKm: 10 + priority,
    bearingDeg: 0, priority, flags: [], enrich: null, trail: [], lastSeen: 1, rssi: -20,
    ...extra,
  } as Aircraft;
}

test("first aircraft becomes hero immediately", () => {
  const sel = new HeroSelector();
  expect(sel.update([plane("aaaaaa", 0)])?.icao).toBe("aaaaaa");
});

test("challenger must hold p0 for STABLE_UPDATES before taking over (anti-flap)", () => {
  const sel = new HeroSelector();
  sel.update([plane("aaaaaa", 0)]);
  const challengerFirst = [plane("bbbbbb", 0), plane("aaaaaa", 1)];
  for (let i = 1; i < STABLE_UPDATES; i++) {
    expect(sel.update(challengerFirst)?.icao).toBe("aaaaaa"); // still the incumbent
  }
  expect(sel.update(challengerFirst)?.icao).toBe("bbbbbb");   // now stable → switch
});

test("flapping between two aircraft never switches hero", () => {
  const sel = new HeroSelector();
  sel.update([plane("aaaaaa", 0)]);
  for (let i = 0; i < 10; i++) {
    sel.update([plane("bbbbbb", 0), plane("aaaaaa", 1)]);
    expect(sel.update([plane("aaaaaa", 0), plane("bbbbbb", 1)])?.icao).toBe("aaaaaa");
  }
});

test("hero vanishing promotes p0 immediately", () => {
  const sel = new HeroSelector();
  sel.update([plane("aaaaaa", 0), plane("bbbbbb", 1)]);
  expect(sel.update([plane("bbbbbb", 0)])?.icao).toBe("bbbbbb");
});

test("hero losing position falls back immediately", () => {
  const sel = new HeroSelector();
  sel.update([plane("aaaaaa", 0), plane("bbbbbb", 1)]);
  const lost = plane("aaaaaa", 0, { lat: null, lon: null, distanceKm: null });
  expect(sel.update([lost, plane("bbbbbb", 1)])?.icao).toBe("bbbbbb");
});

test("emergency takes over instantly regardless of streaks", () => {
  const sel = new HeroSelector();
  sel.update([plane("aaaaaa", 0)]);
  const emer = plane("cccccc", 5, { flags: ["emergency"] });
  expect(sel.update([plane("aaaaaa", 0), emer])?.icao).toBe("cccccc");
});

test("empty sky → null hero", () => {
  const sel = new HeroSelector();
  sel.update([plane("aaaaaa", 0)]);
  expect(sel.update([])).toBeNull();
});
