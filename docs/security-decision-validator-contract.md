# Security Decision Validator Contract

This contract defines fail-closed validation for one Security Decision Record.
The validator checks document structure and bounded claim semantics. It does not
prove that referenced evidence exists, that a reviewer approved the record, or
that any mapped control is effective.

## Inputs

The command accepts one Markdown record and uses these repository schemas:

- `schemas/security-decision.schema.yaml`
- `schemas/control-mapping.schema.yaml`

Missing, malformed, incomplete, or enum-inconsistent schemas fail closed. The
validator must load schema rules before evaluating record rows, including when
the Control Mapping table contains zero data rows.

## Frontmatter

Every key named by `required_frontmatter` must be present. Fields named by
`scalar_frontmatter` must be YAML scalar strings; fields named by
`list_frontmatter` must be non-empty lists of non-empty strings. Scalar values
must be non-empty unless this contract explicitly permits an empty
`review_due`.

- `status` must belong to `allowed_status`.
- `created` must be an exact calendar date in `YYYY-MM-DD` form.
- A non-empty `review_due` must be an exact calendar date in `YYYY-MM-DD` form.
- `review_due` is required when status is `pending`, `needs_changes`,
  `accepted_with_review_due`, or `deferred`.
- Exact date form means parsing succeeds and `parsed.isoformat()` equals the
  original input. Compact and ISO week-date forms fail closed.

## Required Sections

Every heading named by `required_sections` must exist as an exact, line-anchored
level-two Markdown heading. A level-three heading or prose substring does not
satisfy the requirement. `Cannot Claim` must contain non-whitespace content.

## Control Mapping

The `Control Mapping` section must contain exactly this table header:

```text
| Control | Status | Evidence |
```

The table must contain at least one data row. Each row must satisfy the
`control-mapping` schema:

- the header is followed by a Markdown separator row containing only valid
  three-or-more-dash cells with optional alignment colons
- every required field is non-empty
- `Status` belongs to `allowed_status`
- `Evidence` remains an opaque reference string

The validator must not resolve `Evidence` against an Evidence Index or infer
that a reference proves implementation, remediation, compliance, production
safety, audit readiness, or control effectiveness. In particular, an
`implemented` value is structurally allowed but is not independently proven by
this validator.

## Claim Boundary

Forbidden claim phrases are matched case-insensitively outside the `Cannot
Claim` section. A phrase inside `Cannot Claim` is permitted only in that
section; it must not whitelist or mask the same phrase elsewhere in the record.

The validator reports all deterministic validation errors it can identify and
returns a non-zero exit status when any error exists.

## Cannot Claim

A passing result proves only that the record satisfies this structural and
semantic validator contract. It does not prove:

- domain correctness
- human review or approval
- evidence authenticity or sufficiency
- implementation or remediation
- compliance or production safety
- audit readiness or control effectiveness
