import { render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

// Leaflet needs a real canvas — out of scope for the boot-flow test (jsdom).
vi.mock("./components/Map/AircraftMap", () => ({
  AircraftMap: () => <div data-testid="aircraft-map" />,
}));

import { App } from "./App";

test("app boots: fetches config then renders the interactive shell", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          receiver: { lat: 38.7, lon: -8.95 },
          ui: { rangeRingsKm: [50, 100] },
        }),
    }),
  );

  // jsdom has no WebSocket by default — a silent stub keeps WsClient harmless here
  vi.stubGlobal(
    "WebSocket",
    class {
      onopen = null;
      onclose = null;
      onmessage = null;
      onerror = null;
      close() {}
    },
  );

  render(<App />);
  expect(screen.getByText("connecting…")).toBeDefined();
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "sdr-telemetry-node" })).toBeDefined(),
  );
  vi.unstubAllGlobals();
});

test("app surfaces gateway unreachable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("boom")));
  vi.stubGlobal(
    "WebSocket",
    class {
      onopen = null;
      onclose = null;
      onmessage = null;
      onerror = null;
      close() {}
    },
  );
  render(<App />);
  await waitFor(() => expect(screen.getByText(/gateway unreachable/)).toBeDefined());
  vi.unstubAllGlobals();
});
