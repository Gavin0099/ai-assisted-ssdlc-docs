# PLAN.md
<!-- governance-baseline: overridable -->
<!-- baseline_version: 1.0.0 -->

> **最後更新**: 2026-10-03
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
- [x] Phase S1: Real Repo Document Coverage Assessment Pilot (Target Manifest, Corpus Resolver, Multi-file SSDF Assessment, Read-Only Review Engine — delivered and formally closed at 79e33ae)
- [ ] Phase S2: Implementation Evidence Verification Pilot (S2-A Spec Freeze -> S2-B Static Evidence Engine -> S2-C Orchestrator & Golden E2E)

## Active Sprint

<!-- Required: list current sprint tasks -->

- [x] S2-A: Implementation Evidence Verification Specification & Acceptance Criteria (FROZEN at dece98a).
- [ ] S2-B: Implementation Contracts, Manifest, Corpus Resolver, Matchers & Evaluator Core. Candidate WIP is isolated; delivery follows [B0–P1 slice plan](docs/specs/s2-b-slice-plan.md).
- [x] S2-B0 local audit: frozen S2-A versus immutable candidate 663caca; 65 tests run/64 pass/one Windows skip, with independent probes showing numeric resolver, admission integrity and item invariant defects. The 12 selected candidate blobs are durably archived with fingerprints and replayed on public baseline a5a3216; this remediates Codex P2 source availability without a production port. PR review/CI/conditional merge remain delivery gates; B1 starts after B0 merge. Real P1 requires user-supplied product baseline and human-authored rules.
- [x] S2-B1 local core: five closed typed matchers, frozen YAML Path/RFC 6901 and sanitized results; YAML Core numeric/tag handling replaces wrong WIP oracles. New regression rejects the old archived matcher (19 failed subcases/one key-collision error). PR #22 review identified timestamp key canonicalization, shared-alias traversal, deep JSON validation and source-bearing YAML traceback defects. Four regressions reject reviewed d977ba3 (five failed subcases/one error); a second Codex pass identified non-Core explicit tags and escaped YAML surrogate scalars. Two more regressions reject 45636f5 (eight failed subcases). All 34 matcher tests pass after restricting tags to Core plus the frozen timestamp rule and validating Unicode scalar keys/values. Timestamp key equality preserves UTC and full fraction precision, aliases are visited once, JSON validation uses an explicit stack and parser errors suppress source-bearing chains. No policy admission/product repo/evaluator/CLI/schema; latest independent/Codex review and CI are separate PR gates.
- [x] B1 scalar-alias review remediation: the Unicode scan now memoizes successfully checked immutable strings, avoiding repeated full-string work for shared aliases. Independent iteration-count regression rejects 394ae39 and all 35 focused tests pass after the fix. Prior full Windows suite is 353 run/350 pass/3 skips; latest-head full coverage belongs to CI. Latest-head reviews and merge remain pending.
- [x] B1 decimal-integer review remediation: local chunked conversion accepts valid large JSON and YAML decimal integers without changing the process digit limit. Arithmetic-oracle fixtures reject 47e3462 with five errors and all 37 focused tests pass after the fix. Latest-head independent/Codex review, full CI and merge remain pending.
- [x] B1 decimal-conversion performance remediation: replace growing-prefix multiplication with balanced splitting and cached powers. An operand-balance regression rejects 31c9ebb, and all 38 focused tests pass. A local diagnostic root-existence probe of 800,000 digits passes in 0.3675 seconds (timing is diagnostic, not an acceptance threshold). Latest-head reviews/full CI/merge remain pending.
- [x] B1 collection-key remediation: legal YAML Core sequence/mapping keys now use document-local tagged structural identities, preserving mapping-order independence and alias sharing without making non-string keys navigable. Two independent root/navigation and equality fixtures reject ae32727 (four errors); all 40 focused tests pass. Duplicate, recursive, custom-tagged and surrogate-containing keys still fail closed. Latest-head independent/Codex review and CI remain merge gates.
- [ ] S2-C: Dual Provenance Orchestrator, CLI, Deterministic Projection & E2E Validation.

- [x] REPORT-3B: Minimal Report Data Contract v0.1 accepted/frozen by the user; assessment remains unchanged, D1-D3 use report data and D4 uses separate lifecycle records. Published with REPORT-4A as its reviewed behavior source.
- [x] REPORT-4A: Contract Models + Validation Only. Two Python modules and synthetic C1-C8 fixtures implement strict parsing, pinned ArtifactRef reads, D1-D3 cross-references and deterministic acceptance/sync validation. Complete main-based regression: 247 run, 245 pass and two Windows symlink privilege skips; Linux contract run: 50 run, 49 pass and one Windows-junction skip. Each of the 50 new tests passed on at least one platform. Drift/readiness pass; no YAML schemas, actual sidecars, report migration, Markdown/HTML generation, assessment/queue/S2 changes. Delivery through the user-authorized PR, Codex review and conditional merge; remote review/check/merge evidence remains on that PR.
- [x] REPORT-4C/D/E tooling: Recorded REPORT-3B data projects through validated three-layer Markdown and the shared offline HTML reader; the repository skill routes structured project and legacy render separately. Human prose is finalized before data freeze. Public tests use synthetic inputs; private migration/projection fidelity remains local and ignored. Independent technical review and blind skill execution pass. Initial Windows suite: 311 run/309 pass/two existing skips; Linux: 311 run/310 pass/one Windows-only skip. Codex review remediation preserves legacy versions/P0-P3 and adds three regression tests; Current committed-tree LF and CRLF Windows reruns: each 319 run/316 pass/three platform skips; Linux LF and CRLF: each 319 run/318 pass/one skip. Legacy source binding reads unique labeled current scope and rejects historical/document fingerprints; regression tests and actual old-CLI probes confirm the previous defect. Linux publication now atomically rejects concurrent destinations with renameat2 RENAME_NOREPLACE; the regression reproduces empty-directory replacement on reviewed 733f021. All 28 displayed source hashes verified against Git blobs. Windows template text normalizes universal newlines while raw template hashes remain exact. Current-head review and CI remain the delivery gate. Browser visual/interaction QA remains NOT RUN. Public PR review/check/merge is a separate delivery gate; no assessment/schema/queue/S2 changes or company-input publication.
- [x] REPORT-4A Codex review remediation: Review of 465e435 identified one P1 (path-resolution/open race) and two P2 (matching content with explicit not_synced, provenance hex-case normalization). Fixed all three; verified actual opened Windows/Linux file handles before reading, retained independent sync records, normalized only S1 provenance hashes. Added four tests: 54 new contract tests (Windows 52 pass/2 skips, Linux 53 pass/1 skip) and full regression 251 run/249 pass/2 Windows skips. Three focused regression tests detect the old reviewed implementation. Updated-head review/CI/conditional merge evidence belongs to PR #19.

- [x] S0-A: Assessment Contract definition and source-type bounding.
- [x] S0-B: Hand-crafted Golden Fixture for 7 NIST SSDF tasks.
- [x] S0-C: Deterministic assessment YAML linter and CI wiring.
- [x] S0 Review Closure: Resolved 3 P1 linter findings (scoped tasks full 1:1 coverage, nist_normative source baseline match, clause-aware negation scanning; delivered in PR #10).
- [x] S1-A-r2: Target Manifest Schema Authority & Repo Identity Closure (Zero-fallback executable schema validation, source_type syntax binding, and glob semantics layering; delivered in PR #10).
- [x] S1-A Review Closure: Hardened local_git repo URL scheme exclusion and malformed schema fail-closed checks.
- [x] S1-B: Repo Corpus Resolver (Materialize authoritative repository files into an immutable corpus based on Target Manifest include/exclude surface).
- [x] S1-D1: Review Contract & Deterministic Projection Layer (Defined non-collapsible 6 dimensions, deterministic ordering with full tie-breakers, fixed output shape, ReadOnlyReviewRecord domain models, and pure renderer library; 145/145 tests pass).
- [x] S1-D2: CLI Wiring & Reporting Orchestration (Implemented ReviewReportOrchestrator, fail-closed validation orchestration, CLI options with stdout/file artifact outputs; 158/158 tests pass).
- [x] S1-D3: Assessment Comparison & Diffing Engine (Deterministic, evaluative-free comparison between assessment versions; added tools/assessment_diff.py, CLI --diff-baseline flag, 183/183 tests pass).
- [x] S1-D4: Review Queue Action Projection (Project assessment recommendations into deterministic read-only reviewer action view; added tools/review_queue_projection.py, CLI --project-queue flag, 197/197 tests pass).
- [x] S1-D4 Review Closure: Projected non-normative observations as distinct action items without forging task fields, enforced fail-closed on unmapped recommendation statuses, preserved multiline claim boundaries within IMPORTANT blocks, and maintained priority orthogonality strictly derived from review_queue_recommendation independent of coverage_verdict.

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
- 2026-09-18: Phase S1-D Review Engine & Projection Complete: Delivered S1-D1 (Deterministic Read-Only Projection & Domain Contract), S1-D2 (Safe Orchestration CLI with format/output controls), S1-D3 (Objective Sentiment-Free Diffing with Cross-Commit Provenance Verification), and S1-D4 (Read-Only Review Queue Action Projection preserving human-authority boundaries).
- 2026-09-18: Phase S1-D4 Review Closure: Projected non-normative observations as distinct action items (source_kind="non_normative_observation") without forging task fields, enforced fail-closed on unmapped recommendation statuses (raising ReviewQueueProjectionError / CLI Exit 1), preserved multiline claim boundary lines within IMPORTANT admonition blocks, and reinforced priority orthogonality strictly mapped from review_queue_recommendation independent of coverage_verdict.
- 2026-09-18: Phase S1 formally closed at main 79e33ae. Delivered fixed Target Manifest scope, deterministic repository corpus materialization, source-bound multi-file assessment contracts, fail-closed provenance validation, deterministic read-only reviewer reporting, cross-commit assessment diffing, and read-only review queue action projection. S1 does not claim exact quote/span provenance, automated end-to-end semantic assessment execution, NIST SSDF conformance, organizational compliance, implementation effectiveness, or product security.

## Known Risks

- 2026-10-02: REPORT-4A admission validates structure, version relationships and declared records. It does not prove semantic assessment correctness, Git/quote-span provenance, human identity/authority, actual product execution or real report acceptance/sync. Main's pre-existing governance version/hook warnings are outside this PR; readiness passes without a framework update claim.

<!-- Optional: track identified risks and mitigation status -->
- AI-generated documentation may overclaim remediation or compliance unless validators and reviewer guide keep `Cannot Claim` boundaries visible.
- Evidence links can go stale; `review_due` must stay first-class for accepted risk and weak evidence.
