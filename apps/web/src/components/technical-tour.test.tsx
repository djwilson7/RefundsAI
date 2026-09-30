import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TechnicalTour } from "./technical-tour";
import { loadSelectedMockCustomerId } from "./mock-auth-session";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

afterEach(() => {
  window.sessionStorage.clear();
  push.mockReset();
  vi.restoreAllMocks();
});

describe("TechnicalTour", () => {
  it("offers two perspectives and an exit in the main header", () => {
    render(<TechnicalTour />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Choose your perspective.");
    expect(screen.getByRole("article", { name: "Client" })).toHaveTextContent("customer who has made purchases");
    expect(screen.getByRole("article", { name: "Admin" })).toHaveTextContent("transparency is built into RefundsAI");
    expect(screen.getAllByText("Begin Here")).toHaveLength(2);
    const header = screen.getByRole("navigation", { name: "Primary navigation" });
    expect(within(header).getByRole("link", { name: "Exit" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Start admin tour" })).toHaveAttribute("href", "/admin-home?tour=admin");
  });

  it("selects the stable tour customer before opening the client experience", () => {
    render(<TechnicalTour />);

    fireEvent.click(screen.getByRole("button", { name: "Start client tour" }));

    const customerId = "20000000-0000-4000-8000-000000000001";
    expect(loadSelectedMockCustomerId()).toBe(customerId);
    expect(push).toHaveBeenCalledWith(`/user-home?customerId=${customerId}&tour=client`);
    expect(screen.getByRole("button", { name: "Start client tour" })).toBeDisabled();
  });
});
