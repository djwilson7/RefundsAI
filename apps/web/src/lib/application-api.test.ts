import { afterEach, describe, expect, it, vi } from "vitest";
import {
  formatCentsAsDollars,
  formatPurchaseDate,
  formatPurchaseStatus,
  getPurchaseDetails,
  getRefundWorkflow,
  getUserProfile,
  getUserPurchases,
  mapApiPurchaseDetailsToPurchaseDetails,
  mapApiPurchaseToCustomerPurchase,
  mapApiRefundWorkflowToRefundWorkflow,
  mapApiUserToCustomerProfile,
} from "./application-api";

const apiUser = {
  id: "20000000-0000-4000-8000-000000000001",
  first_name: "Avery",
  last_name: "Brooks",
  created_at: "2026-07-03T00:00:00Z",
  display_name: "Avery Brooks",
  roles: [{ key: "customer", name: "Customer" }],
};

const apiPurchase = {
  id: "40000000-0000-4000-8000-000000000001",
  order_number: "RAI-10001",
  purchase_type: "physical" as const,
  product_name: "Wireless Headphones",
  sku: "PHY-HEADPHONES-001",
  amount_cents: 12999,
  purchased_at: "2026-06-20T14:30:00Z",
  status: "refund_pending",
  details_url: "/api/purchases/40000000-0000-4000-8000-000000000001/details",
};

const apiPhysicalPurchaseDetails = {
  purchase_id: "40000000-0000-4000-8000-000000000001",
  purchase_type: "physical" as const,
  details: {
    scheduled_delivery_at: "2026-06-22T14:30:00Z",
    delivered_at: null,
    return_status: "not_requested",
    carrier: "UPS",
    tracking_number: "TRK-RAI-10001",
    return_barcode_generated: false,
    return_label_created_at: null,
    accepted_by_carrier_at: null,
    return_requested_at: null,
    return_authorized_at: null,
    return_received_at: null,
    return_rejected_at: null,
    return_rejection_reason: null,
    refund_window_expires_at: "2026-07-20T14:30:00Z",
  },
};

const apiRefundWorkflow = {
  purchase_id: "40000000-0000-4000-8000-000000000003",
  purchase_type: "subscription" as const,
  can_enter_refund_workflow: true,
  can_prepare_refund: false,
  can_issue_funds: true,
  refund_stage: "prepared" as const,
  required_action: "issue_funds" as const,
  refundable_amount_cents: 1750,
  refund_outcome: "prorated" as const,
  reasons: [],
  policy_facts: {
    auto_renew: false,
  },
};

describe("application API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps API user payloads to customer profiles", () => {
    expect(mapApiUserToCustomerProfile(apiUser)).toEqual({
      id: "20000000-0000-4000-8000-000000000001",
      firstName: "Avery",
      lastName: "Brooks",
      createdAt: "2026-07-03T00:00:00Z",
    });
  });

  it("maps API purchase payloads to customer purchases", () => {
    expect(mapApiPurchaseToCustomerPurchase(apiPurchase)).toEqual({
      id: "40000000-0000-4000-8000-000000000001",
      orderNumber: "RAI-10001",
      purchaseType: "physical",
      productName: "Wireless Headphones",
      amountCents: 12999,
      purchasedAt: "2026-06-20T14:30:00Z",
      status: "refund_pending",
    });
  });

  it("maps API purchase details payloads to type-specific purchase details", () => {
    expect(mapApiPurchaseDetailsToPurchaseDetails(apiPhysicalPurchaseDetails)).toEqual({
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
    });
    expect(
      mapApiPurchaseDetailsToPurchaseDetails({
        purchase_id: "40000000-0000-4000-8000-000000000002",
        purchase_type: "digital",
        details: {
          issued_code: "DIG-RAI-10002",
          code_redeemed: true,
          code_redeemed_at: "2026-06-21T14:30:00Z",
          code_invalidated_at: null,
          code_delivered_at: "2026-06-20T14:30:00Z",
          refund_window_expires_at: "2026-07-05T14:30:00Z",
          refund_lock_reason: "code_redeemed",
        },
      }),
    ).toMatchObject({
      purchaseId: "40000000-0000-4000-8000-000000000002",
      purchaseType: "digital",
      details: {
        issuedCode: "DIG-RAI-10002",
        codeRedeemed: true,
        refundLockReason: "code_redeemed",
      },
    });
    expect(
      mapApiPurchaseDetailsToPurchaseDetails({
        purchase_id: "40000000-0000-4000-8000-000000000003",
        purchase_type: "subscription",
        details: {
          period_start: "2026-06-20T14:30:00Z",
          period_end: "2026-07-20T14:30:00Z",
          cancelled_at: null,
          service_ended_at: null,
          auto_renew: true,
          refund_proration_mode: "none",
          full_refund_window_expires_at: "2026-06-22T14:30:00Z",
          refund_window_expires_at: "2026-07-20T14:30:00Z",
        },
      }),
    ).toMatchObject({
      purchaseId: "40000000-0000-4000-8000-000000000003",
      purchaseType: "subscription",
      details: {
        autoRenew: true,
        refundProrationMode: "none",
      },
    });
  });

  it("maps API refund workflow payloads", () => {
    expect(mapApiRefundWorkflowToRefundWorkflow(apiRefundWorkflow)).toEqual({
      purchaseId: "40000000-0000-4000-8000-000000000003",
      purchaseType: "subscription",
      canEnterRefundWorkflow: true,
      canPrepareRefund: false,
      canIssueFunds: true,
      refundStage: "prepared",
      requiredAction: "issue_funds",
      refundableAmountCents: 1750,
      refundOutcome: "prorated",
      reasons: [],
      policyFacts: {
        auto_renew: false,
      },
    });
  });

  it("loads a user profile from the backend API", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: { user: apiUser },
          error: null,
          meta: {},
        }),
    });
    vi.stubGlobal("fetch", fetch);

    await expect(getUserProfile(apiUser.id)).resolves.toEqual({
      id: "20000000-0000-4000-8000-000000000001",
      firstName: "Avery",
      lastName: "Brooks",
      createdAt: "2026-07-03T00:00:00Z",
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/users/20000000-0000-4000-8000-000000000001",
      { cache: "no-store" },
    );
  });

  it("loads purchase history from the backend API", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: { purchases: [apiPurchase] },
          error: null,
          meta: {},
        }),
    });
    vi.stubGlobal("fetch", fetch);

    await expect(getUserPurchases(apiUser.id)).resolves.toEqual([
      {
        id: "40000000-0000-4000-8000-000000000001",
        orderNumber: "RAI-10001",
        purchaseType: "physical",
        productName: "Wireless Headphones",
        amountCents: 12999,
        purchasedAt: "2026-06-20T14:30:00Z",
        status: "refund_pending",
      },
    ]);
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/users/20000000-0000-4000-8000-000000000001/purchases",
      { cache: "no-store" },
    );
  });

  it("loads purchase details from the backend API", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: apiPhysicalPurchaseDetails,
          error: null,
          meta: {},
        }),
    });
    vi.stubGlobal("fetch", fetch);

    await expect(getPurchaseDetails(apiPurchase.id)).resolves.toEqual({
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
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/purchases/40000000-0000-4000-8000-000000000001/details",
      { cache: "no-store" },
    );
  });

  it("loads refund workflow from the backend API", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: apiRefundWorkflow,
          error: null,
          meta: {},
        }),
    });
    vi.stubGlobal("fetch", fetch);

    await expect(
      getRefundWorkflow("40000000-0000-4000-8000-000000000003"),
    ).resolves.toMatchObject({
      purchaseId: "40000000-0000-4000-8000-000000000003",
      purchaseType: "subscription",
      refundableAmountCents: 1750,
      refundOutcome: "prorated",
      refundStage: "prepared",
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/purchases/40000000-0000-4000-8000-000000000003/refund/eligibility",
      { cache: "no-store" },
    );
  });

  it("returns null when the user API is unavailable or unsuccessful", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getUserProfile(apiUser.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    await expect(getUserProfile(apiUser.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, data: null }),
    }));
    await expect(getUserProfile(apiUser.id)).resolves.toBeNull();
  });

  it("returns null when the purchases API is unavailable or unsuccessful", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getUserPurchases(apiUser.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    await expect(getUserPurchases(apiUser.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, data: null }),
    }));
    await expect(getUserPurchases(apiUser.id)).resolves.toBeNull();
  });

  it("returns null when the purchase details API is unavailable or unsuccessful", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getPurchaseDetails(apiPurchase.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    await expect(getPurchaseDetails(apiPurchase.id)).resolves.toBeNull();

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: false, data: null }),
      }),
    );
    await expect(getPurchaseDetails(apiPurchase.id)).resolves.toBeNull();
  });

  it("returns null when the refund workflow API is unavailable or unsuccessful", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getRefundWorkflow(apiPurchase.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    await expect(getRefundWorkflow(apiPurchase.id)).resolves.toBeNull();

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: false, data: null }),
      }),
    );
    await expect(getRefundWorkflow(apiPurchase.id)).resolves.toBeNull();
  });

  it("formats purchase values for display", () => {
    expect(formatCentsAsDollars(12999)).toBe("$129.99");
    expect(formatPurchaseDate("2026-06-20T14:30:00Z")).toBe(
      "Purchased Jun 20, 2026",
    );
    expect(formatPurchaseDate("not-a-date")).toBe("Purchased date unavailable");
    expect(formatPurchaseStatus("refund_pending")).toBe("Refund Pending");
  });
});
