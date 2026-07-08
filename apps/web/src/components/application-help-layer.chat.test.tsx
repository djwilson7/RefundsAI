import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getNavigationRefreshMock,
  installTranscriptScrollMocks,
  resetApplicationHelpLayerTestState,
  setMockedPathname,
} from "./application-help-layer.test-utils";
import { ApplicationHelpLayer } from "./application-help-layer";
import { HelpTriggerButton } from "./help-trigger-button";

describe("ApplicationHelpLayer", () => {
  afterEach(() => {
    resetApplicationHelpLayerTestState();
  });

  it("does not submit empty chat messages", () => {
    setMockedPathname("/user-home");
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
    setMockedPathname("/user-home");
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
    expect(getNavigationRefreshMock()).not.toHaveBeenCalled();
  });

  it("refreshes purchase data after a chat purchase-data side effect", async () => {
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
              message: {
                content: "I have started the refund workflow.",
              },
              conversation_state: {
                active_refund_context: {
                  purchase_id: "40000000-0000-4000-8000-000000000001",
                },
              },
              side_effects: [
                {
                  type: "purchase_data_changed",
                  customer_id: "20000000-0000-4000-8000-000000000001",
                  purchase_ids: ["40000000-0000-4000-8000-000000000001"],
                  reason: "refund_mutation_completed",
                },
              ],
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
    fireEvent.change(screen.getByLabelText("Message the AI assistant"), {
      target: { value: "Confirm invalidate code and issue refund" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(
      await screen.findByText("I have started the refund workflow."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Confirm invalidate code and issue refund"),
    ).toBeInTheDocument();
    await waitFor(() => expect(getNavigationRefreshMock()).toHaveBeenCalledTimes(1));
    expect(fetch).toHaveBeenNthCalledWith(
      3,
      "/api/purchases/40000000-0000-4000-8000-000000000001/refund/eligibility",
      { cache: "no-store" },
    );
    expect(screen.getByRole("button", { name: "Prep Refund" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Issue Refund" })).toBeEnabled();
  });

  it("scrolls the chat transcript as turns are added", async () => {
    setMockedPathname("/user-home");
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
    setMockedPathname("/user-home");
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
    expect(input).toHaveFocus();
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
    setMockedPathname("/user-home");
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
    setMockedPathname("/user-home");
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
    setMockedPathname("/purchase-details/40000000-0000-4000-8000-000000000001");
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
    setMockedPathname("/user-home");
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
    setMockedPathname("/user-home");
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
    setMockedPathname("/user-home");
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

    expect(
      await screen.findByLabelText("Assistant response pending"),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled(),
    );
    const input = screen.getByLabelText("Message the AI assistant");
    expect(input).toHaveFocus();
    expect(input).not.toBeDisabled();
    fireEvent.change(input, {
      target: { value: "Also check my last order." },
    });
    expect(input).toHaveValue("Also check my last order.");
    fireEvent.submit(screen.getByLabelText("Message the AI assistant").closest("form")!);

    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
