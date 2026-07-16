---
decision_id: SDR-0300
title: Incident follow-up requires redacted evidence and verified recovery actions
status: accepted_with_review_due
owner: security-owner
created: 2026-07-16
review_due: 2026-10-16
risk_categories:
  - incident_response
  - logging_monitoring
  - data_exposure
  - availability
source_refs:
  - INCIDENT-REDACTED-001
  - POSTMORTEM-001
evidence_refs:
  - EVD-0301
  - EVD-0302
  - EVD-0303
---

# Security Decision Record: Incident follow-up requires redacted evidence and verified recovery actions

## Decision

Incident follow-up must use redacted source references, validate the proposed root cause, link recovery and prevention actions to direct evidence, and retain open review items until owners verify their effects.

## Context

`source-notes.md` describes a synthetic authorization incident following a configuration change. Documentation remains metadata-only and excludes customer data, credentials, payloads, internal hostnames, and private logs.

## Risk

An early incident narrative can mistake correlation for root cause. Recovery actions that lack direct evidence can leave recurrence or availability risk unresolved. Copying raw operational data into review artifacts can create additional exposure.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |
| redacted incident timeline and source ownership | planned | EVD-0301 |
| independent root-cause review | planned | EVD-0302 |
| regression and recovery verification | planned | EVD-0303 |

## Compensating Controls

- Keep sensitive operational detail in the restricted incident system.
- Use stable references and metadata in the review queue.
- Keep follow-up items open until direct evidence is reviewed.

## Cannot Claim

- This record does not prove the proposed root cause is final.
- This record does not prove remediation or risk elimination.
- This record does not prove whether customer data exposure occurred.
- This record does not prove production safety or audit readiness.

## Review Notes

- Reviewer: security-owner
- Review status: accepted_with_review_due
- Next review: 2026-10-16
