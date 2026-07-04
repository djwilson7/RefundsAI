import {
  formatCentsAsDollars,
  formatPurchaseStatus,
  type CustomerPurchase,
} from "./application-api";

export type PurchaseType = "digital" | "physical" | "subscription";

export type PurchaseDetailsHeaderMeta = Readonly<{
  amount: string;
  orderNumber: string;
  status: string;
}>;

export type PurchaseDetailsSummary = Readonly<{
  headerMeta: PurchaseDetailsHeaderMeta;
  productName: string;
  purchasedAt: string;
  purchaseId: string;
  purchaseType: PurchaseType;
}>;

const purchaseDetailsStoragePrefix = "refunds-ai:purchase-details-summary:";

export function buildPurchaseDetailsSummary(
  purchase: CustomerPurchase,
): PurchaseDetailsSummary {
  return {
    headerMeta: {
      amount: formatCentsAsDollars(purchase.amountCents),
      orderNumber: purchase.orderNumber,
      status: formatPurchaseStatus(purchase.status),
    },
    productName: purchase.productName,
    purchasedAt: formatPurchaseDetailsDate(purchase.purchasedAt),
    purchaseId: purchase.id,
    purchaseType: purchase.purchaseType,
  };
}

export function buildPurchaseDetailsHref(purchaseId: string) {
  return `/purchase-details/${purchaseId}`;
}

export function buildFallbackPurchaseDetailsSummary(
  purchaseId: string,
): PurchaseDetailsSummary {
  return {
    headerMeta: {
      amount: "Amount unavailable",
      orderNumber: "Order unavailable",
      status: "Status unavailable",
    },
    productName: "Purchase details unavailable",
    purchasedAt: "Purchase date unavailable",
    purchaseId,
    purchaseType: "physical",
  };
}

export function formatPurchaseDetailsDate(purchasedAt: string) {
  const parsedDate = new Date(purchasedAt);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Purchase date unavailable";
  }

  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(parsedDate);
}

export function savePurchaseDetailsSummary(summary: PurchaseDetailsSummary) {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.setItem(
    getPurchaseDetailsStorageKey(summary.purchaseId),
    JSON.stringify(summary),
  );
}

export function loadPurchaseDetailsSummary(purchaseId: string) {
  const storedSummary = loadPurchaseDetailsSummarySnapshot(purchaseId);

  if (!storedSummary) {
    return null;
  }

  return parsePurchaseDetailsSummary(storedSummary, purchaseId);
}

export function loadPurchaseDetailsSummarySnapshot(purchaseId: string) {
  if (typeof window === "undefined") {
    return null;
  }

  return window.sessionStorage.getItem(getPurchaseDetailsStorageKey(purchaseId));
}

export function parsePurchaseDetailsSummary(
  value: string,
  purchaseId: string,
) {
  try {
    const parsed = JSON.parse(value) as Partial<PurchaseDetailsSummary>;

    if (
      parsed.purchaseId === purchaseId &&
      typeof parsed.productName === "string" &&
      typeof parsed.purchasedAt === "string" &&
      isPurchaseType(parsed.purchaseType) &&
      isHeaderMeta(parsed.headerMeta)
    ) {
      return parsed as PurchaseDetailsSummary;
    }
  } catch {
    return null;
  }

  return null;
}

function getPurchaseDetailsStorageKey(purchaseId: string) {
  return `${purchaseDetailsStoragePrefix}${purchaseId}`;
}

function isPurchaseType(value: unknown): value is PurchaseType {
  return value === "digital" || value === "physical" || value === "subscription";
}

function isHeaderMeta(value: unknown): value is PurchaseDetailsHeaderMeta {
  if (!value || typeof value !== "object") {
    return false;
  }

  const headerMeta = value as Partial<PurchaseDetailsHeaderMeta>;

  return (
    typeof headerMeta.amount === "string" &&
    typeof headerMeta.orderNumber === "string" &&
    typeof headerMeta.status === "string"
  );
}
