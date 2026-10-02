# Review Log

## Entries

- Append review summaries and validation history here.

<!-- memory_record_projection:review-log:63090c6c70bccf7d8b74f95091219b665103846da2d3eebbb2b331593c29bb08 -->
### Canonical memory checkpoint — 2026-10-02-REPORT-4A-DELIVERY

- Writer: `governance_tools.memory_record`
- Record identity: `63090c6c70bccf7d8b74f95091219b665103846da2d3eebbb2b331593c29bb08`
- Commit binding: `2190e2930dbd0c955cbc18e6ecd7ba50974ea110` (bound)
- Record: 使用者明確授權直接開 PR、透過 Codex review 並在無阻擋後合併。從 main 0f33834 建立 codex/report-4a-contract-validation，僅提交兩個 report/lifecycle production modules、兩份合成 tests、frozen REPORT-3B v0.1 與驗證說明。原目錄的 S2 commits、治理更新與其他 dirty 工作保留。3B 只調整未交付歷史資料的連結呈現，D1-D4/C1-C8 未改；PLAN 同步這次 reporting milestone。此紀錄是本地實作與交付準備，不宣稱遠端 review/CI/merge 已完成。
- Validation boundary: PASS: main-based python -X utf8 -m unittest discover -s tests -p test_*.py (247 run,245 pass,2 Windows symlink privilege skips); new contract matrix 50 run (Windows48/Linux49 pass, each distinct test passed on at least one platform). PASS: pinned-framework governance_drift_checker and external_repo_readiness; git diff --check. NOT CLAIMED: Windows native symlink, semantic correctness, provenance, human authority/authenticity, real report migration/acceptance/sync, framework update, remote CI or merge.
- Next action: Push implementation and memory companion, open REPORT-4A PR, request Codex review for the exact current head, resolve blocking findings, verify CI and merge under the user authorization. REPORT-4B/C/D require separate scope.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:3acb23a84093f4b04a1b0fcc3bb96858ad2763874c986954fbfd9ad45f357d6b -->
### Canonical memory checkpoint — 2026-10-02-REPORT-4A-DELIVERY

- Writer: `governance_tools.memory_record`
- Record identity: `3acb23a84093f4b04a1b0fcc3bb96858ad2763874c986954fbfd9ad45f357d6b`
- Commit binding: `2190e2930dbd0c955cbc18e6ecd7ba50974ea110` (bound)
- Record: 補齊 REPORT-4A main-based 完整 regression 的可追溯 test receipt，綁定 implementation commit 2190e29。前次 receipt wrapper 從 governance submodule 目錄呼叫，錯跑框架 tests 並因缺少 tuf 失敗；該失敗 receipt/log 保留為 report-4a-pr-regression-attempt-1。已在 consumer root 正確重跑既有 CI discovery 並通過，未修改或安裝框架依賴，production/tests 不變。這是交付證據補正，尚未宣稱 Codex review 或遠端 merge 完成。
- Validation boundary: PASS: artifacts/reporting/report-4a-pr-regression.json -> exit_code=0; paired log records 247 tests in29.398s,245 pass,2 Windows symlink privilege skips. Pinned-framework drift/readiness exit0; no framework update or adoption-completion claim.
- Next action: Push REPORT-4A implementation and companion, open PR and obtain exact-head Codex review and green CI before user-authorized merge.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:f5f37fe41e4ae154b7eba1558237698810dca7f05c12510f6e2cd2cf34264c73 -->
### Canonical memory checkpoint — 2026-10-02-REPORT-4A-REVIEW-FIX

- Writer: `governance_tools.memory_record`
- Record identity: `f5f37fe41e4ae154b7eba1558237698810dca7f05c12510f6e2cd2cf34264c73`
- Commit binding: `8f0efdff86fb38ed997a593e3449ac028f41b25f` (bound)
- Record: Codex GitHub reviewer chatgpt-codex-connector[bot] 對 PR19 head465e435 提出三項 findings (review5389335144; comments4163751491/1498/1504)。P1 introduced/current-decision impact yes: resolve與read分離可能讀到root外；fix now為開啟後以Windows GetFinalPathNameByHandleW或Linux procfs核對實際handle，在內容讀取前拒絕越界，失敗關閉descriptor。兩P2 introduced/current-decision impact yes:保留內容已相同但有明確not_synced紀錄的情境，並按既有S1 target規則正規化commit/manifest/corpus SHA大小寫，raw ArtifactRef與陣列順序仍不變。四項新tests;原production只有兩個模組、既有assessment/schema/queue/S2不變。後續c379877只調整race regression的觀察patch，讓同一測試能對舊reviewed bytes重播。這是修正及本地驗證，不宣稱新版Codex review已通過。
- Validation boundary: PASS: artifacts/reporting/report-4a-pr-fix-regression.json -> exit_code=0,251 run249 pass2 Windows symlink privilege skips,linked implementation8f0efdf. PASS: artifacts/reporting/report-4a-review-regression-replay.json,three assertion failures on old465e435 prove sensitivity; first replay import/patch error is retained as attempt1 and not counted. Latest contract run54: Windows52/Linux53 pass,each platform only skips inapplicable/privilege cases. NOT CLAIMED: semantic correctness, private data/provenance/authenticity, actual product execution or updated-head remote approval.
- Next action: Push fixes and companion, request Codex re-review for the latest exact PR19 head, verify CI and resolve review threads before conditional merge. No real migration/rendering/S2.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:7916a2fa3a90388c5f4551d0d6a94af5ecd9b516d399e3867071ba382960dfa2 -->
### Canonical memory checkpoint — 2026-10-02-REPORT-4E

- Writer: `governance_tools.memory_record`
- Record identity: `7916a2fa3a90388c5f4551d0d6a94af5ecd9b516d399e3867071ba382960dfa2`
- Commit binding: `99644c3` (bound)
- Record: REPORT-4E public tooling: wired the repository skill to validated structured data, fixed three Markdown layers and shared offline HTML. Kept legacy render and independent lifecycle state. Public tests are synthetic and private-free; no private input migration or publication included.
- Validation boundary: artifacts/reporting/report-4e-validation.json: independent technical review NO_BLOCKING_FINDINGS; Windows 311/309 pass/2 skips, Ubuntu 311/310 pass/1 skip; blind skill project exit 0 with four outputs and preserved draft/not_synced state; skill validator and diff check PASS.
- Next action: Open the authorized public tooling PR, obtain current-head Codex review and green checks, then conditionally merge. Browser visual and interaction QA remains not verified.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:562e37784224243014a8392bdc623ac0a2cd93611cceb3f14b28643507f2cd4b -->
### Canonical memory checkpoint — 2026-10-02-REPORT-4E-Codex-remediation

- Writer: `governance_tools.memory_record`
- Record identity: `562e37784224243014a8392bdc623ac0a2cd93611cceb3f14b28643507f2cd4b`
- Commit binding: `191a5c4db24531184e644a898dba94aa4cb09801` (bound)
- Record: Codex review remediation: preserve different existing legacy HTML, allow exact no-op and atomic no-replace publication, retain P0-P3 priorities. Replace delivery evidence with a pinned committed-tree run; historical precommit filesystem evidence is explicitly separate.
- Validation boundary: artifacts/reporting/report-4e-committed-validation.json: actual committed-tree Windows run 314/312 pass/2 skips; all 28 displayed hashes equal Git blobs; 3 new regression tests detect defects at reviewed 5a973d6 baseline (nonzero replay).
- Next action: Push remediation and obtain updated-head Codex review and CI before conditional engineering merge. UI QA remains not verified.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:23cfaff49e3ff6817eda59a1fb537485029be63059eaccf908549fa60db19ef6 -->
### Canonical memory checkpoint — 2026-10-02-REPORT-4E-final-remediation

- Writer: `governance_tools.memory_record`
- Record identity: `23cfaff49e3ff6817eda59a1fb537485029be63059eaccf908549fa60db19ef6`
- Commit binding: `39b76c6ee2b33c69c5a00fc443003ea7ce984451` (bound)
- Record: Finished REPORT-4E remediation including Windows CRLF template admission. Template text uses universal newlines while raw fingerprints remain exact. Final delivery evidence is pinned to implemented commit 39b76c6; earlier precommit and 191a5c4 executions are explicit historical receipts.
- Validation boundary: artifacts/reporting/report-4e-final-validation.json: actual Windows LF and CRLF each 315/313 pass/2 skips; independent Ubuntu LF and CRLF each 315/314 pass/1 skip. Four regression cases detect old implementation defects; all 28 displayed scope hashes match Git blobs. Independent delta review APPROVED.
- Next action: Obtain latest-head remote Codex review and green CI, then apply the already authorized engineering merge. UI qualification remains not verified.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:caeb4e617d6e1aff1b85f03f687ff9796f30aabd4e7b732365001b558fe93874 -->
### Canonical memory checkpoint — 2026-10-02-REPORT-4E-noreplace-remediation

- Writer: `governance_tools.memory_record`
- Record identity: `caeb4e617d6e1aff1b85f03f687ff9796f30aabd4e7b732365001b558fe93874`
- Commit binding: `e7317205c322a1b201a3a015a278cce673ff2eb0` (bound)
- Record: Closed Linux concurrent-empty-destination replacement with atomic renameat2 RENAME_NOREPLACE and no replacing fallback. Previous receipts remain historical; current evidence binds the implemented e731720 Git blobs.
- Validation boundary: artifacts/reporting/report-4e-noreplace-validation.json: actual Windows LF/CRLF each 316 run/313 pass/3 platform skips; independent native Ubuntu LF/CRLF each 316 run/315 pass/1 skip. Race regression fails on reviewed 733f021 with observed inode replacement and passes fixed code. Two-file independent technical review has no blocking findings; all 28 scope hashes match pinned Git blobs.
- Next action: Push evidence and fix, request latest-head Codex review and require green CI before authorized engineering merge. UI qualification remains not verified.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:da88cf86379e426079e0aaada60d162a97672abb57cddb7afddb3ce757222635 -->
### Canonical memory checkpoint — 2026-10-02-REPORT-4E-provenance-remediation

- Writer: `governance_tools.memory_record`
- Record identity: `da88cf86379e426079e0aaada60d162a97672abb57cddb7afddb3ce757222635`
- Commit binding: `4a3e6e32c6202aa769919f844563ff781a656bc3` (bound)
- Record: Closed legacy provenance attribution from incidental history/file hashes. Only unique labeled current scope binds metadata; missing, duplicate or mismatched fields fail closed. Structured admission/exact-byte authority remains. Current receipt pins implemented 4a3e6e3; prior executions remain historical.
- Validation boundary: artifacts/reporting/report-4e-provenance-validation.json: actual Windows LF/CRLF each 319 run/316 pass/3 platform skips; independent native Ubuntu LF/CRLF each 319 run/318 pass/1 skip. New tests replay against reviewed 5c6eb14 with 9 assertion failures and zero errors; actual old CLI probes confirm wrong source attribution. Three-file independent delta review has no blocking findings. All 28 scope hashes match committed Git blobs.
- Next action: Push remediation, obtain current-head Codex review and green CI, then merge under the already authorized engineering gate. UI qualification remains not verified.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:883d807b1e4e3729c52b334eeb0f9bc37b3194f49d1b82e5763ef0aff9cb0d7b -->
### Canonical memory checkpoint — 2026-10-03-S2-B0

- Writer: `governance_tools.memory_record`
- Record identity: `883d807b1e4e3729c52b334eeb0f9bc37b3194f49d1b82e5763ef0aff9cb0d7b`
- Commit binding: `ab39e35` (bound)
- Record: S2-B0 compared frozen S2-A with candidate 663caca without porting code. Recorded REUSE/FIX/REWRITE/DEFER, the 12 scenario owners and B1 two-file scope. Candidate 65 run/64 pass/one Windows skip; independent probes exposed YAML Core numeric oracle errors, admission bypasses and item invariant defects. User authorizes serial PR review and conditional merge of B0-P1; real Pilot product baseline and human-authored rules remain pending. This record is local audit evidence, not remote review/merge completion.
- Validation boundary: PASS: artifacts/evidence/test-results/s2-b0-drift.json and artifacts/evidence/test-results/s2-b0-readiness.json; candidate runs and independent probes are documented in docs/specs/s2-b0-candidate-audit.md, not S2 qualification.
- Next action: Review latest B0 PR head, pass CI, merge conditionally; then start B1 from updated main. Await user inputs before real P1.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:bef0a1494d9e18f18c02ea397f54109d381f58b005e1d1f6f866ff0d6200bd00 -->
### Canonical memory checkpoint — 2026-10-03-S2-B0-durable

- Writer: `governance_tools.memory_record`
- Record identity: `bef0a1494d9e18f18c02ea397f54109d381f58b005e1d1f6f866ff0d6200bd00`
- Commit binding: `6ebc927` (bound)
- Record: PR21 Codex P2 identified that the local WIP commit would not exist in fresh clones. Saved exactly 12 selected candidate Git blobs in an inert ZIP plus per-file Git IDs/SHA256 and public replay baseline; archive bytes were verified against original objects. Replayed the archive on public main baseline: implementation 43/43, product 22 run/21 pass/one Windows skip. Candidate defects remain documented; archive is not a production port or WIP acceptance. Latest-head remote re-review and merge are pending.
- Validation boundary: PASS: artifacts/evidence/test-results/s2-b0-durable-implementation.json and artifacts/evidence/test-results/s2-b0-durable-product.json; receipts retain execution-time e3a65e4 and describe archived candidate replay, not current S2 production acceptance.
- Next action: Review final B0 archive fix, require current-head Codex/CI, merge and begin B1 from refreshed main.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:825df380c48c84c0e15428e9f6d72af6412c4f25ccf58649d4a9981e7b19a7cd -->
### Canonical memory checkpoint — 2026-10-03-S2-B1

- Writer: `governance_tools.memory_record`
- Record identity: `825df380c48c84c0e15428e9f6d72af6412c4f25ccf58649d4a9981e7b19a7cd`
- Commit binding: `f59f41d` (bound)
- Record: S2-B1 ports only typed matchers/tests from the inert candidate. Root cause: WIP numeric resolver and its oracle used non-Core binary/underscore forms and rejected decimal leading zeros; inherited constructors admitted YAML1.1 scalar spellings and Python merged boolean/integer keys. Corrected Core resolution and tag-aware key equality, frozen timestamp-uncomparable semantics, strict result tuples/codes/node invariants and sanitized parse failures. Initial full347 run/344pass/three inherited Windows skips; focused28 pass after final invariants. New regression against old candidate produced19 failed subcases/one key-collision error. No product/policy/evaluator/CLI changes; remote delivery remains pending.
- Validation boundary: PASS: artifacts/evidence/test-results/s2-b1-committed-focus.json -> 28 matcher tests, linked to f59f41d. Initial full suite and deliberate old-candidate failures are separate diagnostic receipts, not product verification.
- Next action: Complete independent latest-head review, open B1 PR, resolve Codex findings, require CI then merge; B2 starts from updated main.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:6364431ec782a9a4db8c5a46963eea361082f14522f0629fead895040fa2b2d0 -->
### Canonical memory checkpoint — 2026-10-03-S2-B1-review-fix

- Writer: `governance_tools.memory_record`
- Record identity: `6364431ec782a9a4db8c5a46963eea361082f14522f0629fead895040fa2b2d0`
- Commit binding: `084fa59` (bound)
- Record: Fixed four S2-B1 independent/Codex review findings: canonical full-precision timestamp keys, linear shared-alias traversal, iterative JSON Unicode scan and sanitized parser traceback chains. Four regressions fail reviewed d977ba3 and pass fixed 084fa59. Full Windows suite 351 tests, 348 pass and 3 inherited platform skips. PR #22 still requires latest-head review and CI before merge.
- Validation boundary: PASS: artifacts/evidence/test-results/s2-b1-review-committed-focused.json; PASS: artifacts/evidence/test-results/s2-b1-review-fixed-full.json; expected old-head FAIL: artifacts/evidence/test-results/s2-b1-review-regression-before.json
- Next action: Review latest PR #22 head and CI, conditionally merge B1, then start B2 from updated main; real P1 still requires human product baseline and rules.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:c3dd09f7aaff1a8718202d70bee253b0fcfa6eeb2dba28b19b122b4449f88a33 -->
### Canonical memory checkpoint — 2026-10-03-S2-B1-schema-fix

- Writer: `governance_tools.memory_record`
- Record identity: `c3dd09f7aaff1a8718202d70bee253b0fcfa6eeb2dba28b19b122b4449f88a33`
- Commit binding: `217440ae1e08e83edc4c4297ca7aca706b439cd6` (bound)
- Record: Fixed second Codex B1 review: restrict YAML constructors to frozen Core plus timestamp and reject escaped surrogate keys/values. Two regression methods reject 45636f5 with eight failed subcases. Focused 34 pass and full Windows regression 353 run/350 pass/3 inherited skips. PR #22 requires new exact-head review and CI.
- Validation boundary: PASS: artifacts/evidence/test-results/s2-b1-schema-committed-focused.json; PASS: artifacts/evidence/test-results/s2-b1-schema-fixed-full.json; expected old-head FAIL: artifacts/evidence/test-results/s2-b1-schema-regression-before.json
- Next action: Independent/Codex review current B1 head and CI; merge only after gate passes, then B2.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:14e956235f4188850c50447ee102605d23455229df7efb6aa99ebeda07275691 -->
### Canonical memory checkpoint — 2026-10-03-S2-B1-scalar-alias

- Writer: `governance_tools.memory_record`
- Record identity: `14e956235f4188850c50447ee102605d23455229df7efb6aa99ebeda07275691`
- Commit binding: `4cc01b19905683f1be03e0d0010cf84e6b8ad3bf` (bound)
- Record: B1 independent review found repeated Unicode scanning of shared scalar aliases introduced by 217440a. Memoized successfully validated string identities. CountingString regression fails 394ae39 and all 35 matcher tests pass fixed 4cc01b1. Prior full suite 353 run/350 pass/3 skips; latest-head full regression is a required CI gate.
- Validation boundary: PASS: artifacts/evidence/test-results/s2-b1-scalar-committed-focused.json; expected old-head FAIL: artifacts/evidence/test-results/s2-b1-scalar-alias-before.json
- Next action: Complete latest-head reviews and CI for PR #22, merge B1 if clean, then start B2.
- PLAN reconciliation: `updated`

<!-- memory_record_projection:review-log:ed8b99669d766f6fb439e91307c5eb886db96dae4dba74214c34c6d9e529a475 -->
### Canonical memory checkpoint — 2026-10-03-S2-B1-integer-cap

- Writer: `governance_tools.memory_record`
- Record identity: `ed8b99669d766f6fb439e91307c5eb886db96dae4dba74214c34c6d9e529a475`
- Commit binding: `9f93b0dde33cdf38a0258252329342465170ab65` (bound)
- Record: B1 Codex integer-digit-cap P2 fixed with local chunked decimal conversion for JSON and YAML; process digit limit unchanged. Arithmetic-oracle regressions reject 47e3462 with five errors; fixed 9f93b0d focused 37 pass. Current full coverage remains a required CI gate before merge.
- Validation boundary: PASS: artifacts/evidence/test-results/s2-b1-integer-committed-focused.json; expected old-head FAIL: artifacts/evidence/test-results/s2-b1-big-integer-before.json
- Next action: Review and CI current PR #22 head, conditional merge, then B2 from main.
- PLAN reconciliation: `updated`
