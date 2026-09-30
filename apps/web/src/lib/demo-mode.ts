// Deployment-owned mode: URL parameters cannot enable external services.
export function isDemoModeEnabled(value = process.env.NEXT_PUBLIC_REFUNDS_AI_DEMO_MODE ?? process.env.REFUNDS_AI_DEMO_MODE) {
  return value?.trim().toLowerCase() !== "false";
}

export function demoServiceUnavailable() {
  return Response.json({
    success: false, data: null,
    error: { code: "DEMO_SERVICE_DISABLED", message: "External services are disabled in the frontend demo." },
    meta: {},
  }, { status: 404 });
}
