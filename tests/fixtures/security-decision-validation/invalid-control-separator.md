---
decision_id: SDR-TEST-0010
title: Invalid control separator
status: accepted_with_review_due
owner: security-owner
created: 2026-07-17
review_due: 2026-10-17
risk_categories:
  - input_validation
source_refs:
  - SOURCE-TEST-0010
evidence_refs:
  - EVD-TEST-0010
---

# Security Decision Record: Invalid control separator

## Decision

Validate the table separator before reading control rows.

## Context

This fixture places an invalid control row where the separator must be.

## Risk

Blindly skipping the separator position can hide an invalid first row.

## Control Mapping

| Control | Status | Evidence |
| skipped control | implmented | |
| validate untrusted input | planned | EVD-TEST-0010 |

## Cannot Claim

- Not compliant.
- Not production safe.
- Not remediated.
- Not audit ready.
