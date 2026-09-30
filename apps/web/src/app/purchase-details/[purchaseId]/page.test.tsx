import { beforeEach, describe, expect, it, vi } from "vitest";
import PurchaseDetailsPage from "./page";
import { getPurchaseDetails, getRefundWorkflow } from "@/lib/application-api";
import { mockCustomers } from "@/components/mock-customers";

vi.mock("next/navigation", () => ({ notFound: () => { throw new Error("not found"); } }));
vi.mock("@/lib/application-api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/application-api")>(),
  getPurchaseDetails: vi.fn().mockResolvedValue(null),
  getRefundWorkflow: vi.fn().mockResolvedValue(null),
}));

describe("purchase detail route", () => {
  beforeEach(() => vi.clearAllMocks());
  it("renders tour details without loading live purchase or refund data", async () => {
    const result = await PurchaseDetailsPage({ params: Promise.resolve({ purchaseId: "40000000-0000-4000-8000-000000000001" }), searchParams: Promise.resolve({ customerId: mockCustomers[0].id, tour: "client" }) });
    expect(result.props.detail.purchase.productName).toBeTruthy();
    expect(getPurchaseDetails).not.toHaveBeenCalled();
    expect(getRefundWorkflow).not.toHaveBeenCalled();
  });
  it("rejects tour links to another customer's purchase", async () => {
    await expect(PurchaseDetailsPage({ params: Promise.resolve({ purchaseId: "40000000-0000-4000-8000-000000000001" }), searchParams: Promise.resolve({ customerId: mockCustomers[1].id, tour: "client" }) })).rejects.toThrow("not found");
    expect(getPurchaseDetails).not.toHaveBeenCalled();
  });
  it("preserves live detail and workflow loading outside the tour", async () => {
    await PurchaseDetailsPage({ params: Promise.resolve({ purchaseId: "live-purchase" }), searchParams: Promise.resolve({}) });
    expect(getPurchaseDetails).toHaveBeenCalledWith("live-purchase");
    expect(getRefundWorkflow).toHaveBeenCalledWith("live-purchase");
  });
});
