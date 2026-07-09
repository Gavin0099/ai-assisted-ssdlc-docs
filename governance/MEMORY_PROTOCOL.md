---
audience: agent-runtime
authority: canonical
can_override: false
overridden_by: AGENT.md
default_load: on-demand
---

# Memory Protocol

Status: extracted from AGENTS.md
Semantic change: no
Runtime behavior change: no
Enforcement change: no

## Purpose

This protocol defines repo-local memory authority, canonical memory writing,
post-push memory, PLAN sync, and memory interpretation rules.

## Memory Surfaces

You wake up fresh each session. These files are continuity:
- Daily notes: `memory/YYYY-MM-DD.md` (create `memory/` if needed).
- Long-term memory: `memory/00_long_term.md`.

Capture decisions, durable context, and lessons. Skip secrets unless the user
explicitly asks to keep them.

## Cross-Agent Memory Channel

- Shared memory for all agents in this workspace must live under this repo's
  `memory/` directory.
- `memory/00_long_term.md` is the canonical long-term cross-agent memory file
  for main sessions.
- External/private tool memory paths are not cross-agent authority and must not
  be cited as repo governance state.
- If important context exists only in an external/private memory file, copy a
  distilled version into `memory/YYYY-MM-DD.md` and/or `memory/00_long_term.md`
  before using it for repo decisions.

## Long-Term Memory

- Load `memory/00_long_term.md` only in main sessions with the user.
- Do not load it in shared contexts.
- It can contain personal context and must not leak to strangers.
- In main sessions, it may be read, edited, and updated when durable context
  should persist.

## Write It Down

- Memory does not survive as "mental notes"; durable context must be written.
- In a governed repository, an ambiguous request to "record this in memory" or
  "remember this" defaults to the repository's canonical memory workflow when
  the content concerns that repository's task state, decisions, evidence,
  closeout, or durable governance knowledge.
- If the content is a personal preference, reminder, cross-repo habit, or
  private-cache pointer, classify that route explicitly before writing. Do not
  treat private/tool memory as governance authority.
- When repository memory is the correct route, update `memory/YYYY-MM-DD.md` or
  the relevant repo memory file through the canonical writer.
- Canonical recording establishes valid provenance and placement for the
  declared claim class. It does not establish truth, human review, acceptance,
  commit, push, or normative authority by itself.
- When a durable lesson is learned, update the appropriate governance doc,
  tool doc, or skill.
- When a mistake is found, document it so future sessions do not repeat it.

## Canonical Memory Writer Rule

Any entry claiming `memory_type: session-derived` must be written via
`governance_tools.memory_record`, not by direct markdown append.

Canonical path:

```powershell
python -m governance_tools.memory_record `
  --what-changed "..." `
  --commit <git-sha> `
  --session-id <session-id> `
  --test-evidence "..." `
  --next-step "..." `
  --project-root .
```

All new session-derived memory entries must use the canonical writer CLI.
Direct markdown append in `- what changed:` or `- what_changed:` format is
prohibited for new entries.

The guard flags direct-format entries in files dated `>= 2026-05-01` as
`old_format_entry_after_canonical_writer_cutoff`.

Violation code: `non_canonical_writer` warning in `memory_authority_guard`.
Historical violations before the cutoff are not to be backfilled unless a
separate scoped cleanup is approved.

## Memory Workflow Dispatch Rule

Repo memory tasks are governed operations, not normal markdown edits.

Before claiming completion for any task that edits `memory/**`, the agent must
run the memory workflow dispatcher:

```powershell
python -m governance_tools.memory_workflow --check --repo .
```

If the repo consumes this framework through a submodule, run the dispatcher from
that submodule path:

```powershell
python ai-governance-framework/governance_tools/memory_workflow.py --check
```

The dispatcher reports whether canonical writer and memory authority guard
requirements apply. If `memory/**` files are changed and the dispatcher was not
run, the agent must not claim memory completion.

If the authority guard was not run after memory changes, report memory status as
not verified. Historical `missing_canonical_memory` continuity gaps are warning
evidence, not clean-completion evidence.

When validating a memory completion claim, run:

```powershell
python -m governance_tools.memory_workflow --check --repo . --run-guard
```

`missing_canonical_memory` and legacy `unbound_memory` are warning evidence.
`active_non_canonical_writer` is reported as a blocker candidate for the current
memory completion claim. This dispatcher is report-only unless a later
selective-blocking phase explicitly changes enforcement.

Selective blocking is opt-in:

```powershell
python -m governance_tools.memory_workflow --check --repo . --run-guard --fail-on-blocker
```

With `--fail-on-blocker`, the dispatcher exits non-zero only for current
completion blocker candidates, such as `active_non_canonical_writer` or a
`memory/**` diff checked without the required authority guard. Historical debt
such as `missing_canonical_memory` remains warning evidence.

The managed `pre-commit` hook may surface this dispatcher as an advisory when
`memory/**` changes are present. That hook advisory does not enable selective
blocking; use `--fail-on-blocker` explicitly when a scoped memory completion
gate is required.

Session closeout records the dispatcher status as advisory evidence. The
session-end hook exposes a `memory_workflow` surface, and closeout receipt schema
`1.2` persists the dispatcher status, task classification, warning codes,
blocker codes, guard summary, and memory completion claim allowance. Receipt
presence is evidence that the workflow status was observed; it is not, by
itself, proof that memory completion was allowed.

## Post-Push Memory Protocol

- After every push in a main session, append one short entry to
  `memory/YYYY-MM-DD.md`.
- Use the canonical writer CLI for all new entries.
- If the push introduced a durable workflow preference, also update
  `memory/00_long_term.md`.
- This protocol is portable to other repos with a local `memory/` directory.

## Memory State Trace Consistency

Memory entries must not mix completed and pending state.

`next_step` must describe the next unfinished action, not repeat an action
already recorded as completed in the same memory entry.

If a `commit` or `commit_hash` is recorded, commit state for that scope must be
treated as completed unless the entry explicitly marks the commit as failed,
local-only, or not pushed.

If push status is unknown, write `verify remote push state` instead of
`commit and push`.

If push is confirmed, `next_step` must name the next unfinished slice rather
than repeat commit or push for the completed scope.

When correcting ambiguous historical memory state, prefer adding a new
canonical corrective memory entry over rewriting historical entries.

## Memory State Interpretation Rule

Memory entries are state evidence of prior work, not authorization for current
action.

A retrieved `memory.next_step` is a candidate continuation signal only. It does
not grant permission to modify files, commit, push, close issues, upgrade
claims, or bypass current workspace checks.

Current user instruction, current workspace state, dirty-tree status, and
applicable governance rules always supersede memory content. Before acting on
any memory-derived next step, revalidate the current repo state and authority
boundary.

## PLAN Sync Protocol

- `PLAN.md` is mandatory governance state, not optional project notes.
- After each phase completion or milestone transition:
  1. update `PLAN.md` phase status or next milestone;
  2. update memory files;
  3. commit and push.
- `PLAN.md` drift is treated as governance drift.

## Definition Of Done

A change is done when:
1. session done-condition is met;
2. changes are committed and pushed;
3. one canonical memory entry is appended to `memory/YYYY-MM-DD.md`.

`PLAN.md` sync and structured memory refresh are required when a phase or
milestone transition happened.

## Cross-Agent Closeout Rule

- Framework repo (`ai-governance-framework`): strict mode. Session/workspace
  constraints live in root `AGENTS.md`; final report envelope details live in
  `governance/RESPONSE_ENVELOPE_CONTRACT.md`; executable closeout entrypoints
  are listed below.
- Consuming repos: minimal mode by default (`done-condition met -> commit/push
  -> one memory entry`).
- Strict closeout is opt-in for consuming repos.

Canonical tools:

```powershell
python -m governance_tools.session_closeout_entry --project-root .
python -m governance_tools.manage_agent_closeout
```

## Non-Claims

This file does not change:
- memory writer schema
- runtime hooks
- validators
- enforcement level
- #17 Copilot memory-authority advisory threshold or any blocking threshold
- historical violation disposition
