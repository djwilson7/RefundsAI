import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildMockCredentials,
  findMockCustomerById,
  getIdentityDisplayName,
  getRandomMockCustomer,
  mockAdmin,
  mockCustomers,
} from "./mock-customers";

describe("mock customer utilities", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("builds display names and mock credentials from seeded identities", () => {
    expect(getIdentityDisplayName(mockAdmin)).toBe("System Administrator");
    expect(buildMockCredentials(mockAdmin)).toEqual({
      email: "system_administrator@example.com",
      password: "12345Password",
    });
  });

  it("selects seeded customers by id and returns null for unknown ids", () => {
    expect(findMockCustomerById(mockCustomers[0].id)).toEqual(mockCustomers[0]);
    expect(findMockCustomerById(undefined)).toBeNull();
    expect(findMockCustomerById("unknown")).toBeNull();
  });

  it("selects a random seeded customer", () => {
    vi.spyOn(Math, "random").mockReturnValue(0.99);

    expect(getRandomMockCustomer()).toEqual(
      mockCustomers[mockCustomers.length - 1],
    );
  });
});
