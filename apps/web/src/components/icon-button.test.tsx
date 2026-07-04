import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IconButton } from "./icon-button";

describe("IconButton", () => {
  it("renders a default icon button as a button", () => {
    render(<IconButton icon={<span aria-hidden="true">x</span>} label="Open" />);

    expect(screen.getByRole("button", { name: "Open" })).toHaveAttribute(
      "type",
      "button",
    );
  });

  it("supports variants, custom classes, explicit type, and click handlers", () => {
    const onClick = vi.fn();

    render(
      <IconButton
        className="extra-class"
        icon={<span aria-hidden="true">x</span>}
        label="Delete"
        onClick={onClick}
        type="submit"
        variant="danger"
      />,
    );

    const button = screen.getByRole("button", { name: "Delete" });

    expect(button).toHaveAttribute("type", "submit");
    expect(button.className).toContain("extra-class");

    fireEvent.click(button);

    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
