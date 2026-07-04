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
  createdAt: "2026-07-03T00:00:00Z",
};

const purchases = [
  {
    id: "40000000-0000-4000-8000-000000000001",
    productName: "Noise-canceling headphones",
    amountCents: 12999,
    purchasedAt: "2026-06-12T14:30:00Z",
    status: "completed",
  },
  {
    id: "40000000-0000-4000-8000-000000000002",
    productName: "Design asset bundle",
    amountCents: 5900,
    purchasedAt: "2026-06-03T14:30:00Z",
    status: "redeemed",
  },
  {
    id: "40000000-0000-4000-8000-000000000003",
    productName: "Productivity Pro monthly",
    amountCents: 2499,
    purchasedAt: "2026-05-28T14:30:00Z",
    status: "subscribed",
  },
];

describe("CustomerMainScreen", () => {
  it("renders the shared customer home header", () => {
    render(<CustomerMainScreen customer={customer} purchases={purchases} />);

    expect(screen.getByText("Welcome")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Avery Brooks" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Summary Dashboard")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Log out" }),
    ).toBeInTheDocument();
  });

  it("renders customer summary metrics from purchases", () => {
    render(<CustomerMainScreen customer={customer} purchases={purchases} />);

    expect(
      screen.getByRole("region", { name: "Customer summary metrics" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Customer Since")).toBeInTheDocument();
    expect(screen.getByText("2026")).toBeInTheDocument();
    expect(screen.getByText("Items Purchased")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Total Spent")).toBeInTheDocument();
    expect(screen.getByText("$213.98")).toBeInTheDocument();
  });

  it("renders purchase history cards from purchases", () => {
    render(<CustomerMainScreen customer={customer} purchases={purchases} />);

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
    expect(screen.getByText("$129.99")).toBeInTheDocument();
    expect(screen.getByText("Purchased Jun 12, 2026")).toBeInTheDocument();
  });

  it("shows unknown when customer creation metadata is invalid", () => {
    render(
      <CustomerMainScreen
        customer={{
          ...customer,
          createdAt: "not-a-date",
        }}
        purchases={[]}
      />,
    );

    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.getByText("$0.00")).toBeInTheDocument();
  });
});
