---
decision_id: SDR-TEST-0005
title: Missing control evidence
status: accepted_with_review_due
owner: security-owner
created: 2026-07-17
review_due: 2026-10-17
risk_categories:
  - input_validation
source_refs:
  - SOURCE-TEST-0005
evidence_refs:
  - EVD-TEST-0005
---

# Security Decision Record: Missing control evidence

## Decision

Keep evidence references explicit.

## Context

This fixture has an empty Evidence cell.

## Risk

An empty reference cannot navigate to supporting material.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |
| validate untrusted input | planned | |

## Cannot Claim

- Not compliant.
- Not production safe.
- Not remediated.
- Not audit ready.
