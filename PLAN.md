# PLAN.md
<!-- governance-baseline: overridable -->
<!-- baseline_version: 1.0.0 -->

> **最後更新**: 2026-07-17
> **Owner**: TODO
> **Freshness**: Sprint (7d)

---

## Current Phase

<!-- Required: fill in current phase ID and description -->

- [x] Phase A: Initial AI Governance adoption and SSDLC documentation scaffold
- [x] Phase B: Add example packs for file upload, dependency upgrade, and incident follow-up
- [x] Phase C: Expand schema-aware validation and reviewer-ready reporting

## Active Sprint

<!-- Required: list current sprint tasks -->

- [x] Adopt AI Governance baseline with a framework checkout.
- [x] Create SSDLC Decision + Evidence + Review Queue skeleton.
- [x] Add lightweight validators for evidence index, review queue, security decision, and due reviews.
- [x] Add CI wiring for SSDLC validators.
- [x] Add dependency-upgrade and production-incident example packs.
- [x] Make Evidence Index and Review Queue validation schema-driven with executable pass/fail fixtures.
- [x] Generate deterministic reviewer reports with aggregation-only, no-inferred-join claim boundaries.

## Backlog

<!-- Required: prioritized items not yet started -->

- None. Next phase not yet selected.

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

## Known Risks

<!-- Optional: track identified risks and mitigation status -->
- AI-generated documentation may overclaim remediation or compliance unless validators and reviewer guide keep `Cannot Claim` boundaries visible.
- Evidence links can go stale; `review_due` must stay first-class for accepted risk and weak evidence.
