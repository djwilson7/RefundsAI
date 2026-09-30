import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeHeaderCard } from "./home-header-card";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace,
  }),
}));

describe("HomeHeaderCard", () => {
  afterEach(() => {
    window.sessionStorage.clear();
    replace.mockReset();
  });

  it("renders shared home header content with logout action", () => {
    render(
      <HomeHeaderCard
        eyebrow="Welcome"
        heading="Avery Brooks"
        summary="Summary Dashboard"
      />,
    );

    expect(screen.getByText("Welcome")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Avery Brooks" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Summary Dashboard")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Log out" }),
    ).toBeInTheDocument();
  });

  it("clears mock login state and returns to the landing page", () => {
    window.sessionStorage.setItem(
      "refunds-ai:selected-mock-customer",
      JSON.stringify({ firstName: "Avery", lastName: "Brooks" }),
    );
    render(
      <HomeHeaderCard
        eyebrow="Welcome"
        heading="Avery Brooks"
        summary="Summary Dashboard"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Log out" }));

    expect(
      window.sessionStorage.getItem("refunds-ai:selected-mock-customer"),
    ).toBeNull();
    expect(replace).toHaveBeenCalledWith("/");
  });

  it("uses the product banner for the client tour without a duplicate logout control", () => {
    render(
      <HomeHeaderCard productBanner eyebrow="Welcome" heading="Avery Brooks" summary="Summary Dashboard" />,
    );

    const banner = screen.getByRole("navigation", { name: "Primary navigation" });
    expect(banner).toContainElement(screen.getByRole("heading", { name: "Avery Brooks" }));
    expect(screen.getByRole("button", { name: "Switch to admin view" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Exit" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("button", { name: "Log out" })).not.toBeInTheDocument();
  });
});
