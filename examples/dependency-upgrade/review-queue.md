---
queue_id: REVIEW-QUEUE-0200
status: active
owner: security-owner
updated: 2026-07-16
---

# Review Queue

| review_id | source_ref | risk_category | reason | priority | status | owner | review_due |
| --- | --- | --- | --- | --- | --- | --- | --- |
| REV-0201 | SDR-0200 | dependency_supply_chain | package provenance and transitive dependency evidence still required | P1 | pending | security-owner | 2026-10-16 |
| REV-0202 | SDR-0200 | availability | compatibility and rollback execution evidence still required | P1 | pending | security-owner | 2026-10-16 |

## Status Rules

- Keep package credentials, private advisory text, and raw scanner output outside this queue.
- Do not close rows from a proposed test plan alone.
- Preserve `review_due` while verification remains incomplete.
