"use client";

import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useId,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { updatePurchaseDetailsSummaryStatus } from "@/lib/purchase-details-data";
import styles from "./application-help-layer.module.css";

type ApplicationHelpLayerProps = Readonly<{
  children: ReactNode;
}>;

type ApplicationHelpContextValue = Readonly<{
  isAvailable: boolean;
  isOpen: boolean;
  panelId: string;
  toggle: () => void;
}>;

type RefundWorkflow = Readonly<{
  canPrepareRefund: boolean;
}>;

type RefundWorkflowLoad = Readonly<{
  purchaseId: string | null;
  state: "idle" | "ready" | "preparing" | "prepared" | "error";
  workflow: RefundWorkflow | null;
}>;

const ApplicationHelpContext =
  createContext<ApplicationHelpContextValue | null>(null);

export function ApplicationHelpLayer({ children }: ApplicationHelpLayerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [workflowLoad, setWorkflowLoad] = useState<RefundWorkflowLoad>({
    purchaseId: null,
    state: "idle",
    workflow: null,
  });
  const panelId = useId();
  const pathname = usePathname();
  const router = useRouter();
  const isAvailable = isHelpAvailable(pathname);
  const purchaseId = getPurchaseIdFromPathname(pathname);
  const workflow =
    workflowLoad.purchaseId === purchaseId ? workflowLoad.workflow : null;
  const workflowState =
    workflowLoad.purchaseId === purchaseId ? workflowLoad.state : "idle";
  const panelContent = getHelpPanelContent(pathname, workflow, workflowState);
  const contextValue = useMemo<ApplicationHelpContextValue>(
    () => ({
      isAvailable,
      isOpen,
      panelId,
      toggle: () => setIsOpen((current) => !current),
    }),
    [isAvailable, isOpen, panelId],
  );

  useEffect(() => {
    if (!purchaseId) {
      return;
    }

    let ignoreResult = false;

    void loadRefundWorkflow(purchaseId)
      .then((nextWorkflow) => {
        if (ignoreResult) {
          return;
        }

        setWorkflowLoad({
          purchaseId,
          state: "ready",
          workflow: nextWorkflow,
        });
      })
      .catch(() => {
        if (ignoreResult) {
          return;
        }

        setWorkflowLoad({
          purchaseId,
          state: "error",
          workflow: null,
        });
      });

    return () => {
      ignoreResult = true;
    };
  }, [purchaseId]);

  async function handlePrepareRefund() {
    if (!purchaseId || workflowState === "preparing") {
      return;
    }

    setWorkflowLoad({
      purchaseId,
      state: "preparing",
      workflow,
    });

    try {
      const nextWorkflow = await prepareRefund(purchaseId);

      setWorkflowLoad({
        purchaseId,
        state: "prepared",
        workflow: nextWorkflow,
      });
      updatePurchaseDetailsSummaryStatus(purchaseId, "Refund Pending");
      router.refresh();
    } catch {
      setWorkflowLoad({
        purchaseId,
        state: "error",
        workflow,
      });
    }
  }

  return (
    <ApplicationHelpContext.Provider value={contextValue}>
      <div className={styles.shell}>
        <div
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
              <p className={styles.title}>Help</p>
            </header>
            <div
              className={[
                styles.body,
                panelContent.isCentered ? styles.centeredBody : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {panelContent.showSelectionIcon ? (
                <SelectionPromptIcon />
              ) : null}
              <p className={styles.prompt}>{panelContent.prompt}</p>
              {panelContent.actionLabel ? (
                <button
                  className={styles.actionButton}
                  disabled={workflowState === "preparing"}
                  onClick={handlePrepareRefund}
                  type="button"
                >
                  {panelContent.actionLabel}
                </button>
              ) : null}
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

function getHelpPanelContent(
  pathname: string | null,
  workflow: RefundWorkflow | null,
  workflowState: string,
) {
  if (pathname?.startsWith("/purchase-details/")) {
    if (workflowState === "preparing") {
      return {
        actionLabel: "Starting refund process...",
        prompt: "Preparing this purchase for refund.",
      };
    }

    if (workflowState === "prepared") {
      return {
        actionLabel: null,
        prompt: "Refund preparation has started. The purchase details are updating.",
      };
    }

    if (workflow?.canPrepareRefund) {
      return {
        actionLabel: "Start refund process",
        prompt: "Need help with this purchase?",
      };
    }

    return {
      actionLabel: null,
      prompt: "Refund preparation is not currently available for this purchase.",
    };
  }

  return {
    actionLabel: null,
    isCentered: true,
    prompt:
      "Select a purchase to view available support options like refunds, returns, delivery status, or subscription changes.",
    showSelectionIcon: true,
  };
}

function getPurchaseIdFromPathname(pathname: string | null) {
  const detailRoutePrefix = "/purchase-details/";

  if (!pathname?.startsWith(detailRoutePrefix)) {
    return null;
  }

  return pathname.slice(detailRoutePrefix.length).split("/")[0] || null;
}

async function loadRefundWorkflow(purchaseId: string) {
  const response = await fetch(
    `/api/purchases/${purchaseId}/refund/eligibility`,
    {
      cache: "no-store",
    },
  );

  return parseRefundWorkflowResponse(response);
}

async function prepareRefund(purchaseId: string) {
  const response = await fetch(`/api/purchases/${purchaseId}/refund/request`, {
    method: "POST",
  });

  return parseRefundWorkflowResponse(response);
}

async function parseRefundWorkflowResponse(response: Response) {
  if (!response.ok) {
    throw new Error("Refund workflow request failed.");
  }

  const body = (await response.json()) as {
    success?: boolean;
    data?: { can_prepare_refund?: boolean } | null;
  };

  if (!body.success || !body.data) {
    throw new Error("Refund workflow response was unsuccessful.");
  }

  return {
    canPrepareRefund: body.data.can_prepare_refund === true,
  };
}

function SelectionPromptIcon() {
  return (
    <svg
      aria-hidden="true"
      className={styles.selectionIcon}
      fill="none"
      viewBox="0 0 64 64"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M18 10 50 38 35.5 40.5 43 54 34.5 58.5 27 45 18 56V10Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="3.8"
      />
      <path
        d="M11 16 5 10M15 6V1M6 25H1"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="3.4"
      />
    </svg>
  );
}
