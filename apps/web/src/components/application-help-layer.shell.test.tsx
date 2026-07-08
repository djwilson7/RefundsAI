import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  resetApplicationHelpLayerTestState,
  setMockedPathname,
} from "./application-help-layer.test-utils";
import {
  ApplicationHelpLayer,
  useApplicationHelpLayer,
} from "./application-help-layer";
import { HelpTriggerButton } from "./help-trigger-button";

describe("ApplicationHelpLayer", () => {
  afterEach(() => {
    resetApplicationHelpLayerTestState();
  });

  it("opens the persistent shell panel from a page-owned trigger", () => {
    setMockedPathname("/user-home");

    render(
      <ApplicationHelpLayer>
        <main>Purchase summary</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    const button = screen.getByRole("button", { name: "Open help chat" });

    expect(
      screen.queryByRole("complementary", { name: "Help panel" }),
    ).not.toBeInTheDocument();
    expect(button).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(button);

    expect(
      screen.getByRole("button", { name: "Close help chat" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("complementary", { name: "Help panel" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Help")).toBeInTheDocument();
    expect(
      screen.queryByText(/Select a purchase/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Prep Refund" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Issue Refund" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByLabelText("Message the AI assistant"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Voice input coming soon" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Send message" }),
    ).toBeDisabled();
  });

  it("does not render the trigger or panel outside purchase surfaces", () => {
    setMockedPathname("/");

    render(
      <ApplicationHelpLayer>
        <main>Mock auth</main>
        <HelpTriggerButton />
      </ApplicationHelpLayer>,
    );

    expect(
      screen.queryByRole("button", { name: "Open help chat" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("complementary", { name: "Help panel" }),
    ).not.toBeInTheDocument();
  });

  it("requires the help-layer context provider for direct hook access", () => {
    function MissingProviderConsumer() {
      useApplicationHelpLayer();

      return null;
    }

    expect(() => render(<MissingProviderConsumer />)).toThrow(
      "useApplicationHelpLayer must be used within ApplicationHelpLayer.",
    );
  });
});
