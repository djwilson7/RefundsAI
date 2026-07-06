import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApplicationHelpLayer,
  useApplicationHelpLayer,
} from "./application-help-layer";
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
    window.sessionStorage.clear();
    window.history.pushState({}, "", "/");
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
    expect(
      screen.getByLabelText("Message the AI assistant"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Voice input coming soon" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Send message" }),
    ).toBeDisabled();
  });

  it("does not submit empty chat messages", () => {
    mockedPathname = "/user-home";
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    render(
      <ApplicationHelpLayer>
        <main>Purchase summary</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
    fireEvent.change(screen.getByLabelText("Message the AI assistant"), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(fetch).not.toHaveBeenCalled();
  });

  it("submits text chat messages and renders the assistant response", async () => {
    mockedPathname = "/user-home";
    window.history.pushState(
      {},
      "",
      "/user-home?customerId=20000000-0000-4000-8000-000000000001",
    );
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: {
            message: {
              content: "The AI workflow infrastructure is connected.",
            },
          },
        }),
    });
    vi.stubGlobal("fetch", fetch);

    render(
      <ApplicationHelpLayer>
        <main>Purchase summary</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
    fireEvent.change(screen.getByLabelText("Message the AI assistant"), {
      target: { value: "How many digital purchases have I made?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(fetch).toHaveBeenCalledWith("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: "How many digital purchases have I made?",
        customer_id: "20000000-0000-4000-8000-000000000001",
        purchase_id: null,
        page_context: {
          surface: "purchase_history",
          purchase_id: null,
        },
        conversation_state: {},
      }),
    });
    expect(
      screen.getByText("How many digital purchases have I made?"),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("The AI workflow infrastructure is connected."),
    ).toBeInTheDocument();
  });

  it("scrolls the chat transcript as turns are added", async () => {
    mockedPathname = "/user-home";
    const scrollMocks = installTranscriptScrollMocks(720);
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: {
            message: {
              content: "Here is the scoped answer.",
            },
          },
        }),
    });
    vi.stubGlobal("fetch", fetch);

    try {
      render(
        <ApplicationHelpLayer>
          <main>Purchase summary</main>
          <HelpTriggerButton />
        </ApplicationHelpLayer>,
      );

      fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));

      await waitFor(() => expect(scrollMocks.scrollTo).toHaveBeenCalled());
      expect(
        screen.getByRole("log", { name: "Chat transcript" }),
      ).toBeInTheDocument();
      scrollMocks.scrollTo.mockClear();

      fireEvent.change(screen.getByLabelText("Message the AI assistant"), {
        target: { value: "Can you list them please?" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Send message" }));

      expect(
        await screen.findByText("Here is the scoped answer."),
      ).toBeInTheDocument();
      await waitFor(() =>
        expect(scrollMocks.scrollTo).toHaveBeenLastCalledWith({
          top: 720,
          behavior: "smooth",
        }),
      );
    } finally {
      scrollMocks.restore();
    }
  });

  it("submits chat messages with Enter from the textarea", async () => {
    mockedPathname = "/user-home";
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: {
            message: {
              content: "Enter submitted the message.",
            },
          },
        }),
    });
    vi.stubGlobal("fetch", fetch);

    render(
      <ApplicationHelpLayer>
        <main>Purchase summary</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
    const input = screen.getByLabelText("Message the AI assistant");
    fireEvent.change(input, {
      target: { value: "Can I return this?" },
    });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(fetch).toHaveBeenCalledWith("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: "Can I return this?",
        customer_id: null,
        purchase_id: null,
        page_context: {
          surface: "purchase_history",
          purchase_id: null,
        },
        conversation_state: {},
      }),
    });
    expect(await screen.findByText("Enter submitted the message.")).toBeInTheDocument();
  });

  it("does not submit chat messages with Shift Enter", () => {
    mockedPathname = "/user-home";
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    render(
      <ApplicationHelpLayer>
        <main>Purchase summary</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
    const input = screen.getByLabelText("Message the AI assistant");
    fireEvent.change(input, {
      target: { value: "Line one" },
    });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter", shiftKey: true });
    fireEvent.change(input, {
      target: { value: "Line one\nLine two" },
    });

    expect(fetch).not.toHaveBeenCalled();
    expect(input).toHaveValue("Line one\nLine two");
  });

  it("sends returned conversation state on follow-up chat messages", async () => {
    mockedPathname = "/user-home";
    window.history.pushState(
      {},
      "",
      "/user-home?customerId=20000000-0000-4000-8000-000000000001",
    );
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: {
              message: {
                content: "You made 2 digital purchases.",
              },
              conversation_state: {
                selected_purchase_type: "digital",
                selected_product: null,
                selected_purchase_id: null,
                selected_policy_scope: null,
                selected_date_range: null,
              },
            },
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: {
              message: {
                content: "Digital products can be refunded within 15 days.",
              },
              conversation_state: {
                selected_purchase_type: "digital",
                selected_product: null,
                selected_purchase_id: null,
                selected_policy_scope: "product_type",
                selected_date_range: null,
              },
            },
          }),
      });
    vi.stubGlobal("fetch", fetch);

    render(
      <ApplicationHelpLayer>
        <main>Purchase summary</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
    fireEvent.change(screen.getByLabelText("Message the AI assistant"), {
      target: { value: "Which of my purchases are digital?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await screen.findByText("You made 2 digital purchases.");

    fireEvent.change(screen.getByLabelText("Message the AI assistant"), {
      target: { value: "What is the refund policy for those purchases?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await screen.findByText("Digital products can be refunded within 15 days.");

    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/api/chat",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: "What is the refund policy for those purchases?",
          customer_id: "20000000-0000-4000-8000-000000000001",
          purchase_id: null,
          page_context: {
            surface: "purchase_history",
            purchase_id: null,
          },
          conversation_state: {
            selected_purchase_type: "digital",
            selected_product: null,
            selected_purchase_id: null,
            selected_policy_scope: null,
            selected_date_range: null,
          },
        }),
      },
    );
  });

  it("uses selected mock customer context for purchase detail chat messages", async () => {
    mockedPathname = "/purchase-details/40000000-0000-4000-8000-000000000001";
    window.sessionStorage.setItem(
      "refunds-ai:selected-mock-customer",
      JSON.stringify({
        id: "20000000-0000-4000-8000-000000000002",
        firstName: "Maya",
        lastName: "Collins",
      }),
    );
    const fetch = vi
      .fn()
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
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: {
              message: {
                content: "You made 4 purchases.",
              },
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
    fireEvent.change(screen.getByLabelText("Message the AI assistant"), {
      target: { value: "How many purchases have I made?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await screen.findByText("You made 4 purchases.");
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/api/chat",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: "How many purchases have I made?",
          customer_id: "20000000-0000-4000-8000-000000000002",
          purchase_id: "40000000-0000-4000-8000-000000000001",
          page_context: {
            surface: "purchase_detail",
            purchase_id: "40000000-0000-4000-8000-000000000001",
          },
          conversation_state: {},
        }),
      },
    );
  });

  it("renders a chat error when the chat service request fails", async () => {
    mockedPathname = "/user-home";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
      }),
    );

    render(
      <ApplicationHelpLayer>
        <main>Purchase summary</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
    fireEvent.change(screen.getByLabelText("Message the AI assistant"), {
      target: { value: "Can you help me?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(
      await screen.findByText(
        "I could not reach the AI chat service. Please try again.",
      ),
    ).toBeInTheDocument();
  });

  it("renders a chat error when the chat response is unsuccessful", async () => {
    mockedPathname = "/user-home";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            success: false,
            data: null,
          }),
      }),
    );

    render(
      <ApplicationHelpLayer>
        <main>Purchase summary</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
    fireEvent.change(screen.getByLabelText("Message the AI assistant"), {
      target: { value: "Can you help me?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(
      await screen.findByText(
        "I could not reach the AI chat service. Please try again.",
      ),
    ).toBeInTheDocument();
  });

  it("does not submit a second chat message while a request is in flight", async () => {
    mockedPathname = "/user-home";
    const fetch = vi.fn(
      () =>
        new Promise<Response>(() => {
          // Keep the request pending so the composer remains in sending state.
        }),
    );
    vi.stubGlobal("fetch", fetch);

    render(
      <ApplicationHelpLayer>
        <main>Purchase summary</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));
    fireEvent.change(screen.getByLabelText("Message the AI assistant"), {
      target: { value: "Can you help me?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled(),
    );
    fireEvent.submit(screen.getByLabelText("Message the AI assistant").closest("form")!);

    expect(fetch).toHaveBeenCalledTimes(1);
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
    expect(
      screen.getByLabelText("Message the AI assistant"),
    ).toBeInTheDocument();
  });

  it("ignores refund workflow update events for other purchases", async () => {
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
    mockedPathname = "/purchase-details/40000000-0000-4000-8000-000000000001";
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
    mockedPathname = "/purchase-details/40000000-0000-4000-8000-000000000001";
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

  it("keeps current workflow state when refund preparation fails", async () => {
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
    expect(refresh).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Issue Refund" })).toBeDisabled();
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

  it("keeps current workflow state when refund issuance fails", async () => {
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
    expect(refresh).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Issue Refund" })).toBeEnabled();
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

  it("requires the help-layer context provider for direct hook access", () => {
    function MissingProviderConsumer() {
      useApplicationHelpLayer();

      return null;
    }

    expect(() => render(<MissingProviderConsumer />)).toThrow(
      "useApplicationHelpLayer must be used within ApplicationHelpLayer.",
    );
  });
});

function installTranscriptScrollMocks(scrollHeight: number) {
  const originalScrollTo = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    "scrollTo",
  );
  const originalScrollHeight = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    "scrollHeight",
  );
  const scrollTo = vi.fn();

  Object.defineProperty(HTMLElement.prototype, "scrollTo", {
    configurable: true,
    value: scrollTo,
  });
  Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
    configurable: true,
    get: () => scrollHeight,
  });

  return {
    scrollTo,
    restore: () => {
      if (originalScrollTo) {
        Object.defineProperty(
          HTMLElement.prototype,
          "scrollTo",
          originalScrollTo,
        );
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, "scrollTo");
      }

      if (originalScrollHeight) {
        Object.defineProperty(
          HTMLElement.prototype,
          "scrollHeight",
          originalScrollHeight,
        );
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, "scrollHeight");
      }
    },
  };
}
