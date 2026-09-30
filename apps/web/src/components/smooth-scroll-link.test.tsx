import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SmoothScrollLink } from "./smooth-scroll-link";

function mockMotionPreference(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({ matches }),
  );
}

function addTarget(id = "platform") {
  const target = document.createElement("section");
  target.id = id;
  target.scrollIntoView = vi.fn();
  document.body.append(target);
  return target;
}

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("SmoothScrollLink", () => {
  it("smoothly scrolls to the target and updates the URL", () => {
    mockMotionPreference(false);
    const target = addTarget();
    const pushState = vi.spyOn(window.history, "pushState");

    render(<SmoothScrollLink href="#platform">Explore</SmoothScrollLink>);
    fireEvent.click(screen.getByRole("link", { name: "Explore" }));

    expect(target.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "start",
    });
    expect(pushState).toHaveBeenCalledWith(null, "", "#platform");
  });

  it("uses immediate scrolling when reduced motion is preferred", () => {
    mockMotionPreference(true);
    const target = addTarget();

    render(<SmoothScrollLink href="#platform">Explore</SmoothScrollLink>);
    fireEvent.click(screen.getByRole("link", { name: "Explore" }));

    expect(target.scrollIntoView).toHaveBeenCalledWith({
      behavior: "auto",
      block: "start",
    });
  });

  it("leaves an unresolved anchor to the browser", () => {
    mockMotionPreference(false);
    const pushState = vi.spyOn(window.history, "pushState");

    render(<SmoothScrollLink href="#missing">Explore</SmoothScrollLink>);
    fireEvent.click(screen.getByRole("link", { name: "Explore" }));

    expect(pushState).not.toHaveBeenCalled();
  });

  it.each([
    ["non-primary", { button: 1 }],
    ["alt-modified", { altKey: true }],
    ["control-modified", { ctrlKey: true }],
    ["meta-modified", { metaKey: true }],
    ["shift-modified", { shiftKey: true }],
  ])("preserves %s clicks", (_name, clickOptions) => {
    mockMotionPreference(false);
    const target = addTarget();
    const pushState = vi.spyOn(window.history, "pushState");

    render(<SmoothScrollLink href="#platform">Explore</SmoothScrollLink>);
    fireEvent.click(screen.getByRole("link", { name: "Explore" }), clickOptions);

    expect(target.scrollIntoView).not.toHaveBeenCalled();
    expect(pushState).not.toHaveBeenCalled();
  });
});
