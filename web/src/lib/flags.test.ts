import { expect, test } from "vitest";
import { decorateRoute, flagEmoji, flagForCountryName, flagForMmsi, icaoToCC } from "./flags";

test("flagEmoji builds regional-indicator pairs", () => {
  expect(flagEmoji("PT")).toBe("🇵🇹");
  expect(flagEmoji("fr")).toBe("🇫🇷"); // case-insensitive
  expect(flagEmoji("US")).toBe("🇺🇸");
  expect(flagEmoji("X")).toBe("");     // invalid → empty, never broken glyph
  expect(flagEmoji("")).toBe("");
});

test("country names from enrichment map to flags", () => {
  expect(flagForCountryName("Portugal")).toBe("🇵🇹");
  expect(flagForCountryName("United Kingdom")).toBe("🇬🇧");
  expect(flagForCountryName("Türkiye")).toBe("🇹🇷");
  expect(flagForCountryName("Atlantis")).toBe(""); // unknown → no flag
  expect(flagForCountryName(null)).toBe("");
});

test("ICAO airport prefixes resolve to country codes", () => {
  expect(icaoToCC("LPPT")).toBe("PT"); // Lisbon
  expect(icaoToCC("LFPO")).toBe("FR"); // Paris Orly
  expect(icaoToCC("EGLL")).toBe("GB"); // Heathrow
  expect(icaoToCC("KJFK")).toBe("US"); // single-letter region K
  expect(icaoToCC("CYYZ")).toBe("CA"); // single-letter region C
  expect(icaoToCC("ZBAA")).toBe("CN"); // single-letter region Z
  expect(icaoToCC("XXXX")).toBe("");   // unknown
});

test("flagForMmsi maps the MID (first 3 digits) to a flag", () => {
  expect(flagForMmsi(263422760)).toBe("🇵🇹"); // Portugal
  expect(flagForMmsi(636020815)).toBe("🇱🇷"); // Liberia (flag of convenience)
  expect(flagForMmsi(245413000)).toBe("🇳🇱"); // Netherlands
  expect(flagForMmsi(338123456)).toBe("🇺🇸"); // USA
  expect(flagForMmsi(999000000)).toBe(""); // unknown MID → no flag
});

test("decorateRoute appends flags per airport", () => {
  expect(decorateRoute("LPPT → LFPO")).toBe("LPPT 🇵🇹 → LFPO 🇫🇷");
  expect(decorateRoute("LPPT → QXYZ")).toBe("LPPT 🇵🇹 → QXYZ"); // Q* unmapped → no flag
  expect(decorateRoute(null)).toBe("");
  expect(decorateRoute("weird format")).toBe("weird format"); // not two tokens → as-is
});
