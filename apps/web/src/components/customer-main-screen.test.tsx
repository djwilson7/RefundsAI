import type { ComponentProps } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApplicationHelpLayer } from "./application-help-layer";
import { CustomerMainScreen } from "./customer-main-screen";

vi.mock("next/navigation", () => ({
  usePathname: () => "/user-home",
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
    orderNumber: "RAI-10001",
    purchaseType: "physical" as const,
    productName: "Noise-canceling headphones",
    amountCents: 12999,
    purchasedAt: "2026-06-12T14:30:00Z",
    status: "completed",
  },
  {
    id: "40000000-0000-4000-8000-000000000002",
    orderNumber: "RAI-10002",
    purchaseType: "digital" as const,
    productName: "Design asset bundle",
    amountCents: 5900,
    purchasedAt: "2026-06-03T14:30:00Z",
    status: "redeemed",
  },
  {
    id: "40000000-0000-4000-8000-000000000003",
    orderNumber: "RAI-10003",
    purchaseType: "subscription" as const,
    productName: "Productivity Pro monthly",
    amountCents: 2499,
    purchasedAt: "2026-05-28T14:30:00Z",
    status: "subscribed",
  },
];

describe("CustomerMainScreen", () => {
  it("renders the shared customer home header", () => {
    renderCustomerMainScreen();

    expect(screen.getByText("Welcome")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Avery Brooks" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Summary Dashboard")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Log out" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Open help chat" }),
    ).toBeInTheDocument();
  });

  it("renders customer summary metrics from purchases", () => {
    renderCustomerMainScreen();

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
    renderCustomerMainScreen();

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
    expect(
      screen.getByRole("link", { name: /Noise-canceling headphones/ }),
    ).toHaveAttribute(
      "href",
      "/purchase-details/40000000-0000-4000-8000-000000000001",
    );
  });

  it("shows unknown when customer creation metadata is invalid", () => {
    renderCustomerMainScreen({
      customer: {
        ...customer,
        createdAt: "not-a-date",
      },
      purchases: [],
    });

    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.getByText("$0.00")).toBeInTheDocument();
  });
});

function renderCustomerMainScreen(
  props: Partial<ComponentProps<typeof CustomerMainScreen>> = {},
) {
  return render(
    <ApplicationHelpLayer>
      <CustomerMainScreen
        customer={props.customer ?? customer}
        purchases={props.purchases ?? purchases}
      />
    </ApplicationHelpLayer>,
  );
}
