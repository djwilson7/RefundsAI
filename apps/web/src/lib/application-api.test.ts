import { afterEach, describe, expect, it, vi } from "vitest";
import {
  formatCentsAsDollars,
  formatPurchaseDate,
  formatPurchaseStatus,
  getUserProfile,
  getUserPurchases,
  mapApiPurchaseToCustomerPurchase,
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
      productName: "Wireless Headphones",
      amountCents: 12999,
      purchasedAt: "2026-06-20T14:30:00Z",
      status: "refund_pending",
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

  it("formats purchase values for display", () => {
    expect(formatCentsAsDollars(12999)).toBe("$129.99");
    expect(formatPurchaseDate("2026-06-20T14:30:00Z")).toBe(
      "Purchased Jun 20, 2026",
    );
    expect(formatPurchaseDate("not-a-date")).toBe("Purchased date unavailable");
    expect(formatPurchaseStatus("refund_pending")).toBe("Refund Pending");
  });
});
