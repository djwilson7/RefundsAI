import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProductLanding } from "./product-landing";

describe("ProductLanding", () => {
  it("presents the product and commercial integration model", () => {
    render(<ProductLanding />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Refund conversations with transactional boundaries.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Designed to sit between support conversations and systems of record.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Connect existing commerce data")).toBeInTheDocument();
    expect(screen.getByText("Encode policy as deterministic rules")).toBeInTheDocument();
    expect(screen.getByText("Automate with explicit boundaries")).toBeInTheDocument();
  });

  it("shows the intentionally unavailable technical tour control", () => {
    render(<ProductLanding />);

    expect(
      screen.getByRole("button", { name: /technical tour/i }),
    ).toBeDisabled();
    expect(screen.getByText("Coming soon")).toBeInTheDocument();
  });
});
