# Reviewer Report Output Contract

This contract defines the first reviewer-ready report generated from an SSDLC
package's Evidence Index and Review Queue. The report is a deterministic,
metadata-only navigation aid. It is not a reviewer decision or primary
evidence.

## Inputs

The command accepts one package directory and uses exactly these two input
files; other package files are out of scope and ignored:

- `evidence-index.md`
- `review-queue.md`

Both inputs must pass their repository validators before any report content is
written. Every non-empty `review_due` used by the report must be an ISO date in
`YYYY-MM-DD` form. Missing files, invalid tables, invalid schemas, or invalid
dates fail closed with a non-zero exit status and no partial report on stdout.

## Aggregation-Only Boundary

The report aggregates rows from the two validated files into separate sections.
It must not join, correlate, reconcile, or close a Review Queue row with an
Evidence Index row.

In particular:

- `source_ref` is opaque metadata, not a cross-file join key.
- Equal, similar, ordered, or adjacent references do not establish a relation.
- Evidence strength or review status does not close a queue item.
- A queue status does not upgrade evidence strength or claim authority.
- No inferred relation may support remediation, compliance, production-safety,
  audit-readiness, or control-effectiveness claims.

A future explicit mapping artifact and schema change are required before any
cross-file relationship may be reported.

## Command and Output

The version 1 command is:

```text
python tools/generate_reviewer_report.py <package-directory> --today YYYY-MM-DD
```

Successful output is Markdown on stdout with these sections in this order:

1. `# Reviewer Report: <package-name>`
2. `## Report Metadata`
3. `## Summary`
4. `## Review Queue Attention`
5. `## Evidence Attention`
6. `## Aggregation Boundary`
7. `## Cannot Claim`

Report metadata contains only the `as_of` date, the two input filenames, and
`validation: PASS`. It must not expose absolute local paths.

## Attention Rules

Review Queue attention includes every row whose status is not `accepted` or
`rejected`. Sort rows by:

1. priority: `P0`, `P1`, `P2`, `P3`
2. due state: `overdue`, `due`, `upcoming`
3. `review_due`
4. `review_id`

Evidence attention includes every row that is weak or whose review status is
one of:

- `pending`
- `needs_changes`
- `accepted_with_review_due`
- `deferred`

Sort evidence rows by:

1. due state: `overdue`, `due`, `upcoming`, `not_applicable`
2. strength: `weak`, `medium`, `strong`
3. `review_due`
4. `evidence_id`

When an attention section has no rows, emit a single plain-language empty-state
sentence instead of an empty Markdown table.

## Fixed Claim Boundary

The Aggregation Boundary section must state that the two inputs were aggregated
without inferred joins and that source artifacts still require direct human
review.

The Cannot Claim section must always deny that the generated report proves:

- a queue-to-evidence correlation or closure
- domain correctness
- compliance
- remediation or vulnerability resolution
- production safety
- audit readiness
- control effectiveness

These boundaries are fixed output requirements. Input content cannot remove or
weaken them.
