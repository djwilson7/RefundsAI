import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockAuthLanding } from "./mock-auth-landing";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push,
  }),
}));

describe("MockAuthLanding", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    push.mockReset();
  });

  it("renders the mock authentication landing page", () => {
    render(<MockAuthLanding />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Refund AI" }),
    ).toBeInTheDocument();
    expect(screen.getByText("A customer support agent.")).toBeInTheDocument();

    expect(screen.getByLabelText("Email")).toHaveAttribute("readOnly");
    expect(screen.getByLabelText("Password")).toHaveAttribute("readOnly");

    expect(
      screen.getByRole("button", { name: "Load User" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Load Admin" }),
    ).toBeInTheDocument();
  });

  it("stores a random seeded customer and routes to the user home screen", async () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    render(<MockAuthLanding />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Load User" }));
    });

    expect(screen.getByLabelText("Email")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Loading User" })).toBeDisabled();

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(push).toHaveBeenCalledWith("/user-home");
    expect(window.sessionStorage.getItem("refunds-ai:selected-mock-customer")).toContain(
      "Avery",
    );
  });

  it("animates generated mock credentials before showing the customer screen", async () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    render(<MockAuthLanding />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Load User" }));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(28);
    });
    expect(screen.getByLabelText("Email")).toHaveValue("a");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_080);
    });
    expect(screen.getByLabelText("Email")).toHaveValue(
      "avery_brooks@example.com",
    );
    expect(screen.getByLabelText("Password")).toHaveValue("12345Password");

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(push).toHaveBeenCalledWith("/user-home");
  });

  it("animates generated admin credentials before routing to admin home", async () => {
    render(<MockAuthLanding />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Load Admin" }));
    });

    expect(screen.getByRole("button", { name: "Loading Admin" })).toBeDisabled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_320);
    });
    expect(screen.getByLabelText("Email")).toHaveValue(
      "system_administrator@example.com",
    );
    expect(screen.getByLabelText("Password")).toHaveValue("12345Password");

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(push).toHaveBeenCalledWith("/admin-home");
  });
});
