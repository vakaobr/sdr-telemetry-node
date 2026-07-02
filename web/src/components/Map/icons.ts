/**
 * Aircraft map iconography (tar1090-inspired):
 *  - silhouette by type category (from enrichment typeCode)
 *  - fill color by barometric altitude (ground → gray, low → orange … high → violet)
 *  - size scales with map zoom (with a readable floor)
 */
import type { Aircraft } from "../../types/generated/ws";

export type Category = "airliner" | "heavy" | "ga" | "heli";

const HELI_TYPES = new Set([
  "EC35", "EC45", "EC75", "AS50", "S92", "AW39", "AW09", "AW19", "A109", "A139",
  "R44", "R66", "B06", "B412", "B429", "H60", "EH10", "MI8", "KA32", "EC20",
  "EC30", "EC55", "EC65", "S76", "B505",
]);

const HEAVY_TYPES = new Set([
  "A332", "A333", "A338", "A339", "A342", "A343", "A345", "A346", "A359", "A35K",
  "A388", "B742", "B744", "B748", "B762", "B763", "B764", "B772", "B77L", "B773",
  "B77W", "B778", "B779", "B788", "B789", "B78X", "MD11", "A124", "A225", "C17",
  "C5M", "A400", "K35R", "B52",
]);

// light GA / small props / trainers / bizjets-small
const GA_PREFIXES = ["C1", "C2", "P28", "PA", "DA4", "DV2", "SR2", "DR4", "BE", "TBM", "PC1", "RV", "GLID"];
const GA_TYPES = new Set([
  "C172", "C152", "C182", "C208", "P28A", "PA34", "DA40", "DA42", "DV20",
  "SR20", "SR22", "DR40", "BE20", "BE9L", "B350", "BE58", "PC12", "TBM9",
  "C510", "C525", "E50P", "SF34", "D228", "JS41",
]);

export function categoryFor(typeCode: string | null | undefined): Category {
  if (!typeCode) return "airliner";
  const t = typeCode.toUpperCase();
  if (HELI_TYPES.has(t)) return "heli";
  if (HEAVY_TYPES.has(t)) return "heavy";
  if (GA_TYPES.has(t) || GA_PREFIXES.some((p) => t.startsWith(p))) return "ga";
  return "airliner";
}

/** Ground → gray; 0–40k ft ramps orange → violet (tar1090-style readability on dark). */
export function altitudeColor(altFt: number | null | undefined): string {
  if (altFt == null) return "#e2e8f0";
  if (altFt <= 50) return "#9ca3af"; // on/near ground
  const t = Math.min(altFt, 40000) / 40000;
  const hue = 25 + t * 245; // 25 (orange) → 270 (violet)
  return `hsl(${hue.toFixed(0)} 85% 62%)`;
}

/** Icon px size for a given map zoom — grows when zooming in, readable floor. */
export function sizeForZoom(zoom: number): number {
  return Math.round(Math.min(44, Math.max(24, 24 + (zoom - 7) * 4)));
}

// silhouettes on a 64×64 viewBox, nose pointing up (north / track 0°)
const PATHS: Record<Category, string> = {
  airliner:
    "M32 4 L36 14 L36 24 L58 36 L58 41 L36 33 L36 48 L44 54 L44 58 L32 55 L20 58 L20 54 L28 48 L28 33 L6 41 L6 36 L28 24 L28 14 Z",
  heavy:
    "M32 2 L37 12 L37 22 L62 37 L62 43 L37 34 L37 48 L47 55 L47 59 L32 56 L17 59 L17 55 L27 48 L27 34 L2 43 L2 37 L27 22 L27 12 Z",
  ga:
    "M32 6 L35 16 L35 26 L56 26 L56 33 L35 33 L34 48 L42 52 L42 56 L32 54 L22 56 L22 52 L30 48 L29 33 L8 33 L8 26 L29 26 L29 16 Z",
  heli:
    "M10 10 L54 54 M54 10 L10 54 M32 22 C36 22 38 26 38 32 L38 44 C38 50 35 54 32 54 C29 54 26 50 26 44 L26 32 C26 26 28 22 32 22 Z",
};

export function iconHtml(ac: Aircraft, opts: { sizePx: number; selected: boolean }): string {
  const cat = categoryFor(ac.enrich?.typeCode);
  const color = altitudeColor(ac.altFt);
  const rot = ac.track ?? 0;
  const flagged = ac.flags.length > 0;
  const cls = `ac-svg${opts.selected ? " ac-svg-selected" : ""}${flagged ? " ac-svg-flagged" : ""}`;
  const stroke = opts.selected ? "#38bdf8" : flagged ? "#f59e0b" : "rgba(0,0,0,0.7)";
  const strokeW = opts.selected || flagged ? 3 : 1.5;
  // helicopter path includes rotor lines that must be stroked, not filled
  const heli = cat === "heli";
  return (
    `<div class="${cls}" style="transform: rotate(${rot}deg)">` +
    `<svg viewBox="0 0 64 64" width="${opts.sizePx}" height="${opts.sizePx}">` +
    `<path d="${PATHS[cat]}" fill="${heli ? "none" : color}" ` +
    `stroke="${heli ? color : stroke}" stroke-width="${heli ? 5 : strokeW}" ` +
    `stroke-linejoin="round" stroke-linecap="round"/>` +
    `</svg></div>`
  );
}
