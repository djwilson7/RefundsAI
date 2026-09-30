import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import UserHome from "@/app/user-home/page";
import AdminHome from "@/app/admin-home/page";
import PurchaseDetailsPage from "@/app/purchase-details/[purchaseId]/page";
import AdminSessionPage from "@/app/admin/sessions/[sessionId]/page";
import { ApplicationHelpLayer } from "@/components/application-help-layer";
import { AdminAuditLiveUpdates } from "@/components/admin-audit-live-updates";
import { AdminAuditSessionList } from "@/components/admin-audit-session-list";
import { mockCustomers } from "@/components/mock-customers";
import { buildDemoAuditSessions } from "./demo-audit";
import { getUserProfile, getUserPurchases, getPurchaseDetails, getRefundWorkflow, getModelAuditInvocationPage, getModelAuditInvocation, getModelAuditSessionDetail } from "./application-api";
import { POST as chat } from "@/app/api/chat/route";
import { GET as sessions } from "@/app/api/admin/audit/sessions/route";
import { GET as session } from "@/app/api/admin/audit/sessions/[sessionId]/route";
import { GET as events } from "@/app/api/admin/audit/sessions/[sessionId]/events/route";
import { GET as stream } from "@/app/api/admin/audit/events/stream/route";
import { GET as eligibility } from "@/app/api/purchases/[purchaseId]/refund/eligibility/route";
import { POST as prepare } from "@/app/api/purchases/[purchaseId]/refund/request/route";
import { POST as issue } from "@/app/api/purchases/[purchaseId]/refund/issue/route";
import { POST as carrier } from "@/app/api/purchases/[purchaseId]/physical/confirm-carrier-acceptance/route";
import nextConfig from "../../next.config";

vi.mock("next/navigation", () => ({ usePathname: () => "/user-home", useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }), notFound: () => { throw new Error("not found"); } }));
const network = vi.fn(() => { throw new Error("Demo attempted network access"); });
const liveStream = vi.fn(() => { throw new Error("Demo attempted streaming"); });

beforeEach(() => {
  vi.stubGlobal("fetch", network);
  vi.stubGlobal("EventSource", liveStream);
  network.mockClear(); liveStream.mockClear();
});
afterEach(() => { vi.unstubAllGlobals(); window.sessionStorage.clear(); });

describe("frontend-only deployment", () => {
  it("restricts browser services and assets to the demo origin", async () => {
    const headers = await nextConfig.headers!();
    const policy = headers[0].headers.find((header) => header.key === "Content-Security-Policy")?.value;
    expect(policy).toContain("default-src 'self'");
    expect(policy).toContain("connect-src 'self'");
    expect(policy).toContain("frame-src 'none'");
  });
  it("cannot reach services through any proxy, even with malformed requests", async () => {
    const request = new Request("http://localhost/api/test?tour=live", { method: "POST", body: "not JSON" });
    const context = { params: Promise.resolve({ purchaseId: "any", sessionId: "any" }) };
    const responses = await Promise.all([chat(request), sessions(request), session(request, context), events(request, context), stream(request), eligibility(request, context), prepare(request, context), issue(request, context), carrier(request, context)]);
    for (const response of responses) {
      expect(response.status).toBe(404);
      expect((await response.json()).error.code).toBe("DEMO_SERVICE_DISABLED");
    }
    expect(network).not.toHaveBeenCalled();
  });

  it("blocks the API data layer independently of page routing", async () => {
    const results = await Promise.all([getUserProfile("any"), getUserPurchases("any"), getPurchaseDetails("any"), getRefundWorkflow("any"), getModelAuditInvocationPage(), getModelAuditInvocation("any"), getModelAuditSessionDetail("any")]);
    expect(results.every((result) => result === null)).toBe(true);
    expect(network).not.toHaveBeenCalled();
  });

  it("serves generated pages when tour parameters are absent or changed", async () => {
    const customerId = mockCustomers[0].id;
    const page = await UserHome({ searchParams: Promise.resolve({ customerId, tour: "live" }) });
    expect(page.props.demo).toBe(true);
    const admin = await AdminHome({ searchParams: Promise.resolve({}) });
    expect(admin.props.tour).toBe(true);
    const purchase = await PurchaseDetailsPage({ params: Promise.resolve({ purchaseId: page.props.purchases[0].id }), searchParams: Promise.resolve({ customerId }) });
    expect(purchase.props.detail.purchase.id).toBe(page.props.purchases[0].id);
    const audit = await AdminSessionPage({ params: Promise.resolve({ sessionId: "demo-audit-1" }), searchParams: Promise.resolve({}) });
    expect(audit.props.tour).toBe(true);
    await expect(AdminSessionPage({ params: Promise.resolve({ sessionId: "live-session" }), searchParams: Promise.resolve({}) })).rejects.toThrow("not found");
    expect(network).not.toHaveBeenCalled();
  });

  it("shows a local support preview and cannot submit to chat", async () => {
    const page = await UserHome({ searchParams: Promise.resolve({}) });
    render(<ApplicationHelpLayer>{page}</ApplicationHelpLayer>);
    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
    expect(screen.getByText(/does not connect to an AI service/)).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Message the AI assistant" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    fireEvent.submit(screen.getByRole("textbox").closest("form")!);
    expect(network).not.toHaveBeenCalled();
    expect(liveStream).not.toHaveBeenCalled();
  });

  it("suppresses background reads and SSE even if live components are mounted accidentally", () => {
    render(<><AdminAuditLiveUpdates sessionId="any" /><AdminAuditSessionList initialHasMore initialInvocations={buildDemoAuditSessions("2026-09-30T12:00:00Z").map((item) => ({ ...item.invocation, description: "Original prompt unavailable" }))} /></>);
    expect(network).not.toHaveBeenCalled();
    expect(liveStream).not.toHaveBeenCalled();
  });
});
