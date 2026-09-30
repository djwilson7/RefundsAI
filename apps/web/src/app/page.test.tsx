import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Home, { isDemoModeEnabled } from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe("root experience", () => {
  const originalDemoMode = process.env.REFUNDS_AI_DEMO_MODE;

  afterEach(() => {
    if (originalDemoMode === undefined) {
      delete process.env.REFUNDS_AI_DEMO_MODE;
    } else {
      process.env.REFUNDS_AI_DEMO_MODE = originalDemoMode;
    }
  });

  it("shows the product landing page by default", () => {
    delete process.env.REFUNDS_AI_DEMO_MODE;

    render(<Home />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Refunds, governed.",
      }),
    ).toBeInTheDocument();
  });

  it("restores the mock login when demo mode is explicitly disabled", () => {
    process.env.REFUNDS_AI_DEMO_MODE = "false";

    render(<Home />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Refund AI" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load User" })).toBeInTheDocument();
  });

  it("normalizes the demo mode environment value", () => {
    expect(isDemoModeEnabled(" FALSE ")).toBe(false);
    expect(isDemoModeEnabled("true")).toBe(true);
    expect(isDemoModeEnabled()).toBe(true);
  });
});
