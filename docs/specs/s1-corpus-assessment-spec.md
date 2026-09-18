# S1-C Multi-File Corpus SSDF Assessment Specification & Contract

## 1. 領域定位與邊界 (Scope & Claim Boundary)

本規格定義從單一文件評估（Phase S0）晉升至**多檔案儲存庫文件庫評估合約與來源綁定驗證層（Phase S1-C: Corpus Assessment Contract & Source-Bound Validation Layer）**。

### 階段職責劃分 (S1 Phased Responsibilities)
- **Phase S1-A**: 定義「看哪裡」（Target Manifest 權威範疇與儲存庫身分）。
- **Phase S1-B**: 確定「實際讀到什麼」（Repo Corpus Resolver 零 working-tree 讀取與 `CorpusSnapshot` 指紋）。
- **Phase S1-C**: 定義「finding 如何綁定 corpus」（Assessment Provenance Envelope 與 Corpus-Member Source-File Validation）。
- **Phase S1-D**: 定義「人最後怎麼 review / consume」（Read-Only Review Engine、Diffing 與報表匯出）。

### 驗證能力精確定義 (Validation Capability Definition)
- **Corpus-Member Source-File Validation**: 本階段保證所有 finding 的 `company_source_ref` 檔案路徑嚴格存在於不可變之 `CorpusSnapshot` 之中，阻斷幽靈檔案與被排除檔案。
- **Non-Claims**: 本階段**不宣稱**「Exact Quote / Span Provenance」（即不宣稱已證明行號區間或逐字引文之物理存在），亦不包含端到端全自動 AI 語意審查執行（Semantic Assessment Execution）。

---

## 2. Target Provenance Envelope 規格

S1-C 擴充 `assessment.target` 支援多檔案儲存庫規格，並強制綁定 Manifest 內容指紋 (`manifest_digest`)：

```yaml
assessment:
  id: S1-ASSESSMENT-001
  baseline: NIST_SP_800_218_v1.1
  target:
    type: repository_corpus
    repo: Gavin0099/ai-assisted-ssdlc-docs
    commit: 39b270f8f3c74aee2afcebe6935272a352691dff
    manifest_path: examples/sample-target-manifest.yaml
    manifest_digest: a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0
    corpus_digest: 669f694e4324fbfb2cf2724495ea7f12e847c20ad4ba7eb472477b7eebcbcd88
  scope_tasks:
    - PO.1.2
    - PO.3.1
    - PS.2.1
    - PW.1.1
    - PW.4.4
    - PW.8.1
    - RV.1.3
  claim_boundary:
    - This assessment evaluates document coverage across the materialized repository corpus only.
    - It does not establish NIST SSDF conformance, organizational compliance, implementation effectiveness, or product security.
    - It does not claim any percentage coverage of the full SSDF or of all possible SSDLC gaps.
```

### 欄位約束
1. `target.type`: 必須為 `"repository_corpus"`。
2. `target.repo`: 必須為非空字串（若為 GitHub 來源，需符合 `owner/repo` 格式），且在驗證時必須與不可變 Snapshot 的 `snapshot.manifest.target.repo` 完全一致。
3. `target.commit`: 必須為 40 字元之十六進位 Git commit SHA（允許大小寫十六進位輸入，內部建構與驗證時一律正規化為小寫）。
4. `target.manifest_path`: 指向宣告權威邊界之 Target Manifest 相對路徑。此欄位僅作為導覽與定位之 navigation metadata；評估合約與重現性之真實不可變依據為 `manifest_digest`。
5. `target.manifest_digest`: 必須為 64 字元之十六進位 SHA-256 指紋（允許大小寫十六進位，內部正規化為小寫），鎖定 Manifest 規則內容以保證可重現性。
6. `target.corpus_digest`: 必須與由 `CorpusSnapshot` 依據字典序相對路徑與內容雜湊所計算出之 SHA-256 數位指紋完全相符（允許大小寫十六進位，內部正規化為小寫）。

---

## 3. 來源參照、結構分離與 `<corpus>#unmentioned` 哨兵規格

在多檔案語料庫評估中，每一項 `task_finding` 或 `non_normative_observation` 的 `company_source_ref` 必須遵守下列規則：

1. **頂層結構分離 (Schema Separation)**:
   - 規範任務評估結果放置於頂層 `results:` 列表，每一項之 `finding_type` 必須為 `"task_finding"`。
   - 非規範觀察項目放置於頂層 `non_normative_observations:` 列表，每一項之 `finding_type` 必須為 `"non_normative_observation"`。兩者在序列化與驗證中不可混用。
2. **語法格式**: `<relative_path>#<section_anchor>` 或 `<relative_path>`。
   - 範例: `policy/secure-development-policy.md#3-security-requirements`。
3. **存在性校驗 (Corpus-Member Source-File Validation)**:
   - 提取錨點前之 `<relative_path>`，必須完全匹配 `CorpusSnapshot.paths()` 中的其中一個已物化檔案。
   - 若檔案不存在於該 Snapshot 中（例如不在 Manifest include 範圍、已被 exclude 排除、或是幽靈路徑），評估引擎與驗證器必須**立即中斷並 fail-closed**。
4. **`<corpus>#unmentioned` 哨兵使用限制**:
   - 僅允許於 `coverage_verdict` 為 `MISSING` 或 `UNRESOLVED` 的 `task_finding` 時使用。
   - 若 `coverage_verdict` 為 `COVERED` 或 `PARTIAL`，**嚴格禁止**使用 `<corpus>#unmentioned`，必須引用具體存在之語料庫文件路徑，否則驗證器立即判定為違規。
   - `non_normative_observation` 觀察項目**嚴格禁止**使用 `<corpus>` 哨兵，必須精確指向語料庫既有文件路徑。

---

## 4. 行為驅動開發場景 (BDD Scenarios)

### Scenario 1: Multi-File Corpus Provenance Validation
**Given** 一個由 Target Manifest 與固定 commit SHA 物化之 `CorpusSnapshot`  
**When** 評估引擎建立評估報告 Envelope 時  
**Then** `target` 必須包含 `type: repository_corpus`、`repo`、40 字元 `commit`、`manifest_path`、64 字元 `manifest_digest` 與匹配之 `corpus_digest`  
**And** 任一指紋若與實際 Snapshot 或規格不符，必須 fail-closed 拋出例外。

### Scenario 2: Corpus-Member Source-File Validation
**Given** 一個包含多份政策文件的 `CorpusSnapshot`（如 `policy/general.md` 與 `policy/crypto.md`）  
**When** 評估發現（Finding）的 `company_source_ref` 引用 `policy/general.md#sec-1` 時  
**Then** 評估驗證器確認該檔案存在於 Snapshot 中，校驗通過。

### Scenario 3: Phantom / Excluded Source File Fails Closed
**Given** 一個由 Target Manifest 物化之 `CorpusSnapshot`，其中 `secret/internal.md` 被排除，且不存在 `policy/nonexistent.md`  
**When** 評估結果中的 `company_source_ref` 引用 `secret/internal.md` 或 `policy/nonexistent.md` 時  
**Then** 評估引擎必須拒絕該評估報告，並明確拋出 `SourceRefNotFoundError`。

### Scenario 4: Strict Sentinel Constraints
**Given** 一個任務評估結果被判定為 `COVERED` 或 `PARTIAL`  
**When** 其 `company_source_ref` 填寫為 `<corpus>#unmentioned` 時  
**Then** 評估驗證器與 SSDF Linter 必須 fail-closed 拒絕，要求具體檔案路徑。

### Scenario 5: SSDF Linter Integration
**Given** 一份多檔案語料庫評估 YAML 檔案  
**When** 執行 `validate_ssdf_assessment.py` 驗證時  
**Then** Linter 必須能辨識 `type: repository_corpus` 之 Target Envelope 並校驗所有指紋格式  
**And** 嚴格檢驗其 7 個 scoped tasks 覆蓋、NIST normative 基準與 claim boundary。
