# Due-Review Generator Contract

This contract defines fail-closed date handling for the due-review report. The
report is a deterministic navigation aid over Review Queue metadata. It is not
a reviewer decision, evidence of closure, or proof that a risk was remediated.

## Command and Inputs

The command is:

```text
python tools/generate_due_reviews.py <root> --today YYYY-MM-DD
```

The generator recursively discovers files named `review-queue.md` below
`<root>`. Each file must contain the repository Review Queue table shape.

## Canonical Date Rule

`--today` and every discovered row's `review_due` must be exact calendar dates
in `YYYY-MM-DD` form. Parsing must succeed and `parsed.isoformat()` must equal
the original input.

Compact dates such as `20260717`, ISO week dates such as `2026-W29-5`, and
invalid calendar dates fail closed. Date validation occurs before terminal
statuses are filtered from the due report, so an `accepted` or `rejected` row
cannot hide a malformed date.

The generator and other report commands must use the same shared strict date
parser rather than maintaining separate acceptance rules.

## Fail-Closed Output

The command must validate `--today`, all discovered tables, and all row dates
before writing report content. On any input error it must:

- return a non-zero exit status
- write no partial report to stdout
- write a `due_reviews: FAIL` diagnostic to stderr
- identify the invalid field and require `YYYY-MM-DD`

On success it returns zero and writes the Markdown due-review table to stdout.
Rows with status `accepted` or `rejected` are validated but omitted. Other rows
are emitted only when their due date is today or earlier.

## Cannot Claim

A successful report proves only that discovered Review Queue tables were
readable and their dates satisfied this contract. It does not prove:

- source or evidence authenticity
- reviewer approval
- risk closure or remediation
- compliance or production safety
- audit readiness or control effectiveness
