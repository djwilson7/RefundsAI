import { isDemoModeEnabled, demoServiceUnavailable } from "@/lib/demo-mode";
const defaultApiBaseUrl = "http://localhost:8000";

type RefundEligibilityRouteContext = Readonly<{
  params: Promise<{
    purchaseId: string;
  }>;
}>;

export async function GET(_request: Request, context: RefundEligibilityRouteContext) {
  if (isDemoModeEnabled()) return demoServiceUnavailable();
  const { purchaseId } = await context.params;

  return proxyBackendRefundRequest(
    `/api/purchases/${purchaseId}/refund/eligibility`,
  );
}

async function proxyBackendRefundRequest(path: string) {
  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      cache: "no-store",
    });
    const body = await response.json();

    return Response.json(body, { status: response.status });
  } catch {
    return Response.json(
      {
        success: false,
        data: null,
        error: {
          code: "BACKEND_UNAVAILABLE",
          message: "Refund workflow service is unavailable.",
        },
        meta: {},
      },
      { status: 503 },
    );
  }
}

function getApiBaseUrl() {
  return process.env.REFUNDS_AI_API_BASE_URL ?? defaultApiBaseUrl;
}
