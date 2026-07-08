const defaultApiBaseUrl = "http://localhost:8000";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const backendUrl = new URL(`${getApiBaseUrl()}/api/admin/audit/sessions`);

  for (const key of ["limit", "offset"]) {
    const value = requestUrl.searchParams.get(key);

    if (value !== null) {
      backendUrl.searchParams.set(key, value);
    }
  }

  return proxyBackendAuditRead(backendUrl);
}

async function proxyBackendAuditRead(url: URL) {
  try {
    const response = await fetch(url, {
      cache: "no-store",
    });
    const body = await response.json();

    return Response.json(body, { status: response.status });
  } catch {
    return backendUnavailableResponse();
  }
}

function backendUnavailableResponse() {
  return Response.json(
    {
      success: false,
      data: null,
      error: {
        code: "BACKEND_UNAVAILABLE",
        message: "Audit session data is unavailable.",
      },
      meta: {},
    },
    { status: 503 },
  );
}

function getApiBaseUrl() {
  return process.env.REFUNDS_AI_API_BASE_URL ?? defaultApiBaseUrl;
}
