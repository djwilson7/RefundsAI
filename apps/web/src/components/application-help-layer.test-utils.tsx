import { vi } from "vitest";

const navigationMocks = vi.hoisted(() => ({
  pathname: "/user-home",
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMocks.pathname,
  useRouter: () => ({
    refresh: navigationMocks.refresh,
  }),
}));

export function setMockedPathname(pathname: string) {
  navigationMocks.pathname = pathname;
}

export function getNavigationRefreshMock() {
  return navigationMocks.refresh;
}

export function resetApplicationHelpLayerTestState() {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
  window.history.pushState({}, "", "/");
  navigationMocks.pathname = "/user-home";
  navigationMocks.refresh.mockClear();
}

export function installTranscriptScrollMocks(scrollHeight: number) {
  const originalScrollTo = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    "scrollTo",
  );
  const originalScrollHeight = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    "scrollHeight",
  );
  const scrollTo = vi.fn();

  Object.defineProperty(HTMLElement.prototype, "scrollTo", {
    configurable: true,
    value: scrollTo,
  });
  Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
    configurable: true,
    get: () => scrollHeight,
  });

  return {
    scrollTo,
    restore: () => {
      if (originalScrollTo) {
        Object.defineProperty(
          HTMLElement.prototype,
          "scrollTo",
          originalScrollTo,
        );
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, "scrollTo");
      }

      if (originalScrollHeight) {
        Object.defineProperty(
          HTMLElement.prototype,
          "scrollHeight",
          originalScrollHeight,
        );
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, "scrollHeight");
      }
    },
  };
}
