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
import styles from "./purchase-details-placeholder.module.css";

type PurchaseDetailsPlaceholderProps = Readonly<{
  purchaseDetails: PurchaseDetails | null;
  purchaseId: string;
}>;

type DetailMetaCard = Readonly<{
  label: string;
  value: string;
}>;

const purchaseTypeEyebrows = {
  digital: "Digital Purchase Details",
  physical: "Purchase Details",
  subscription: "Subscription Details",
} as const;

export function PurchaseDetailsPlaceholder({
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
  const detailMetaCards = buildDetailMetaCards(purchaseType, purchaseDetails);

  return (
    <main className={styles.page}>
      <AppCard className={styles.content}>
        <p className={styles.eyebrow}>{eyebrow}</p>
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
    </main>
  );
}

function subscribeToStoredPurchaseSummary() {
  return () => {};
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
      { label: "Issued Code", value: details.issuedCode },
      { label: "Code Redeemed", value: formatBoolean(details.codeRedeemed) },
      { label: "Code Redeemed At", value: formatDetailDate(details.codeRedeemedAt) },
      {
        label: "Code Invalidated At",
        value: formatDetailDate(details.codeInvalidatedAt),
      },
      {
        label: "Code Delivered At",
        value: formatDetailDate(details.codeDeliveredAt),
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
      { label: "Period Start", value: formatDetailDate(details.periodStart) },
      { label: "Period End", value: formatDetailDate(details.periodEnd) },
      { label: "Cancelled At", value: formatDetailDate(details.cancelledAt) },
      { label: "Service Ended At", value: formatDetailDate(details.serviceEndedAt) },
      { label: "Auto Renew", value: formatBoolean(details.autoRenew) },
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
    {
      label: "Scheduled Delivery",
      value: formatDetailDate(details.scheduledDeliveryAt),
    },
    { label: "Delivered At", value: formatDetailDate(details.deliveredAt) },
    { label: "Return Status", value: formatDetailStatus(details.returnStatus) },
    { label: "Carrier", value: formatNullableText(details.carrier) },
    {
      label: "Tracking Number",
      value: formatNullableText(details.trackingNumber),
    },
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

const placeholderDetailMetaCards = {
  digital: [
    { label: "Issued Code", value: "DIG-RAI-10001" },
    { label: "Code Redeemed", value: "No" },
    { label: "Code Redeemed At", value: "Not set" },
    { label: "Code Invalidated At", value: "Not set" },
    { label: "Code Delivered At", value: "Jun 20, 2026" },
    { label: "Refund Window Expires", value: "Jul 05, 2026" },
    { label: "Refund Lock Reason", value: "Not set" },
  ],
  physical: [
    { label: "Scheduled Delivery", value: "Jun 22, 2026" },
    { label: "Delivered At", value: "Not set" },
    { label: "Return Status", value: "Not Requested" },
    { label: "Carrier", value: "UPS" },
    { label: "Tracking Number", value: "TRK-RAI-10001" },
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
    { label: "Period Start", value: "Jun 20, 2026" },
    { label: "Period End", value: "Jul 20, 2026" },
    { label: "Cancelled At", value: "Not set" },
    { label: "Service Ended At", value: "Not set" },
    { label: "Auto Renew", value: "Yes" },
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
