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
1. **強制先驗證後投影 (Fail-Closed Gate)**:
   - 輸入之 Assessment YAML 必須先通過 S1-C `validate_ssdf_assessment` 檢核（結構、Schema、禁止宣稱語句、任務對應完整性）。
   - 若提供 `--repo-path`，必須載入 Target Manifest 並由 `RepoCorpusResolver` 生成快照，透過 `validate_report_against_snapshot` 嚴格核對 commit、`manifest_digest`、`corpus_digest` 與所有 `company_source_ref` 存在性。
   - 若驗證失敗，立即中斷（Exit Code 1），輸出明確之錯誤原因，嚴禁產出未驗證之報表。
2. **命令列介面規格**:
   - `python tools/review_engine.py <assessment-file.yaml> [options]`
   - 參數選項：
     - `target`: Path to assessment YAML file.
     - `--format {markdown,json,both}`: 報表輸出格式（預設值：若指定 `--stdout` 則為 `markdown`；若指定 `--out-dir` 則為 `both`）。
     - `--out-dir <dir>`: 輸出目錄。寫入 `<assessment_id>.review.md` 與/或 `<assessment_id>.review.json`。
     - `--stdout`: 輸出至標準輸出（支援 Unix pipeline）。
     - `--repo-path <dir>`: 目標儲存庫根目錄路徑。提供時自動執行 S1-C Snapshot Provenance 與語料庫完整性驗證。
     - `--reference`, `--tasks-ref`: NIST SSDF 權威任務定義檔（可選，預設指向 references）。
     - `--evidence-schema`: Evidence Schema 檔案路徑（可選）。
     - `--review-queue-schema`: Review Queue Schema 檔案路徑（可選）。

### 6.2 抽象服務介面 (Service Interface)
```python
class IReviewReportOrchestrator(Protocol):
    def orchestrate(
        self,
        assessment_path: Path,
        repo_path: Path | None = None,
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

### Scenario 6: Provenance & Snapshot Validation Orchestration
**Given** 一份宣告之 `corpus_digest` 或 `commit` 與 `--repo-path` 實體儲存庫不符之評估 YAML  
**When** 執行帶有 `--repo-path` 之審查編排服務或 CLI 時  
**Then** 必須拋出 `ReviewProvenanceError` 或 CLI 以 Exit Code 1 結束  
**And** 明確回報 Provenance 不符原因。

### Scenario 7: Deterministic Artifact Output Generation
**Given** 一份合規之評估 YAML 與 `--out-dir output/ --format both`  
**When** 執行 CLI 產生報告時  
**Then** `output/<assessment_id>.review.md` 與 `output/<assessment_id>.review.json` 必須被正確寫入  
**And** 產出的內容必須具備確定性（與 Renderer 直接產出內容 bit-for-bit 一致）。

### Scenario 8: Stdout Output Streaming
**Given** 一份合規之評估 YAML 與 `--stdout --format markdown`  
**When** 執行 CLI 產生報告時  
**Then** 格式化之 Markdown 報表輸出至標準輸出，Exit Code 為 0。

