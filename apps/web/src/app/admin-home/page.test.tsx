import { describe, expect, it, vi } from "vitest";
import AdminHome from "./page";
import { getModelAuditInvocationPage } from "@/lib/application-api";

vi.mock("@/lib/application-api", () => ({ getModelAuditInvocationPage: vi.fn().mockResolvedValue(null) }));

describe("admin home data source", () => {
  it("builds tour examples without the API", async () => {
    vi.mocked(getModelAuditInvocationPage).mockClear();
    const page = await AdminHome({ searchParams: Promise.resolve({ tour: "admin" }) });
    expect(page.props.tour).toBe(true);
    expect(page.props.invocations).toHaveLength(6);
    expect(getModelAuditInvocationPage).not.toHaveBeenCalled();
  });
  it("keeps the integrated route connected to the API", async () => {
    await AdminHome({ searchParams: Promise.resolve({}) });
    expect(getModelAuditInvocationPage).toHaveBeenCalledWith({ limit: 10 });
  });
});
