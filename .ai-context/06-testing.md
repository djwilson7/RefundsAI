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

# Validation

Before completing work:

* Execute the relevant test suite.
* Verify new functionality behaves as expected.
* Ensure coverage remains above project targets.
* Confirm tests meaningfully validate logic, not just execution paths.
* Resolve failing tests before considering the implementation complete.
