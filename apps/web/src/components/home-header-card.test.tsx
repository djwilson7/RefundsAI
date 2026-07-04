import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeHeaderCard } from "./home-header-card";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push,
  }),
}));

describe("HomeHeaderCard", () => {
  afterEach(() => {
    window.sessionStorage.clear();
    push.mockReset();
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
    expect(push).toHaveBeenCalledWith("/");
  });
});
