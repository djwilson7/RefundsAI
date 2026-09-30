"use client";

import {
  createContext,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { ArrowUpIcon } from "./icons";
import { loadSelectedMockCustomerId } from "./mock-auth-session";
import styles from "./application-help-layer.module.css";
import { isDemoModeEnabled } from "@/lib/demo-mode";

type ApplicationHelpLayerProps = Readonly<{
  children: ReactNode;
  demoMode?: boolean;
}>;

type ApplicationHelpContextValue = Readonly<{
  isAvailable: boolean;
  isOpen: boolean;
  panelId: string;
  toggle: () => void;
}>;

type ChatMessage = Readonly<{
  id: string;
  role: "assistant" | "user";
  content: string;
}>;

type ConversationState = Readonly<{
  selected_purchase_type?: string | null;
  selected_product?: string | null;
  selected_purchase_id?: string | null;
  selected_purchase_ids?: string[];
  selected_scope_label?: string | null;
  selected_policy_scope?: string | null;
  selected_date_range?: Record<string, string> | null;
  selected_refund_purchase_ids?: string[];
  selected_refund_context?: string | null;
  active_refund_context?: Record<string, unknown> | null;
  active_result_set?: Record<string, unknown> | null;
  active_workflow?: Record<string, unknown> | null;
  pending_refund_action?: Record<string, unknown> | null;
  current_page?: Record<string, unknown> | null;
}>;

type ChatSideEffect = Readonly<{
  type?: string;
  customer_id?: string;
  purchase_ids?: string[];
  reason?: string;
}>;

type PageContext = Readonly<{
  surface: "purchase_history" | "purchase_detail";
  purchase_id: string | null;
}>;

const ApplicationHelpContext =
  createContext<ApplicationHelpContextValue | null>(null);
const initialChatMessages: ChatMessage[] = [
  {
    id: "welcome",
    role: "assistant",
    content: "Ask me about your purchases, orders, or account activity.",
  },
];

const demoChatMessages: ChatMessage[] = [
  { id: "demo-intro", role: "assistant", content: "This is a local preview of the support experience. The tour does not connect to an AI service or change purchases." },
  { id: "demo-question", role: "user", content: "What is the refund policy for digital purchases?" },
  { id: "demo-answer", role: "assistant", content: "Digital purchases have a 15-day refund window, and the code must remain unredeemed. Open a purchase to explore its details, or swap to Admin to inspect example audit sessions." },
];

export function ApplicationHelpLayer({ children, demoMode: modeFromServer = false }: ApplicationHelpLayerProps) {
  const demoMode = modeFromServer || isDemoModeEnabled();
  const [isOpen, setIsOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] =
    useState<ChatMessage[]>(demoMode ? demoChatMessages : initialChatMessages);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const chatInputRef = useRef<HTMLTextAreaElement | null>(null);
  const pageContentRef = useRef<HTMLDivElement | null>(null);
  const closePanelRef = useRef<HTMLButtonElement | null>(null);
  const chatMessageIdCounterRef = useRef(0);
  const chatSessionVersionRef = useRef(0);
  const [conversationState, setConversationState] =
    useState<ConversationState>({});
  const [chatState, setChatState] = useState<"idle" | "sending" | "error">(
    "idle",
  );
  const panelId = useId();
  const pathname = usePathname();
  const router = useRouter();
  const isAvailable = isHelpAvailable(pathname);
  const purchaseId = getPurchaseIdFromPathname(pathname);
  const resetChat = useCallback(() => {
    chatSessionVersionRef.current += 1;
    chatMessageIdCounterRef.current = 0;
    setChatInput("");
    setChatMessages(demoMode ? demoChatMessages : initialChatMessages);
    setConversationState({});
    setChatState("idle");
  }, [demoMode]);
  const toggleHelpPanel = useCallback(() => {
    setIsOpen((current) => {
      if (current) {
        resetChat();
      }

      return !current;
    });
  }, [resetChat]);
  const contextValue = useMemo<ApplicationHelpContextValue>(
    () => ({
      isAvailable,
      isOpen,
      panelId,
      toggle: toggleHelpPanel,
    }),
    [isAvailable, isOpen, panelId, toggleHelpPanel],
  );

  useEffect(() => {
    if (!isOpen || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(max-width: 900px)");
    const content = pageContentRef.current;
    const previousOverflow = document.body.style.overflow;
    const previousInert = content?.inert ?? false;
    const returnFocus = document.activeElement as HTMLElement | null;
    const updatePanelMode = () => {
      document.body.style.overflow = media.matches ? "hidden" : previousOverflow;
      if (content) content.inert = media.matches || previousInert;
      if (media.matches) closePanelRef.current?.focus();
    };
    updatePanelMode();
    media.addEventListener("change", updatePanelMode);
    return () => {
      media.removeEventListener("change", updatePanelMode);
      document.body.style.overflow = previousOverflow;
      if (content) content.inert = previousInert;
      returnFocus?.focus();
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const transcript = transcriptRef.current;

    if (!transcript) {
      return;
    }

    if (typeof transcript.scrollTo === "function") {
      transcript.scrollTo({
        top: transcript.scrollHeight,
        behavior: "smooth",
      });
      return;
    }

    transcript.scrollTop = transcript.scrollHeight;
  }, [chatMessages.length, isOpen]);

  async function submitChatMessage() {
    if (demoMode) return;
    const message = chatInput.trim();

    if (!message || chatState === "sending") {
      return;
    }

    const userMessage: ChatMessage = {
      id: nextChatMessageId("user", chatMessageIdCounterRef),
      role: "user",
      content: message,
    };
    const requestSessionVersion = chatSessionVersionRef.current;

    setChatInput("");
    setChatState("sending");
    setChatMessages((messages) => [...messages, userMessage]);
    chatInputRef.current?.focus();

    try {
      const chatResponse = await sendChatMessage(
        message,
        purchaseId,
        buildPageContext(pathname, purchaseId),
        getCustomerIdFromCurrentUrl() ?? loadSelectedMockCustomerId(),
        conversationState,
      );

      if (requestSessionVersion !== chatSessionVersionRef.current) {
        return;
      }

      setChatMessages((messages) => [
        ...messages,
        {
          id: nextChatMessageId("assistant", chatMessageIdCounterRef),
          role: "assistant",
          content: chatResponse.message,
        },
      ]);
      setConversationState(chatResponse.conversationState);
      await refreshPurchaseDataAfterChatSideEffects(chatResponse.sideEffects);
      setChatState("idle");
    } catch {
      if (requestSessionVersion !== chatSessionVersionRef.current) {
        return;
      }

      setChatMessages((messages) => [
        ...messages,
        {
          id: nextChatMessageId("assistant-error", chatMessageIdCounterRef),
          role: "assistant",
          content: "I could not reach the AI chat service. Please try again.",
        },
      ]);
      setChatState("error");
    }
  }

  async function refreshPurchaseDataAfterChatSideEffects(
    sideEffects: readonly ChatSideEffect[],
  ) {
    const purchaseDataChanged = sideEffects.some(
      (sideEffect) => sideEffect.type === "purchase_data_changed",
    );

    if (!purchaseDataChanged) {
      return;
    }

    router.refresh();
  }

  async function handleChatSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitChatMessage();
  }

  function handleChatInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }

    event.preventDefault();
    void submitChatMessage();
  }

  return (
    <ApplicationHelpContext.Provider value={contextValue}>
      <div className={styles.shell}>
        <div
          ref={pageContentRef}
          className={[
            styles.content,
            isAvailable && isOpen ? styles.contentOpen : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          {children}
        </div>

        {isAvailable ? (
          <aside
            aria-hidden={!isOpen}
            aria-label="Help panel"
            className={[styles.panel, isOpen ? styles.panelOpen : ""]
              .filter(Boolean)
              .join(" ")}
            id={panelId}
          >
            <header className={styles.header}>
              <p className={styles.title}>{demoMode ? "Support preview" : "Help"}</p>
              <button ref={closePanelRef} className={styles.closePanel} type="button" aria-label="Close help panel" onClick={toggleHelpPanel}>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
                  <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </button>
            </header>
            <div className={styles.body}>
              <div className={styles.chatSurface}>
                <div
                  aria-label="Chat transcript"
                  aria-live="polite"
                  className={styles.transcript}
                  ref={transcriptRef}
                  role="log"
                >
                  {chatMessages.map((message) => (
                    <div
                      className={[
                        styles.message,
                        message.role === "user"
                          ? styles.userMessage
                          : styles.assistantMessage,
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      key={message.id}
                    >
                      {message.content}
                    </div>
                  ))}
                  {chatState === "sending" ? (
                    <div
                      aria-label="Assistant response pending"
                      className={[
                        styles.message,
                        styles.assistantMessage,
                        styles.thinkingMessage,
                      ].join(" ")}
                      role="status"
                    >
                      <span className={styles.skeletonLine} />
                      <span className={styles.skeletonLine} />
                      <span className={styles.skeletonLine} />
                    </div>
                  ) : null}
                </div>

                <form className={styles.composer} onSubmit={handleChatSubmit}>
                  <label className={styles.inputLabel} htmlFor={`${panelId}-chat`}>
                    Message the AI assistant
                  </label>
                  <textarea
                    disabled={demoMode}
                    className={styles.chatInput}
                    id={`${panelId}-chat`}
                    onChange={(event) => setChatInput(event.target.value)}
                    onKeyDown={handleChatInputKeyDown}
                    placeholder={demoMode ? "Example conversation · frontend demo" : "Ask about your purchases..."}
                    ref={chatInputRef}
                    rows={1}
                    value={chatInput}
                  />
                  <div className={styles.inputActions}>
                    <button
                      aria-label="Send message"
                      className={styles.iconAction}
                      disabled={demoMode || !chatInput.trim() || chatState === "sending"}
                      type="submit"
                    >
                      <ArrowUpIcon size={16} />
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </aside>
        ) : null}
      </div>
    </ApplicationHelpContext.Provider>
  );
}

export function useApplicationHelpLayer() {
  const context = useContext(ApplicationHelpContext);

  if (!context) {
    throw new Error(
      "useApplicationHelpLayer must be used within ApplicationHelpLayer.",
    );
  }

  return context;
}

function isHelpAvailable(pathname: string | null) {
  return (
    pathname === "/user-home" ||
    Boolean(pathname?.startsWith("/purchase-details/"))
  );
}

function getPurchaseIdFromPathname(pathname: string | null) {
  const detailRoutePrefix = "/purchase-details/";

  if (!pathname?.startsWith(detailRoutePrefix)) {
    return null;
  }

  return pathname.slice(detailRoutePrefix.length).split("/")[0] || null;
}

function nextChatMessageId(
  prefix: string,
  counterRef: { current: number },
) {
  counterRef.current += 1;
  return `${prefix}-${counterRef.current}`;
}

function getCustomerIdFromCurrentUrl() {
  if (typeof window === "undefined") {
    return null;
  }

  return new URLSearchParams(window.location.search).get("customerId");
}

async function sendChatMessage(
  message: string,
  purchaseId: string | null,
  pageContext: PageContext,
  customerId: string | null,
  conversationState: ConversationState,
) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      customer_id: customerId,
      purchase_id: purchaseId,
      page_context: pageContext,
      conversation_state: conversationState,
    }),
  });

  if (!response.ok) {
    throw new Error("AI chat request failed.");
  }

  const body = (await response.json()) as {
    success?: boolean;
    data?: {
      message?: {
        content?: string;
      };
      conversation_state?: ConversationState;
      side_effects?: ChatSideEffect[];
    } | null;
  };

  if (!body.success || !body.data?.message?.content) {
    throw new Error("AI chat response was unsuccessful.");
  }

  return {
    message: body.data.message.content,
    conversationState: body.data.conversation_state ?? {},
    sideEffects: body.data.side_effects ?? [],
  };
}

function buildPageContext(pathname: string | null, purchaseId: string | null): PageContext {
  if (pathname?.startsWith("/purchase-details/") && purchaseId) {
    return {
      surface: "purchase_detail",
      purchase_id: purchaseId,
    };
  }

  return {
    surface: "purchase_history",
    purchase_id: null,
  };
}

