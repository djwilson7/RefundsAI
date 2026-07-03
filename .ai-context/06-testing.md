# 06-testing.md

# Testing Standards

## Purpose

This document defines the testing expectations for the repository.

Testing is considered part of implementation. New functionality is not complete until it has been validated through automated tests.

Tests exist to validate real business logic and behavior, not simply to satisfy coverage metrics or produce passing results. Superficial tests that do not meaningfully exercise logic are not acceptable.

---

# Coverage Goals

Maintain a minimum of **90% coverage** across:

* Statements
* Functions
* Lines
* Branches

Coverage should be maintained throughout development rather than recovered at the end of the project.

Coverage is a signal, not a goal in itself. High coverage without meaningful validation is insufficient.

---

# Test Maintenance

Tests should be updated whenever changes affect:

* New files
* New functions
* Business logic
* Conditional branches
* Existing functionality
* Bug fixes

Changes to application behavior should be reflected in the test suite.

---

# Testing Philosophy

* Test business behavior rather than implementation details.
* Validate deterministic business logic thoroughly.
* Avoid writing tests that only assert trivial or obvious outcomes.
* Ensure tests meaningfully exercise logic paths and edge cases.
* Keep tests isolated and repeatable.
* Write clear, descriptive test cases.
* Prevent regressions as the codebase evolves.

---

# Refund Policy Coverage

Refund management tests should validate database-backed policy behavior rather than model reasoning.

Expected coverage includes:

* refund eligibility derived from purchase and purchase detail state
* product-specific refund window validation
* digital policy failures for redeemed codes
* digital success paths that invalidate issued entitlements
* physical policy failures for missing carrier acceptance, rejected returns, or expired windows
* physical success paths that progress return lifecycle state
* subscription full-refund and prorated-refund paths
* subscription failures for expired or inactive billing periods
* invalid state transitions, such as rejected physical returns without a rejection reason
* prevention of duplicate refund state outside the owning detail table

Tests should assert that backend services consume `digital_purchase_details`, `physical_purchase_details`, and `subscription_purchase_details` directly when evaluating refund policy.

---

# Validation

Before completing work:

* Execute the relevant test suite.
* Verify new functionality behaves as expected.
* Ensure coverage remains above project targets.
* Confirm tests meaningfully validate logic, not just execution paths.
* Resolve failing tests before considering the implementation complete.
