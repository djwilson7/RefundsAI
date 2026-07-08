import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  resetApplicationHelpLayerTestState,
  setMockedPathname,
} from "./application-help-layer.test-utils";
import { ApplicationHelpLayer } from "./application-help-layer";
import { HelpTriggerButton } from "./help-trigger-button";

describe("ApplicationHelpLayer refund controls", () => {
  afterEach(() => {
    resetApplicationHelpLayerTestState();
  });

  it("does not show manual refund commands on purchase details", () => {
    setMockedPathname("/purchase-details/40000000-0000-4000-8000-000000000001");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    render(
      <ApplicationHelpLayer>
        <main>Purchase details</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open help chat" }));

    expect(
      screen.queryByRole("button", { name: "Prep Refund" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Issue Refund" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByLabelText("Message the AI assistant"),
    ).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
});
