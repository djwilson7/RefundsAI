import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScaffoldStatus } from "./scaffold-status";

describe("ScaffoldStatus", () => {
  it("communicates the frontend scaffold baseline", () => {
    render(<ScaffoldStatus />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "RefundsAI frontend scaffold is ready.",
      }),
    ).toBeInTheDocument();

    expect(screen.getByText("Next.js baseline")).toBeInTheDocument();
    expect(screen.getByText("Frontend validation")).toBeInTheDocument();
    expect(screen.getByText("Container runtime")).toBeInTheDocument();
  });
});
