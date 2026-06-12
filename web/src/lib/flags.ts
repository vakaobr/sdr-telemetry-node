/**
 * Country flags for the hero/detail views.
 *  - flagEmoji(cc): ISO-3166 alpha-2 → 🇵🇹 (regional-indicator pair)
 *  - flagForCountryName: maps the enrichment's country names → alpha-2
 *  - icaoToCC / decorateRoute: maps ICAO airport prefixes → country, so a
 *    route "LPPT → LFPO" renders "LPPT 🇵🇹 → LFPO 🇫🇷" (FR-8.1 polish).
 * Unknown inputs degrade to no flag — never a broken glyph (UX #4).
 */

export function flagEmoji(cc: string): string {
  if (!/^[A-Za-z]{2}$/.test(cc)) return "";
  const A = 0x1f1e6;
  return String.fromCodePoint(
    A + cc.toUpperCase().charCodeAt(0) - 65,
    A + cc.toUpperCase().charCodeAt(1) - 65,
  );
}

// Names exactly as emitted by the gateway's staticdata.country_for_hex.
const COUNTRY_NAME_TO_CC: Record<string, string> = {
  Zimbabwe: "ZW", Mozambique: "MZ", "South Africa": "ZA", Egypt: "EG", Libya: "LY",
  Morocco: "MA", Tunisia: "TN", Algeria: "DZ", Russia: "RU", Cameroon: "CM",
  Italy: "IT", Spain: "ES", France: "FR", Germany: "DE", "United Kingdom": "GB",
  Austria: "AT", Belgium: "BE", Bulgaria: "BG", Denmark: "DK", Finland: "FI",
  Greece: "GR", Hungary: "HU", Norway: "NO", Netherlands: "NL", Poland: "PL",
  Portugal: "PT", Czechia: "CZ", Romania: "RO", Sweden: "SE", Switzerland: "CH",
  "Türkiye": "TR", Serbia: "RS", Cyprus: "CY", Ireland: "IE", Iceland: "IS",
  Luxembourg: "LU", "San Marino": "SM", Albania: "AL", Croatia: "HR", Latvia: "LV",
  Lithuania: "LT", Moldova: "MD", Slovakia: "SK", Slovenia: "SI", Ukraine: "UA",
  Armenia: "AM", Azerbaijan: "AZ", Georgia: "GE", Turkmenistan: "TM",
  Afghanistan: "AF", Bangladesh: "BD", "South Korea": "KR", Iraq: "IQ", Iran: "IR",
  Israel: "IL", Jordan: "JO", Lebanon: "LB", Malaysia: "MY", Philippines: "PH",
  Pakistan: "PK", Singapore: "SG", "Sri Lanka": "LK", Syria: "SY", China: "CN",
  Australia: "AU", India: "IN", Japan: "JP", Thailand: "TH", "Viet Nam": "VN",
  Yemen: "YE", "United Arab Emirates": "AE", Bahrain: "BH", Kuwait: "KW", Oman: "OM",
  Qatar: "QA", "Saudi Arabia": "SA", Indonesia: "ID", "United States": "US",
  Canada: "CA", "New Zealand": "NZ", Argentina: "AR", Brazil: "BR", Chile: "CL",
  Ecuador: "EC", Paraguay: "PY", Peru: "PE", Uruguay: "UY", Venezuela: "VE",
  Mexico: "MX",
};

export function flagForCountryName(name: string | null | undefined): string {
  if (!name) return "";
  return flagEmoji(COUNTRY_NAME_TO_CC[name] ?? "");
}

// ICAO location-indicator prefixes → ISO alpha-2 (2-letter first, then 1-letter
// regions). Focused on what a European receiver actually sees; misses → no flag.
const ICAO_PREFIX_TO_CC: Record<string, string> = {
  // Europe
  LP: "PT", LE: "ES", GC: "ES", LF: "FR", EG: "GB", EI: "IE", ED: "DE", ET: "DE",
  EH: "NL", EB: "BE", EL: "LU", LS: "CH", LO: "AT", EK: "DK", ES: "SE", EN: "NO",
  EF: "FI", BI: "IS", LI: "IT", LG: "GR", LT: "TR", LM: "MT", LC: "CY", EP: "PL",
  LK: "CZ", LZ: "SK", LJ: "SI", LD: "HR", LH: "HU", LR: "RO", LB: "BG", LA: "AL",
  LW: "MK", LU: "MD", LQ: "BA", LY: "RS", BK: "XK",
  // Eastern Europe / Caucasus
  UK: "UA", UB: "AZ", UD: "AM", UG: "GE", UM: "BY",
  // Africa (Lisbon sees N/W Africa)
  GM: "MA", DT: "TN", DA: "DZ", HL: "LY", HE: "EG", FA: "ZA", GO: "SN", GV: "CV",
  DN: "NG", DG: "GH", GU: "GN", GF: "SL", FN: "AO",
  // Middle East
  OM: "AE", OE: "SA", OB: "BH", OK: "KW", OO: "OM", OT: "QA", OI: "IR", OJ: "JO",
  OL: "LB", OS: "SY", OR: "IQ", OP: "PK", OY: "YE",
  // Asia / Pacific
  RK: "KR", RJ: "JP", RO: "JP", RC: "TW", RP: "PH", VT: "TH", VV: "VN", VD: "KH",
  VL: "LA", VY: "MM", VC: "LK", VG: "BD", VN: "NP", VA: "IN", VE: "IN", VI: "IN",
  VO: "IN", WS: "SG", WM: "MY", WB: "MY", WI: "ID", WA: "ID", WR: "ID", WQ: "ID",
  ZK: "KP", ZM: "MN", NZ: "NZ",
  // Americas
  SA: "AR", SB: "BR", SD: "BR", SI: "BR", SJ: "BR", SS: "BR", SW: "BR", SC: "CL",
  SE: "EC", SG: "PY", SP: "PE", SU: "UY", SV: "VE", SK: "CO", MM: "MX", MP: "PA",
  MR: "CR", MD: "DO", MU: "CU", MK: "JM", TJ: "PR",
};

// single-letter regions resolved by first char only
const ICAO_SINGLE_TO_CC: Record<string, string> = { K: "US", C: "CA", Y: "AU", Z: "CN" };

export function icaoToCC(code: string): string {
  const c = code.trim().toUpperCase();
  if (c.length < 2) return "";
  return ICAO_PREFIX_TO_CC[c.slice(0, 2)] ?? ICAO_SINGLE_TO_CC[c[0]] ?? "";
}

/** "LPPT → LFPO" → "LPPT 🇵🇹 → LFPO 🇫🇷" (flags appended where known). */
export function decorateRoute(route: string | null | undefined): string {
  if (!route) return "";
  const parts = route.split("→").map((s) => s.trim());
  if (parts.length !== 2) return route; // unexpected shape → show as-is
  return parts
    .map((code) => {
      const flag = flagEmoji(icaoToCC(code));
      return flag ? `${code} ${flag}` : code;
    })
    .join(" → ");
}
