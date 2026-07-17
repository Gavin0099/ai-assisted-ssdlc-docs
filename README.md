# AI-Assisted SSDLC Docs

This repository is a lightweight, evidence-first documentation governance framework for SSDLC work.

The goal is not to claim that AI-generated security documentation is automatically correct. The goal is to structure SSDLC documentation evidence, review status, decision records, and claim boundaries for AI-assisted engineering workflows.

## Core Workflow

```text
source artifact
  -> risk classification
  -> control mapping
  -> evidence record
  -> review queue
  -> security decision record
  -> review_due follow-up
  -> audit trail
```

## Minimum Useful Scope

Version 0 starts with three document surfaces:

- Security Decision Record: what was decided, why risk was accepted or mitigated, what compensating controls exist, and when it must be reviewed again.
- Evidence Index: which PRs, tests, scans, incidents, design notes, or reviews support each security claim.
- Review Queue: which risks, weak evidence, exceptions, or decisions need human review.

## Claim Ceiling

This repo may support claims such as:

- documented security decision
- evidence-linked SSDLC artifact
- reviewer status recorded
- review due date tracked
- AI-assisted summary bounded by source references

This repo must not claim:

- compliant
- production safe
- remediated
- risk closed
- vulnerability fixed
- evidence complete

unless the referenced source artifacts and reviewer decisions explicitly support that claim.

## Entrypoints

- Workflow: [docs/workflow.md](docs/workflow.md)
- Claim ceiling: [docs/claim-ceiling.md](docs/claim-ceiling.md)
- AI agent instructions: [docs/ai-agent-instructions.md](docs/ai-agent-instructions.md)
- Reviewer guide: [docs/reviewer-guide.md](docs/reviewer-guide.md)
- Security Decision validator contract: [docs/security-decision-validator-contract.md](docs/security-decision-validator-contract.md)
- Reviewer report contract: [docs/reviewer-report-contract.md](docs/reviewer-report-contract.md)
- Templates: [templates/](templates/)
- Schemas: [schemas/](schemas/)
- Feature demos: [examples/feature-file-upload/](examples/feature-file-upload/) and [examples/feature-auth-flow/](examples/feature-auth-flow/)
- Change-management demo: [examples/dependency-upgrade/](examples/dependency-upgrade/)
- Incident follow-up demo: [examples/production-incident/](examples/production-incident/)

## Validation

Run the local validators:

```powershell
python -m pip install -r requirements-validation.txt
python -m unittest discover -s tests -p "test_*.py"
python tools\validate_evidence_index.py examples\feature-auth-flow\evidence-index.md
python tools\validate_review_queue.py examples\feature-auth-flow\review-queue.md
python tools\validate_security_decision.py examples\feature-auth-flow\security-decision-record.md
python tools\validate_security_decision.py examples\feature-file-upload\security-decision-record.md
python tools\validate_evidence_index.py examples\dependency-upgrade\evidence-index.md
python tools\validate_review_queue.py examples\dependency-upgrade\review-queue.md
python tools\validate_security_decision.py examples\dependency-upgrade\security-decision-record.md
python tools\validate_evidence_index.py examples\production-incident\evidence-index.md
python tools\validate_review_queue.py examples\production-incident\review-queue.md
python tools\validate_security_decision.py examples\production-incident\security-decision-record.md
python tools\generate_due_reviews.py examples --today 2026-07-16
python tools\generate_reviewer_report.py examples\feature-file-upload --today 2026-07-17
```

The Evidence Index and Review Queue validators load required fields, allowed values, and conditional due-date rules from `schemas/evidence-record.schema.yaml` and `schemas/review-queue.schema.yaml`. Invalid or malformed schemas fail closed.

The Security Decision validator loads frontmatter, section, forbidden-claim, and control-mapping rules from `schemas/security-decision.schema.yaml` and `schemas/control-mapping.schema.yaml`. It requires canonical dates, keeps evidence references opaque, and fails closed when a forbidden claim appears outside `Cannot Claim`.

Reviewer reports validate both inputs before rendering, aggregate queue and evidence metadata into separate attention sections, and never infer cross-file joins from `source_ref`.

Run AI Governance checks:

```powershell
python -X utf8 ai-governance-framework\governance_tools\governance_drift_checker.py --repo . --framework-root ai-governance-framework
python -X utf8 ai-governance-framework\governance_tools\external_repo_readiness.py --repo . --framework-root ai-governance-framework --format human
```
