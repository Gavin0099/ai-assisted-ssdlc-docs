---
decision_id: SDR-TEST-0006
title: Compact date
status: accepted_with_review_due
owner: security-owner
created: 20260717
review_due: 2026-10-17
risk_categories:
  - input_validation
source_refs:
  - SOURCE-TEST-0006
evidence_refs:
  - EVD-TEST-0006
---

# Security Decision Record: Compact date

## Decision

Require canonical dates.

## Context

This fixture uses a compact created date.

## Risk

Permissive parsing can accept non-contract date forms.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |
| validate untrusted input | planned | EVD-TEST-0006 |

## Cannot Claim

- Not compliant.
- Not production safe.
- Not remediated.
- Not audit ready.
