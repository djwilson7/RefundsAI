import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PhysicalReturnWorkflowCard } from "./physical-return-workflow-card";

describe("PhysicalReturnWorkflowCard", () => {
  it("renders return workflow fields", () => {
    render(
      <PhysicalReturnWorkflowCard
        acceptedByCourierAt="Awaiting courier acceptance"
        acceptedByCourierComplete={false}
        labelCreatedAt="Jul 03, 2026"
        returnRequestedAt="Jul 03, 2026"
      />,
    );

    expect(
      screen.getByRole("region", { name: "Physical return workflow" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Return Requested")).toBeInTheDocument();
    expect(screen.getByText("Label Created")).toBeInTheDocument();
    expect(screen.getByText("Accepted by Courier")).toBeInTheDocument();
    expect(screen.getAllByText("Jul 03, 2026")).toHaveLength(2);
    expect(
      screen.queryByText("Awaiting courier acceptance"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Given to Carrier" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Return Requested complete" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Label Created complete" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Accepted by Courier active" }),
    ).toBeInTheDocument();
  });

  it("calls the carrier acceptance handler from the pending step", () => {
    const onConfirmCarrierAcceptance = vi.fn();

    render(
      <PhysicalReturnWorkflowCard
        acceptedByCourierAt="Awaiting courier acceptance"
        acceptedByCourierComplete={false}
        labelCreatedAt="Jul 03, 2026"
        onConfirmCarrierAcceptance={onConfirmCarrierAcceptance}
        returnRequestedAt="Jul 03, 2026"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Given to Carrier" }));

    expect(onConfirmCarrierAcceptance).toHaveBeenCalledTimes(1);
  });
});
