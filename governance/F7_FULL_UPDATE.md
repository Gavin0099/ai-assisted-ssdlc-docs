---
audience: agent-on-demand
authority: reference
can_override: false
overridden_by: AGENT.md
default_load: on-demand
---

# F-7 Full Update

Status: extracted from AGENTS.md
Semantic change: no
Runtime behavior change: yes — submodule consumer apply path now refreshes memory workflow router coverage and managed hook advisory coverage.
Enforcement change: no

## Purpose

F-7 is the AI Governance Full Update workflow. A governed submodule pointer
update is Stage 1 of F-7, not the whole workflow.

When the user asks to update or adopt the latest AI Governance through F-7, F-7
must execute the full adoption/update workflow or explicitly report a blocker.

A submodule pointer update alone is insufficient and must be reported as
`partially_updated`, not completed.

## Required Stages

1. framework pointer update
2. repo-local instruction refresh
3. memory writer coverage check
4. hook / validator coverage check
5. existing memory normalization status check
6. final adoption status report backed by `governance_maturity_summary`

## Layered Status Fields

```text
framework_pointer: updated | already_current | blocked | not_present | not_verified
repo_local_instruction: updated | already_current | blocked | missing | not_verified
memory_writer_coverage: verified | updated | blocked | missing | not_applicable | not_verified
hook_validator_enforcement: verified | updated | blocked | missing | not_applicable | not_verified
existing_memory_normalization: completed | needed | blocked | not_applicable | not_verified
governance_maturity_summary: present | not_available | not_run
human_readable_adoption_summary: reported | not_reported
ai_governance_update_result: reported | not_reported
final_status: full_update_completed | already_current | partially_updated | manual_update | destructive_manual_update | blocked | not_submodule_consumer | not_verified
```

`full_update_completed` may be used only when every required stage is
`updated`, `already_current`, `verified`, `completed`, or `not_applicable`.

If any required surface is `missing`, `needed`, `blocked`, or `not_verified`,
the final status must not be `full_update_completed`.

Manual pointer, gitlink, checkout, or lock-file edits that bypass F-7 may be
reported as `manual_update`, but must not be reported as
`full_update_completed`, `already_current`, or `updated`. If that manual path
discarded local framework checkout state, report `destructive_manual_update`
and include the discarded modified and untracked path inventory in the final
operator-facing report.

This is the F-7-specific projection of the canonical manual-update reporting
vocabulary in `governance/AI_GOVERNANCE_UPDATE_PROTOCOL.md`. Do not treat this
file as an independent source for `manual_update` or
`destructive_manual_update` definitions.

The final adoption status report must follow the canonical adoption-summary
relay contract in `governance/AI_GOVERNANCE_UPDATE_PROTOCOL.md`. The concrete
table and final-report projection are produced by
`governance_tools/governance_update_reporting.py`; F-7 must not maintain a
separate copy of the table rows or header here. Operationally, when
`human_readable_adoption_summary` is present, relay the table rows as a table,
not only as machine-readable status fields.

`adoption_doctor: findings 0`, `governance_version_check: compatible`, a clean
build, or a framework pointer update is not a substitute for the final adoption
status report. If `governance_maturity_summary` cannot be produced, F-7 must
report `governance_maturity_summary: not_available` or
`governance_maturity_summary: not_run` with the reason and must not claim that
the operator was shown complete adoption status.

If the machine-readable summary is available but the table cannot be relayed,
F-7 must report `human_readable_adoption_summary: not_reported` with the reason
and must not claim that the operator was shown the complete human-readable
feature adoption table.

## Consumer Test-Quality Expectations

F-7 instruction refresh must keep semantic test-quality expectations visible to
agents that later write feature or bugfix code in the consuming repo.

For non-trivial behavior changes:

- happy-path-only tests are not sufficient evidence;
- reproducible bug fixes need regression tests when feasible;
- expected values must come from a specification, invariant, reviewed fixture,
  or other independent source, not copied production logic;
- mock-only assertions are weak evidence unless the test also asserts
  observable behavior, state, output, or persisted effect;
- domain validators need pass/fail fixtures, and fixture evidence is strongest
  only when a focused harness actually executes the validator against those
  fixtures.

Report-only `test_signal_quality_audit` output can help reviewers find weak
signals. It does not prove tests are industry-grade, does not prove domain
correctness, and does not create enforcement.

F-7 human and JSON outputs must also carry `ai_governance_update_result` as a
report-only presentation and claim-boundary envelope. This envelope must not
replace `final_status`, must not change F-7 completion criteria, and must not
be used as proof of runtime enforcement, full adoption, semantic correctness,
memory completeness, fleet/CI enforcement, domain correctness, or release
readiness.

When F-7 reports `manual_update` or `destructive_manual_update`, the envelope
must preserve that same status as a disclosure state. Manual and destructive
manual states are not successful governed F-7 completions, and destructive
manual reporting must include the discarded modified and untracked path
inventory.

## Implemented Automation

For `submodule_consumer` apply mode, the updater now performs these scoped
surfaces:

- refreshes `AGENTS.base.md`
- refreshes / appends AI Governance update rules in `AGENTS.md`
- ensures an `AGENTS.md` `governance:key=memory_workflow` router section
- installs managed hook advisory files from the governance submodule checkout
- surfaces `governance_maturity_summary` as a report-only adoption visibility
  stage for consuming-repo operators
- reports `full_update_completed` only when memory workflow coverage, hook
  advisory coverage, and normalization status are all eligible

## Non-Claims

This protocol defines the required F-7 reporting contract. It does not by
itself implement updater automation for all stages.

Not claimed unless separately implemented and validated:
- updater automation performs all F-7 stages for all repo roles
- validators changed
- artifact schema changed
- existing memory was normalized
