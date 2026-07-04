"use client";

import { useCallback, useMemo, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { AppCard } from "./app-card";
import {
  formatCentsAsDollars,
  type PurchaseDetails,
  type PurchaseType,
  type RefundWorkflow,
} from "@/lib/application-api";
import {
  buildFallbackPurchaseDetailsSummary,
  loadPurchaseDetailsSummarySnapshot,
  parsePurchaseDetailsSummary,
  type PurchaseDetailsSummary,
} from "@/lib/purchase-details-data";
import { DigitalCodeDetailsCard } from "./digital-code-details-card";
import { DigitalPurchaseTimelineCard } from "./digital-purchase-timeline-card";
import { DigitalRefundSummaryCard } from "./digital-refund-summary-card";
import { DigitalReturnDetailsCard } from "./digital-return-details-card";
import { HelpTriggerButton } from "./help-trigger-button";
import { PhysicalDeliveryTimelineCard } from "./physical-delivery-timeline-card";
import { PhysicalRefundSummaryCard } from "./physical-refund-summary-card";
import { PhysicalReturnWorkflowCard } from "./physical-return-workflow-card";
import { PhysicalTrackingCard } from "./physical-tracking-card";
import { SubscriptionBillingCycleCard } from "./subscription-billing-cycle-card";
import { SubscriptionRefundSummaryCard } from "./subscription-refund-summary-card";
import styles from "./purchase-details-placeholder.module.css";

type PurchaseDetailsPlaceholderProps = Readonly<{
  currentDate: string;
  purchaseDetails: PurchaseDetails | null;
  purchaseId: string;
  refundWorkflow: RefundWorkflow | null;
}>;

type DetailMetaCard = Readonly<{
  label: string;
  value: string;
}>;

type HeaderBadge = Readonly<{
  label: string;
  tone: "active" | "inactive";
}>;

type RefundCommandWorkflow = Readonly<{
  canIssueFunds: boolean;
  canPrepareRefund: boolean;
}>;

const refundWorkflowUpdatedEvent = "refunds-ai:refund-workflow-updated";

const purchaseTypeEyebrows = {
  digital: "Digital Purchase Details",
  physical: "Purchase Details",
  subscription: "Subscription Details",
} as const;

export function PurchaseDetailsPlaceholder({
  currentDate,
  purchaseDetails,
  purchaseId,
  refundWorkflow,
}: PurchaseDetailsPlaceholderProps) {
  const router = useRouter();
  const [isConfirmingCarrierAcceptance, setIsConfirmingCarrierAcceptance] =
    useState(false);
  const fallbackSummary = useMemo(
    () => buildFallbackPurchaseDetailsSummary(purchaseId),
    [purchaseId],
  );
  const getSnapshot = useCallback(
    () => loadPurchaseDetailsSummarySnapshot(purchaseId) ?? "",
    [purchaseId],
  );
  const getServerSnapshot = useCallback(() => "", []);
  const summarySnapshot = useSyncExternalStore(
    subscribeToStoredPurchaseSummary,
    getSnapshot,
    getServerSnapshot,
  );
  const summary = useMemo<PurchaseDetailsSummary>(
    () =>
      summarySnapshot
        ? parsePurchaseDetailsSummary(summarySnapshot, purchaseId) ??
          fallbackSummary
        : fallbackSummary,
    [fallbackSummary, purchaseId, summarySnapshot],
  );
  const purchaseType = purchaseDetails?.purchaseType ?? summary.purchaseType;
  const isDigitalPurchase = purchaseType === "digital";
  const isPhysicalPurchase = purchaseType === "physical";
  const eyebrow = purchaseTypeEyebrows[purchaseType];
  const headerBadge = buildSubscriptionHeaderBadge(purchaseType, purchaseDetails);
  const detailMetaCards = buildDetailMetaCards(purchaseType, purchaseDetails);
  const digitalTimeline = buildDigitalPurchaseTimeline(
    purchaseType,
    purchaseDetails,
    summary,
  );
  const digitalCodeDetails = buildDigitalCodeDetails(
    purchaseType,
    purchaseDetails,
  );
  const digitalReturnDetails = buildDigitalReturnDetails(
    purchaseType,
    purchaseDetails,
  );
  const digitalRefundSummary = buildDigitalRefundSummary(
    purchaseType,
    refundWorkflow,
  );
  const physicalTimeline = buildPhysicalDeliveryTimeline(
    purchaseType,
    purchaseDetails,
    summary,
  );
  const physicalTracking = buildPhysicalTracking(
    purchaseType,
    purchaseDetails,
  );
  const physicalReturnWorkflow = buildPhysicalReturnWorkflow(
    purchaseType,
    purchaseDetails,
  );
  const physicalRefundSummary = buildPhysicalRefundSummary(
    purchaseType,
    refundWorkflow,
  );
  const billingCycle = buildSubscriptionBillingCycle(
    purchaseType,
    purchaseDetails,
  );
  const subscriptionRefundSummary = buildSubscriptionRefundSummary(
    purchaseType,
    purchaseDetails,
    refundWorkflow,
  );

  async function handleConfirmCarrierAcceptance() {
    if (
      purchaseDetails?.purchaseType !== "physical" ||
      !physicalReturnWorkflow ||
      physicalReturnWorkflow.acceptedByCourierComplete ||
      isConfirmingCarrierAcceptance
    ) {
      return;
    }

    setIsConfirmingCarrierAcceptance(true);

    try {
      await confirmCarrierAcceptance(purchaseId);
      const nextWorkflow = await loadRefundWorkflow(purchaseId);

      dispatchRefundWorkflowUpdate(purchaseId, nextWorkflow);
      router.refresh();
    } finally {
      setIsConfirmingCarrierAcceptance(false);
    }
  }

  return (
    <main className={styles.page}>
      <AppCard className={styles.content}>
        <div className={styles.headerTopline}>
          <p className={styles.eyebrow}>{eyebrow}</p>
          {headerBadge ? (
            <p
              className={`${styles.headerBadge} ${styles[headerBadge.tone]}`}
            >
              {headerBadge.label}
            </p>
          ) : null}
        </div>
        <h1 className={styles.heading}>{summary.productName}</h1>
        <p className={styles.summary}>
          This view is ready for the purchase detail API integration.
        </p>
        <div className={styles.meta} aria-label="Purchase summary" role="group">
          <div className={styles.metaItem}>
            <p>Order Number</p>
            <p>{summary.headerMeta.orderNumber}</p>
          </div>
          <div className={styles.metaItem}>
            <p>Amount</p>
            <p>{summary.headerMeta.amount}</p>
          </div>
          <div className={styles.metaItem}>
            <p>Status</p>
            <p>{summary.headerMeta.status}</p>
          </div>
        </div>
      </AppCard>

      {digitalTimeline || digitalCodeDetails ? (
        <section
          className={styles.detailsSection}
          aria-labelledby="digital-code-details-title"
        >
          <h2 className={styles.sectionTitle} id="digital-code-details-title">
            Code Details
          </h2>
          {digitalTimeline ? (
            <DigitalPurchaseTimelineCard
              codeIssuedAt={digitalTimeline.codeIssuedAt}
              isMuted={Boolean(digitalReturnDetails)}
              purchasedAt={digitalTimeline.purchasedAt}
            />
          ) : null}

          {digitalCodeDetails ? (
            <DigitalCodeDetailsCard
              codeRedeemed={digitalCodeDetails.codeRedeemed}
              isMuted={Boolean(digitalReturnDetails)}
              issuedCode={digitalCodeDetails.issuedCode}
            />
          ) : null}
        </section>
      ) : null}

      {digitalReturnDetails ? (
        <section
          className={styles.detailsSection}
          aria-labelledby="digital-return-details-title"
        >
          <h2 className={styles.sectionTitle} id="digital-return-details-title">
            Return Details
          </h2>
          <DigitalReturnDetailsCard
            invalidatedAt={digitalReturnDetails.invalidatedAt}
          />
          {digitalRefundSummary ? (
            <DigitalRefundSummaryCard
              estimatedReleaseDateRange={
                digitalRefundSummary.estimatedReleaseDateRange
              }
              estimatedReleasePolicy={digitalRefundSummary.estimatedReleasePolicy}
              refundAmount={digitalRefundSummary.refundAmount}
              refundIssuedAt={digitalRefundSummary.refundIssuedAt}
            />
          ) : null}
        </section>
      ) : null}

      {physicalTimeline || physicalTracking ? (
        <section
          className={styles.detailsSection}
          aria-labelledby="physical-delivery-details-title"
        >
          <h2
            className={styles.sectionTitle}
            id="physical-delivery-details-title"
          >
            Delivery Details
          </h2>
          {physicalTimeline ? (
            <PhysicalDeliveryTimelineCard
              deliveredAt={physicalTimeline.deliveredAt}
              isMuted={Boolean(physicalReturnWorkflow)}
              purchasedAt={physicalTimeline.purchasedAt}
              scheduledDeliveryAt={physicalTimeline.scheduledDeliveryAt}
            />
          ) : null}

          {physicalTracking ? (
            <PhysicalTrackingCard
              courier={physicalTracking.courier}
              isMuted={Boolean(physicalReturnWorkflow)}
              trackingNumber={physicalTracking.trackingNumber}
            />
          ) : null}
        </section>
      ) : null}

      {isPhysicalPurchase && (physicalReturnWorkflow || detailMetaCards.length > 0) ? (
        <section
          className={styles.detailsSection}
          aria-labelledby="physical-return-details-title"
        >
          <h2 className={styles.sectionTitle} id="physical-return-details-title">
            Return Details
          </h2>
          {physicalReturnWorkflow ? (
            <PhysicalReturnWorkflowCard
              acceptedByCourierAt={physicalReturnWorkflow.acceptedByCourierAt}
              acceptedByCourierComplete={
                physicalReturnWorkflow.acceptedByCourierComplete
              }
              isConfirmingCarrierAcceptance={isConfirmingCarrierAcceptance}
              labelCreatedAt={physicalReturnWorkflow.labelCreatedAt}
              onConfirmCarrierAcceptance={handleConfirmCarrierAcceptance}
              returnRequestedAt={physicalReturnWorkflow.returnRequestedAt}
            />
          ) : null}
          {physicalRefundSummary ? (
            <PhysicalRefundSummaryCard
              estimatedReleaseDateRange={
                physicalRefundSummary.estimatedReleaseDateRange
              }
              estimatedReleasePolicy={physicalRefundSummary.estimatedReleasePolicy}
              refundAmount={physicalRefundSummary.refundAmount}
              returnIssuedAt={physicalRefundSummary.returnIssuedAt}
            />
          ) : null}
          {detailMetaCards.length > 0 ? (
            <div className={styles.detailGrid}>
              {detailMetaCards.map((card) => (
                <div className={styles.detailCard} key={card.label}>
                  <p>{card.label}</p>
                  <p>{card.value}</p>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {billingCycle ? (
        <section
          className={styles.detailsSection}
          aria-labelledby="subscription-billing-cycle-details-title"
        >
          <h2
            className={styles.sectionTitle}
            id="subscription-billing-cycle-details-title"
          >
            Billing Cycle Details
          </h2>
          <SubscriptionBillingCycleCard
            currentDate={currentDate}
            periodEnd={billingCycle.periodEnd}
            periodStart={billingCycle.periodStart}
            serviceEndedAt={billingCycle.serviceEndedAt}
          />
        </section>
      ) : null}

      {subscriptionRefundSummary ? (
        <section
          className={styles.detailsSection}
          aria-labelledby="subscription-return-details-title"
        >
          <h2 className={styles.sectionTitle} id="subscription-return-details-title">
            Return Details
          </h2>
          <SubscriptionRefundSummaryCard
            autoRenewState={subscriptionRefundSummary.autoRenewState}
            cancelledAt={subscriptionRefundSummary.cancelledAt}
            cancellationStatus={subscriptionRefundSummary.cancellationStatus}
            daysUsed={subscriptionRefundSummary.daysUsed}
            estimatedReleaseDateRange={
              subscriptionRefundSummary.estimatedReleaseDateRange
            }
            estimatedReleasePolicy={subscriptionRefundSummary.estimatedReleasePolicy}
            refundAmount={subscriptionRefundSummary.refundAmount}
          />
        </section>
      ) : null}

      {!isDigitalPurchase && !isPhysicalPurchase && detailMetaCards.length > 0 ? (
        <section
          className={styles.detailsSection}
          aria-labelledby="purchase-detail-meta-title"
        >
          <h2 className={styles.sectionTitle} id="purchase-detail-meta-title">
            Metadata
          </h2>
          <div className={styles.detailGrid}>
            {detailMetaCards.map((card) => (
              <div className={styles.detailCard} key={card.label}>
                <p>{card.label}</p>
                <p>{card.value}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}
      <HelpTriggerButton />
    </main>
  );
}

function subscribeToStoredPurchaseSummary() {
  return () => {};
}

function buildSubscriptionHeaderBadge(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
): HeaderBadge | null {
  void purchaseType;
  void purchaseDetails;

  return null;
}

function buildDetailMetaCards(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
): readonly DetailMetaCard[] {
  if (!purchaseDetails) {
    return placeholderDetailMetaCards[purchaseType];
  }

  if (purchaseDetails.purchaseType === "digital") {
    return [];
  }

  if (purchaseDetails.purchaseType === "subscription") {
    return [];
  }

  return [];
}

function buildSubscriptionRefundSummary(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
  refundWorkflow: RefundWorkflow | null,
) {
  if (
    purchaseType !== "subscription" ||
    purchaseDetails?.purchaseType !== "subscription" ||
    refundWorkflow?.purchaseType !== "subscription" ||
    !["prepared", "issued"].includes(refundWorkflow.refundStage) ||
    !purchaseDetails.details.cancelledAt
  ) {
    return null;
  }

  const refundedAt = readStringPolicyFact(refundWorkflow.policyFacts.refunded_at);
  const releaseWindow =
    refundWorkflow.refundStage === "issued" && refundedAt
      ? buildBusinessDayReleaseWindow(refundedAt)
      : null;

  return {
    autoRenewState: purchaseDetails.details.autoRenew ? "On" : "Off",
    cancelledAt: formatDetailDate(purchaseDetails.details.cancelledAt),
    cancellationStatus: "Subscription Cancelled",
    daysUsed: formatDaysUsedInBillingCycle(
      purchaseDetails.details.periodStart,
      purchaseDetails.details.serviceEndedAt ?? purchaseDetails.details.cancelledAt,
    ),
    estimatedReleaseDateRange: releaseWindow?.dateRange ?? null,
    estimatedReleasePolicy: releaseWindow ? "3-10 business days" : null,
    refundAmount:
      refundWorkflow.refundStage === "issued"
        ? formatCentsAsDollars(refundWorkflow.refundableAmountCents)
        : null,
  };
}

function buildSubscriptionBillingCycle(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
) {
  if (purchaseDetails?.purchaseType === "subscription") {
    return {
      periodEnd: purchaseDetails.details.periodEnd,
      periodStart: purchaseDetails.details.periodStart,
      serviceEndedAt: purchaseDetails.details.serviceEndedAt,
    };
  }

  if (purchaseType === "subscription") {
    return {
      periodEnd: "2026-07-20T00:00:00Z",
      periodStart: "2026-06-20T00:00:00Z",
      serviceEndedAt: null,
    };
  }

  return null;
}

function buildDigitalPurchaseTimeline(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
  summary: PurchaseDetailsSummary,
) {
  if (purchaseDetails?.purchaseType === "digital") {
    return {
      codeIssuedAt: purchaseDetails.details.codeDeliveredAt,
      purchasedAt: summary.purchasedAt,
    };
  }

  if (purchaseType === "digital") {
    return {
      codeIssuedAt: "2026-06-20T00:00:00Z",
      purchasedAt: summary.purchasedAt,
    };
  }

  return null;
}

function buildDigitalCodeDetails(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
) {
  if (purchaseDetails?.purchaseType === "digital") {
    return {
      codeRedeemed: purchaseDetails.details.codeRedeemed,
      issuedCode: purchaseDetails.details.issuedCode,
    };
  }

  if (purchaseType === "digital") {
    return {
      codeRedeemed: false,
      issuedCode: "DIG-RAI-10001",
    };
  }

  return null;
}

function buildDigitalReturnDetails(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
) {
  if (purchaseDetails?.purchaseType === "digital") {
    if (!purchaseDetails.details.codeInvalidatedAt) {
      return null;
    }

    return {
      invalidatedAt: formatDetailDate(purchaseDetails.details.codeInvalidatedAt),
    };
  }

  if (purchaseType === "digital") {
    return null;
  }

  return null;
}

function buildDigitalRefundSummary(
  purchaseType: PurchaseType,
  refundWorkflow: RefundWorkflow | null,
) {
  if (
    purchaseType !== "digital" ||
    refundWorkflow?.purchaseType !== "digital" ||
    refundWorkflow.refundStage !== "issued"
  ) {
    return null;
  }

  const refundedAt = readStringPolicyFact(refundWorkflow.policyFacts.refunded_at);

  if (!refundedAt) {
    return null;
  }

  const releaseWindow = buildBusinessDayReleaseWindow(refundedAt);

  return {
    estimatedReleaseDateRange: releaseWindow.dateRange,
    estimatedReleasePolicy: "3-10 business days",
    refundAmount: formatCentsAsDollars(refundWorkflow.refundableAmountCents),
    refundIssuedAt: formatDetailDate(refundedAt),
  };
}

function buildPhysicalDeliveryTimeline(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
  summary: PurchaseDetailsSummary,
) {
  if (purchaseDetails?.purchaseType === "physical") {
    return {
      deliveredAt: purchaseDetails.details.deliveredAt,
      purchasedAt: summary.purchasedAt,
      scheduledDeliveryAt: purchaseDetails.details.scheduledDeliveryAt,
    };
  }

  if (purchaseType === "physical") {
    return {
      deliveredAt: null,
      purchasedAt: summary.purchasedAt,
      scheduledDeliveryAt: "2026-06-22T00:00:00Z",
    };
  }

  return null;
}

function buildPhysicalTracking(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
) {
  if (purchaseDetails?.purchaseType === "physical") {
    return {
      courier: purchaseDetails.details.carrier,
      trackingNumber: purchaseDetails.details.trackingNumber,
    };
  }

  if (purchaseType === "physical") {
    return {
      courier: "UPS",
      trackingNumber: "TRK-RAI-10001",
    };
  }

  return null;
}

function buildPhysicalReturnWorkflow(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
) {
  if (purchaseDetails?.purchaseType === "physical") {
    const details = purchaseDetails.details;

    if (!isPhysicalReturnActive(details.returnStatus)) {
      return null;
    }

    return {
      acceptedByCourierAt: details.acceptedByCarrierAt
        ? formatDetailDate(details.acceptedByCarrierAt)
        : "Awaiting courier acceptance",
      acceptedByCourierComplete: details.acceptedByCarrierAt !== null,
      labelCreatedAt: formatDetailDate(details.returnLabelCreatedAt),
      returnRequestedAt: formatDetailDate(details.returnRequestedAt),
    };
  }

  if (purchaseType === "physical") {
    return null;
  }

  return null;
}

function buildPhysicalRefundSummary(
  purchaseType: PurchaseType,
  refundWorkflow: RefundWorkflow | null,
) {
  if (
    purchaseType !== "physical" ||
    refundWorkflow?.purchaseType !== "physical" ||
    refundWorkflow.refundStage !== "issued"
  ) {
    return null;
  }

  const refundedAt = readStringPolicyFact(refundWorkflow.policyFacts.refunded_at);

  if (!refundedAt) {
    return null;
  }

  const releaseWindow = buildBusinessDayReleaseWindow(refundedAt);

  return {
    estimatedReleaseDateRange: releaseWindow.dateRange,
    estimatedReleasePolicy: "3-10 business days",
    refundAmount: formatCentsAsDollars(refundWorkflow.refundableAmountCents),
    returnIssuedAt: formatDetailDate(refundedAt),
  };
}

function isPhysicalReturnActive(returnStatus: string) {
  return returnStatus !== "not_requested";
}

const placeholderDetailMetaCards = {
  digital: [
  ],
  physical: [],
  subscription: [],
} as const satisfies Record<PurchaseType, readonly DetailMetaCard[]>;

function formatDetailDate(value: string | null) {
  if (!value) {
    return "Not set";
  }

  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Date unavailable";
  }

  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(parsedDate);
}

function buildBusinessDayReleaseWindow(refundedAt: string) {
  const startDate = addBusinessDays(refundedAt, 3);
  const endDate = addBusinessDays(refundedAt, 10);

  return {
    dateRange: `${formatShortDate(startDate)} - ${formatShortDate(endDate)}`,
  };
}

function formatDaysUsedInBillingCycle(periodStart: string, periodEndedAt: string | null) {
  if (!periodEndedAt) {
    return "Not set";
  }

  const startDate = new Date(periodStart);
  const endDate = new Date(periodEndedAt);

  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
    return "Unavailable";
  }

  const millisecondsPerDay = 24 * 60 * 60 * 1000;
  const daysUsed = Math.max(
    0,
    Math.ceil((endDate.getTime() - startDate.getTime()) / millisecondsPerDay),
  );

  return `${daysUsed} days`;
}

function addBusinessDays(value: string, businessDays: number) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return null;
  }

  const nextDate = new Date(date);
  let remainingDays = businessDays;

  while (remainingDays > 0) {
    nextDate.setUTCDate(nextDate.getUTCDate() + 1);

    const dayOfWeek = nextDate.getUTCDay();

    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      remainingDays -= 1;
    }
  }

  return nextDate;
}

function formatShortDate(value: Date | null) {
  if (!value) {
    return "Date unavailable";
  }

  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  }).format(value);
}

function readStringPolicyFact(value: unknown) {
  return typeof value === "string" ? value : null;
}

async function confirmCarrierAcceptance(purchaseId: string) {
  const response = await fetch(
    `/api/purchases/${purchaseId}/physical/confirm-carrier-acceptance`,
    {
      method: "POST",
    },
  );

  if (!response.ok) {
    throw new Error("Carrier acceptance confirmation failed.");
  }

  const body = (await response.json()) as {
    success?: boolean;
  };

  if (!body.success) {
    throw new Error("Carrier acceptance response was unsuccessful.");
  }
}

async function loadRefundWorkflow(purchaseId: string) {
  const response = await fetch(
    `/api/purchases/${purchaseId}/refund/eligibility`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Refund workflow refresh failed.");
  }

  const body = (await response.json()) as {
    success?: boolean;
    data?: {
      can_issue_funds?: boolean;
      can_prepare_refund?: boolean;
    } | null;
  };

  if (!body.success || !body.data) {
    throw new Error("Refund workflow refresh was unsuccessful.");
  }

  return {
    canIssueFunds: body.data.can_issue_funds === true,
    canPrepareRefund: body.data.can_prepare_refund === true,
  };
}

function dispatchRefundWorkflowUpdate(
  purchaseId: string,
  workflow: RefundCommandWorkflow,
) {
  window.dispatchEvent(
    new CustomEvent(refundWorkflowUpdatedEvent, {
      detail: {
        purchaseId,
        workflow,
      },
    }),
  );
}
