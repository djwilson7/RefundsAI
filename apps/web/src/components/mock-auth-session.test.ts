import { afterEach, describe, expect, it } from "vitest";
import {
  clearSelectedMockCustomer,
  loadSelectedMockCustomerId,
  storeSelectedMockCustomer,
} from "./mock-auth-session";

describe("mock auth session", () => {
  afterEach(() => {
    window.sessionStorage.clear();
  });

  it("stores and loads the selected mock customer id", () => {
    storeSelectedMockCustomer({
      id: "20000000-0000-4000-8000-000000000001",
      firstName: "Avery",
      lastName: "Brooks",
      createdAt: "2026-07-03T00:00:00Z",
    });

    expect(loadSelectedMockCustomerId()).toBe(
      "20000000-0000-4000-8000-000000000001",
    );
  });

  it("returns null when no selected mock customer is stored", () => {
    expect(loadSelectedMockCustomerId()).toBeNull();
  });

  it("returns null for malformed selected mock customer data", () => {
    window.sessionStorage.setItem("refunds-ai:selected-mock-customer", "{");

    expect(loadSelectedMockCustomerId()).toBeNull();
  });

  it("returns null when selected mock customer data has no string id", () => {
    window.sessionStorage.setItem(
      "refunds-ai:selected-mock-customer",
      JSON.stringify({ id: 123 }),
    );

    expect(loadSelectedMockCustomerId()).toBeNull();
  });

  it("clears the selected mock customer", () => {
    storeSelectedMockCustomer({
      id: "20000000-0000-4000-8000-000000000001",
      firstName: "Avery",
      lastName: "Brooks",
      createdAt: "2026-07-03T00:00:00Z",
    });

    clearSelectedMockCustomer();

    expect(loadSelectedMockCustomerId()).toBeNull();
  });
});
