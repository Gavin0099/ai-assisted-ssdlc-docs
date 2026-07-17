---
decision_id: SDR-TEST-0003
title: Invalid control status
status: accepted_with_review_due
owner: security-owner
created: 2026-07-17
review_due: 2026-10-17
risk_categories:
  - input_validation
source_refs:
  - SOURCE-TEST-0003
evidence_refs:
  - EVD-TEST-0003
---

# Security Decision Record: Invalid control status

## Decision

Keep the control status within the governed enum.

## Context

This fixture contains a misspelled status.

## Risk

Unknown status values make the control state ambiguous.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |
| validate untrusted input | implmented | EVD-TEST-0003 |

## Cannot Claim

- Not compliant.
- Not production safe.
- Not remediated.
- Not audit ready.
