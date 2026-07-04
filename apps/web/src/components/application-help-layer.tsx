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
  canIssueFunds: boolean;
  canPrepareRefund: boolean;
}>;

type RefundWorkflowLoad = Readonly<{
  purchaseId: string | null;
  state:
    | "idle"
    | "ready"
    | "preparing"
    | "prepared"
    | "issuing"
    | "issued"
    | "error";
  workflow: RefundWorkflow | null;
}>;

const ApplicationHelpContext =
  createContext<ApplicationHelpContextValue | null>(null);
const refundWorkflowUpdatedEvent = "refunds-ai:refund-workflow-updated";

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
  const isPurchaseDetailsRoute = Boolean(
    pathname?.startsWith("/purchase-details/"),
  );
  const commandDisabled =
    workflowState === "preparing" || workflowState === "issuing";
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

  useEffect(() => {
    function handleRefundWorkflowUpdated(event: Event) {
      const detail = (event as CustomEvent<{
        purchaseId?: string;
        workflow?: RefundWorkflow;
      }>).detail;

      if (!detail?.purchaseId || detail.purchaseId !== purchaseId) {
        return;
      }

      setWorkflowLoad({
        purchaseId: detail.purchaseId,
        state: "ready",
        workflow: detail.workflow ?? null,
      });
    }

    window.addEventListener(
      refundWorkflowUpdatedEvent,
      handleRefundWorkflowUpdated,
    );

    return () => {
      window.removeEventListener(
        refundWorkflowUpdatedEvent,
        handleRefundWorkflowUpdated,
      );
    };
  }, [purchaseId]);

  async function handlePrepareRefund() {
    if (!purchaseId || !workflow?.canPrepareRefund || commandDisabled) {
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

  async function handleIssueRefund() {
    if (!purchaseId || !workflow?.canIssueFunds || commandDisabled) {
      return;
    }

    setWorkflowLoad({
      purchaseId,
      state: "issuing",
      workflow,
    });

    try {
      const nextWorkflow = await issueRefund(purchaseId);

      setWorkflowLoad({
        purchaseId,
        state: "issued",
        workflow: nextWorkflow,
      });
      updatePurchaseDetailsSummaryStatus(purchaseId, "Refunded");
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
            <div className={styles.body}>
              {isPurchaseDetailsRoute ? (
                <div className={styles.commandStack}>
                  <button
                    className={styles.actionButton}
                    disabled={!workflow?.canPrepareRefund || commandDisabled}
                    onClick={handlePrepareRefund}
                    type="button"
                  >
                    Prep Refund
                  </button>
                  <button
                    className={styles.actionButton}
                    disabled={!workflow?.canIssueFunds || commandDisabled}
                    onClick={handleIssueRefund}
                    type="button"
                  >
                    Issue Refund
                  </button>
                </div>
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

async function issueRefund(purchaseId: string) {
  const response = await fetch(`/api/purchases/${purchaseId}/refund/issue`, {
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
    data?: {
      can_issue_funds?: boolean;
      can_prepare_refund?: boolean;
    } | null;
  };

  if (!body.success || !body.data) {
    throw new Error("Refund workflow response was unsuccessful.");
  }

  return {
    canIssueFunds: body.data.can_issue_funds === true,
    canPrepareRefund: body.data.can_prepare_refund === true,
  };
}
