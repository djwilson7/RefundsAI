import type { ComponentProps } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
      screen.getByRole("heading", { level: 2, name: "Delivery Details" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { level: 2, name: "Return Details" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { level: 2, name: "Metadata" }),
    ).not.toBeInTheDocument();
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
    expect(
      screen.getByRole("heading", { level: 2, name: "Delivery Details" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { level: 2, name: "Return Details" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Return Status")).not.toBeInTheDocument();
    expect(screen.queryByText("Return Barcode Generated")).not.toBeInTheDocument();
    expect(screen.queryByText("Refund Window Expires")).not.toBeInTheDocument();
    expect(screen.queryByText("Return Authorized")).not.toBeInTheDocument();
    expect(screen.queryByText("Return Received")).not.toBeInTheDocument();
    expect(screen.queryByText("Return Rejected")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Return Rejection Reason"),
    ).not.toBeInTheDocument();
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

  it("renders requested physical returns as the active detail context", async () => {
    renderPurchaseDetailsPlaceholder({
      purchaseDetails: {
        purchaseId: "40000000-0000-4000-8000-000000000001",
        purchaseType: "physical",
        details: {
          scheduledDeliveryAt: "2026-06-22T14:30:00Z",
          deliveredAt: "2026-06-23T14:30:00Z",
          returnStatus: "requested",
          carrier: "UPS",
          trackingNumber: "TRK-RAI-10001",
          returnBarcodeGenerated: true,
          returnLabelCreatedAt: "2026-07-03T14:30:00Z",
          acceptedByCarrierAt: null,
          returnRequestedAt: "2026-07-03T14:30:00Z",
          returnAuthorizedAt: null,
          returnReceivedAt: null,
          returnRejectedAt: null,
          returnRejectionReason: null,
          refundWindowExpiresAt: "2026-07-20T14:30:00Z",
        },
      },
    });

    expect(
      screen.getByRole("region", { name: "Physical delivery timeline" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Delivery tracking details" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Physical return workflow" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Delivery Details" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Return Details" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Return Requested")).toBeInTheDocument();
    expect(screen.getByText("Label Created")).toBeInTheDocument();
    expect(screen.getByText("Accepted by Courier")).toBeInTheDocument();
    expect(screen.getAllByText("Jul 03, 2026")).toHaveLength(2);
    expect(
      screen.queryByText("Awaiting courier acceptance"),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Given to Carrier" }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/purchases/40000000-0000-4000-8000-000000000001/physical/confirm-carrier-acceptance",
        { method: "POST" },
      ),
    );
    expect(fetch).toHaveBeenCalledWith(
      "/api/purchases/40000000-0000-4000-8000-000000000001/refund/eligibility",
      { cache: "no-store" },
    );
    expect(screen.queryByText("Return Status")).not.toBeInTheDocument();
    expect(screen.queryByText("Return Barcode Generated")).not.toBeInTheDocument();
    expect(screen.queryByText("Refund Window Expires")).not.toBeInTheDocument();
    expect(screen.queryByText("Return Label Created")).not.toBeInTheDocument();
    expect(screen.queryByText("Accepted By Carrier")).not.toBeInTheDocument();
  });

  it("renders issued physical refund funds summary", () => {
    renderPurchaseDetailsPlaceholder({
      purchaseDetails: {
        purchaseId: "40000000-0000-4000-8000-000000000001",
        purchaseType: "physical",
        details: {
          scheduledDeliveryAt: "2026-06-22T14:30:00Z",
          deliveredAt: "2026-06-23T14:30:00Z",
          returnStatus: "accepted_by_carrier",
          carrier: "UPS",
          trackingNumber: "TRK-RAI-10001",
          returnBarcodeGenerated: true,
          returnLabelCreatedAt: "2026-07-03T14:30:00Z",
          acceptedByCarrierAt: "2026-07-04T14:30:00Z",
          returnRequestedAt: "2026-07-03T14:30:00Z",
          returnAuthorizedAt: null,
          returnReceivedAt: null,
          returnRejectedAt: null,
          returnRejectionReason: null,
          refundWindowExpiresAt: "2026-07-20T14:30:00Z",
        },
      },
      refundWorkflow: {
        canEnterRefundWorkflow: false,
        canIssueFunds: false,
        canPrepareRefund: false,
        policyFacts: {
          refunded_at: "2026-07-04T15:00:00Z",
          refund_amount_cents: 999,
          refund_outcome: "full",
        },
        purchaseId: "40000000-0000-4000-8000-000000000001",
        purchaseType: "physical",
        reasons: ["purchase_status_refunded"],
        refundableAmountCents: 999,
        refundOutcome: "full",
        refundStage: "issued",
        requiredAction: "none",
      },
    });

    expect(
      screen.getByRole("region", { name: "Physical return workflow" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Physical refund summary" }),
    ).toBeInTheDocument();
    const refundSummary = within(
      screen.getByRole("region", { name: "Physical refund summary" }),
    );

    expect(refundSummary.getByText("Return Issued")).toBeInTheDocument();
    expect(refundSummary.getByText("Jul 04, 2026")).toBeInTheDocument();
    expect(refundSummary.getByText("Amount")).toBeInTheDocument();
    expect(refundSummary.getByText("$9.99")).toBeInTheDocument();
    expect(refundSummary.getByText("Estimated Return Window")).toBeInTheDocument();
    expect(refundSummary.getByText("3-10 business days")).toBeInTheDocument();
    expect(refundSummary.getByText("Jul 08 - Jul 17")).toBeInTheDocument();
    expect(screen.queryByText("Return Authorized")).not.toBeInTheDocument();
    expect(screen.queryByText("Return Received")).not.toBeInTheDocument();
    expect(screen.queryByText("Return Rejected")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Return Rejection Reason"),
    ).not.toBeInTheDocument();
  });

  it("renders API-backed digital code details without generic metadata", () => {
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
      refundWorkflow: {
        canEnterRefundWorkflow: true,
        canIssueFunds: true,
        canPrepareRefund: false,
        policyFacts: {},
        purchaseId: "40000000-0000-4000-8000-000000000002",
        purchaseType: "digital",
        reasons: [],
        refundableAmountCents: 13999,
        refundOutcome: "full",
        refundStage: "prepared",
        requiredAction: "issue_funds",
      },
    });

    expect(screen.getByText("Digital Purchase Details")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Code Details" }),
    ).toBeInTheDocument();
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
      screen.queryByRole("heading", { level: 2, name: "Metadata" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { level: 2, name: "Return Details" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Code Invalidated At")).not.toBeInTheDocument();
    expect(screen.queryByText("Refund Lock Reason")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Subscription billing cycle" }),
    ).not.toBeInTheDocument();
  });

  it("renders invalidated digital codes as return details", () => {
    renderPurchaseDetailsPlaceholder({
      purchaseDetails: {
        purchaseId: "40000000-0000-4000-8000-000000000002",
        purchaseType: "digital",
        details: {
          issuedCode: "DIG-RAI-10002",
          codeRedeemed: false,
          codeRedeemedAt: null,
          codeInvalidatedAt: "2026-07-04T14:30:00Z",
          codeDeliveredAt: "2026-06-20T14:30:00Z",
          refundWindowExpiresAt: "2026-07-05T14:30:00Z",
          refundLockReason: null,
        },
      },
      purchaseId: "40000000-0000-4000-8000-000000000002",
      refundWorkflow: {
        canEnterRefundWorkflow: true,
        canIssueFunds: true,
        canPrepareRefund: false,
        policyFacts: {},
        purchaseId: "40000000-0000-4000-8000-000000000002",
        purchaseType: "digital",
        reasons: [],
        refundableAmountCents: 13999,
        refundOutcome: "full",
        refundStage: "prepared",
        requiredAction: "issue_funds",
      },
    });

    expect(
      screen.getByRole("heading", { level: 2, name: "Code Details" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Return Details" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Digital return details" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Code Invalidated")).toBeInTheDocument();
    expect(screen.getByText("Invalidated")).toBeInTheDocument();
    expect(screen.getByText("Invalidated At")).toBeInTheDocument();
    expect(screen.getByText("Jul 04, 2026")).toBeInTheDocument();
    expect(screen.queryByText("Amount to Refund")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Digital refund summary" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { level: 2, name: "Metadata" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Code Invalidated At")).not.toBeInTheDocument();
    expect(screen.queryByText("Refund Lock Reason")).not.toBeInTheDocument();
  });

  it("renders issued digital refund funds summary", () => {
    renderPurchaseDetailsPlaceholder({
      purchaseDetails: {
        purchaseId: "40000000-0000-4000-8000-000000000002",
        purchaseType: "digital",
        details: {
          issuedCode: "DIG-RAI-10002",
          codeRedeemed: false,
          codeRedeemedAt: null,
          codeInvalidatedAt: "2026-07-04T14:30:00Z",
          codeDeliveredAt: "2026-06-20T14:30:00Z",
          refundWindowExpiresAt: "2026-07-05T14:30:00Z",
          refundLockReason: null,
        },
      },
      purchaseId: "40000000-0000-4000-8000-000000000002",
      refundWorkflow: {
        canEnterRefundWorkflow: false,
        canIssueFunds: false,
        canPrepareRefund: false,
        policyFacts: {
          refunded_at: "2026-07-04T15:00:00Z",
          refund_amount_cents: 5900,
          refund_outcome: "full",
        },
        purchaseId: "40000000-0000-4000-8000-000000000002",
        purchaseType: "digital",
        reasons: ["purchase_status_refunded"],
        refundableAmountCents: 5900,
        refundOutcome: "full",
        refundStage: "issued",
        requiredAction: "none",
      },
    });

    expect(
      screen.getByRole("region", { name: "Digital return details" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Digital refund summary" }),
    ).toBeInTheDocument();
    const refundSummary = within(
      screen.getByRole("region", { name: "Digital refund summary" }),
    );

    expect(refundSummary.getByText("Date Issued")).toBeInTheDocument();
    expect(refundSummary.getByText("Jul 04, 2026")).toBeInTheDocument();
    expect(refundSummary.getByText("Amount")).toBeInTheDocument();
    expect(refundSummary.getByText("$59.00")).toBeInTheDocument();
    expect(refundSummary.getByText("Estimated Return Window")).toBeInTheDocument();
    expect(refundSummary.getByText("3-10 business days")).toBeInTheDocument();
    expect(refundSummary.getByText("Jul 08 - Jul 17")).toBeInTheDocument();
    expect(screen.queryByText("Amount to Refund")).not.toBeInTheDocument();
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
    expect(screen.queryByText("Auto Renew Enabled")).not.toBeInTheDocument();
    expect(screen.queryByText("Period Start")).not.toBeInTheDocument();
    expect(screen.queryByText("Period End")).not.toBeInTheDocument();
    expect(screen.queryByText("Auto Renew")).not.toBeInTheDocument();
    expect(screen.queryByText("Service Ended At")).not.toBeInTheDocument();
    expect(screen.queryByText("Full Refund Window Expires")).not.toBeInTheDocument();
    expect(screen.queryByText("Refund Window Expires")).not.toBeInTheDocument();
    expect(screen.queryByText("Refund Proration Mode")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Subscription refund summary" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Billing Cycle Details" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { level: 2, name: "Return Details" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Subscription billing cycle" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Billing Start")).toBeInTheDocument();
    expect(screen.getByText("Billing End")).toBeInTheDocument();
    expect(screen.getByText("Today")).toBeInTheDocument();
  });

  it("renders subscription cancellation state in return details", () => {
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
      refundWorkflow: {
        canEnterRefundWorkflow: true,
        canIssueFunds: true,
        canPrepareRefund: false,
        policyFacts: {},
        purchaseId: "40000000-0000-4000-8000-000000000003",
        purchaseType: "subscription",
        reasons: [],
        refundableAmountCents: 1750,
        refundOutcome: "prorated",
        refundStage: "prepared",
        requiredAction: "issue_funds",
      },
    });

    expect(screen.queryByText("Subscription Canceled")).not.toBeInTheDocument();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(screen.getByText("Jul 03")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Billing Cycle Details" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Return Details" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Subscription refund summary" }),
    ).toBeInTheDocument();
    const refundSummary = within(
      screen.getByRole("region", { name: "Subscription refund summary" }),
    );

    expect(refundSummary.getByText("Auto Renew")).toBeInTheDocument();
    expect(refundSummary.getByText("Off")).toBeInTheDocument();
    expect(refundSummary.getByText("Days Used")).toBeInTheDocument();
    expect(refundSummary.getByText("13 days")).toBeInTheDocument();
    expect(refundSummary.getByText("Status")).toBeInTheDocument();
    expect(refundSummary.getByText("Subscription Cancelled")).toBeInTheDocument();
    expect(screen.queryByText("Cancel Date")).not.toBeInTheDocument();
    expect(screen.queryByText("Expected Refund Window")).not.toBeInTheDocument();
    expect(screen.queryByText("Auto Renew Enabled")).not.toBeInTheDocument();
    expect(screen.queryByText("Service Ended At")).not.toBeInTheDocument();
  });

  it("renders issued subscription refund summary in return details", () => {
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
      refundWorkflow: {
        canEnterRefundWorkflow: false,
        canIssueFunds: false,
        canPrepareRefund: false,
        policyFacts: {
          refunded_at: "2026-07-04T15:00:00Z",
          refund_amount_cents: 1750,
          refund_outcome: "prorated",
        },
        purchaseId: "40000000-0000-4000-8000-000000000003",
        purchaseType: "subscription",
        reasons: ["purchase_status_refunded"],
        refundableAmountCents: 1750,
        refundOutcome: "prorated",
        refundStage: "issued",
        requiredAction: "none",
      },
    });

    const refundSummary = within(
      screen.getByRole("region", { name: "Subscription refund summary" }),
    );

    expect(refundSummary.getByText("Auto Renew")).toBeInTheDocument();
    expect(refundSummary.getByText("Off")).toBeInTheDocument();
    expect(refundSummary.getByText("Days Used")).toBeInTheDocument();
    expect(refundSummary.getByText("13 days")).toBeInTheDocument();
    expect(refundSummary.getByText("Status")).toBeInTheDocument();
    expect(refundSummary.getByText("Subscription Cancelled")).toBeInTheDocument();
    expect(refundSummary.getByText("Cancel Date")).toBeInTheDocument();
    expect(refundSummary.getByText("Jul 03, 2026")).toBeInTheDocument();
    expect(refundSummary.getByText("Amount")).toBeInTheDocument();
    expect(refundSummary.getByText("$17.50")).toBeInTheDocument();
    expect(refundSummary.getByText("Expected Refund Window")).toBeInTheDocument();
    expect(refundSummary.getByText("3-10 business days")).toBeInTheDocument();
    expect(refundSummary.getByText("Jul 08 - Jul 17")).toBeInTheDocument();
    expect(screen.queryByText("Subscription Canceled")).not.toBeInTheDocument();
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
        refundWorkflow={props.refundWorkflow ?? null}
      />
    </ApplicationHelpLayer>,
  );
}
