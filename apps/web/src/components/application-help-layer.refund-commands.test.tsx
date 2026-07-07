import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getNavigationRefreshMock,
  resetApplicationHelpLayerTestState,
  setMockedPathname,
} from "./application-help-layer.test-utils";
import { ApplicationHelpLayer } from "./application-help-layer";
import { HelpTriggerButton } from "./help-trigger-button";

describe("ApplicationHelpLayer", () => {
  afterEach(() => {
    resetApplicationHelpLayerTestState();
  });

  it("shows refund commands on purchase details with workflow-controlled state", async () => {
    setMockedPathname("/purchase-details/40000000-0000-4000-8000-000000000001");
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
    expect(
      screen.getByLabelText("Message the AI assistant"),
    ).toBeInTheDocument();
  });

  it("ignores refund workflow update events for other purchases", async () => {
    setMockedPathname("/purchase-details/40000000-0000-4000-8000-000000000001");
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
    expect(await screen.findByRole("button", { name: "Prep Refund" }))
      .toBeEnabled();

    window.dispatchEvent(
      new CustomEvent("refunds-ai:refund-workflow-updated", {
        detail: {
          purchaseId: "different-purchase",
          workflow: {
            canIssueFunds: true,
            canPrepareRefund: false,
          },
        },
      }),
    );

    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Issue Refund" })).toBeDisabled();
  });

  it("keeps refund commands disabled when workflow loading fails", async () => {
    setMockedPathname("/purchase-details/40000000-0000-4000-8000-000000000001");
    const fetch = vi.fn().mockResolvedValue({
      ok: false,
    });
    vi.stubGlobal("fetch", fetch);

    render(
      <ApplicationHelpLayer>
        <main>Purchase details</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Issue Refund" })).toBeDisabled();
  });

  it("keeps refund commands disabled when workflow response is unsuccessful", async () => {
    setMockedPathname("/purchase-details/40000000-0000-4000-8000-000000000001");
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: false,
          data: null,
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

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Issue Refund" })).toBeDisabled();
  });

  it("starts refund preparation and refreshes purchase detail data", async () => {
    setMockedPathname("/purchase-details/40000000-0000-4000-8000-000000000001");
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

    await waitFor(() => expect(getNavigationRefreshMock()).toHaveBeenCalledTimes(1));
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
    expect(getNavigationRefreshMock()).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Issue Refund" }),
    ).toBeEnabled();
  });

  it("keeps current workflow state when refund preparation fails", async () => {
    setMockedPathname("/purchase-details/40000000-0000-4000-8000-000000000001");
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
        ok: false,
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

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(getNavigationRefreshMock()).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Issue Refund" })).toBeDisabled();
  });

  it("issues prepared refunds and refreshes purchase detail data", async () => {
    setMockedPathname("/purchase-details/40000000-0000-4000-8000-000000000001");
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

    await waitFor(() => expect(getNavigationRefreshMock()).toHaveBeenCalledTimes(1));
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

  it("keeps current workflow state when refund issuance fails", async () => {
    setMockedPathname("/purchase-details/40000000-0000-4000-8000-000000000001");
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
        ok: false,
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

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(getNavigationRefreshMock()).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Issue Refund" })).toBeEnabled();
  });
});
