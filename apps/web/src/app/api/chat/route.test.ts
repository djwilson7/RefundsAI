import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

describe("chat API proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("forwards chat requests to the backend API", async () => {
    const backendBody = {
      success: true,
      data: {
        message: {
          role: "assistant",
          content: "The AI workflow infrastructure is connected.",
        },
        model: "gpt-5.4-mini",
        graph_ready: false,
      },
      error: null,
      meta: {},
    };
    const fetch = vi.fn().mockResolvedValue({
      status: 200,
      json: () => Promise.resolve(backendBody),
    });
    vi.stubGlobal("fetch", fetch);

    const response = await POST(
      new Request("http://localhost/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: "Hello" }),
      }),
    );

    await expect(response.json()).resolves.toEqual(backendBody);
    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message: "Hello" }),
    });
  });

  it("returns a backend-unavailable response when the backend request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    const response = await POST(
      new Request("http://localhost/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: "Hello" }),
      }),
    );

    await expect(response.json()).resolves.toEqual({
      success: false,
      data: null,
      error: {
        code: "BACKEND_UNAVAILABLE",
        message: "AI chat service is unavailable.",
      },
      meta: {},
    });
    expect(response.status).toBe(503);
  });
});
