import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import UserHome from "./page";
import { getUserProfile, getUserPurchases } from "@/lib/application-api";
import { mockCustomers } from "@/components/mock-customers";
import { ApplicationHelpLayer } from "@/components/application-help-layer";

vi.mock("next/navigation", () => ({usePathname: () => "/user-home", useRouter: () => ({push: vi.fn()})}));
vi.mock("@/lib/application-api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/application-api")>(),
  getUserProfile: vi.fn().mockResolvedValue(null),
  getUserPurchases: vi.fn().mockResolvedValue([]),
}));

afterEach(() => { vi.clearAllMocks(); window.sessionStorage.clear(); });

describe("client tour purchase history", () => {
  it("generates display-only cards without API calls or purchase storage", async () => {
    render(<ApplicationHelpLayer>{await UserHome({searchParams: Promise.resolve({customerId: mockCustomers[0].id, tour: "client"})})}</ApplicationHelpLayer>);
    expect(getUserProfile).not.toHaveBeenCalled();
    expect(getUserPurchases).not.toHaveBeenCalled();
    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(screen.getByText("Wireless Headphones")).toBeInTheDocument();
    expect(screen.getByRole("heading", {name: "Simulated Purchase History"})).toBeInTheDocument();
    expect(screen.getByRole("button", {name: "Open help chat"})).toBeInTheDocument();
    expect(screen.queryAllByRole("link").filter((link) => link.getAttribute("href")?.includes("purchase-details"))).toHaveLength(12);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("keeps the integrated dashboard connected to backend data", async () => {
    await UserHome({searchParams: Promise.resolve({customerId: mockCustomers[0].id})});
    expect(getUserProfile).toHaveBeenCalledWith(mockCustomers[0].id);
    expect(getUserPurchases).toHaveBeenCalledWith(mockCustomers[0].id);
  });
});
