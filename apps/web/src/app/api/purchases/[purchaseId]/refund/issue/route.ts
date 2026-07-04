const defaultApiBaseUrl = "http://localhost:8000";

type RefundIssueRouteContext = Readonly<{
  params: Promise<{
    purchaseId: string;
  }>;
}>;

export async function POST(_request: Request, context: RefundIssueRouteContext) {
  const { purchaseId } = await context.params;

  return proxyBackendRefundIssue(`/api/purchases/${purchaseId}/refund/issue`);
}

async function proxyBackendRefundIssue(path: string) {
  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      method: "POST",
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
