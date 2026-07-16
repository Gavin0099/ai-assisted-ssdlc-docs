---
decision_id: SDR-0200
title: Dependency upgrade requires provenance, regression, and rollback evidence
status: accepted_with_review_due
owner: security-owner
created: 2026-07-16
review_due: 2026-10-16
risk_categories:
  - dependency_supply_chain
  - availability
  - configuration
source_refs:
  - CHANGE-DEPENDENCY-001
  - SBOM-DEPENDENCY-001
evidence_refs:
  - EVD-0201
  - EVD-0202
  - EVD-0203
---

# Security Decision Record: Dependency upgrade requires provenance, regression, and rollback evidence

## Decision

The dependency upgrade must preserve an approved package source, review transitive dependency changes, run compatibility tests, and document a rollback path before release approval.

## Context

`source-notes.md` describes a synthetic major-version upgrade for a shared HTTP client. The source boundary excludes credentials, private advisory text, internal registry locations, and raw scanner output.

## Risk

An unverified package source can introduce supply-chain risk. Transitive changes or altered defaults can break security assumptions, availability, or runtime configuration. Missing rollback evidence can extend recovery time if the upgrade behaves unexpectedly.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |
| approved package source and integrity verification | planned | EVD-0201 |
| transitive dependency comparison | planned | EVD-0202 |
| compatibility test and rollback rehearsal | planned | EVD-0203 |

## Compensating Controls

- Keep the prior lock file and release artifact available for rollback planning.
- Restrict package retrieval to the approved registry configuration.
- Require direct test evidence before changing any control to `implemented`.

## Cannot Claim

- This record does not prove the dependency is vulnerability free.
- This record does not prove the upgrade is production safe.
- This record does not prove remediation or compliance.
- This record does not prove rollback effectiveness.

## Review Notes

- Reviewer: security-owner
- Review status: accepted_with_review_due
- Next review: 2026-10-16
