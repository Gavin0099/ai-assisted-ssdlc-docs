---
decision_id: SDR-TEST-0004
title: Zero control rows
status: accepted_with_review_due
owner: security-owner
created: 2026-07-17
review_due: 2026-10-17
risk_categories:
  - input_validation
source_refs:
  - SOURCE-TEST-0004
evidence_refs:
  - EVD-TEST-0004
---

# Security Decision Record: Zero control rows

## Decision

Require an explicit control mapping row.

## Context

This fixture has a table header but no data rows.

## Risk

An empty mapping cannot describe a control state.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |

## Cannot Claim

- Not compliant.
- Not production safe.
- Not remediated.
- Not audit ready.
