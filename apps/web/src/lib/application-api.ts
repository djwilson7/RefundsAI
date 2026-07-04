const defaultApiBaseUrl = "http://localhost:8000";

type ApiResponse<TData> = Readonly<{
  success: boolean;
  data: TData | null;
  error: { code: string; message: string } | null;
  meta: Record<string, unknown>;
}>;

type ApiUser = Readonly<{
  id: string;
  first_name: string;
  last_name: string;
  created_at: string;
  display_name: string;
  roles: readonly { key: string; name: string }[];
}>;

type ApiPurchase = Readonly<{
  id: string;
  order_number: string;
  purchase_type: "digital" | "physical" | "subscription";
  product_name: string;
  sku: string;
  amount_cents: number;
  purchased_at: string;
  status: string;
  details_url: string;
}>;

export type CustomerProfile = Readonly<{
  id: string;
  firstName: string;
  lastName: string;
  createdAt: string;
}>;

export type CustomerPurchase = Readonly<{
  id: string;
  productName: string;
  amountCents: number;
  purchasedAt: string;
  status: string;
}>;

function getApiBaseUrl() {
  return process.env.REFUNDS_AI_API_BASE_URL ?? defaultApiBaseUrl;
}

export async function getUserProfile(userId: string) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/users/${userId}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as ApiResponse<{ user: ApiUser }>;

    if (!body.success || !body.data) {
      return null;
    }

    return mapApiUserToCustomerProfile(body.data.user);
  } catch {
    return null;
  }
}

export async function getUserPurchases(userId: string) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/users/${userId}/purchases`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as ApiResponse<{
      purchases: ApiPurchase[];
    }>;

    if (!body.success || !body.data) {
      return null;
    }

    return body.data.purchases.map(mapApiPurchaseToCustomerPurchase);
  } catch {
    return null;
  }
}

export function mapApiUserToCustomerProfile(user: ApiUser): CustomerProfile {
  return {
    id: user.id,
    firstName: user.first_name,
    lastName: user.last_name,
    createdAt: user.created_at,
  };
}

export function mapApiPurchaseToCustomerPurchase(
  purchase: ApiPurchase,
): CustomerPurchase {
  return {
    id: purchase.id,
    productName: purchase.product_name,
    amountCents: purchase.amount_cents,
    purchasedAt: purchase.purchased_at,
    status: purchase.status,
  };
}

export function formatCentsAsDollars(amountCents: number) {
  return new Intl.NumberFormat("en-US", {
    currency: "USD",
    style: "currency",
  }).format(amountCents / 100);
}

export function formatPurchaseDate(purchasedAt: string) {
  const parsedDate = new Date(purchasedAt);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Purchased date unavailable";
  }

  return `Purchased ${new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(parsedDate)}`;
}

export function formatPurchaseStatus(status: string) {
  return status
    .split("_")
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}
