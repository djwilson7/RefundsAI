import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProductHeader } from "./product-header";
import { loadSelectedMockCustomerId } from "./mock-auth-session";
import { mockCustomers } from "./mock-customers";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

// jsdom does not implement the native dialog methods; browser checks cover them.
const originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "showModal");
const originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "close");

beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: function (this: HTMLDialogElement) { this.removeAttribute("open"); },
  });
});

afterEach(() => {
  window.sessionStorage.clear();
  push.mockReset();
  vi.restoreAllMocks();
  if (originalShowModal) Object.defineProperty(HTMLDialogElement.prototype, "showModal", originalShowModal);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
  if (originalClose) Object.defineProperty(HTMLDialogElement.prototype, "close", originalClose);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
});

describe("ProductHeader perspective switching", () => {
  it("confirms switching from admin to the initial client tour", () => {
    render(<ProductHeader tour identityName="System Administrator" tourRole="admin" />);
    fireEvent.click(screen.getByRole("button", { name: "Switch to client view" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Start the Client tour from the beginning?");
    fireEvent.click(screen.getByRole("button", { name: "Swap" }));
    expect(push).toHaveBeenCalledWith(`/user-home?customerId=${mockCustomers[0].id}&tour=client`);
  });
  it("requires confirmation before opening admin and remembers the displayed customer", () => {
    render(<ProductHeader tour identityName="Maya Collins" tourRole="client" customerId={mockCustomers[1].id} />);
    fireEvent.click(screen.getByRole("button", { name: "Switch to admin view" }));
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Start the Admin tour from the beginning?" })).toHaveTextContent("won’t be saved");
    fireEvent.click(screen.getByRole("button", { name: "Swap" }));
    expect(loadSelectedMockCustomerId()).toBe(mockCustomers[1].id);
    expect(push).toHaveBeenCalledWith("/admin-home?tour=admin");
    expect(screen.getByRole("link", { name: "Exit" })).toHaveTextContent("");
  });

  it("continues the client tour without navigation or changing identity", () => {
    render(<ProductHeader tour identityName="Maya Collins" tourRole="client" customerId={mockCustomers[1].id} />);
    fireEvent.click(screen.getByRole("button", { name: "Switch to admin view" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
    expect(loadSelectedMockCustomerId()).toBeNull();
  });

  it("does not offer a swap on the perspective selection screen", () => {
    render(<ProductHeader tour />);
    expect(screen.queryByRole("button", { name: "Switch to admin view" })).not.toBeInTheDocument();
  });
});
