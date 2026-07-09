# SSDLC Evidence Workflow

This repo treats SSDLC documentation as governed evidence, not prose output.

## 1. Capture Source

Record only stable references to the original artifact:

- requirement, design note, ticket, issue, PR, incident, scan, test run, or review
- source owner
- source date
- source location
- sensitivity boundary

Do not copy secrets, credentials, private incident payloads, customer data, or raw scanner dumps into AI summaries.

## 2. Classify Risk

Use the smallest useful risk vocabulary:

- `authn_authz`
- `input_validation`
- `secret_handling`
- `data_exposure`
- `dependency_supply_chain`
- `logging_monitoring`
- `incident_response`
- `configuration`
- `availability`
- `privacy`

## 3. Map Controls

Every control mapping must say whether the control is:

- `required`
- `implemented`
- `planned`
- `not_applicable`
- `accepted_exception`

## 4. Link Evidence

Evidence must be linked before a claim is made. Weak evidence is allowed, but it must be labeled.

Evidence strength:

- `strong`: direct test, scan, signed review, reproducible result, or approved decision.
- `medium`: reviewed design artifact or indirect test coverage.
- `weak`: AI summary, manual note, unchecked assumption, or stale artifact.

## 5. Queue Review

Queue anything that has weak evidence, accepted risk, missing owner, missing due date, or a claim that exceeds available evidence.

## 6. Record Decisions

Security decisions are append-only records. Later changes should create a new decision or update review status without rewriting the old rationale.

## 7. Revisit Due Items

`review_due` is required for risk acceptance, deferred review, exception, and weak-evidence claims.
