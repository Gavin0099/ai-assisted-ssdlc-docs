# Governance Authority Table

> machine-readable: true
> version: 1.0.0
> updated: 2026-07-03


> Authority-loader note: `runtime_hooks/core/session_start.py` derives the live
> authority filter from each `governance/*.md` file's frontmatter through
> `governance_tools.authority_loader`. This table is the human-facing registry
> and must mirror that frontmatter; table-only edits do not change live
> `allowed_governance_files` behavior.

## Authority Levels

- `canonical`：最高權威來源。若與其他來源衝突，以它為準；其他只能是 derived 或補充層。
- `reference`：輔助性權威來源。可提供解釋與判準，但不能覆蓋 canonical。
- `derived`：由 canonical / reference 推導出的工作性輸出，可快取、摘要、投影，但不能反向覆蓋上游真相。

## Audience Types

- `agent-runtime`：在 `session_start` 或等效 runtime path 中會被直接讀入
- `agent-on-demand`：只在特定情境、特定 task 類型下按需讀入
- `human-only`：提供給人類 reviewer / operator 參考，不屬於 agent 預設 runtime 載入面

## Default Load Modes

- `always`：每次 session 都應載入；通常只給 canonical / derived 的 agent-runtime surface
- `on-demand`：只有當 context 需要時才讀
- `incremental`：只增量讀取最近候選，不做 full rescan
- `never`：agent 不自動載入；通常對應 human-only 文件

---

## Authority Table

| document | audience | authority | can_override | overridden_by | default_load |
|----------|----------|-----------|--------------|---------------|--------------|
| `governance/SYSTEM_PROMPT.md` | agent-runtime | canonical | false | ~ | always |
| `governance/AGENT.md` | agent-runtime | canonical | false | ~ | always |
| `governance/RULE_REGISTRY.md` | agent-runtime | canonical | false | ~ | always |
| `governance/PLAN.md` | agent-on-demand | reference | false | ../PLAN.md | on-demand |
| `governance/MEMORY_PROTOCOL.md` | agent-runtime | canonical | false | AGENT.md | on-demand |
| `governance/AI_GOVERNANCE_UPDATE_PROTOCOL.md` | agent-on-demand | reference | false | AGENT.md | on-demand |
| `governance/F7_FULL_UPDATE.md` | agent-on-demand | reference | false | AGENT.md | on-demand |
| `governance/ARCHITECTURE.md` | agent-on-demand | reference | false | SYSTEM_PROMPT.md | on-demand |
| `governance/TESTING.md` | agent-on-demand | reference | false | AGENT.md | on-demand |
| `governance/NATIVE-INTEROP.md` | agent-on-demand | reference | false | AGENT.md | on-demand |
| `governance/RESPONSE_ENVELOPE_CONTRACT.md` | agent-runtime | reference | false | AGENT.md | on-demand |
| `governance/HUMAN-OVERSIGHT.md` | human-only | reference | false | ~ | never |
| `governance/REVIEW_CRITERIA.md` | agent-on-demand | reference | false | AGENT.md | on-demand |
| `governance/PHASE_D_CLOSE_AUTHORITY.md` | human-only | canonical | false | ~ | never |
| `AGENTS.md` (workspace) | agent-runtime | derived | false | AGENT.md | always |
| `.github/copilot-instructions.md` | agent-runtime | derived | false | AGENT.md | always |
| `.github/agents/*.agent.md` | agent-on-demand | derived | false | AGENT.md | on-demand |
| `domain contract (full)` | agent-on-demand | canonical | false | ~ | on-demand |
| `domain adapter summary` | agent-runtime | derived | false | domain contract | always |
| `docs/e1-mutation-catalog.md` | agent-on-demand | reference | false | PLAN.md | on-demand |
| `governance_tools.memory_workflow` | agent-runtime | derived | false | MEMORY_PROTOCOL.md | on-demand |
| `memory/01_active_task.md` | agent-runtime | canonical | false | ~ | incremental |
| `memory/02_workflow.md` | agent-runtime | canonical | false | ~ | incremental |
| `memory/03_knowledge_base.md` | agent-runtime | canonical | false | ~ | incremental |
| `memory/04_review_log.md` | agent-runtime | canonical | false | ~ | incremental |
| `memory/reviewer_handoff_*` | agent-on-demand | derived | false | 03_knowledge_base.md | on-demand |
| `memory/framework_artifact_*` | agent-on-demand | derived | false | ~ | on-demand |
| `external repo aliases` | agent-on-demand | reference | false | ~ | on-demand |

---

## Conflict Resolution Rules

衝突處理的基本順序是：

```text
canonical > reference > derived
```

具體規則：

1. `canonical` vs `reference`：以 canonical 為準，reference 只能補充或說明
2. `canonical` vs `derived`：以 canonical 為準，derived 必須被視為可失效投影
3. `reference` vs `derived`：以 reference 為準
4. workspace instruction（如 `AGENTS.md`、`copilot-instructions`）不得覆蓋 repo canonical
5. `agent-on-demand` 載入時，可以引入 reference，但不得改寫 canonical 的主張
6. `derived` 載入時，只能幫助 session_start 或 task context 收斂，不能創造新的 authority
7. Phase D completion claims: `PHASE_D_CLOSE_AUTHORITY.md` takes precedence over README,
   PLAN.md, implementation presence, version tags, commit history, and all generated
   summaries. No agent-produced signal may override this contract.

---

## Memory Source Authority

| memory source | authority | promotion policy |
|---------------|-----------|-----------------|
| `01_active_task.md` | canonical | 可直接 promote |
| `02_workflow.md` | canonical | 可直接 promote |
| `03_knowledge_base.md` | canonical | 可直接 promote |
| `04_review_log.md` | canonical | 可直接 promote |
| reviewer handoff summary | derived | cache only，不得 promote 成 truth |
| framework artifact cache | derived | cache only，不得 promote 成 truth |
| external repo aliases | reference | 可視情況 promote，但仍需對照 canonical |

---


## Registered Governance Surface Notes

| surface | authority role | scope | limitation |
|---------|----------------|-------|------------|
| `governance/MEMORY_PROTOCOL.md` | canonical memory write protocol | governed memory write path, canonical writer usage, memory workflow dispatch, and memory completion claim boundaries | does not itself guarantee structured memory freshness |
| `docs/e1-mutation-catalog.md` | mutation contract catalog / mutation surface inventory | documents mutation-capable surfaces and their allowed claim level | catalog presence is not enforcement by itself |
| `governance_tools.memory_workflow` | implementation surface for governed memory workflow | dispatch, write-path assessment, guard summary, and receipt status reporting | implementation behavior must not exceed documented contract |

---
## Loading Condition Summary

| task_level | always | on-demand | incremental | never |
|------------|--------|-----------|-------------|-------|
| L0 | canonical runtime core | minimal reference only when needed | candidates only | human-only docs |
| L1 | canonical runtime core | boundary / testing / domain reference | candidates only | human-only docs |
| L2 | canonical runtime core | broader reference + contract context | candidates only | human-only docs |
| any | human-only surface 不自動載入 | | | |
