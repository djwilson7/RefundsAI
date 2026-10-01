import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { DemoScreen } from "../../static-site/app/demo-screen";
import { ApplicationHelpLayer } from "@/components/application-help-layer";
import { mockCustomers } from "@/components/mock-customers";
import { buildDemoPurchases } from "./demo-purchases";
import { buildDemoAuditSessions } from "./demo-audit";
import { formatPurchaseDate } from "./application-api";

vi.mock("next/navigation", () => ({ usePathname: () => "/user-home/", useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
const network = vi.fn(() => { throw new Error("Static screen attempted a service request"); });
const stream = vi.fn(() => { throw new Error("Static screen attempted streaming"); });

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-10T20:00:00Z"));
  vi.stubEnv("NEXT_PUBLIC_REFUNDS_AI_STATIC_REFERENCE_DATE", "2020-01-01T14:00:00Z");
  vi.stubEnv("REFUNDS_AI_API_BASE_URL", undefined);
  vi.stubEnv("SUPABASE_DB_URL", undefined);
  vi.stubEnv("OPENAI_API_KEY", undefined);
  vi.stubGlobal("fetch", network);
  vi.stubGlobal("EventSource", stream);
  network.mockClear(); stream.mockClear();
});

afterEach(() => {
  cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.unstubAllEnvs();
  expect(network).not.toHaveBeenCalled();
  expect(stream).not.toHaveBeenCalled();
});

it("uses today's examples even when the static build snapshot is old", () => {
  const purchases = buildDemoPurchases(mockCustomers[0].id, "2026-10-10T14:00:00Z");
  render(<ApplicationHelpLayer><DemoScreen perspective="client" /></ApplicationHelpLayer>);
  expect(screen.getByRole("heading", { name: "Simulated Purchase History" })).toBeVisible();
  expect(screen.getAllByText(formatPurchaseDate(purchases[0].purchasedAt)).length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
  expect(screen.getByRole("textbox", { name: "Message the AI assistant" })).toBeDisabled();
  fireEvent.submit(screen.getByRole("textbox").closest("form")!);
});

it("renders exported purchase and audit detail screens without service configuration", () => {
  const purchase = buildDemoPurchases(mockCustomers[0].id)[0];
  const audit = buildDemoAuditSessions("2026-10-10T14:00:00Z")[0];
  const view = render(<ApplicationHelpLayer><DemoScreen perspective="purchase" id={purchase.id} /></ApplicationHelpLayer>);
  expect(screen.getByRole("heading", { name: purchase.productName })).toBeVisible();
  view.rerender(<ApplicationHelpLayer><DemoScreen perspective="admin" /></ApplicationHelpLayer>);
  expect(screen.getByText(/Total Token Usage/i)).toBeVisible();
  view.rerender(<ApplicationHelpLayer><DemoScreen perspective="audit" id={audit.invocation.id} /></ApplicationHelpLayer>);
  expect(screen.getByRole("heading", { name: audit.invocation.title })).toBeVisible();
});


