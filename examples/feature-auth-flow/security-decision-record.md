---
decision_id: SDR-0001
title: Auth flow requires server-side session validation
status: accepted_with_review_due
owner: security-owner
created: 2026-07-09
review_due: 2026-10-09
risk_categories:
  - authn_authz
source_refs:
  - DESIGN-AUTH-001
evidence_refs:
  - EVD-0001
---

# Security Decision Record: Auth flow requires server-side session validation

## Decision

The auth flow must validate session state on the server before protected data is returned.

## Context

The feature-auth-flow example represents a product feature that reads user-specific data after login.

## Risk

If session state is trusted only on the client, authorization bypass can expose user data.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |
| server-side session validation | planned | EVD-0001 |

## Compensating Controls

- Keep protected API routes behind a server-side session check.
- Add regression tests before marking the control implemented.

## Cannot Claim

- This record does not prove production remediation.
- This record does not prove the implementation is complete.

## Review Notes

- Reviewer: security-owner
- Review status: accepted_with_review_due
- Next review: 2026-10-09
