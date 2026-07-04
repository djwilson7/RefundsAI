import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DigitalCodeDetailsCard } from "./digital-code-details-card";

describe("DigitalCodeDetailsCard", () => {
  it("renders issued code and redeemed state", () => {
    render(
      <DigitalCodeDetailsCard codeRedeemed issuedCode="DIG-RAI-10002" />,
    );

    expect(
      screen.getByRole("region", { name: "Digital code details" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Issued Code")).toBeInTheDocument();
    expect(screen.getByText("DIG-RAI-10002")).toBeInTheDocument();
    expect(screen.getByText("Redeemed State")).toBeInTheDocument();
    expect(screen.getByText("Redeemed")).toBeInTheDocument();
  });

  it("renders an unredeemed state", () => {
    render(
      <DigitalCodeDetailsCard
        codeRedeemed={false}
        issuedCode="DIG-RAI-10003"
      />,
    );

    expect(screen.getByText("Not redeemed")).toBeInTheDocument();
  });
});
