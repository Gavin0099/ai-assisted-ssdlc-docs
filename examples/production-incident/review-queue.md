---
queue_id: REVIEW-QUEUE-0300
status: active
owner: security-owner
updated: 2026-07-16
---

# Review Queue

| review_id | source_ref | risk_category | reason | priority | status | owner | review_due |
| --- | --- | --- | --- | --- | --- | --- | --- |
| REV-0301 | SDR-0300 | incident_response | independent root-cause validation still required | P1 | pending | security-owner | 2026-10-16 |
| REV-0302 | SDR-0300 | availability | regression and recovery execution evidence still required | P1 | pending | security-owner | 2026-10-16 |
| REV-0303 | SDR-0300 | data_exposure | privacy impact scope requires restricted-system reviewer confirmation | P1 | accepted_with_review_due | privacy-owner | 2026-10-16 |

## Status Rules

- Keep this queue metadata-only and link to restricted incident systems by stable reference.
- Do not copy customer data, credentials, payloads, private logs, or forensic timelines here.
- Preserve `review_due` while root-cause, recovery, or privacy scope remains open.
