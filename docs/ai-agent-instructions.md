# AI Agent Instructions

When editing this repo, treat SSDLC documents as evidence records.

## Required Behavior

- Preserve source references.
- Keep `Cannot Claim` sections when evidence is incomplete.
- Add `review_due` for accepted risk, deferred review, exception, or weak evidence.
- Prefer status-only queue records over copying sensitive source content.
- Keep raw scanner results, secrets, credentials, and customer data out of generated summaries.

## Forbidden Behavior

- Do not upgrade a claim from `planned` to `implemented` without direct evidence.
- Do not mark risk as closed from an AI summary alone.
- Do not rewrite historical decision rationale to make a later result look cleaner.
- Do not remove weak-evidence or cannot-claim notes just because a template looks cleaner.

## Closeout Checklist

Before reporting a SSDLC documentation slice as done:

- templates or examples changed: run the relevant validator.
- review queue changed: run `tools/validate_review_queue.py`.
- evidence index changed: run `tools/validate_evidence_index.py`.
- due-date logic changed: run `tools/generate_due_reviews.py` against `examples/`.
- governance files changed: run drift/readiness checks.
