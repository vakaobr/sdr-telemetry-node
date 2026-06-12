import { expect, test } from "vitest";
import { altitudeColor, categoryFor, iconHtml, sizeForZoom } from "./icons";
import type { Aircraft } from "../../types/generated/ws";

test("category by type code", () => {
  expect(categoryFor("A20N")).toBe("airliner");
  expect(categoryFor("B738")).toBe("airliner");
  expect(categoryFor("B77W")).toBe("heavy");
  expect(categoryFor("A388")).toBe("heavy");
  expect(categoryFor("C172")).toBe("ga");
  expect(categoryFor("PC12")).toBe("ga");
  expect(categoryFor("EC35")).toBe("heli");
  expect(categoryFor("R44")).toBe("heli");
  expect(categoryFor(null)).toBe("airliner");     // unknown → sensible default
  expect(categoryFor("ZZZZ")).toBe("airliner");
});

test("altitude color ramp: ground gray, low orange-ish, high violet-ish, capped", () => {
  expect(altitudeColor(0)).toBe("#9ca3af");
  expect(altitudeColor(null)).toBe("#e2e8f0");
  const low = altitudeColor(2000);   // hue ≈ 37
  const mid = altitudeColor(20000);  // hue ≈ 148
  const high = altitudeColor(40000); // hue = 270
  expect(low).toMatch(/^hsl\(3[0-9] /);
  expect(mid).toMatch(/^hsl\(14[0-9] /);
  expect(high).toMatch(/^hsl\(270 /);
  expect(altitudeColor(60000)).toBe(high); // capped at 40k
});

test("zoom size scales with floor and ceiling", () => {
  expect(sizeForZoom(5)).toBe(24);   // floor — stays findable when zoomed out
  expect(sizeForZoom(9)).toBe(32);
  expect(sizeForZoom(12)).toBe(44);  // ceiling
  expect(sizeForZoom(15)).toBe(44);
});

test("iconHtml embeds rotation, size and altitude color", () => {
  const ac = {
    icao: "4951ce", callsign: "TST", lat: 38, lon: -9, altFt: 40000, gsKt: 400,
    vrFpm: 0, track: 215, squawk: "2041", distanceKm: 10, bearingDeg: 0,
    priority: 0, flags: [], enrich: null, trail: [], lastSeen: 1, rssi: -10,
  } as unknown as Aircraft;
  const html = iconHtml(ac, { sizePx: 36, selected: false });
  expect(html).toContain("rotate(215deg)");
  expect(html).toContain('width="36"');
  expect(html).toContain("hsl(270");
});
