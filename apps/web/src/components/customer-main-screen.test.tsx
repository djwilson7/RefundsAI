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

  it("renders placeholder customer summary metrics", () => {
    render(<CustomerMainScreen customer={customer} />);

    expect(
      screen.getByRole("region", { name: "Customer summary metrics" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Customer Since")).toBeInTheDocument();
    expect(screen.getByText("1992")).toBeInTheDocument();
    expect(screen.getByText("Items Purchased")).toBeInTheDocument();
    expect(screen.getByText("745")).toBeInTheDocument();
    expect(screen.getByText("Total Spent")).toBeInTheDocument();
    expect(screen.getByText("14,254.35")).toBeInTheDocument();
  });

  it("renders placeholder purchase history cards", () => {
    render(<CustomerMainScreen customer={customer} />);

    expect(
      screen.getByRole("heading", { level: 2, name: "Purchase History" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "Noise-canceling headphones",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "Design asset bundle" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "Productivity Pro monthly",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Redeemed")).toBeInTheDocument();
    expect(screen.getByText("Subscribed")).toBeInTheDocument();
  });
});
