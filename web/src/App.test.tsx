import { render, screen } from "@testing-library/react";
import { App } from "./App";

test("app shell renders", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "sdr-telemetry-node" })).toBeDefined();
});
