# Reviewer Guide

Review SSDLC artifacts in this order:

1. Source references exist and are stable.
2. Risk category matches the source.
3. Control status does not overstate implementation.
4. Evidence strength is labeled honestly.
5. `Cannot Claim` section blocks unsupported claims.
6. Risk acceptance has owner, rationale, compensating control, and `review_due`.
7. Review queue contains open weak evidence, exceptions, and due reviews.

## Review Status

Use these statuses:

- `pending`
- `needs_changes`
- `accepted`
- `accepted_with_review_due`
- `deferred`
- `rejected`

## Blocking Findings

Block the artifact when:

- a security claim has no source reference
- accepted risk has no review due date
- sensitive source content is copied into a status-only artifact
- AI summary is treated as primary evidence
- claim ceiling is missing or contradicted
