import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HelpButton } from "./help-button";

describe("HelpButton", () => {
  it("renders a closed chat help button", () => {
    render(<HelpButton isOpen={false} panelId="help-panel" />);

    const button = screen.getByRole("button", { name: "Open help chat" });

    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveAttribute("aria-controls", "help-panel");
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("renders an open chat help button", () => {
    render(<HelpButton isOpen panelId="help-panel" />);

    expect(
      screen.getByRole("button", { name: "Close help chat" }),
    ).toHaveAttribute("aria-expanded", "true");
  });
});
