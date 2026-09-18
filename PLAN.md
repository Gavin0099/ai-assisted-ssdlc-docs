# PLAN.md
<!-- governance-baseline: overridable -->
<!-- baseline_version: 1.0.0 -->

> **最後更新**: 2026-09-18
> **Owner**: TODO
> **Freshness**: Sprint (7d)

---

## Current Phase

<!-- Required: fill in current phase ID and description -->

- [x] Phase A: Initial AI Governance adoption and SSDLC documentation scaffold
- [x] Phase B: Add example packs for file upload, dependency upgrade, and incident follow-up
- [x] Phase C: Expand schema-aware validation and reviewer-ready reporting
- [x] Phase D: Harden Security Decision claim-boundary and control-mapping validation
- [x] Phase S0: NIST SSDF Direct Assessment (S0-A Contract, S0-B Golden, S0-C Linter, S0-D Blind Eval - PR #10 merged to main; delivery complete)
- [ ] Phase S1: Real Repo Document Coverage Assessment Pilot (Target Manifest, Corpus Resolver, Multi-file SSDF Assessment, Read-Only Review Engine)

## Active Sprint

<!-- Required: list current sprint tasks -->

- [x] S0-A: Assessment Contract definition and source-type bounding.
- [x] S0-B: Hand-crafted Golden Fixture for 7 NIST SSDF tasks.
- [x] S0-C: Deterministic assessment YAML linter and CI wiring.
- [x] S0 Review Closure: Resolved 3 P1 linter findings (scoped tasks full 1:1 coverage, nist_normative source baseline match, clause-aware negation scanning; delivered in PR #10).
- [x] S1-A-r2: Target Manifest Schema Authority & Repo Identity Closure (Zero-fallback executable schema validation, source_type syntax binding, and glob semantics layering; delivered in PR #10).
- [x] S1-A Review Closure: Hardened local_git repo URL scheme exclusion and malformed schema fail-closed checks.
- [x] S1-B: Repo Corpus Resolver (Materialize authoritative repository files into an immutable corpus based on Target Manifest include/exclude surface).
- [x] S1-D1: Review Contract & Deterministic Projection Layer (Defined non-collapsible 6 dimensions, deterministic ordering with full tie-breakers, fixed output shape, ReadOnlyReviewRecord domain models, and pure renderer library; 145/145 tests pass).
- [x] S1-D2: CLI Wiring & Reporting Orchestration (Implemented ReviewReportOrchestrator, fail-closed validation orchestration, CLI options with stdout/file artifact outputs; 158/158 tests pass).
- [x] S1-D3: Assessment Comparison & Diffing Engine (Deterministic, evaluative-free comparison between assessment versions; added tools/assessment_diff.py, CLI --diff-baseline flag, 172/172 tests pass).
- [ ] S1-D4: Review Queue Action Projection (Project assessment recommendations into reviewer action view).

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

- P1: Phase S1 - Real Repo Document Coverage Assessment Pilot (Target Manifest, Corpus Resolver, Multi-file SSDF Assessment, Read-Only Review Engine).
- P2: Phase S2 - Implementation Evidence Verification Pilot (Product Repo CI / Artifact Evidence vs Company SSDLC Policy).
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
- 2026-09-17: Phase S0 qualified and Remote CI (PR #10, Run 35212697108) verified ssdlc-validators and governance-drift green; delivery pending PR merge to main.
- 2026-09-17: Phase S1-A-r1 Target Manifest Contract Hardening: transformed target-manifest.schema.yaml into executable validator source of truth, added target.source_type (local_git | github), enforced strict string type for baseline.version (prohibiting float 1.1), and established fail-closed glob boundaries (no absolute paths, no '..', normalized '/').
- 2026-09-17: Phase S1-A-r2 Schema Authority & Repo Identity Closure: eliminated all silent Python fallbacks from validator (schema fails closed if rules missing), syntax-bound target.repo to source_type (github strictly owner/repo, local_git strictly local path), and clarified S1-A pattern boundaries vs S1-B materialization obligations.
- 2026-09-17: Phase S1 Architecture Decision: Treat target SSDLC documentation as a Git repository corpus pinned to a fixed commit SHA with explicit Target Manifest (include/exclude authority surface). Decouple Layer 1 (Document Coverage Assessment on policy repo) from Layer 2 (Implementation Evidence Assessment on product repos).
- 2026-09-18: Hardened S0 linter to require full 1:1 coverage of scope_tasks, baseline match for normative sources, and clause-aware negation to prevent boundary bypass; hardened S1-A target manifest schema against URL schemes in local_git and enforced fail-closed regex/type compilation.
- 2026-09-18: Phase S1-B Repo Corpus Resolver Architecture: Implemented zero-working-tree Git materialization via `git ls-tree` and `git cat-file`, enforced Exclude Always Wins, filtered symlinks (`120000`), enforced UTF-8, and established deterministic `corpus_digest` calculation across all authoritative documents.
- [x] S1-B Review Closure: Resolved NUL-delimited git ls-tree parsing (supporting non-ASCII/spaces), enforced github remote origin verification, fail-closed on empty corpus, and rejected binary/NUL/C0 control characters.
- 2026-09-18: Phase S1-C Multi-File Corpus SSDF Assessment Engine & Contract: Extended SSDF assessment to multi-file repository corpora pinned by Target Manifest and Corpus Snapshot (`corpus_digest`). Enforced exact source file tracking requiring `company_source_ref` paths to strictly exist within the materialized corpus snapshot, and expanded SSDF linter to validate `repository_corpus` provenance envelope while preserving all claim ceiling boundaries.

## Known Risks

<!-- Optional: track identified risks and mitigation status -->
- AI-generated documentation may overclaim remediation or compliance unless validators and reviewer guide keep `Cannot Claim` boundaries visible.
- Evidence links can go stale; `review_due` must stay first-class for accepted risk and weak evidence.
