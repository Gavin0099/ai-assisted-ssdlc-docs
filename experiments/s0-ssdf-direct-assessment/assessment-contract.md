# S0 SSDF Assessment Contract

Status: experimental
Issue: #6

This contract defines the output boundary for `S0-SSDF Direct Assessment`.
It governs how a reviewer may compare a company SSDLC document with the selected
NIST SP 800-218 SSDF v1.1 reference slice. It does **not** define NIST
conformance, organization compliance, implementation effectiveness, or product
security.

## 1. Authority and Basis Types

Every task-scoped finding must distinguish the basis for each material statement.

- `nist_normative`: a conclusion directly supported by the selected NIST SSDF task
  and its authoritative source. Only this basis may be described as an SSDF task
  expectation.
- `local_derived_guidance`: a local review question or evidence expectation from
  `references/nist-ssdf/v1.1/tasks.yaml`. It may help evaluate the company
  document, but it must not be presented as text required by NIST.
- `reviewer_inference`: a reviewer recommendation, risk hypothesis, or domain
  observation that is not established by the selected NIST task. It must be
  labeled as non-normative and cannot by itself support a claim of missing SSDF
  conformance.

Examples such as requiring a specific HSM, PGP disclosure channel, CVE workflow,
SBOM format, or forbidding email evidence are `reviewer_inference` unless the
selected reference task explicitly supports that requirement.

## 2. Finding Types

### `task_finding`

A finding scoped to exactly one selected SSDF task.

Required fields:

- `finding_id`
- `finding_type: task_finding`
- `task_id`
- `company_source_ref`
- `company_statement`
- `coverage_verdict`
- `basis`
- `assessment_rationale`
- `identified_evidence`
- `evidence_strength`
- `review_queue_recommendation`
- `cannot_claim`

### `non_normative_observation`

A useful observation that cannot be cleanly attributed to one selected SSDF task.
It must not use an SSDF task ID as if NIST directly established the observation.

Required fields:

- `finding_id`
- `finding_type: non_normative_observation`
- `company_source_ref`
- `observation`
- `basis: reviewer_inference`
- `review_queue_recommendation`
- `cannot_claim`

S0 does not allow composite references such as `PO.1 / RV.1` to make a
cross-cutting observation appear normative.

## 3. Coverage Verdict

Coverage verdict describes **document coverage of the selected task**, not
control effectiveness and not organizational compliance.

Allowed values:

- `COVERED`: the document clearly defines the selected task expectation at policy
  or procedure level. This still does not prove implementation.
- `PARTIAL`: the document addresses the task but leaves material ambiguity,
  optionality, missing ownership, missing criteria, or another task-relevant gap.
- `MISSING`: no relevant policy/procedure coverage for the selected task was found
  in the reviewed source.
- `NOT_APPLICABLE`: the reviewed source explicitly establishes non-applicability
  with a reason. Reviewer silence is not sufficient.
- `UNRESOLVED`: the source is insufficient or ambiguous enough that document
  coverage cannot be determined without additional material or human review.

`evidence_strength` is independent of `coverage_verdict`. A policy may have
`COVERED` document coverage while implementation evidence remains `weak`.

## 4. Evidence Strength

Reuse the existing Evidence Index vocabulary without modification:

- `strong`
- `medium`
- `weak`

For S0, a policy statement by itself is normally `weak` evidence of
implementation. This label does not mean the policy text is invalid; it means the
policy statement alone is not direct evidence that the practice was executed.

## 5. Review Queue Recommendation

Reuse the existing Review Queue status vocabulary exactly:

- `pending`
- `needs_changes`
- `accepted`
- `accepted_with_review_due`
- `deferred`
- `rejected`

Assessment verdicts and Review Queue statuses are separate dimensions. Do not add
`needs_review`, `partial`, or other assessment vocabulary to Review Queue output.

## 6. Minimum Basis Record

Each `task_finding` must include at least one basis record:

```yaml
basis:
  - type: nist_normative
    task_id: PW.1.1
    source: NIST_SP_800_218_v1.1
    rationale: "Why the selected company statement is covered by this task."
```

When local guidance or reviewer inference is used, add it separately:

```yaml
  - type: local_derived_guidance
    rationale: "Local question used to expose ambiguity in the policy."
  - type: reviewer_inference
    rationale: "Optional recommendation; not a NIST requirement."
```

A reviewer inference must never be rewritten as `NIST requires ...`.

## 7. Cannot-Claim Boundary

S0 findings must not claim or imply any of the following from document mapping
alone:

- NIST SSDF compliance or conformance
- organization-wide SSDLC effectiveness
- product security or production safety
- remediation completion
- vulnerability closure
- control effectiveness
- audit readiness
- full evidence completeness
- a percentage of SSDF or policy coverage without a predefined denominator and
  evaluation method

S0 therefore does not permit statements such as `this review found 80% of the
policy's critical gaps` or `the organization is 70% SSDF compliant`.

## 8. Source-Bounded Rationale Rules

A task finding is valid only when:

1. the company statement or explicit absence is traceable to the reviewed source;
2. the selected NIST task is traceable to the S0 reference slice and authoritative
   NIST source;
3. the rationale explains the gap using the selected task boundary;
4. non-normative recommendations are labeled as derived guidance or reviewer
   inference;
5. the finding ends with an explicit claim boundary.

If a useful concern cannot satisfy these conditions, record it as
`non_normative_observation` or leave it for a later domain-profile experiment.

## 9. S0 Stop Conditions

Do not expand the reference set, add another framework, or add a domain profile
merely because a reviewer can imagine additional good practices.

Stop and document the limitation when:

- a high-value finding depends mainly on domain assumptions not supported by the
  selected SSDF task;
- repeated findings require a second framework to disambiguate the same control;
- the reviewer cannot distinguish document coverage from implementation evidence;
- useful output requires changing existing core Evidence/Review Queue vocabulary.

Those are experiment results, not automatic authorization to expand scope.
