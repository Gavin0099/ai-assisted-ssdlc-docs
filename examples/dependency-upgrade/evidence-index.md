---
index_id: EVIDENCE-INDEX-0200
status: draft
owner: security-owner
updated: 2026-07-16
---

# Evidence Index

| evidence_id | source_ref | artifact_type | supports_claim | strength | review_status | review_due |
| --- | --- | --- | --- | --- | --- | --- |
| EVD-0201 | CHANGE-DEPENDENCY-001 | change_request | control_mapped | medium | accepted_with_review_due | 2026-10-16 |
| EVD-0202 | SBOM-DEPENDENCY-001 | dependency_inventory | risk_identified | medium | accepted_with_review_due | 2026-10-16 |
| EVD-0203 | TEST-DEPENDENCY-001 | test_plan | mitigation_planned | weak | pending | 2026-10-16 |

## Cannot Claim

- The change request does not prove package provenance by itself.
- The dependency inventory does not prove every transitive risk was reviewed.
- A test plan is not test execution evidence.
