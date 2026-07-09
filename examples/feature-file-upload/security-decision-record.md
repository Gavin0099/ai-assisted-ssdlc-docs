---
decision_id: SDR-0002
title: File upload requires validation, scanning, and private storage
status: accepted_with_review_due
owner: security-owner
created: 2026-07-09
review_due: 2026-10-09
risk_categories:
  - input_validation
  - data_exposure
  - logging_monitoring
source_refs:
  - DESIGN-FILE-UPLOAD-001
evidence_refs:
  - EVD-0101
  - EVD-0102
---

# Security Decision Record: File upload requires validation, scanning, and private storage

## Decision

The file upload feature must enforce server-side file validation, route uploaded files through scanning, and store accepted files in private object storage.

## Context

`source-notes.md` describes a feature that accepts user-provided files. The source boundary forbids copying raw files, malware samples, credentials, signed URLs, or scanner payloads into generated documentation.

## Risk

Unvalidated upload can lead to malware handling risk, stored content exposure, or unsafe downstream parsing. Public object access can expose user data. Excessive logging can leak sensitive file metadata.

## Control Mapping

| Control | Status | Evidence |
| --- | --- | --- |
| server-side file type and size validation | planned | EVD-0101 |
| malware scan before downstream processing | planned | EVD-0102 |
| private object storage by default | planned | EVD-0102 |

## Compensating Controls

- Keep files private until validation and scan status are available.
- Keep only metadata-level review records in the queue.
- Require implementation evidence before changing control status to `implemented`.

## Cannot Claim

- This record does not prove the feature is production safe.
- This record does not prove remediation.
- This record does not prove scanner effectiveness.
- This record does not prove compliance.

## Review Notes

- Reviewer: security-owner
- Review status: accepted_with_review_due
- Next review: 2026-10-09
