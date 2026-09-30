import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProductLanding } from "./product-landing";

describe("ProductLanding", () => {
  it("presents the product, refund workspace, and lifecycle-specific workflows", () => {
    render(<ProductLanding />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Refunds, governed.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("RefundsAI refund workspace preview"),
    ).toBeInTheDocument();
    expect(screen.getByText("$89.00")).toBeInTheDocument();
    expect(screen.getByText("Digital")).toBeInTheDocument();
    expect(screen.getByText("Physical")).toBeInTheDocument();
    expect(screen.getByText("Subscription")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Integration entry points"),
    ).toHaveTextContent("CommerceCustomer contextPolicyEntitlementsPaymentsAudit");
    expect(
      screen.getByLabelText("RefundsAI orchestration model"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Flexible language. Fixed control." }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Every handoff stays visible." }),
    ).toBeInTheDocument();
    const loggedLifecycle = screen.getByLabelText("Logged request lifecycle");
    expect(loggedLifecycle).toHaveTextContent("User request received");
    expect(loggedLifecycle).toHaveTextContent("Intent interpreted + tools mapped");
    expect(loggedLifecycle).toHaveTextContent("Backend gates + result verified");
    expect(loggedLifecycle).toHaveTextContent("User informed");
    expect(screen.getByText("Across your stack")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    expect(screen.queryByText("Confirm invalidate code and issue refund")).not.toBeInTheDocument();
  });

  it("shows the intentionally unavailable technical tour control", () => {
    render(<ProductLanding />);

    expect(
      screen.getByRole("button", { name: "Technical tour (coming soon)" }),
    ).toBeDisabled();
  });
});
