import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AdminHomePage } from "./admin-home-page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

describe("AdminHomePage", () => {
  it("renders the shared admin home header", () => {
    render(<AdminHomePage />);

    expect(screen.getByText("Welcome")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "System Administrator",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Summary Dashboard")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Log out" }),
    ).toBeInTheDocument();
  });
});
