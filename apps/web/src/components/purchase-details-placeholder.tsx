"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";
import { AppCard } from "./app-card";
import {
  type PurchaseDetails,
  type PurchaseType,
} from "@/lib/application-api";
import {
  buildFallbackPurchaseDetailsSummary,
  loadPurchaseDetailsSummarySnapshot,
  parsePurchaseDetailsSummary,
  type PurchaseDetailsSummary,
} from "@/lib/purchase-details-data";
import { DigitalCodeDetailsCard } from "./digital-code-details-card";
import { DigitalPurchaseTimelineCard } from "./digital-purchase-timeline-card";
import { HelpTriggerButton } from "./help-trigger-button";
import { PhysicalDeliveryTimelineCard } from "./physical-delivery-timeline-card";
import { PhysicalTrackingCard } from "./physical-tracking-card";
import { SubscriptionBillingCycleCard } from "./subscription-billing-cycle-card";
import styles from "./purchase-details-placeholder.module.css";

type PurchaseDetailsPlaceholderProps = Readonly<{
  currentDate: string;
  purchaseDetails: PurchaseDetails | null;
  purchaseId: string;
}>;

type DetailMetaCard = Readonly<{
  label: string;
  value: string;
}>;

type HeaderBadge = Readonly<{
  label: string;
  tone: "active" | "inactive";
}>;

const purchaseTypeEyebrows = {
  digital: "Digital Purchase Details",
  physical: "Purchase Details",
  subscription: "Subscription Details",
} as const;

export function PurchaseDetailsPlaceholder({
  currentDate,
  purchaseDetails,
  purchaseId,
}: PurchaseDetailsPlaceholderProps) {
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
  const physicalTimeline = buildPhysicalDeliveryTimeline(
    purchaseType,
    purchaseDetails,
    summary,
  );
  const physicalTracking = buildPhysicalTracking(
    purchaseType,
    purchaseDetails,
  );
  const billingCycle = buildSubscriptionBillingCycle(
    purchaseType,
    purchaseDetails,
  );

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

      {digitalTimeline ? (
        <DigitalPurchaseTimelineCard
          codeIssuedAt={digitalTimeline.codeIssuedAt}
          purchasedAt={digitalTimeline.purchasedAt}
        />
      ) : null}

      {digitalCodeDetails ? (
        <DigitalCodeDetailsCard
          codeRedeemed={digitalCodeDetails.codeRedeemed}
          issuedCode={digitalCodeDetails.issuedCode}
        />
      ) : null}

      {physicalTimeline ? (
        <PhysicalDeliveryTimelineCard
          deliveredAt={physicalTimeline.deliveredAt}
          purchasedAt={physicalTimeline.purchasedAt}
          scheduledDeliveryAt={physicalTimeline.scheduledDeliveryAt}
        />
      ) : null}

      {physicalTracking ? (
        <PhysicalTrackingCard
          courier={physicalTracking.courier}
          trackingNumber={physicalTracking.trackingNumber}
        />
      ) : null}

      {billingCycle ? (
        <SubscriptionBillingCycleCard
          currentDate={currentDate}
          periodEnd={billingCycle.periodEnd}
          periodStart={billingCycle.periodStart}
        />
      ) : null}

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
  if (purchaseType !== "subscription") {
    return null;
  }

  if (purchaseDetails?.purchaseType !== "subscription") {
    return { label: "Auto Renew Enabled", tone: "active" };
  }

  const details = purchaseDetails.details;
  const subscriptionCanceled =
    !details.autoRenew || details.cancelledAt !== null || details.serviceEndedAt !== null;

  return subscriptionCanceled
    ? { label: "Subscription Canceled", tone: "inactive" }
    : { label: "Auto Renew Enabled", tone: "active" };
}

function buildDetailMetaCards(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
): readonly DetailMetaCard[] {
  if (!purchaseDetails) {
    return placeholderDetailMetaCards[purchaseType];
  }

  if (purchaseDetails.purchaseType === "digital") {
    const details = purchaseDetails.details;

    return [
      {
        label: "Code Invalidated At",
        value: formatDetailDate(details.codeInvalidatedAt),
      },
      {
        label: "Refund Window Expires",
        value: formatDetailDate(details.refundWindowExpiresAt),
      },
      {
        label: "Refund Lock Reason",
        value: formatNullableText(details.refundLockReason),
      },
    ];
  }

  if (purchaseDetails.purchaseType === "subscription") {
    const details = purchaseDetails.details;

    return [
      { label: "Cancelled At", value: formatDetailDate(details.cancelledAt) },
      { label: "Service Ended At", value: formatDetailDate(details.serviceEndedAt) },
      {
        label: "Refund Proration Mode",
        value: formatDetailStatus(details.refundProrationMode),
      },
      {
        label: "Full Refund Window Expires",
        value: formatDetailDate(details.fullRefundWindowExpiresAt),
      },
      {
        label: "Refund Window Expires",
        value: formatDetailDate(details.refundWindowExpiresAt),
      },
    ];
  }

  const details = purchaseDetails.details;

  return [
    { label: "Return Status", value: formatDetailStatus(details.returnStatus) },
    {
      label: "Return Barcode Generated",
      value: formatBoolean(details.returnBarcodeGenerated),
    },
    {
      label: "Return Label Created",
      value: formatDetailDate(details.returnLabelCreatedAt),
    },
    {
      label: "Accepted By Carrier",
      value: formatDetailDate(details.acceptedByCarrierAt),
    },
    {
      label: "Return Requested",
      value: formatDetailDate(details.returnRequestedAt),
    },
    {
      label: "Return Authorized",
      value: formatDetailDate(details.returnAuthorizedAt),
    },
    { label: "Return Received", value: formatDetailDate(details.returnReceivedAt) },
    { label: "Return Rejected", value: formatDetailDate(details.returnRejectedAt) },
    {
      label: "Return Rejection Reason",
      value: formatNullableText(details.returnRejectionReason),
    },
    {
      label: "Refund Window Expires",
      value: formatDetailDate(details.refundWindowExpiresAt),
    },
  ];
}

function buildSubscriptionBillingCycle(
  purchaseType: PurchaseType,
  purchaseDetails: PurchaseDetails | null,
) {
  if (purchaseDetails?.purchaseType === "subscription") {
    return {
      periodEnd: purchaseDetails.details.periodEnd,
      periodStart: purchaseDetails.details.periodStart,
    };
  }

  if (purchaseType === "subscription") {
    return {
      periodEnd: "2026-07-20T00:00:00Z",
      periodStart: "2026-06-20T00:00:00Z",
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

const placeholderDetailMetaCards = {
  digital: [
    { label: "Code Invalidated At", value: "Not set" },
    { label: "Refund Window Expires", value: "Jul 05, 2026" },
    { label: "Refund Lock Reason", value: "Not set" },
  ],
  physical: [
    { label: "Return Status", value: "Not Requested" },
    { label: "Return Barcode Generated", value: "No" },
    { label: "Return Label Created", value: "Not set" },
    { label: "Accepted By Carrier", value: "Not set" },
    { label: "Return Requested", value: "Not set" },
    { label: "Return Authorized", value: "Not set" },
    { label: "Return Received", value: "Not set" },
    { label: "Return Rejected", value: "Not set" },
    { label: "Return Rejection Reason", value: "Not set" },
    { label: "Refund Window Expires", value: "Jul 20, 2026" },
  ],
  subscription: [
    { label: "Cancelled At", value: "Not set" },
    { label: "Service Ended At", value: "Not set" },
    { label: "Refund Proration Mode", value: "None" },
    { label: "Full Refund Window Expires", value: "Jun 22, 2026" },
    { label: "Refund Window Expires", value: "Jul 20, 2026" },
  ],
} as const satisfies Record<PurchaseType, readonly DetailMetaCard[]>;

function formatBoolean(value: boolean) {
  return value ? "Yes" : "No";
}

function formatNullableText(value: string | null) {
  return value ?? "Not set";
}

function formatDetailStatus(value: string) {
  return value
    .split("_")
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

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
