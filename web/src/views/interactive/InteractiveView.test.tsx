/** Regression: clicking a list row opens the detail pane (P4 bug fix). */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

vi.mock("../../components/Map/AircraftMap", () => ({
  AircraftMap: () => <div data-testid="aircraft-map" />,
}));

import { useStore } from "../../state/store";
import type { Aircraft } from "../../types/generated/ws";
import { InteractiveView } from "./InteractiveView";

const plane: Aircraft = {
  icao: "4951ce", callsign: "TAP123", lat: 38.8, lon: -9.1, altFt: 12000,
  gsKt: 250, vrFpm: -500, track: 90, squawk: "2041", distanceKm: 12.3,
  bearingDeg: 184, priority: 0, flags: [],
  enrich: { registration: "CS-TVA", typeCode: "A20N", typeName: "Airbus A320neo",
            operator: "TAP", country: "Portugal", route: null, photoUrl: null },
  trail: [[38.8, -9.1]], lastSeen: 1000, rssi: -18.2,
};

beforeEach(() => {
  useStore.setState({
    aircraft: { [plane.icao]: plane }, vessels: {}, radio2: null, health: null,
    latestPass: null, alerts: [], selectedIcao: null, connected: true, lastMessageTs: 0,
  });
});

test("clicking a list row opens the detail pane with enrichment", () => {
  render(<InteractiveView receiver={{ lat: 38.7, lon: -8.95, rangeRingsKm: [50] }} />);
  expect(screen.queryByLabelText("aircraft detail")).toBeNull();

  fireEvent.click(screen.getByText("TAP123"));

  const pane = within(screen.getByLabelText("aircraft detail"));
  expect(pane.getByText("CS-TVA")).toBeDefined();
  expect(pane.getByText("Airbus A320neo")).toBeDefined();
  expect(pane.getByText("12,000 ft")).toBeDefined();
});

test("clicking the selected row again closes the pane", () => {
  render(<InteractiveView receiver={{ lat: 38.7, lon: -8.95, rangeRingsKm: [50] }} />);
  fireEvent.click(screen.getByText("TAP123"));
  expect(screen.getByLabelText("aircraft detail")).toBeDefined();
  // the row callsign and the pane <h2> share text — click the row (listitem) explicitly
  fireEvent.click(screen.getByRole("listitem"));
  expect(screen.queryByLabelText("aircraft detail")).toBeNull();
});

test("close button dismisses the pane", () => {
  render(<InteractiveView receiver={{ lat: 38.7, lon: -8.95, rangeRingsKm: [50] }} />);
  fireEvent.click(screen.getByText("TAP123"));
  fireEvent.click(screen.getByLabelText("close"));
  expect(screen.queryByLabelText("aircraft detail")).toBeNull();
});
