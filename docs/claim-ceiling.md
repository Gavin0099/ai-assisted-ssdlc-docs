# Claim Ceiling

AI-assisted SSDLC documentation must separate observed evidence from compliance claims.

## Allowed Claims

Use these claims when the referenced artifact supports them:

- `documented`
- `reviewed`
- `evidence_linked`
- `risk_identified`
- `control_mapped`
- `accepted_with_review_due`
- `mitigation_planned`

## Forbidden Claims Without Explicit Evidence

Do not claim:

- `compliant`
- `production_safe`
- `remediated`
- `vulnerability_fixed`
- `risk_eliminated`
- `all_controls_effective`
- `audit_ready`

## AI Summary Boundary

AI summaries are secondary artifacts. They can help reviewers navigate source material, but they do not replace:

- source artifact review
- human security decision
- test or scan evidence
- signed risk acceptance
- due-date review

## Reviewer Override

A reviewer may raise or lower a status only by recording:

- reviewer
- date
- decision
- source references
- cannot-claim boundary
- next review date when risk remains open
