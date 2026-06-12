/** Show/hide the AIS vessel layer on the map. State persists per device. */
import { useStore } from "../state/store";

export function VesselsToggle() {
  const on = useStore((s) => s.vesselsVisible);
  const set = useStore((s) => s.setVesselsVisible);
  return (
    <button
      className={`overlay-toggle${on ? " overlay-on" : ""}`}
      onClick={() => set(!on)}
      aria-pressed={on}
      title="Show/hide AIS vessels"
    >
      🚢 Vessels
    </button>
  );
}
