import type { ComponentProps } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { savePurchaseDetailsSummary } from "@/lib/purchase-details-data";
import { ApplicationHelpLayer } from "./application-help-layer";
import { PurchaseDetailsPlaceholder } from "./purchase-details-placeholder";

vi.mock("next/navigation", () => ({
  usePathname: () => "/purchase-details/40000000-0000-4000-8000-000000000001",
  useRouter: () => ({
    refresh: vi.fn(),
  }),
}));

describe("PurchaseDetailsPlaceholder", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: { can_prepare_refund: true },
          }),
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the selected purchase summary data object", async () => {
    savePurchaseDetailsSummary({
      headerMeta: {
        amount: "$129.99",
        orderNumber: "RAI-10001",
        status: "Completed",
      },
      productName: "Wireless Headphones",
      purchasedAt: "Jun 20, 2026",
      purchaseId: "40000000-0000-4000-8000-000000000001",
      purchaseType: "physical",
    });

    renderPurchaseDetailsPlaceholder();

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Wireless Headphones",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Purchase Details")).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: "Purchase summary" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Order Number")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("RAI-10001")).toBeInTheDocument(),
    );
    expect(screen.getByText("Amount")).toBeInTheDocument();
    expect(screen.getByText("$129.99")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Metadata" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Scheduled Delivery")).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Delivery tracking details" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Carrier")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Subscription billing cycle" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Physical delivery timeline" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Purchased")).toBeInTheDocument();
    expect(
      screen.queryByText("40000000-0000-4000-8000-000000000001"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Open help chat" }),
    ).toBeInTheDocument();
  });

  it("can render digital detail variants", () => {
    savePurchaseDetailsSummary({
      headerMeta: {
        amount: "$59.00",
        orderNumber: "RAI-10002",
        status: "Redeemed",
      },
      productName: "Design Asset Pack",
      purchasedAt: "Jun 03, 2026",
      purchaseId: "40000000-0000-4000-8000-000000000001",
      purchaseType: "digital",
    });

    renderPurchaseDetailsPlaceholder();

    return waitFor(() =>
      expect(screen.getByText("Digital Purchase Details")).toBeInTheDocument(),
    );
  });

  it("falls back to the generic physical detail variant", () => {
    renderPurchaseDetailsPlaceholder();

    expect(screen.getByText("Purchase Details")).toBeInTheDocument();
    expect(screen.getByText("Order unavailable")).toBeInTheDocument();
  });

  it("renders API-backed physical metadata cards", () => {
    renderPurchaseDetailsPlaceholder({
      purchaseDetails: {
        purchaseId: "40000000-0000-4000-8000-000000000001",
        purchaseType: "physical",
        details: {
          scheduledDeliveryAt: "2026-06-22T14:30:00Z",
          deliveredAt: null,
          returnStatus: "not_requested",
          carrier: "UPS",
          trackingNumber: "TRK-RAI-10001",
          returnBarcodeGenerated: false,
          returnLabelCreatedAt: null,
          acceptedByCarrierAt: null,
          returnRequestedAt: null,
          returnAuthorizedAt: null,
          returnReceivedAt: null,
          returnRejectedAt: null,
          returnRejectionReason: null,
          refundWindowExpiresAt: "2026-07-20T14:30:00Z",
        },
      },
    });

    expect(screen.getByText("Scheduled Delivery")).toBeInTheDocument();
    expect(screen.getByText("Jun 22, 2026")).toBeInTheDocument();
    expect(screen.getByText("Return Status")).toBeInTheDocument();
    expect(screen.getByText("Not Requested")).toBeInTheDocument();
    expect(screen.getByText("TRK-RAI-10001")).toBeInTheDocument();
    expect(screen.getByText("Delivery Courier")).toBeInTheDocument();
    expect(screen.getByText("UPS")).toBeInTheDocument();
    expect(screen.queryByText("Carrier")).not.toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Physical delivery timeline" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Awaiting delivery")).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Subscription billing cycle" }),
    ).not.toBeInTheDocument();
  });

  it("renders API-backed digital metadata cards", () => {
    renderPurchaseDetailsPlaceholder({
      purchaseDetails: {
        purchaseId: "40000000-0000-4000-8000-000000000002",
        purchaseType: "digital",
        details: {
          issuedCode: "DIG-RAI-10002",
          codeRedeemed: true,
          codeRedeemedAt: "2026-06-21T14:30:00Z",
          codeInvalidatedAt: null,
          codeDeliveredAt: "2026-06-20T14:30:00Z",
          refundWindowExpiresAt: "2026-07-05T14:30:00Z",
          refundLockReason: "code_redeemed",
        },
      },
      purchaseId: "40000000-0000-4000-8000-000000000002",
    });

    expect(screen.getByText("Digital Purchase Details")).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Digital code details" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Issued Code")).toBeInTheDocument();
    expect(screen.getByText("DIG-RAI-10002")).toBeInTheDocument();
    expect(screen.queryByText("Code Redeemed")).not.toBeInTheDocument();
    expect(screen.getByText("Redeemed State")).toBeInTheDocument();
    expect(screen.getByText("Redeemed")).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Digital purchase timeline" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Purchased At")).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Subscription billing cycle" }),
    ).not.toBeInTheDocument();
  });

  it("renders API-backed subscription metadata cards", () => {
    renderPurchaseDetailsPlaceholder({
      purchaseDetails: {
        purchaseId: "40000000-0000-4000-8000-000000000003",
        purchaseType: "subscription",
        details: {
          periodStart: "2026-06-20T14:30:00Z",
          periodEnd: "2026-07-20T14:30:00Z",
          cancelledAt: null,
          serviceEndedAt: null,
          autoRenew: true,
          refundProrationMode: "none",
          fullRefundWindowExpiresAt: "2026-06-22T14:30:00Z",
          refundWindowExpiresAt: "2026-07-20T14:30:00Z",
        },
      },
      purchaseId: "40000000-0000-4000-8000-000000000003",
    });

    expect(screen.getByText("Subscription Details")).toBeInTheDocument();
    expect(screen.getByText("Auto Renew Enabled")).toBeInTheDocument();
    expect(screen.queryByText("Period Start")).not.toBeInTheDocument();
    expect(screen.queryByText("Period End")).not.toBeInTheDocument();
    expect(screen.queryByText("Auto Renew")).not.toBeInTheDocument();
    expect(screen.getByText("Refund Proration Mode")).toBeInTheDocument();
    expect(screen.getByText("None")).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Subscription billing cycle" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Billing Start")).toBeInTheDocument();
    expect(screen.getByText("Billing End")).toBeInTheDocument();
    expect(screen.getByText("Today")).toBeInTheDocument();
  });

  it("renders a canceled subscription badge when auto renew is disabled", () => {
    renderPurchaseDetailsPlaceholder({
      purchaseDetails: {
        purchaseId: "40000000-0000-4000-8000-000000000003",
        purchaseType: "subscription",
        details: {
          periodStart: "2026-06-20T14:30:00Z",
          periodEnd: "2026-07-20T14:30:00Z",
          cancelledAt: "2026-07-03T14:30:00Z",
          serviceEndedAt: "2026-07-03T14:30:00Z",
          autoRenew: false,
          refundProrationMode: "prorated",
          fullRefundWindowExpiresAt: "2026-06-22T14:30:00Z",
          refundWindowExpiresAt: "2026-07-20T14:30:00Z",
        },
      },
      purchaseId: "40000000-0000-4000-8000-000000000003",
    });

    expect(screen.getByText("Subscription Canceled")).toBeInTheDocument();
    expect(screen.queryByText("Auto Renew Enabled")).not.toBeInTheDocument();
    expect(screen.queryByText("Auto Renew")).not.toBeInTheDocument();
  });
});

function renderPurchaseDetailsPlaceholder(
  props: Partial<ComponentProps<typeof PurchaseDetailsPlaceholder>> = {},
) {
  return render(
    <ApplicationHelpLayer>
      <PurchaseDetailsPlaceholder
        currentDate={props.currentDate ?? "2026-07-05T00:00:00Z"}
        purchaseDetails={props.purchaseDetails ?? null}
        purchaseId={props.purchaseId ?? "40000000-0000-4000-8000-000000000001"}
      />
    </ApplicationHelpLayer>,
  );
}
