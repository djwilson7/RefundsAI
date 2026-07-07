const defaultApiBaseUrl = "http://localhost:8000";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const sessionId = url.searchParams.get("session_id");
  const streamUrl = new URL(`${getApiBaseUrl()}/api/admin/audit/events/stream`);

  if (sessionId) {
    streamUrl.searchParams.set("session_id", sessionId);
  }

  try {
    const response = await fetch(streamUrl, {
      cache: "no-store",
      headers: {
        Accept: "text/event-stream",
      },
    });

    if (!response.ok || !response.body) {
      return backendUnavailableResponse();
    }

    return new Response(response.body, {
      status: response.status,
      headers: {
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
        "Content-Type": "text/event-stream",
        "X-Accel-Buffering": "no",
      },
    });
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
        message: "Audit event stream is unavailable.",
      },
      meta: {},
    },
    { status: 503 },
  );
}

function getApiBaseUrl() {
  return process.env.REFUNDS_AI_API_BASE_URL ?? defaultApiBaseUrl;
}
