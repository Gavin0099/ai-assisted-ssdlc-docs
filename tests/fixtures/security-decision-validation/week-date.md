---
decision_id: SDR-TEST-0007
title: ISO week date
status: accepted_with_review_due
owner: security-owner
created: 2026-07-17
review_due: 2026-W42-6
risk_categories:
  - input_validation
source_refs:
  - SOURCE-TEST-0007
evidence_refs:
  - EVD-TEST-0007
---

# Security Decision Record: ISO week date

## Decision

Require canonical dates.

## Context

This fixture uses an ISO week review date.

## Risk

Permissive parsing can accept non-contract date forms.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |
| validate untrusted input | planned | EVD-TEST-0007 |

## Cannot Claim

- Not compliant.
- Not production safe.
- Not remediated.
- Not audit ready.
