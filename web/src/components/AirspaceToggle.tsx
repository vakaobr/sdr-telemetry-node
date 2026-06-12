/** Toggle the OpenAIP airspace overlay on the map (R2). Rendered only when the
 *  gateway has an API key configured. State persists per device (store). */
import { useStore } from "../state/store";

export function AirspaceToggle() {
  const on = useStore((s) => s.airspaceOverlay);
  const set = useStore((s) => s.setAirspaceOverlay);
  return (
    <button
      className={`overlay-toggle${on ? " overlay-on" : ""}`}
      onClick={() => set(!on)}
      aria-pressed={on}
      title="Toggle airspace overlay (CTR/TMA/airways)"
    >
      ✈️ Airspace
    </button>
  );
}
