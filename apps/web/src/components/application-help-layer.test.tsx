import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
      screen.queryByText(/Select a purchase/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Prep Refund" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Issue Refund" }),
    ).not.toBeInTheDocument();
  });

  it("shows refund commands on purchase details with workflow-controlled state", async () => {
    mockedPathname = "/purchase-details/40000000-0000-4000-8000-000000000001";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: {
              can_issue_funds: false,
              can_prepare_refund: true,
            },
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

    expect(screen.queryByText(/Need help/)).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Prep Refund" }))
      .toBeEnabled();
    expect(screen.getByRole("button", { name: "Issue Refund" })).toBeDisabled();
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
            data: {
              can_issue_funds: false,
              can_prepare_refund: true,
            },
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: {
              can_issue_funds: true,
              can_prepare_refund: false,
            },
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
      await screen.findByRole("button", { name: "Prep Refund" }),
    );

    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
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
    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Issue Refund" }),
    ).toBeEnabled();
  });

  it("issues prepared refunds and refreshes purchase detail data", async () => {
    mockedPathname = "/purchase-details/40000000-0000-4000-8000-000000000001";
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: {
              can_issue_funds: true,
              can_prepare_refund: false,
            },
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: {
              can_issue_funds: false,
              can_prepare_refund: false,
            },
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
      await screen.findByRole("button", { name: "Issue Refund" }),
    );

    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "/api/purchases/40000000-0000-4000-8000-000000000001/refund/eligibility",
      { cache: "no-store" },
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/api/purchases/40000000-0000-4000-8000-000000000001/refund/issue",
      { method: "POST" },
    );
    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Issue Refund" })).toBeDisabled();
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
