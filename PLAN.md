# PLAN.md
<!-- governance-baseline: overridable -->
<!-- baseline_version: 1.0.0 -->

> **最後更新**: 2026-09-17
> **Owner**: TODO
> **Freshness**: Sprint (7d)

---

## Current Phase

<!-- Required: fill in current phase ID and description -->

- [x] Phase A: Initial AI Governance adoption and SSDLC documentation scaffold
- [x] Phase B: Add example packs for file upload, dependency upgrade, and incident follow-up
- [x] Phase C: Expand schema-aware validation and reviewer-ready reporting
- [x] Phase D: Harden Security Decision claim-boundary and control-mapping validation
- [ ] Phase S0: NIST SSDF Direct Assessment (S0-A Contract, S0-B Golden, S0-C Linter, S0-D Semantic Eval - local verified, pending PR remote CI)

## Active Sprint

<!-- Required: list current sprint tasks -->

- [x] S0-A: Assessment Contract definition and source-type bounding.
- [x] S0-B: Hand-crafted Golden Fixture for 7 NIST SSDF tasks.
- [x] S0-C: Deterministic assessment YAML linter and CI wiring.
- [ ] S0-D: AI Semantic Evaluation (S0-D-r1 blind run verified locally with 20 atoms; pending PR remote CI).

- [x] Adopt AI Governance baseline with a framework checkout.
- [x] Create SSDLC Decision + Evidence + Review Queue skeleton.
- [x] Add lightweight validators for evidence index, review queue, security decision, and due reviews.
- [x] Add CI wiring for SSDLC validators.
- [x] Add dependency-upgrade and production-incident example packs.
- [x] Make Evidence Index and Review Queue validation schema-driven with executable pass/fail fixtures.
- [x] Generate deterministic reviewer reports with aggregation-only, no-inferred-join claim boundaries.
- [x] Make Security Decision validation schema-aware and fail closed on claim-boundary, control-mapping, and canonical-date violations.

## Backlog

<!-- Required: prioritized items not yet started -->

- P2: Apply a shared strict date parser to due-review generation.
- P2: Add a status-only Review Receipt schema and validator.

## Decision Log

<!-- Optional but recommended: record architecture or governance decisions with dates -->

<!-- Example:
- 2026-03-21: Chose X over Y because Z
-->
- 2026-07-09: Start with Decision + Evidence + Review Queue instead of a heavy compliance platform.
- 2026-07-09: Treat AI summaries as secondary evidence and preserve claim ceilings by default.
- 2026-07-16: Keep dependency and incident examples synthetic, metadata-only, and bounded by explicit cannot-claim statements.
- 2026-07-17: Treat YAML schemas as executable validator inputs and require CLI-level positive and negative fixtures.
- 2026-07-17: Keep reviewer reports aggregation-only; `source_ref` is opaque metadata and cannot establish queue-to-evidence joins or closure.
- 2026-07-17: Treat Control Mapping evidence as an opaque reference and reject unsupported claims outside the `Cannot Claim` boundary without inferring evidence joins.
- 2026-09-17: Phase S0-D-r1 blind rerun with isolated subagent verified direct assessment capability without golden contamination using 20 Golden Gap Atoms; attribution defect in RV.1.3 resolved by separating reviewer inference; pending PR remote CI.

## Known Risks

<!-- Optional: track identified risks and mitigation status -->
- AI-generated documentation may overclaim remediation or compliance unless validators and reviewer guide keep `Cannot Claim` boundaries visible.
- Evidence links can go stale; `review_due` must stay first-class for accepted risk and weak evidence.
