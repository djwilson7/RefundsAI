import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DigitalReturnDetailsCard } from "./digital-return-details-card";

describe("DigitalReturnDetailsCard", () => {
  it("renders invalidated code return details", () => {
    render(
      <DigitalReturnDetailsCard
        invalidatedAt="Jul 04, 2026"
      />,
    );

    expect(
      screen.getByRole("region", { name: "Digital return details" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Code Invalidated")).toBeInTheDocument();
    expect(screen.getByText("Invalidated")).toBeInTheDocument();
    expect(screen.getByText("Invalidated At")).toBeInTheDocument();
    expect(screen.getByText("Jul 04, 2026")).toBeInTheDocument();
    expect(screen.queryByText("Amount to Refund")).not.toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Code invalidated complete" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Invalidated at complete" }),
    ).toBeInTheDocument();
  });
});
