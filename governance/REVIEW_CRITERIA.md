---
audience: agent-on-demand
authority: reference
can_override: false
overridden_by: AGENT.md
default_load: on-demand
---

# REVIEW_CRITERIA.md

**Code Review and Audit Protocol - v1.2**

> **Version**: 1.2 | **Priority**: 3 (audit protocol)
>
> Defines how to audit, critique, and verify code changes.
> Load this document when `SCOPE = review`.

---

## 0. Activation

This document applies when `SCOPE = review`.

When active:

- keep a governance-first posture;
- act as a skeptical verifier, not an implementer;
- bind every finding to evidence, not intuition.

Before issuing findings, inspect the applicable prior-review surfaces for open
or unresolved items that may overlap the current review scope. At minimum, check
`memory/04_review_log.md` and `memory/03_knowledge_base.md` when they exist.
If this check is not possible, state that explicitly in the review inputs.

---

## 1. Review Philosophy

The purpose of review is to verify that the change is:

- predictable;
- safe;
- reviewable under governance.

Do not assume a small diff is safe.
Do not approve without naming the supporting evidence.

---

## 2. Verdict Model

| Verdict | Meaning | Use when |
|---|---|---|
| `APPROVED` | Safe enough to accept | No blocking governance or correctness issue remains |
| `CHANGES_REQUESTED` | Must be fixed | A clear blocking issue exists |
| `ESCALATED` | Requires human decision | Material risk or trade-off ambiguity remains after review |

A verdict is evidence-bound. `APPROVED` requires named evidence that no blocking
finding remains in the reviewed scope. If the review depends on missing
evidence, unresolved prior findings, or unreviewed dirty work, do not present
the verdict as clean approval; use `CHANGES_REQUESTED`, `ESCALATED`, or an
explicit `WARNING` as appropriate.

### 2.1 Finding Levels

| Level | Meaning |
|---|---|
| `BLOCKING` | A governance, correctness, or safety issue that must be fixed |
| `WARNING` | A risk, debt item, or weak evidence point that must be explicit |
| `SUGGESTION` | A non-blocking improvement |

Do not confuse `ESCALATED` with `BLOCKING`.
Escalation is for unresolved consequential ambiguity, not merely for defects.

---

## 3. Mandatory Audit Checklist

### 3.1 Boundary and Architecture

Check:

- whether domain code touches forbidden I/O, UI, OS, or native concerns;
- whether external or native model input uses an appropriate ACL boundary;
- whether the change conflicts with an ADR or boundary rule.

### 3.2 Physical and Native Safety

If native interop is involved, check:

- whether memory ownership is explicit;
- whether ABI layout is explicit when needed;
- whether panic / fail-fast and recoverable error handling are consistent.

If native interop is not involved, mark this section `N/A`.

### 3.3 Quality and Verification

Check:

- whether evidence matches task risk;
- whether failure paths were considered when applicable;
- whether validation locks observable behavior, not implementation trivia;
- whether legacy refactor work first verified baseline buildability.

### 3.4 Thread Safety and Async Safety

If UI or async paths are involved, check:

- whether UI-affecting updates stay on the correct thread;
- whether async failure paths are handled.

If this is not relevant, mark this section `N/A`.

### 3.5 Dirty Worktree and Scope Hygiene

If the worktree is dirty during implementation or review, check:

- whether unrelated dirty files were kept out of scope;
- whether touched-file overlap was handled or explicitly escalated;
- whether the commit and review boundary remains understandable.

---

## 4. Knowledge Base Cross-Check

Before issuing a verdict, check `memory/03_knowledge_base.md` for:

1. anti-pattern matches;
2. recorded regression patterns.

If a known anti-pattern reappears, call it out explicitly.

---

## 5. Legacy Refactor Review Addendum

For legacy repos, refactors, rollbacks, or baseline resets, also check:

- whether the claimed baseline was verified through the authoritative build path;
- whether the canonical toolchain was identified;
- whether the change is being presented as a safe refactor while the baseline is unstable.

If the baseline was not verified:

- do not call the result a clean refactor;
- include at least one `WARNING`;
- escalate when the conclusion depends on baseline stability.

---

## 6. Review Output Format

Every review response should include:

```markdown
### Review Inputs Checked
- governance/REVIEW_CRITERIA.md
- <list any additional documents read per REVIEW_CRITERIA.md conditions>

### [Decision Summary]
**Verdict**: APPROVED | CHANGES_REQUESTED | ESCALATED
**Risk Level**: Low | Medium | High

### Governance Audit
- Architecture: ...
- Native Safety: ... | N/A
- Test Integrity: ...
- Thread Safety: ... | N/A
- Baseline Status: Stable | Unverified | Unstable | N/A

### Technical Findings
1. [BLOCKING|WARNING|SUGGESTION] Title
   - Location: `path:line`
   - Evidence: ...
   - Rule Reference: ...
   - Fix Required / Reasoning: ...

### Knowledge Base Alignment
- Anti-patterns checked: N
- Regression notes checked: N
- Result: Pass | Conflict Found
```

Every non-trivial finding must include:

- location;
- evidence;
- rule reference.

Open findings must also include:

- status: `open` | `resolved` | `carried-forward` | `not-reproduced`;
- disposition: what was fixed, what remains, or why it is being carried forward.

The review output must separate findings resolved in the reviewed diff from
findings that remain open or are carried forward to a later slice. Do not hide
carried-forward findings inside a passing summary.

---

## 7. Post-Review Memory Actions

After issuing a verdict:

1. append the full review record to `memory/04_review_log.md`;
2. add a one-line summary to `memory/01_active_task.md`;
3. if a new anti-pattern was found, record it in `memory/03_knowledge_base.md`.

Keep `memory/01_active_task.md` concise. Do not dump full findings into it.

---

## 8. C++ Build Boundary Addendum

Apply this addendum whenever review touches C++ project files, header layout, or build configuration.

Hard checks:

- `AdditionalIncludeDirectories` or equivalent settings must not point to a peer project's private tree;
- cross-project private headers must not be justified merely because the build passes;
- shared headers must live in a shared boundary layer with clear ownership.

This is a boundary issue, not a style issue.

---

## 9. Final Principle

> A review that cannot name its evidence is not a valid review.
> Use escalation for conclusions that depend on ambiguity; use blocking findings for concrete violations.
