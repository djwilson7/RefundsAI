const defaultApiBaseUrl = "http://localhost:8000";

export async function POST(request: Request) {
  const body = await request.json();

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    const responseBody = await response.json();

    return Response.json(responseBody, { status: response.status });
  } catch {
    return Response.json(
      {
        success: false,
        data: null,
        error: {
          code: "BACKEND_UNAVAILABLE",
          message: "AI chat service is unavailable.",
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
