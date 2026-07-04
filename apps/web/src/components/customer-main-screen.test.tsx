import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CustomerMainScreen } from "./customer-main-screen";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

const customer = {
  id: "20000000-0000-4000-8000-000000000001",
  firstName: "Avery",
  lastName: "Brooks",
};

describe("CustomerMainScreen", () => {
  it("renders the shared customer home header", () => {
    render(<CustomerMainScreen customer={customer} />);

    expect(screen.getByText("Welcome")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Avery Brooks" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Summary Dashboard")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Log out" }),
    ).toBeInTheDocument();
  });
});
