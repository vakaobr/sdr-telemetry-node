/** ATC player visibility + tap-to-play + activity pulse (P8). */
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { useStore } from "../state/store";
import type { Radio2Status } from "../types/generated/ws";
import { AtcPlayer } from "./AtcPlayer";

const atcMode: Radio2Status = {
  mode: "atc", since: 1, reason: "schedule", nextPass: null,
  audioUrl: "http://nodeb.local:8000/atc", tleAgeDays: 0,
};

function reset(radio2: Radio2Status | null) {
  useStore.setState({
    aircraft: {}, vessels: {}, radio2, health: null, latestPass: null, alerts: [],
    selectedIcao: null, connected: true, lastMessageTs: 0, atcActive: false, atcActiveTs: 0,
  });
}

beforeEach(() => {
  // jsdom has no real audio element playback
  vi.spyOn(window.HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  vi.spyOn(window.HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
});

test("hidden when radio2 is not in ATC mode", () => {
  reset({ ...atcMode, mode: "ais", audioUrl: null });
  const { container } = render(<AtcPlayer />);
  expect(container.firstChild).toBeNull();
});

test("hidden when offline", () => {
  reset(null);
  const { container } = render(<AtcPlayer />);
  expect(container.firstChild).toBeNull();
});

test("shows play control and channel when in ATC mode", () => {
  reset(atcMode);
  render(<AtcPlayer />);
  expect(screen.getByLabelText("play ATC audio")).toBeDefined();
  expect(screen.getByText(/ATC · atc/)).toBeDefined();
});

test("tap toggles play/pause", async () => {
  reset(atcMode);
  render(<AtcPlayer />);
  const btn = screen.getByLabelText("play ATC audio");
  fireEvent.click(btn);
  // play() resolves → button flips to stop
  expect(await screen.findByLabelText("stop ATC audio")).toBeDefined();
  fireEvent.click(screen.getByLabelText("stop ATC audio"));
  expect(screen.getByLabelText("play ATC audio")).toBeDefined();
});
