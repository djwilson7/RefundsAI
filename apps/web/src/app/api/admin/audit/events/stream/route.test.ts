import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

describe("admin audit event stream proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("forwards the audit event stream to the backend API", async () => {
    const stream = new ReadableStream();
    const fetch = vi.fn().mockResolvedValue({
      body: stream,
      ok: true,
      status: 200,
    });
    vi.stubGlobal("fetch", fetch);

    const response = await GET(
      new Request("http://localhost/api/admin/audit/events/stream"),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/event-stream");
    expect(response.headers.get("cache-control")).toBe("no-cache");
    expect(fetch).toHaveBeenCalledWith(
      new URL("http://localhost:8000/api/admin/audit/events/stream"),
      {
        cache: "no-store",
        headers: {
          Accept: "text/event-stream",
        },
      },
    );
  });

  it("forwards optional session filters", async () => {
    const stream = new ReadableStream();
    const fetch = vi.fn().mockResolvedValue({
      body: stream,
      ok: true,
      status: 200,
    });
    vi.stubGlobal("fetch", fetch);

    await GET(
      new Request(
        "http://localhost/api/admin/audit/events/stream?session_id=70000000-0000-4000-8000-000000000001",
      ),
    );

    expect(fetch).toHaveBeenCalledWith(
      new URL(
        "http://localhost:8000/api/admin/audit/events/stream?session_id=70000000-0000-4000-8000-000000000001",
      ),
      expect.any(Object),
    );
  });

  it("returns backend unavailable when the stream cannot be opened", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    const response = await GET(
      new Request("http://localhost/api/admin/audit/events/stream"),
    );

    await expect(response.json()).resolves.toEqual({
      success: false,
      data: null,
      error: {
        code: "BACKEND_UNAVAILABLE",
        message: "Audit event stream is unavailable.",
      },
      meta: {},
    });
    expect(response.status).toBe(503);
  });
});
