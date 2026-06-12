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

// MMSI MID (first 3 digits) → ISO alpha-2 (ITU Maritime Identification Digits).
// Europe + common flags-of-convenience + major maritime nations; misses → no flag.
const MID_TO_CC: Record<string, string> = {
  "201": "AL", "202": "AD", "203": "AT", "204": "PT", "205": "BE", "206": "BY",
  "207": "BG", "209": "CY", "210": "CY", "211": "DE", "212": "CY", "213": "GE",
  "214": "MD", "215": "MT", "218": "DE", "219": "DK", "220": "DK", "224": "ES",
  "225": "ES", "226": "FR", "227": "FR", "228": "FR", "229": "MT", "230": "FI",
  "231": "FO", "232": "GB", "233": "GB", "234": "GB", "235": "GB", "236": "GI",
  "237": "GR", "238": "HR", "239": "GR", "240": "GR", "241": "GR", "242": "MA",
  "243": "HU", "244": "NL", "245": "NL", "246": "NL", "247": "IT", "248": "MT",
  "249": "MT", "250": "IE", "251": "IS", "252": "LI", "253": "LU", "254": "MC",
  "255": "PT", "256": "MT", "257": "NO", "258": "NO", "259": "NO", "261": "PL",
  "262": "ME", "263": "PT", "264": "RO", "265": "SE", "266": "SE", "267": "SK",
  "268": "SM", "269": "CH", "271": "TR", "272": "UA", "273": "RU", "274": "MK",
  "304": "AG", "305": "AG", "306": "CW", "308": "BS", "309": "BS", "310": "BM",
  "311": "BS", "312": "BZ", "316": "CA", "319": "KY", "338": "US", "366": "US",
  "367": "US", "368": "US", "369": "US", "351": "PA", "352": "PA", "353": "PA",
  "354": "PA", "355": "PA", "356": "PA", "357": "PA", "370": "PA", "371": "PA",
  "372": "PA", "373": "PA", "374": "PA", "412": "CN", "413": "CN", "414": "CN",
  "416": "TW", "431": "JP", "432": "JP", "440": "KR", "441": "KR", "477": "HK",
  "525": "ID", "538": "MH", "563": "SG", "564": "SG", "565": "SG", "566": "SG",
  "636": "LR", "637": "LR", "710": "BR", "725": "CL",
};

/** MMSI → flag of the vessel's registry (first 3 digits = ITU MID). */
export function flagForMmsi(mmsi: number): string {
  const mid = String(mmsi).padStart(9, "0").slice(0, 3);
  return flagEmoji(MID_TO_CC[mid] ?? "");
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
