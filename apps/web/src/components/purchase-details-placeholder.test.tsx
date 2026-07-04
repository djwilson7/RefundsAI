import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { savePurchaseDetailsSummary } from "@/lib/purchase-details-data";
import { PurchaseDetailsPlaceholder } from "./purchase-details-placeholder";

describe("PurchaseDetailsPlaceholder", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
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

    render(
      <PurchaseDetailsPlaceholder
        purchaseDetails={null}
        purchaseId="40000000-0000-4000-8000-000000000001"
      />,
    );

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
    await waitFor(() => expect(screen.getByText("RAI-10001")).toBeInTheDocument());
    expect(screen.getByText("Amount")).toBeInTheDocument();
    expect(screen.getByText("$129.99")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Metadata" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Scheduled Delivery")).toBeInTheDocument();
    expect(screen.getByText("Tracking Number")).toBeInTheDocument();
    expect(screen.queryByText("Purchased")).not.toBeInTheDocument();
    expect(
      screen.queryByText("40000000-0000-4000-8000-000000000001"),
    ).not.toBeInTheDocument();
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

    render(
      <PurchaseDetailsPlaceholder
        purchaseDetails={null}
        purchaseId="40000000-0000-4000-8000-000000000001"
      />,
    );

    return waitFor(() =>
      expect(screen.getByText("Digital Purchase Details")).toBeInTheDocument(),
    );
  });

  it("falls back to the generic physical detail variant", () => {
    render(
      <PurchaseDetailsPlaceholder
        purchaseDetails={null}
        purchaseId="40000000-0000-4000-8000-000000000001"
      />,
    );

    expect(screen.getByText("Purchase Details")).toBeInTheDocument();
    expect(screen.getByText("Order unavailable")).toBeInTheDocument();
  });

  it("renders API-backed physical metadata cards", () => {
    render(
      <PurchaseDetailsPlaceholder
        purchaseDetails={{
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
        }}
        purchaseId="40000000-0000-4000-8000-000000000001"
      />,
    );

    expect(screen.getByText("Scheduled Delivery")).toBeInTheDocument();
    expect(screen.getByText("Jun 22, 2026")).toBeInTheDocument();
    expect(screen.getByText("Return Status")).toBeInTheDocument();
    expect(screen.getByText("Not Requested")).toBeInTheDocument();
    expect(screen.getByText("TRK-RAI-10001")).toBeInTheDocument();
  });

  it("renders API-backed digital metadata cards", () => {
    render(
      <PurchaseDetailsPlaceholder
        purchaseDetails={{
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
        }}
        purchaseId="40000000-0000-4000-8000-000000000002"
      />,
    );

    expect(screen.getByText("Digital Purchase Details")).toBeInTheDocument();
    expect(screen.getByText("Issued Code")).toBeInTheDocument();
    expect(screen.getByText("DIG-RAI-10002")).toBeInTheDocument();
    expect(screen.getByText("Code Redeemed")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
  });

  it("renders API-backed subscription metadata cards", () => {
    render(
      <PurchaseDetailsPlaceholder
        purchaseDetails={{
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
        }}
        purchaseId="40000000-0000-4000-8000-000000000003"
      />,
    );

    expect(screen.getByText("Subscription Details")).toBeInTheDocument();
    expect(screen.getByText("Period Start")).toBeInTheDocument();
    expect(screen.getByText("Auto Renew")).toBeInTheDocument();
    expect(screen.getByText("Refund Proration Mode")).toBeInTheDocument();
    expect(screen.getByText("None")).toBeInTheDocument();
  });
});
