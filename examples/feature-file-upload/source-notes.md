# Source Notes: Feature File Upload

This example is intentionally synthetic. It demonstrates how source notes feed SSDLC evidence records without copying sensitive payloads.

## Source Summary

- Source ref: DESIGN-FILE-UPLOAD-001
- Feature: user file upload
- Primary risks: file type validation, malware scanning, object storage exposure, logging of file metadata
- Reviewer: security-owner

## Security Claims Requested

- The feature has a documented secure design review.
- Upload controls are mapped to evidence.
- Remaining review items are visible in the review queue.

## Source Boundary

Do not copy raw customer files, malware samples, credentials, signed URLs, or scanner payloads into generated docs.
