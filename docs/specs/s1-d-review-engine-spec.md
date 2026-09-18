# S1-D Read-Only Review Engine & Reporting Specification

## 1. 領域定位與階段劃分 (Scope & Phased Slices)

在 Phase S1-C 完成多檔案儲存庫評估合約與來源綁定驗證層（Corpus Assessment Contract & Source-Bound Validation Layer）之後，**Phase S1-D** 負責建立**唯讀審查引擎與報表生成層（Read-Only Review Engine & Reporting）**。

為防止在報表層引入不當推論或將前期建立的精細證據與宣稱護欄抹平，S1-D 嚴格劃分為四個漸進 Slice：

| Slice | 核心目標 | 嚴格邊界（明確不做） |
| :--- | :--- | :--- |
| **S1-D1 Review Contract & Core Projection** | 定義 Reviewer View 固定欄位、確定性投影、純函式渲染函式庫（Pure Renderer Library）、保留 6 大核心維度與 Claim Boundary | 不實作 CLI / 檔案寫入，不改寫任何 assessment verdict，不引入跨 commit 比較 |
| **S1-D2 CLI Wiring & Reporting** | 實作 CLI 進入點、檔案/構件輸出（File/Artifact Output）與輸入驗證編排（Input Validation Orchestration） | 不推論 gap 關閉（closure）或法規合規性（compliance） |
| **S1-D3 Comparison (Diffing)** | 比對相同 repo / 任務在不同 commit 間的 assessment 差異 | 不將 diff 結果自動推論為「改善」或「退步」等評價性結論 |
| **S1-D4 Review Queue Projection** | 將評估建議投影至審查行動清單（Reviewer Action View） | 不自動更改或寫入 Review Queue 狀態 |

**本規格核心定義 S1-D1 Review Contract & Core Projection**。

---

## 2. 審查合約與六大核心維度保留 (Dimension Preservation Contract)

審查引擎與產出報表**嚴格禁止**將多維度評估信號濃縮為單一概括標籤（例如 `Risk: High` 或 `Status: Bad`）。
每一個任務審查記錄（`ReadOnlyReviewFindingRecord`）必須獨立完整保留以下六大維度：

1. **`coverage_verdict`**:
   - 僅允許合約合法值：`COVERED` | `PARTIAL` | `MISSING` | `NOT_APPLICABLE` | `UNRESOLVED`。
   - 審查引擎嚴格透傳，不得自行改判。
2. **`evidence_strength`**:
   - `strong` | `medium` | `weak`。
3. **`review_queue_recommendation`**:
   - `pending` | `needs_changes` | `accepted` | `accepted_with_review_due` | `deferred` | `rejected`。
4. **`basis` & Attribution**:
   - 保持嚴格區分的三類基準：
     - `nist_normative`: NIST SP 800-218 規範條文要求。
     - `local_derived_guidance`: 本地衍生指引或檢查問題。
     - `reviewer_inference`: 審查員領域推論（非規範性）。
5. **`cannot_claim`**:
   - 該項發現明確宣告不能宣稱之限制事項清單（如不證明合規、不證明漏洞已修復）。
6. **`company_source_ref`**:
   - 引用之語料庫文件相對路徑與章節錨點，或 `<corpus>#unmentioned` 哨兵。

### 固定輸出形狀 (Fixed Output Shape)
為利於下游消費（D2 CLI、D3 Diffing、D4 Queue Projection），`ReadOnlyReviewRecord` 輸出至字典或 JSON 時，結構欄位永遠保持固定。即使無任何非規範觀察，亦必須輸出 `"observations": []`，嚴禁動態省略該鍵值。

---

## 3. 確定性排序規則與可重現邊界 (Deterministic Ordering & Reproducibility)

為保證輸出之確定性，審查引擎區分兩類集合的處理邊界：

### A. 規範集合：保證輸入順序無關（Input-Order Independence via Canonical Ordering）
對下列已明確定義 Canonical 排序規則的集合，無論輸入清單的原始先後順序為何，多次投影保證產出完全一致的排序：
1. **Findings 排序**:
   - 第一排序鍵：`task_id`（字典序升冪，如 `PO.1.2` < `PO.3.1` < `PS.2.1` < `PW.1.1` ...）。
   - 第二排序鍵：`finding_id`（字典序升冪）。
2. **Observations 排序**:
   - 依 `finding_id`（字典序升冪）。
3. **Basis 條目排序 (完整 Tie-breaker)**:
   - 依 `(priority, rationale, task_id or "", source or "")` 排序：
     1. 類型權重：`nist_normative` (1) -> `local_derived_guidance` (2) -> `reviewer_inference` (3) -> 其他 (4)
     2. `rationale`（字典序升冪）
     3. `task_id`（字典序升冪）
     4. `source`（字典序升冪）
4. **Identified Evidence 排序**:
   - 依 `source_ref` 字典序升冪；若相同則依 `type` 字典序升冪。

### B. 語意文字清單：保證同輸入確定性重現（Deterministic Reproduction for Identical Inputs）
具有作者原有意圖表達順序之文字清單（如 `claim_boundary`、`assessment_rationale`、`cannot_claim`），審查引擎**不人為打亂或重新排序**，以保留原作者之語意權重；對於相同的已驗證輸入，引擎保證產出 bit-for-bit 完全相同的投影結果。

---

## 4. 唯讀投影、不重判保證與 D2 驗證邊界

- **投影職責 (Pure Projection)**:
  審查引擎（`ReadOnlyReviewProjector`）之職責僅為將已經由驗證器核可的 `CorpusAssessmentReport` 投影轉換為適合審查員檢視的結構化領域模型（`ReadOnlyReviewRecord`）。
- **禁止行為 (No Evaluative Inference)**:
  - 禁止根據 finding statement 或 rationale 的內容，自行修正或覆寫原先 assessment 記錄的 `coverage_verdict`。
  - 禁止在報表中加入未經由原始 finding 授權的結論性語句（如「此項目已達標」、「組織已具備威脅建模能力」）。
  - 所有宣稱限制事項（`claim_boundary` 與各項 finding 之 `cannot_claim`）必須完整保留並於報表中清晰展示。
- **D2 整合與驗證編排邊界 (D2 Validation Orchestration Rule)**:
  - D1 投影引擎本身**假設輸入為已驗證之合法領域模型**，不重複塞入驗證器邏輯。
  - 後續 S1-D2 CLI（`tools/review_engine.py <file>`）**嚴禁**直接 parse 任意未驗證 YAML 後逕行投影，必須先編排通過 S1-C 結構性與 Provenance 合約校驗（`validate_ssdf_assessment` 與 Snapshot Provenance 驗證）後，方可交付 D1 Projector 投影。

---

## 5. 行為驅動開發場景 (BDD Scenarios)

### Scenario 1: Deterministic Review Projection & Ordering
**Given** 一份經由 S1-C 驗證核可的 `CorpusAssessmentReport`，其內部的 findings 順序被打亂（如 `PW.8.1`, `PO.1.2`, `PW.1.1`）  
**When** 審查投影引擎執行 `project(report)` 時  
**Then** 產生的 `ReadOnlyReviewRecord` 中的 `findings` 必須嚴格依據 `task_id` 字典序排列（`PO.1.2` 先於 `PW.1.1` 先於 `PW.8.1`）  
**And** 連續多次投影之輸出內容完全一致。

### Scenario 2: Faithful Dimension Preservation (No Roll-up)
**Given** 一份包含 `PARTIAL` 判決、`weak` 證據強度、`needs_changes` 建議與明確 `cannot_claim` 清單之評估發現  
**When** 審查引擎將其轉換為 `ReadOnlyReviewFindingRecord` 時  
**Then** 這 6 個維度必須完整且獨立地存在於記錄中  
**And** 投影模型與渲染報表不得將其濃縮為單一概括狀態標籤。

### Scenario 3: Non-Evaluative Projection Guarantee
**Given** 一份報告中特定任務的 `coverage_verdict` 為 `PARTIAL`，其 rationale 包含詳細的政策描述  
**When** 審查引擎執行投影與報表渲染時  
**Then** 產出的審查視圖中該任務 verdict 必須維持 `PARTIAL`  
**And** 不得推論任何「已改善」、「合規」或「通過」之評價性結論。

### Scenario 4: Strict Claim Boundary Display
**Given** 一份包含全域 `claim_boundary` 之評估報告  
**When** 審查引擎產出審查報告視圖（Markdown 或 JSON）時  
**Then** 全域 `claim_boundary` 必須置於獨立且顯要的區塊展示  
**And** 每一項 finding 的局部 `cannot_claim` 必須完整附加於該任務條目下方。

---

## 6. S1-D2: CLI Wiring & Reporting Orchestration Specification

### 6.1 職責與編排護欄 (Responsibilities & Guardrails)
S1-D2 負責為審查引擎提供命令列進入點與報表產出編排服務：
1. **完整出處驗證信任邊界 (Full Provenance Trust Boundary as Default)**:
   - 輸入之 Assessment YAML 必須先通過 S1-C `validate_ssdf_assessment` 檢核（結構、Schema、禁止宣稱語句、任務對應完整性）。
   - 對於 `repository_corpus` 評估類型，CLI 預設**強制要求**同時提供 `--manifest <target-manifest.yaml>` 與 `--repo-path <dir>`，絕不允許靜默降級為半驗證（結構驗證）報表。
   - 若使用者明確需要離線渲染，必須顯式加上 `--allow-unverified-provenance` 旗標；產出之報表（Markdown 與 JSON）將明確標記 `provenance_verified: false`，並置頂顯要警示。
2. **明確 Manifest 輸入與導覽分離**:
   - `assessment.target.manifest_path` 嚴格維持其 S1-C 凍結之「導覽 metadata」語意，不再作為執行時 locator。
   - CLI 透過 `--manifest <path>` 明確傳入 Target Manifest 檔案，校驗其 Schema 與合法性後，比對計算之 `manifest.digest` 是否與 `assessment.target.manifest_digest` 一致。
   - 傳入之 `--manifest` 檔案實體路徑必須局限於 `--repo-path` 儲存庫邊界內，嚴禁路徑穿越。
3. **安全輸出檔名防護 (Safe Filename & Directory Traversal Protection)**:
   - 輸出至 `--out-dir` 時，`assessment_id` 嚴格限定為安全檔名字元（禁止包含 `/`、`\`、`..`、控制字元或空字串）。
   - 驗證解析後之報告輸出路徑嚴格位於 `--out-dir` 目錄內部，一旦發現越界立即 Fail-Closed 中斷，嚴禁寫入任何檔案。
4. **命令列介面規格**:
   - `python tools/review_engine.py <assessment-file.yaml> [options]`
   - 參數選項：
     - `target`: Path to assessment YAML file.
     - `--manifest <path>`: 目標 Target Manifest YAML 檔案路徑（`repository_corpus` 預設必填）。
     - `--repo-path <dir>`: 目標儲存庫根目錄路徑（`repository_corpus` 預設必填）。
     - `--allow-unverified-provenance`: 明確允許在未驗證儲存庫出處與快照之情況下產出未驗證報表。
     - `--format {markdown,json,both}`: 報表輸出格式（預設值：若指定 `--stdout` 則為 `markdown`；若指定 `--out-dir` 則為 `both`）。
     - `--out-dir <dir>`: 輸出目錄。寫入 `<assessment_id>.review.md` 與/或 `<assessment_id>.review.json`。
     - `--stdout`: 輸出至標準輸出（支援 Unix pipeline）。
     - `--reference`, `--tasks-ref`: NIST SSDF 權威任務定義檔別名（可選，預設指向 references）。
     - `--evidence-schema`: Evidence Schema 檔案路徑（可選）。
     - `--review-queue-schema`: Review Queue Schema 檔案路徑（可選）。

### 6.2 抽象服務介面 (Service Interface)
```python
class IReviewReportOrchestrator(Protocol):
    def orchestrate(
        self,
        assessment_path: Path,
        manifest_path: Path | None = None,
        repo_path: Path | None = None,
        allow_unverified_provenance: bool = False,
        tasks_ref: Path | None = None,
        evidence_schema: Path | None = None,
        review_queue_schema: Path | None = None,
    ) -> ReadOnlyReviewRecord:
        """Validates input, materializes domain models, and projects to review record."""
        ...
```

### 6.3 S1-D2 行為驅動開發場景 (BDD Scenarios)

### Scenario 5: Input Validation Orchestration (Fail-Closed on Invalid Assessment)
**Given** 一份未通過 S1-C 結構性或語意約束的評估 YAML（如缺少 `cannot_claim` 或含有禁止之宣稱語句）  
**When** 審查編排服務或 CLI 執行評估報告處理時  
**Then** 必須拋出 `ReviewValidationError` 或 CLI 以 Exit Code 1 結束  
**And** 輸出清晰的驗證錯誤清單，嚴禁產出任何報表。

### Scenario 6: Full Provenance Verification Success & Digest Matching
**Given** 一份合法之 assessment YAML、合法的 `--manifest` 與 `--repo-path` 實體儲存庫  
**When** 執行帶有 `--manifest` 與 `--repo-path` 之審查編排服務或 CLI 時  
**Then** 完整校驗 commit、`manifest_digest`、`corpus_digest` 與所有 `company_source_ref` 存在性  
**And** 產出的審查記錄與報表中 `provenance_verified` 為 `true`。

### Scenario 7: Provenance Trust Boundary Violation (Missing Repo/Manifest without Opt-In)
**Given** 一份 `repository_corpus` 評估 YAML，且未傳入 `--manifest` 或 `--repo-path`  
**When** 未提供 `--allow-unverified-provenance` 旗標而執行 CLI 時  
**Then** CLI 以 Exit Code 1 結束，拋出 `ReviewProvenanceError` 拒絕產出未驗證報表。

### Scenario 8: Output Directory Traversal Protection
**Given** 一份 `assessment.id` 為 `../escaped_report` 之評估 YAML 與指定之 `--out-dir`  
**When** 執行 CLI 產出檔案時  
**Then** CLI 以 Exit Code 1 結束，拒絕寫入任何檔案至 `--out-dir` 外部。

---

## 7. S1-D3: Assessment Comparison & Diffing Engine Specification

### 7.1 職責與無評價情緒合約 (Responsibilities & Evaluative-Free Contract)
S1-D3 負責在兩份合法的 SSDF 評估報告（Baseline vs Target，例如跨版本演進、或不同評估模型之獨立產出）之間進行純確定性客觀比對：
1. **無評價情緒（Without Evaluative Sentiment）原則**:
   - 差異比對引擎嚴格作為「客觀事實轉變記錄器」，僅忠實呈現欄位變化與狀態轉換（如 `coverage_verdict: PARTIAL -> COVERED`）。
   - 嚴格禁止使用任何帶有價值判斷、合規宣稱或進展假設的語句，包含但不限於：「改善 (Improved)」、「修復 (Remediated)」、「解決 (Resolved)」、「合規 (Compliant)」、「符合規範 (Conforming)」、「安全 (Safe)」或「退步 (Regressed)」。
   - 比對結果不產出任何總結性正向/負向得分、百分比或健康度評級。
2. **不可宣稱邊界合併 (Claim Boundary Preservation & Merging)**:
   - 差異結果必須顯要包含所有不可宣稱項目，合併 Baseline 與 Target 兩份報告中的 `claim_boundary`，去重並依字母順序排列，置頂呈現。
3. **比較維度 (Comparison Dimensions)**:
   - **Target Metadata Diff**: 比對 `repo`、`commit`、`manifest_path`、`manifest_digest`、`corpus_digest`、`target_type` 等出處元數據。
   - **Task Status Diff**: 依據 NIST SSDF 任務定義與兩邊 findings，客觀標示各任務狀態為：
     - `ADDED`: 僅存在於 Target。
     - `REMOVED`: 僅存在於 Baseline。
     - `MODIFIED`: 兩邊皆存在，但其以下任何一個欄位有所異動：
       * `coverage_verdict` (COVERED, PARTIAL, MISSING, NOT_APPLICABLE, UNRESOLVED)
       * `company_source_ref`
       * `company_statement`
       * `review_queue_recommendation`
       * `evidence_strength`
       * `assessment_rationale` (嚴格保留作者文字順序比對)
       * `identified_evidence` (使用 `(type, source_ref)` 規範化排序比對)
       * `basis` (使用 `(priority, rationale, task_id, source)` 規範化排序比對)
       * `cannot_claim` (嚴格保留作者文字順序比對)
     - `UNCHANGED`: 兩邊皆存在且上述所有欄位內容完全一致。
   - **集合規範化 vs 作者文字順序 (Canonical Collections vs Author Order)**:
     - `basis` 與 `identified_evidence` 屬於無序集合語意，比對前必須以確定性規則排序規範化，避免序列化順序差異引發偽陽性 `MODIFIED`。
     - `assessment_rationale` 與 `cannot_claim` 屬於作者表達分析與邊界之有序文字段落，保留作者順序進行比對（順序調換即視為作者修改，標記 `MODIFIED`）。
   - **觀察項目邊界宣告 (Non-Normative Observation Scope Boundary)**:
     - 於 S1-D3 階段，差異比對聚焦於規範性任務（Normative Tasks）與出處元數據。
     - `non_normative_observations` 明確宣告不納入比對範圍（`observations_compared: false`）。Diff 報告中需顯式提示 reviewer 觀察項目未納入比較，避免將任務未變更誤讀為整體評估完全相同。
   - **獨立出處驗證 (Independent Provenance Verification)**:
     - CLI 提供 `--baseline-manifest` 與 `--baseline-repo-path`（若未指定則繼承 `--repo-path`），使跨 commit 或跨 snapshot 評估比較時，兩端皆可進行獨立的信任邊界校驗。
     - 僅在 Baseline 與 Target 兩端皆驗證成功時，`provenance_verified` 為 `true`；若任一端未通過且未顯式指定 `--allow-unverified-provenance`，則拒絕產出並 Fail-Closed。

### 7.2 領域模型與資料結構 (Domain Models & DTOs)
```python
class DiffKind(str, Enum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    UNCHANGED = "UNCHANGED"

@dataclass(frozen=True)
class FieldDiff:
    field_name: str
    baseline_value: Any
    target_value: Any

@dataclass(frozen=True)
class TaskFindingDiff:
    task_id: str
    diff_kind: DiffKind
    baseline_finding_id: str | None
    target_finding_id: str | None
    verdict_transition: tuple[str | None, str | None]  # (baseline_verdict, target_verdict)
    changed_fields: tuple[FieldDiff, ...]

@dataclass(frozen=True)
class AssessmentDiffRecord:
    baseline_id: str
    target_id: str
    target_metadata_diff: tuple[FieldDiff, ...]
    task_diffs: tuple[TaskFindingDiff, ...]
    added_count: int
    removed_count: int
    modified_count: int
    unchanged_count: int
    claim_boundary: tuple[str, ...]
    provenance_verified: bool = False
    observations_compared: bool = False
```

### 7.3 服務介面與 CLI 選項 (Service Interface & CLI Options)
```python
class IAssessmentDiffEngine(Protocol):
    def compare(
        self,
        baseline: CorpusAssessmentReport,
        target: CorpusAssessmentReport,
        provenance_verified: bool = False,
    ) -> AssessmentDiffRecord:
        """Determines differences between two assessment reports without evaluative sentiment."""
        ...
```

CLI 參數規格：
```text
python tools/review_engine.py <target_assessment.yaml> \
  --diff-baseline <baseline_assessment.yaml> \
  --manifest <target-manifest.yaml> \
  --repo-path <target_repo_dir> \
  --baseline-manifest <baseline-manifest.yaml> \
  [--baseline-repo-path <baseline_repo_dir>] \
  [--allow-unverified-provenance] \
  [--stdout] [--out-dir <out_dir>] [--format {markdown,json,both}]
```

### 7.4 S1-D3 行為驅動開發場景 (BDD Scenarios)

### Scenario 9: Identical Assessment Comparison (All Unchanged)
**Given** 兩份完全相同的合規評估報告（Baseline 與 Target 具有相同的任務涵蓋與判定）  
**When** 執行 `diff_engine.compare(baseline, target)`  
**Then** 所有任務的 `diff_kind` 均為 `UNCHANGED`  
**And** 統計結果為 `added=0, removed=0, modified=0, unchanged=N`  
**And** 輸出不含任何評價性字眼（如「完全合格」或「無退步」）。

### Scenario 10: Objective Verdict and Field Transition (Without Sentiment)
**Given** Baseline 中任務 `PO.1.2` 為 `PARTIAL`，Target 中同一任務更新了 `company_source_ref` 且判定轉為 `COVERED`  
**When** 執行比對時  
**Then** 任務 `PO.1.2` 標記為 `MODIFIED`  
**And** `verdict_transition` 記錄為 `('PARTIAL', 'COVERED')`  
**And** `changed_fields` 包含 `coverage_verdict` 與 `company_source_ref` 之新舊值  
**And** 報表中客觀陳述轉變，嚴禁輸出「改善」或「修復完成」。

### Scenario 11: Added and Removed Task Findings
**Given** Target 相較 Baseline 增加了任務 `RV.1.3`，且 Baseline 原有的某項 Finding 在 Target 中被移除  
**When** 執行比對時  
**Then** 新任務標記為 `ADDED`，移除之任務標記為 `REMOVED`  
**And** 統計數據中對應計數正確更新。

### Scenario 12: Verified Cross-Commit Diffing (Independent Provenance Verification)
**Given** Commit A 評估報告與其對應之 `baseline-manifest`，以及 Commit B 評估報告與其對應之 `manifest`  
**When** 執行帶有 `--diff-baseline`、`--baseline-manifest`、`--manifest` 與 `--repo-path` 之 CLI 時  
**Then** 兩份報告分別完成出處與快照校驗，比對產出之 `provenance_verified` 為 `true`  
**And** `target_metadata_diff` 記錄 `commit` 從 Commit A 變更為 Commit B 之客觀事實  
**And** 比對報表不呈現 `UNVERIFIED` 警告橫幅。

### Scenario 13: Author Order Sensitivity for Cannot Claim & Rationale
**Given** 兩份評估報告僅在 `cannot_claim` 或 `assessment_rationale` 的條目順序上不同  
**When** 執行比對時  
**Then** 該任務標記為 `MODIFIED`，其 `changed_fields` 列出順序轉變，尊重作者排序語意。


