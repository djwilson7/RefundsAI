# RefundsAI Refund Policy

**Effective Date:** July 3, 2026

## Purpose

This policy is the customer-facing reference. The executable policy remains the
backend catalog and deterministic workflow helpers listed below.

Backend implementation source:

* `apps/api/src/refunds_ai_api/services/refund_policy_catalog.py`
* `apps/api/src/refunds_ai_api/services/refund_policy.py`

The AI assistant may explain this policy, but backend workflow services decide
account-specific eligibility from persisted purchase and purchase-detail state.

## Physical Products

Physical products may be returned within 30 calendar days of the original purchase date.

To qualify:

* The refund request must be submitted before the 31st calendar day after purchase.
* The product must be returned using the designated shipping carrier after approval.
* The return package must be accepted by the carrier before refund processing begins.

Requests submitted after the 30-day return window are not eligible for refund.

## Digital Products

Digital products may be refunded within 15 calendar days of the original purchase date.

To qualify:

* The refund request must be submitted within 15 calendar days of purchase.
* The issued activation code, license, or digital entitlement must not have been redeemed.

Approved digital refunds permanently invalidate the associated digital entitlement before
the refund is processed.

Digital products that have already been redeemed are not eligible for refund.

## Subscription Products

Subscription purchases may be cancelled at any time.

Refund eligibility:

* A full refund may be available within 48 hours of the original purchase if the subscription remains active.
* After 48 hours, eligible refunds are prorated from the unused portion of the current active billing period.
* Refunds are limited to the current active billing period.
* Refund requests cannot be applied retroactively to previous billing cycles.
* Subscriptions that have expired without an active billing period are not eligible for refund.

Approved subscription refunds cancel the subscription, terminate service access according
to the effective refund date, and disable auto-renewal.

Customer-facing subscription detail screens should show prepared cancellations and issued
refunds in `Return Details` instead of asking customers to infer refund state from
renewal settings alone.

## Refund Processing

Approved refunds are processed using the original payment method whenever possible.

Most refunds are completed within 3-10 business days, depending on the financial
institution or payment provider.

## Administrative Review

Certain refund requests may require additional review before a final decision.

Examples:

* Incomplete purchase information.
* Suspected fraud or abuse.
* Requests that cannot be verified.
* Circumstances requiring additional investigation.

Additional review does not guarantee refund approval.

## Scoped Policy Explanations

RefundsAI support surfaces should keep policy explanations scoped to the customer
question.

Examples:

* If the customer asks about digital purchases, answer from the digital policy.
* If the customer asks about an active result set, do not broaden to unrelated product types.
* If the customer asks whether a specific purchase is refundable, use backend eligibility rather than policy text alone.

## Policy Updates

Refund policy updates may apply to future purchases unless otherwise required by
applicable law.
