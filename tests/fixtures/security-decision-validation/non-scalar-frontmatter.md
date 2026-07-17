---
decision_id: SDR-TEST-0008
title: Non-scalar frontmatter
status:
  - accepted_with_review_due
owner: security-owner
created:
  - 20260717
review_due: 2026-10-17
risk_categories:
  - input_validation
source_refs:
  - SOURCE-TEST-0008
evidence_refs:
  - EVD-TEST-0008
---

# Security Decision Record: Non-scalar frontmatter

## Decision

Require schema-declared scalar values.

## Context

This fixture encodes status and created as YAML lists.

## Risk

Wrong YAML types can bypass enum and canonical-date checks.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |
| validate untrusted input | planned | EVD-TEST-0008 |

## Cannot Claim

- Not compliant.
- Not production safe.
- Not remediated.
- Not audit ready.
