/**
 * ATC airband audio (FR-5.2, story E1/E2). Tap-to-play the Icecast MP3 mount
 * (browsers block autoplay), shows the active channel, and pulses on
 * squelch-open activity. Only rendered when radio2 is in ATC mode with a URL.
 */
import { useEffect, useRef, useState } from "react";
import { useStore } from "../state/store";

export function AtcPlayer() {
  const radio2 = useStore((s) => s.radio2);
  const atcActive = useStore((s) => s.atcActive);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(false);

  const url = radio2?.mode === "atc" ? radio2.audioUrl : null;

  // stop audio if we leave ATC mode (radio retasked to AIS/satellite)
  useEffect(() => {
    if (!url && audioRef.current) {
      audioRef.current.pause();
      setPlaying(false);
    }
  }, [url]);

  if (!url) return null;

  const toggle = async () => {
    const el = audioRef.current;
    if (!el) return;
    if (playing) {
      el.pause();
      setPlaying(false);
      return;
    }
    try {
      setError(false);
      el.src = url; // (re)attach on play so a stale stream reconnects
      await el.play();
      setPlaying(true);
    } catch {
      setError(true);
      setPlaying(false);
    }
  };

  const channel = radio2?.nextPass ? null : url.split("/").pop();

  return (
    <div className={`atc-player${atcActive && playing ? " atc-live" : ""}`}>
      <button className="atc-toggle" onClick={toggle} aria-label={playing ? "stop ATC audio" : "play ATC audio"}>
        {playing ? "⏸" : "▶"}
      </button>
      <span className="atc-label">
        📻 ATC{channel ? ` · ${channel}` : ""}
        {playing && <span className={`atc-dot${atcActive ? " atc-dot-on" : ""}`} />}
      </span>
      {error && <span className="atc-error">stream unavailable</span>}
      <audio ref={audioRef} preload="none" />
    </div>
  );
}
