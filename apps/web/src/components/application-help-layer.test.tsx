import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApplicationHelpLayer } from "./application-help-layer";
import { HelpTriggerButton } from "./help-trigger-button";

let mockedPathname = "/user-home";
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => mockedPathname,
  useRouter: () => ({
    refresh,
  }),
}));

describe("ApplicationHelpLayer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    refresh.mockClear();
  });

  it("opens the persistent shell panel from a page-owned trigger", () => {
    mockedPathname = "/user-home";

    render(
      <ApplicationHelpLayer>
        <main>Purchase summary</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    const button = screen.getByRole("button", { name: "Open help chat" });

    expect(
      screen.queryByRole("complementary", { name: "Help panel" }),
    ).not.toBeInTheDocument();
    expect(button).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(button);

    expect(
      screen.getByRole("button", { name: "Close help chat" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("complementary", { name: "Help panel" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Help")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Select a purchase to view available support options like refunds, returns, delivery status, or subscription changes.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start refund process" }),
    ).not.toBeInTheDocument();
  });

  it("shows the refund process command placeholder on purchase details", async () => {
    mockedPathname = "/purchase-details/40000000-0000-4000-8000-000000000001";
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

    render(
      <ApplicationHelpLayer>
        <main>Purchase details</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));

    expect(
      await screen.findByText("Need help with this purchase?"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Start refund process" }),
    ).toHaveAttribute("type", "button");
  });

  it("starts refund preparation and refreshes purchase detail data", async () => {
    mockedPathname = "/purchase-details/40000000-0000-4000-8000-000000000001";
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: { can_prepare_refund: true },
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: { can_prepare_refund: false },
          }),
      });
    vi.stubGlobal("fetch", fetch);

    render(
      <ApplicationHelpLayer>
        <main>Purchase details</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Start refund process" }),
    );

    expect(
      await screen.findByText(/Refund preparation has started/),
    ).toBeInTheDocument();
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "/api/purchases/40000000-0000-4000-8000-000000000001/refund/eligibility",
      { cache: "no-store" },
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/api/purchases/40000000-0000-4000-8000-000000000001/refund/request",
      { method: "POST" },
    );
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(
      screen.queryByRole("button", { name: "Start refund process" }),
    ).not.toBeInTheDocument();
  });

  it("does not render the trigger or panel outside purchase surfaces", () => {
    mockedPathname = "/";

    render(
      <ApplicationHelpLayer>
        <main>Mock auth</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    expect(
      screen.queryByRole("button", { name: "Open help chat" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("complementary", { name: "Help panel" }),
    ).not.toBeInTheDocument();
  });
});
