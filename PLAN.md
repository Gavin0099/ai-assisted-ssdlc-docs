# PLAN.md
<!-- governance-baseline: overridable -->
<!-- baseline_version: 1.0.0 -->

> **最後更新**: 2026-07-09
> **Owner**: TODO
> **Freshness**: Sprint (7d)

---

## Current Phase

<!-- Required: fill in current phase ID and description -->

- [x] Phase A: Initial AI Governance adoption and SSDLC documentation scaffold
- [ ] Phase B: Add more example packs for file upload, dependency upgrade, and incident follow-up

## Active Sprint

<!-- Required: list current sprint tasks -->

- [x] Adopt AI Governance baseline with a framework checkout.
- [x] Create SSDLC Decision + Evidence + Review Queue skeleton.
- [x] Add lightweight validators for evidence index, review queue, security decision, and due reviews.
- [ ] Add CI wiring for SSDLC validators.

## Backlog

<!-- Required: prioritized items not yet started -->

- P1: Add examples for `dependency-upgrade` and `production-incident`.
- P1: Expand schema-aware validation beyond the Security Decision Record.
- P2: Add reviewer-ready report generation from queue and evidence files.

## Decision Log

<!-- Optional but recommended: record architecture or governance decisions with dates -->

<!-- Example:
- 2026-03-21: Chose X over Y because Z
-->
- 2026-07-09: Start with Decision + Evidence + Review Queue instead of a heavy compliance platform.
- 2026-07-09: Treat AI summaries as secondary evidence and preserve claim ceilings by default.

## Known Risks

<!-- Optional: track identified risks and mitigation status -->
- AI-generated documentation may overclaim remediation or compliance unless validators and reviewer guide keep `Cannot Claim` boundaries visible.
- Evidence links can go stale; `review_due` must stay first-class for accepted risk and weak evidence.
