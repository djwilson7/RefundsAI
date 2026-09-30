import { describe, expect, it, vi } from "vitest";
import AdminSessionPage from "./page";
import { getModelAuditSessionDetail } from "@/lib/application-api";

vi.mock("@/lib/application-api", () => ({ getModelAuditSessionDetail: vi.fn().mockResolvedValue(null) }));
vi.mock("next/navigation", () => ({ notFound: () => { throw new Error("not found"); } }));

describe("admin session data source", () => {
  it("loads a complete simulated detail without the API", async () => {
    vi.mocked(getModelAuditSessionDetail).mockClear();
    const page = await AdminSessionPage({ params: Promise.resolve({ sessionId: "demo-audit-4" }), searchParams: Promise.resolve({ tour: "admin" }) });
    expect(page.props.tour).toBe(true);
    expect(page.props.detail.metrics.modelCalls).toBe(0);
    expect(page.props.detail.toolCalls).toHaveLength(2);
    expect(getModelAuditSessionDetail).not.toHaveBeenCalled();
  });
  it("rejects unknown simulated sessions", async () => {
    await expect(AdminSessionPage({ params: Promise.resolve({ sessionId: "unknown" }), searchParams: Promise.resolve({ tour: "admin" }) })).rejects.toThrow("not found");
  });
  it("keeps integrated detail reads on the API", async () => {
    await AdminSessionPage({ params: Promise.resolve({ sessionId: "live-session" }), searchParams: Promise.resolve({}) });
    expect(getModelAuditSessionDetail).toHaveBeenCalledWith("live-session");
  });
});
