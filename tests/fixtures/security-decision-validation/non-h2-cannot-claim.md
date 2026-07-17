---
decision_id: SDR-TEST-0009
title: Non-H2 claim boundary
status: accepted_with_review_due
owner: security-owner
created: 2026-07-17
review_due: 2026-10-17
risk_categories:
  - input_validation
source_refs:
  - SOURCE-TEST-0009
evidence_refs:
  - EVD-TEST-0009
---

# Security Decision Record: Non-H2 claim boundary

## Decision

Keep claim boundaries at the required heading level.

## Context

This fixture uses an H3 claim-boundary heading.

## Risk

Substring heading matches can hide text from the outside-boundary scan.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |
| validate untrusted input | planned | EVD-TEST-0009 |

### Cannot Claim

- Not compliant.
- Not production safe.
- Not remediated.
- Not audit ready.
