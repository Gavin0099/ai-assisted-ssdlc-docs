# Phase S2-A: Implementation Evidence Verification Specification
<!-- governance-baseline: overridable -->
<!-- baseline_version: 1.0.0 -->

## 1. 概述與目標 (Overview & Objectives)

Phase S1 建立了政策文件層（Layer 1: Policy Governance Context）的文件覆蓋率評估能力，解決了「公司政策與流程文件是否涵蓋 NIST SSDF 任務」之合約檢驗與確定性審查投影。

**Phase S2: Implementation Evidence Verification Pilot** 進入實體產品應用程式層（Layer 2: Product Implementation Evidence Context），旨在回答：

> 「受測產品儲存庫（Product Repository）在固定不可變 Commit 下的實體代碼與宣告式配置，是否具備公司政策所要求的實作憑證？」

本階段 **S2-A** 為純規則與邊界定義階段（Rule & Bounded Context Definition），嚴格遵循以下核心護欄原則：
1. **純靜態儲存庫憑證 (Static Repository Evidence Only)**：受測對象嚴格限定為固定 Commit、固定 Authority Surface 內的靜態代碼、配置與腳本，排除任何外部 API、即時 Runner 查詢、動態掃描或即時 CI 觸發。
2. **多維輸入條件確定性 (Strict Input-Snapshot Determinism)**：系統保證具備 **Deterministic for identical validated inputs, rule set, expectation set, and repository snapshots** 特性。
3. **無推斷關聯與防腐層合約 (No Inferred Join via ACL Contract)**：政策要求與實作檢驗之間，禁止由 AI 或引擎自行猜測憑證形式，必須透過顯式人類核可的 `PolicyImplementationExpectation` 與封閉比對規格的 `ImplementationEvidenceRule` 介接。
4. **雙邊出處信任邊界 (Dual-Sided Provenance Verification)**：S2 的驗證有效性同時取決於 Policy 評估出處與 Product 實作端出處，整體出處為衍生性唯讀邏輯 (`policy AND product`)。
5. **規則不可變身分與完整性約束 (Immutable Identity & Integrity Invariants)**：所有 Expectation 與 Rule 均具備 Canonical JSON SHA-256 雜湊摘要，且嚴格執行 ID 唯一性與參照完整性檢驗。
6. **機械化兩階段判定 (Mechanical Two-Stage Evaluation)**：將候選定位（Candidate Selector）與斷言檢驗（Assertion）嚴格解耦，確保判定結果數學性唯一。
7. **型別狀態不變性 (Verdict-Specific Field Invariants)**：每一種 Verdict 皆有嚴格限定的欄位組合，嚴禁非法領域狀態。
8. **判定與優先級正交 (Verdict Orthogonality)**：實作驗證結果為客觀事實判定，絕不自動綁定或推導為審查行動優先級（Action Priority）。
9. **多規則不聚合不坍塌 (No Task-Level Roll-Up Invariant)**：同一任務下的多條規則各自產出獨立驗證項目，絕不自動合成單一任務結論。
10. **結果負向判定與系統 Fail-Closed 嚴格分離**：找不到憑證為合法的負向事實（`EVIDENCE_MISSING`，Exit Code 0）；出處不明、Commit 不符或規格損毀才屬於 Fail-Closed 異常（Exit Code 1）。

---

## 2. 領域驅動設計：Bounded Context 與 Anti-Corruption Layer (DDD)

```text
┌───────────────────────────────────────────────────────────────────┐
│ Layer 1: Policy Governance Context (Phase S1)                     │
│  - Authority Surface: Company Policy Repository                   │
│  - Aggregate Root: CorpusAssessmentReport                         │
│  - Provenance: policy_target_repo, policy_target_commit,          │
│                policy_manifest_digest, policy_corpus_digest       │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ Explicit Authority Matching
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│ Anti-Corruption Layer (ACL)                                       │
│  - PolicyImplementationExpectation (Human-Approved, Immutable SHA)│
│  - ImplementationEvidenceRule (Human-Approved, Immutable SHA)     │
│  - Invariant: No expectation may be auto-synthesized by AI/engine │
│  - Integrity: No duplicate IDs, no dangling rule references       │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│ Layer 2: Static Implementation Evidence Context (Phase S2)        │
│  - Authority Surface: Product Target Manifest (Static Repo Files) │
│  - Aggregate Root: ImplementationVerificationRecord               │
│  - Dual Provenance: policy_provenance_verified AND                │
│                     product_provenance_verified                   │
│  - Mechanical Evaluation: Candidate Selector -> Assertion         │
│  - Item Verdicts: EVIDENCE_FOUND, EVIDENCE_MISSING,               │
│                   EVIDENCE_DISCREPANCY, RULE_NOT_APPLICABLE       │
│  - Invariant: NO Task-Level Roll-Up, NO Automatic Priority        │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ Candidate Facts (Non-Aggregated)
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│ Human Review Context (Review Queue & Security Decision)           │
│  - Human Decision: Accepted, Needs Changes, Exception Approved   │
│  - Invariant: AI never auto-closes findings or certifies safety   │
└───────────────────────────────────────────────────────────────────┘
```

---

## 3. S2 Pilot 受測範疇：3 項 NIST SSDF Tasks

S2 Pilot 嚴格依據 `references/nist-ssdf/v1.1/tasks.yaml` 之標準定義，選取具備明確靜態儲存庫憑證之三項任務。

> **Attribution 邊界聲明**：以下實作憑證範例屬於公司政策與本地衍生指引（Pilot Policy Expectation Example / Local Derived Evidence Mapping），非 NIST SP 800-218 原文規範之強制工具要求。

| NIST SSDF Task | Pilot Policy Expectation Example / Local Derived Evidence Mapping | 產品實作層靜態憑證範疇 (Static Evidence Scope) | 憑證定位器型態 |
| :--- | :--- | :--- | :--- |
| **`PO.3.1`**<br>Implement Supporting Toolchains | 政策要求 CI/CD 整合安全工具鏈（如 SAST, Linter, 秘密掃描等）。 | `.github/workflows/*.yml`、`.gitlab-ci.yml`、工具配置檔（如 `.semgrep.yml`, `sonar-project.properties`）。 | `yaml_path`<br>`json_pointer` |
| **`PW.4.4`**<br>Verify Third-Party Components | 政策要求第三方相依套件進行版控鎖定、清冊追蹤與相依性檢查。 | 依賴鎖定檔（`package-lock.json`, `poetry.lock`, `Cargo.lock`, `go.sum`）、套件漏洞配置或相依性掃描 Step。 | `file_existence`<br>`yaml_path` |
| **`PS.2.1`**<br>Verify Release Integrity | 政策要求發佈產物具備雜湊清冊、簽章程序或校驗機制。 | 發佈工作流中的 Checksum 產出腳本、簽章配置（如 Sigstore/Cosign step）、Release Manifest 配置檔。 | `yaml_path`<br>`file_existence` |


---

## 4. 領域模型與資料合約 (Domain Models & Contracts)

### 4.1 Anti-Corruption Layer Contracts

#### 權威性與完整性約束 (Expectation & Rule Authority Invariants)
1. **禁止自動合成 (No Auto-Synthesis)**：
   **嚴禁由 AI、推論引擎或 CLI 根據 `task_id`、`coverage_verdict` 或 derived guidance 自行拼湊或推導 `PolicyImplementationExpectation`**。每一筆 Expectation 必須由人類審查員顯式制定。
2. **來源身分強校驗 (Authority Matching)**：
  Expectation 之 `task_id`、`policy_finding_id` 與 `policy_source_ref` 必須嚴格存在於已驗證的 Layer 1 政策評估報告中，否則驗證程序即刻 Fail-Closed。S1 report 的 source field 名稱為 `company_source_ref`；S2 expectation 的 `policy_source_ref` 必須與該 finding 的值完全相同，不得由 `identified_evidence[].source_ref`、reviewer inference 或任意字串替代。
3. **政策評估來源與通過條件 (Policy Assessment Input & Admission)**：
  - policy assessment 是獨立輸入，必須是成功解析且通過 `validate_ssdf_assessment` 的 S1 assessment；S2 admission 必須同時取得原始 S1 Target Manifest、policy repo 與可重建的 `CorpusSnapshot`，並通過 `ReviewReportOrchestrator.load_and_verify` 等價的 manifest/corpus provenance 驗證。缺少任一項時無法驗證 `policy_source_ref` 的 corpus membership，必須 fail closed；S2 不得只因 YAML/JSON 中的 `provenance_verified: true` 欄位就信任該輸入。
  - 經驗證的 `assessment.id`、原始 S1 manifest 的 `target.source_type`，以及 `assessment.target.{repo,commit,manifest_digest,corpus_digest}` 合稱 `policy_assessment_identity`；manifest digest 必須與 assessment target digest 一致，`policy_assessment_id` 必須等於 `assessment.id`。這個 identity 是該 policy assessment target 的 repo/commit，不是另行臆造的 policy organization 或 policy server identity。
  - 每個 expectation 的 `(task_id, policy_finding_id, policy_source_ref)` 必須唯一對應一筆 `results[]` task finding，並符合 `finding.task_id == expectation.task_id` 與 `finding.company_source_ref == expectation.policy_source_ref`。finding ID 缺失、重複或歧義，或 source reference 只存在於 non-normative observation / `identified_evidence` 時，均 fail closed。
  - expectation admission 必須以 `StrictCorpusSourceRefValidator` 等價檢查 `company_source_ref` 的相對檔案路徑屬於 policy `CorpusSnapshot`；S1 helper 不驗證 `#section_anchor` 存在，也不證明 assessment 語意正確。S2 應沿用這個 claim ceiling，不把 anchor、finding 的政策解讀或 reviewer 身分升格為已驗證事實。
  - 工具驗證輸入連結與 digest，不驗證誰實際核准 expectation/rule。Human approval 是本規格的治理前提，須由受控審查/提交流程提供；S2 執行輸出只能記錄輸入 identity/digest，不得自行聲稱已驗證作者或核准者身分。
4. **參照完整性約束 (Referential Integrity)**：
   - `expectation_id` 集合內嚴禁重複 ID。
   - `rule_id` 集合內嚴禁重複 ID。
   - Expectation 中列出之 `verification_rule_ids` 必須 100% 存在於 Rule 集合中，嚴禁懸空參照 (Dangling Reference)。
   - Expectation 之 `task_id` 必須與所參照 Rule 之 `task_id` 嚴格一致，嚴禁跨 Task 誤掛。
   - **Fail-Closed 門禁**：若偵測到重複 ID、懸空參照或 Task ID 不一致，程序即刻中斷（Fail-Closed, Exit 1），嚴禁繼續執行。
5. **證據種類完整性約束 (Evidence-Kind Integrity Invariant)**：
   - Expectation 之 `expected_evidence_kinds` 必須為非空（non-empty）且無重複（unique）之字串 tuple。
   - **雙向嚴格覆蓋**：
     1. `expected_evidence_kinds` 中宣告的每一種 `evidence_kind`，在該 Expectation 所參照之 Rule 集合（`verification_rule_ids`）中，**必須至少有一條 Rule 之 `rule.evidence_kind` 與之相符**（不得有預期了某類憑證卻沒有任何規則檢驗該憑證）。
     2. 參照的所有 Rule 之 `rule.evidence_kind`，**必須 100% 屬於該 Expectation 之 `expected_evidence_kinds`**，嚴禁掛載超出預期宣告以外之異質憑證規則（例如 Expectation 宣告 `expected_evidence_kinds = ("dependency_lockfile",)`，但關聯的 Rule 卻標註 `evidence_kind = "sast_workflow"`，即便兩者 `task_id` 同為 `PW.4.4`，仍屬違規）。
   - 若違反上述任一項，即判定為無效合約（`ContractInputError`），程序即刻中斷（Fail-Closed, Exit 1）。


#### 封閉 Matcher 集合 (Frozen Matcher Family)
拒絕任意字串與無約束 Criteria，Pilot 階段僅支援以下封閉枚舉：
```python
class MatcherKind(str, Enum):
    FILE_EXISTS = "FILE_EXISTS"                   # 檢查檔案是否存在於指定路徑
    YAML_PATH_EXISTS = "YAML_PATH_EXISTS"         # 檢查 YAML 結構中特定 path 節點是否存在
    YAML_PATH_EQUALS = "YAML_PATH_EQUALS"         # 檢查 YAML 結構中特定 path 節點是否等於預期值
    JSON_POINTER_EXISTS = "JSON_POINTER_EXISTS"   # 檢查 JSON 結構中 pointer 是否存在
    JSON_POINTER_EQUALS = "JSON_POINTER_EQUALS"   # 檢查 JSON 結構中 pointer 是否等於預期值
```

#### Matcher 輸入、結構路徑與比較語意 (Matcher Input & Evaluation Semantics)
- **斷言欄位合法組合**：`FILE_EXISTS` 僅接受 `target_path_expression: null` 與 `expected_value: null`；`YAML_PATH_EXISTS`、`JSON_POINTER_EXISTS` 必須提供 path expression 且 `expected_value: null`；`YAML_PATH_EQUALS`、`JSON_POINTER_EQUALS` 必須提供 path expression 與非空 `ExpectedScalar`。任何多餘、缺漏或型別不符欄位均為 invalid rule，Exit 1。
- **期望值型別**：Pilot 使用明確型別標籤的 scalar，不把 YAML/JSON 值壓成無型別字串。僅支援 `STRING`、`BOOLEAN`、`INTEGER`、`NULL`；不支援 float、mapping、sequence。字串逐 code point 精確、區分大小寫比較，不做 trim 或 Unicode 正規化；integer 以數值比較，boolean 僅與 boolean 比較，null 僅與 null 比較。YAML 端只將 YAML 1.2 Core Schema 的 string、boolean、integer、null 當作可比較 scalar；若被定位節點為 float、timestamp、custom tag 或 collection，`*_PATH_EXISTS` 仍可判定節點存在，但 `*_PATH_EQUALS` 判為該 candidate 不相等。
- **JSON Pointer**：遵守 RFC 6901 URI-fragment-free pointer 形式；root 用空字串，非 root 必須以 `/` 開始。每個 token 僅依 `~1` 解碼為 `/`、`~0` 解碼為 `~`；其他或殘缺 `~` escape 為 invalid rule。object key 精確比對；array token 僅接受 `0` 或不帶前導零的正整數索引（`0` 除外），`-` 不作讀取索引。不存在 token、型別不符或越界是「path 無值」，不是 parser crash。JSON 文件含重複 object key 或非 RFC 8259 值時，視為 invalid evidence input，fail closed。
- **YAML 1.2 Core Schema 與 YAML Path 解析約束**：
  - **Single YAML 1.2 Document Only**：候選 YAML 憑證僅支援單一 YAML 1.2 文件。若輸入包含多文件串流（包含多個 `---` 分隔之 documents），即刻判定為 `InvalidEvidenceInputError`，Exit 1。
  - **YAML 1.2 Core Schema 強制約束**：解析器必須嚴格遵循 **YAML 1.2 Core Schema** 規範，禁止採用舊版 YAML 1.1 規範。此約束確保 GitHub Actions 工作流定義中的 `on:` 觸發鍵不會被 YAML 1.1 錯誤隱式轉譯為布林值 `true`，防止布林污染與語意分歧。布林值僅接受 YAML 1.2 Core Schema 之 `true` / `false`（不接受 `yes`, `no`, `on`, `off` 作為布林值）。
  - **結構損毀與安全性門禁 (Fail-Closed on Malformed Input)**：重複鍵名（Duplicate Mapping Keys）、自定義標籤（Custom Tags，如 `!tag`, `!!python/*`）、遞迴錨點別名（Recursive Alias Loop）或任何語法解析錯誤，一律視為 `InvalidEvidenceInputError`，Fail-Closed Exit 1；禁止採 parser 的 first-wins/last-wins 偶然行為。空 YAML document 視為 root `null`。
  - **導覽語法**：以既有 S2 YAML Path Subset v1 導覽；root mapping key 以 `.` 分隔，list index/wildcard 僅用 `[n]` / `[*]`。每個 key token 非空，且不得含 `.`、`[`、`]` 或反斜線；不支援 escape，其他字元（含空白）按字面精確比對。
- **多節點量化**：path evaluation 回傳按文件結構順序排列的 node sequence。`*_PATH_EXISTS` 在至少一個 node 存在時通過；`*_PATH_EQUALS` 在至少一個 node 的 canonical scalar 等於 expected value 時通過。路徑選不到 node 或所有 node 都不等於 expected value，該 candidate assertion 失敗；不得因 wildcard 多節點而擴張 `ANY/ALL` 的檔案候選量化對象。
- **候選 selector 子集與順序**：selector 使用 S1 Target Manifest 的 Supported Glob Subset v1（僅 `*`, `**`, `?`；`[]`, `{}`, `!` 等 fail closed），並套用既有 relative-path、`/` separator、無絕對路徑及禁止 `..` 邊界。selector union 後按 repo-relative POSIX path 字典序去重；相同路徑只評估一次。空 selector 清單是 invalid rule，不等同於合法的 `EVIDENCE_MISSING`。
- **ANY/ALL 空集合**：先依上述排序得到 candidate set。set 為空時固定產生 `EVIDENCE_MISSING`（空 refs）；非空時 ANY 是至少一個 candidate assertion pass，ALL 是每個 candidate assertion pass。ANY 成功時 refs 只列所有 passing candidates；ALL 成功時列全部 candidates；兩者失敗時 refs 列全部 failing candidates，且需有 deterministic discrepancy details。selector 匹配到非 regular file、symlink 或不在 resolved authority snapshot 的路徑時不得讀取該物件；symlink 不進入 candidate set，其他越權/未授權讀取則 fail closed。
- **EvidenceRef locator**：每個成功/失敗 candidate 恰有一個 ref；`FILE_EXISTS` locator 固定為 `file_existence` 且 value 為 repo-relative path；YAML/JSON path matcher locator 分別固定為 `yaml_path` / `json_pointer` 且 value 原樣保留 assertion expression。`resolved_node_paths` 依文件 traversal order 記錄實際命中的 concrete node address，以 RFC 6901 JSON Pointer 表示、object key 使用 `~0` / `~1` escape；root 為空字串。YAML list wildcard 展開為 concrete list indices；file existence 的 node paths 為空 tuple。若 expression 導出多個 nodes，仍是一個 file-level ref；equals 成功時只列匹配 nodes，exists 成功與 mismatch 時列所有被評估 nodes，無節點時為空 tuple。
- **Discrepancy 資料最小化**：`discrepancy_details` 必須是 compact、key-sorted JSON array；每筆僅含 `repo_path` 與固定 code（`NO_NODE_MATCH`、`VALUE_MISMATCH`、`UNCOMPARABLE_NODE` 之一），按 candidate path 排序。不得輸出 observed/expected 原始 scalar、附近 source text、environment value 或 secret；解析錯誤屬 invalid evidence input，不轉成 discrepancy。Pilot 的 `matched_snippet` 固定為 `None`，避免原始設定值或秘密被複製進報表。

```python
class ExpectedScalarKind(str, Enum):
  STRING = "STRING"
  BOOLEAN = "BOOLEAN"
  INTEGER = "INTEGER"
  NULL = "NULL"

@dataclass(frozen=True)
class ExpectedScalar:
  kind: ExpectedScalarKind
  value: str | bool | int | None
```

合法值組合：STRING -> 任意 string（含空字串）；BOOLEAN -> 嚴格 bool；INTEGER -> 嚴格 int（`bool` 不可因 Python 子類關係視為 int）；NULL -> 僅 `None`。`ExpectedScalar` digest payload 固定為 `{ "kind": <canonical enum string>, "value": <typed value> }`。

#### S2 YAML Path Subset v1 語法合約
為保證跨執行環境與實作語言之唯一確定性，Pilot 階段僅支援受限語法子集：
- **Grammar**：`path := [key ( ("." key) | index )* ]`；`key` 為非空字元序列且不得含 `.`, `[`, `]` 或反斜線；`index := "[" ("*" | "0" | [1-9][0-9]*) "]"`，數字僅使用 ASCII 十進位且不得有前導零。空 `path` 僅表示 root node。每個 path 必須完整符合 grammar，不得忽略前後綴或部分解析。
- **支援語法**：
  1. `Dot Key Navigation`：以句點分隔層級鍵名（如 `jobs.security.steps`）。
  2. `List Wildcard`：`[*]` 表示遍歷該列表之所有元素（如 `steps[*].uses`）。
  3. `List Index`：`[index]` 精確索引特定元素（如 `steps[0]`）。
- **明確不支援語法 (Fail-Closed if present)**：
  - 條件過濾器（如 `[?(@.foo == 'bar')]`）
  - 遞迴遞減運算子（如 `..`）
  - 正則表達式或表達式腳本
  - 逸出字元 DSL
- **求值規則**：若導覽路徑之任一中介鍵不存在或型別不符合，視為節點不存在（False），不拋出未捕獲異常；若路徑語法包含不支援之運算子，則拋出 `InvalidRuleError` 並 Exit 1。

#### 顯式適用性合約 (Explicit Rule Applicability)
禁止在驗證引擎中引入動態表達式或語言引擎（如 `"tech_stack == 'python'"`），改採人類/宣告者顯式輸入與封閉狀態枚舉：
```python
class RuleApplicabilityStatus(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"

@dataclass(frozen=True)
class RuleApplicability:
    """Explicit applicability status supplied by rule author or manifest."""

    status: RuleApplicabilityStatus
    reason: str | None = None
```

- **適用性狀態不變性約束 (Applicability Invariants)**：
  - `status == RuleApplicabilityStatus.APPLICABLE`：`reason` 必須嚴格為 `None`（若提供 reason 則判定為無效規則，Exit 1）。
  - `status == RuleApplicabilityStatus.NOT_APPLICABLE`：`reason` 必須為非空字串（non-empty string；若缺少 reason 則判定為無效規則，Exit 1）。
  - 任何其他字串值或未在 enum 內之 status 均為非法領域狀態（Fail-Closed / Exit 1）。


#### Canonical Digest 演算法合約
所有 digest 均為小寫 64-hex SHA-256。先依各項欄位清單建構 canonical payload，並在序列化前驗證欄位型別；不允許透過排除未識別欄位而靜默接納未知 schema。以下 S2 domain digests 依下列演算法計算：
1. **欄位過濾**：各 digest 的 payload 欄位集合明列如下；明確排除 runtime/output-only metadata、digest 欄位本身、執行時暫態、快取與除錯字串。
2. **型別規範化**：Enum 欄位一律轉換為對應之 canonical 字串值。
3. **集合規範化**：
   - 作者有序陣列（如 path lists、steps、candidate_selectors）維持原作者定義順序。
   - 無序集合（如 ruleset 中的 rules、expectationset 中的 expectations）必須嚴格依照其主要鍵名（`rule_id` 或 `expectation_id`）進行字典序升冪排序。
  - `verification_rule_ids` 依字典序升冪排序後才納入 expectation digest；`candidate_selectors`、`expected_evidence_kinds`、Product Manifest `include` / `exclude` 維持作者順序。重複 selector 不在 digest 層去重，而由輸入 validator 拒絕。
4. **S2 domain digest 序列化格式**：`rule_digest`、`expectation_digest`、`ruleset_digest`、`expectation_set_digest` 使用 UTF-8 編碼 JSON，指定 `sort_keys=True`、`separators=(",", ":")`、`ensure_ascii=False`；不修剪或 Unicode-normalize 字串。Boolean/null/integer 使用 JSON 原生型別，不得字串化。`product_manifest_digest` 是明確例外，精確重用下一節規定的 S1 `TargetManifest.digest` serializer；`product_corpus_digest` 使用該欄位條款定義的 byte stream，不序列化 JSON。
5. **雜湊輸出**：對 Canonical JSON 位元組串進行 SHA-256 運算，產出 64 碼十六進位字串。

Digest payload 的完整 semantic field 清單：
- `expectation_digest`：`expectation_id`, `task_id`, `policy_assessment_id`, `policy_finding_id`, `policy_source_ref`, `expected_evidence_kinds`（作者順序）、`verification_rule_ids`（canonical 排序）。不含 `expectation_digest` 自身。`policy_assessment_id` 對應的完整 target identity 由 `expectation_set_digest` 一次綁定，避免同一 identity 在每筆 expectation 重複。
- `rule_digest`：`rule_id`, `task_id`, `evidence_kind`, `candidate_selectors`（作者順序）、`candidate_quantifier`, assertion 的 `matcher`/`target_path_expression`/`expected_value`、applicability 的 `status`/`reason`。不含 `rule_digest` 自身。
- `ruleset_digest`：canonical payload 是 `{ "ruleset_version": "1.0", "rules": [...] }`；rules 依 `rule_id` 排序，record 不含每筆 `rule_digest` 欄位（整份 payload 綁定 rule semantics）。
- `expectation_set_digest`：canonical payload 是 `{ "expectation_set_version": "1.0", "policy_assessment_identity": {...}, "expectations": [...] }`；expectations 依 `expectation_id` 排序，record 不含每筆 `expectation_digest` 欄位。
- `policy_assessment_identity` 的 canonical object 固定包含 `assessment_id`, `target_source_type`, `target_repo`, `target_commit`, `target_manifest_digest`, `target_corpus_digest`；`target_source_type` 取自與 assessment target manifest digest 相符的原始 S1 Target Manifest，不可由 assessment 自述或 repo URL 推導。
- `product_manifest_digest` 與 Manifest 解析架構邊界：
  ```text
  ProductTargetManifest
      ↓
  S2-specific schema (schemas/product-target-manifest.schema.yaml) / parser / validator
      ↓
  共用 S1 的底層 Git materialization primitives (RepoCorpusResolver, GitCliClient)
  ```
  S2 Product Manifest 擁有專屬的獨立 Schema（`schemas/product-target-manifest.schema.yaml`）與解析校驗器（`validate_product_target_manifest.py`）。
  刻意排除 S1 Policy Manifest 的 `baseline` 欄位（因為產品儲存庫驗證直接比對政策與代碼，無 baseline 需求），並包含 `manifest_version: "1.0"`。
  **嚴禁直接重用 S1 的 `TargetManifest` 解析器**（S1 解析器因強制要求 `baseline` 會對 S2 Product Manifest 報錯）。
  S2 僅共用 S1 之底層 Git 物化原語（`tools/repo_corpus_resolver.py` 中的 `GitCliClient` 與透過泛型 `CorpusSnapshot[ManifestT]` 實作的零工作區 Git blob 提取邏輯）。
  Product Manifest semantic payload 為 `{ "manifest_version": "1.0", "target": {"source_type", "repo", "commit"}, "authority_surface": {"include", "exclude"}, "mode": {"read_only": true} }`。`exclude` 缺省時 canonical payload 使用空陣列；target commit 先正規化小寫；include/exclude 作者順序保留。序列化必須精確沿用 S1 `TargetManifest.digest`：`json.dumps(payload, sort_keys=True).encode("utf-8")`（包含 Python 預設 `ensure_ascii=True` 與預設 separators），之後 SHA-256。S2 payload 不含 S1 的 `baseline`，且額外含 `manifest_version`；不得直接重用 S1 digest 值，亦不得改用本節 compact serializer。
- `product_corpus_digest`：只納入 pinned Git commit tree 中、authority surface 選出的 regular-file blobs；排除 symlink 與被排除路徑。Git path 嚴格 UTF-8 解碼並使用 repo-relative POSIX `/`；按 Unicode scalar lexicographic path 順序排序。每個 file hash 為原始 Git blob bytes（不正規化換行）的 SHA-256。納入 blob 需 strict UTF-8 且不含 NUL / 禁止 C0 control bytes，否則 fail closed。串接每筆 `relative_path + TAB + lowercase_file_sha256 + LF` 後計算整體 SHA-256，與 S1 `CorpusSnapshot.corpus_digest` 演算法一致；manifest digest 獨立綁定 authority rule。

每種 digest 均須有獨立 golden byte/payload fixture，並測試欄位重排、未知欄位、digest 自我包含、大小寫 hash、空 optional list 與排序邊界。不得用 production digest helper 計算同一測試的 expected digest。

```python
@dataclass(frozen=True)
class PolicyImplementationExpectation:
    """Explicit expectation derived from Layer 1 policy assessment."""

    expectation_id: str
    expectation_digest: str               # Canonical SHA-256 of semantic fields
    task_id: str
    policy_assessment_id: str
    policy_finding_id: str
    policy_source_ref: str
    expected_evidence_kinds: tuple[str, ...]
    verification_rule_ids: tuple[str, ...]

class CandidateQuantifier(str, Enum):
    ANY = "ANY"                           # 候選集合中任一檔案符合 Assertion 即為 FOUND
    ALL = "ALL"                           # 候選集合中所有檔案皆符合 Assertion 才是 FOUND

@dataclass(frozen=True)
class EvidenceAssertion:
    """Deterministic static assertion applied to selected candidates."""

    matcher: MatcherKind
    target_path_expression: str | None = None # S2 YAML Path Subset v1 or JSON Pointer
    expected_value: ExpectedScalar | None = None # Explicitly typed comparison value

@dataclass(frozen=True)
class ImplementationEvidenceRule:
    """Human-approved rule specifying exact patterns and criteria for an evidence kind."""

    rule_id: str
    rule_digest: str                      # Canonical SHA-256 of semantic fields
    task_id: str
    evidence_kind: str
    candidate_selectors: tuple[str, ...]  # Path glob patterns, e.g. (".github/workflows/*.yml",)
    candidate_quantifier: CandidateQuantifier # ANY | ALL
    assertion: EvidenceAssertion
    applicability: RuleApplicability = field(default_factory=lambda: RuleApplicability(status="APPLICABLE"))
```

```python
@dataclass(frozen=True)
class PolicyAssessmentIdentity:
    """Identity projected from an admitted S1 assessment and target envelope."""

    assessment_id: str
    target_source_type: str
    target_repo: str
    target_commit: str
    target_manifest_digest: str
    target_corpus_digest: str

@dataclass(frozen=True)
class ImplementationEvidenceRuleset:
    ruleset_version: str                 # Pilot accepts exactly "1.0"
    rules: tuple[ImplementationEvidenceRule, ...]
    ruleset_digest: str

@dataclass(frozen=True)
class PolicyImplementationExpectationSet:
    expectation_set_version: str         # Pilot accepts exactly "1.0"
    policy_assessment_identity: PolicyAssessmentIdentity
    expectations: tuple[PolicyImplementationExpectation, ...]
    expectation_set_digest: str
```

Ruleset 輸入固定為 `{ "ruleset_version": "1.0", "rules": [...], "ruleset_digest": "<64 lowercase hex>" }`；expectation set 固定為 `{ "expectation_set_version": "1.0", "policy_assessment_identity": {...}, "expectations": [...], "expectation_set_digest": "<64 lowercase hex>" }`。Set digest 欄位不納入自身 digest payload。Pilot 僅接受 version `1.0`；未知版本、缺 required key、未知 key 或錯誤型別均 fail closed，不可只保留已知 key 後繼續。Expectation set 的 identity 必須逐欄取自通過 admission 的原始 S1 manifest `target.source_type` 與 assessment `assessment.id` / `assessment.target.{repo,commit,manifest_digest,corpus_digest}`；`manifest_path` 不納入 identity，因 S1 將它定義為 navigation metadata。每筆 expectation 的 `policy_assessment_id` 必須與 set identity 的 `assessment_id` 相同。若 assessment file 改變，即使 assessment ID 相同，也必須重新驗證 findings/source refs。

#### Assessment 輸入 admission 與 policy provenance 驗證
S2 輸入載入分成「S1 assessment admission」與「expectation/rule integrity」兩步；兩者任一步失敗均不得進入 evaluator：
1. 呼叫既有 `validate_ssdf_assessment` 驗 assessment 結構、task/finding 關聯與格式；S2 必須取得原始 S1 Target Manifest 與 repo，並由 `ReviewReportOrchestrator.load_and_verify`（或逐項等價的 manifest digest、CorpusSnapshot digest 與 `validate_report_against_snapshot` 驗證）建立 admission result。Policy `CorpusSnapshot` 是必需品，即使使用 identity opt-in 也不可省略。S2 不可只因 assessment JSON/YAML 內宣告的 `provenance_verified: true` 就信任輸入。
2. `policy_finding_id` 必須在唯一一筆 `results[]` task finding 中解析；同一 `finding_id` 若跨 task 重複或沒有明確唯一 finding，拒絕。Expectation task/source ref 必須逐字匹配該 finding 的 `task_id` / `company_source_ref`，並以 admission 建立的 policy snapshot 驗證 source path membership。`non_normative_observations[]`、`identified_evidence[].source_ref` 與 `basis[].source` 不可替代 task finding。
3. S1 source-ref membership helper 僅驗檔案 path 在 corpus 中，不驗 `#section_anchor`。S2 report 只可聲稱 assessment target/snapshot 與 expectation reference 已機械比對；不得宣稱 anchor、政策語意、finding 正確性或 reviewer approval 身分已被驗證。
4. No-auto-synthesis 是輸入/authority invariant，不可由資料欄位 `approved: true` 自證。受控審查/提交流程負責提供 human approval；S2 不驗證作者或核准者身分，也不得在輸出中宣稱已驗證該身分。

---

### 4.2 Product Target Manifest Contract

受測產品 Repo 之出處契約重用 S1 infrastructure，但不繼承 Layer 1 的 Policy baseline 概念：

```yaml
manifest_version: "1.0"
target:
  source_type: "local_git"                # "local_git" | "github"
  repo: "E:/Repos/sample-payment-app"
  commit: "d4b8e3a1f2c4e6a8b0c2d4e6f8a0b2c4d6e8f0a2"
authority_surface:
  include:
    - ".github/workflows/**"
    - "package-lock.json"
    - "poetry.lock"
    - "src/**"
  exclude:
    - "node_modules/**"
    - "dist/**"
mode:
  read_only: true
```

Product Manifest schema 固定 `additionalProperties: false`；`target.source_type` 與 `repo` 語法沿用 S1（`github` 為 `owner/repo`，`local_git` 為本機 repo path），`commit` 為完整 40 位 hex 並正規化小寫，`authority_surface.include` 必須非空，include/exclude 使用 S1 Supported Glob Subset v1，`mode.read_only` 必須嚴格為 boolean `true`。禁止絕對路徑、`..` traversal 與反斜線。`authority_surface.exclude` 缺省視為空 tuple；exclude wins；空物化 corpus fail closed。

#### Product Manifest Canonical Digest 規範
`product_manifest_digest` 使用 S1 `TargetManifest.digest` 的實際 JSON serializer（`json.dumps(payload, sort_keys=True).encode("utf-8")`）後 SHA-256，但只納入 Product Target Manifest 的 `manifest_version`, `target`, `authority_surface`, `mode` 四組語意欄位，嚴格不含 Policy baseline。Product manifest schema 不允許未宣告欄位；不得把 S1 manifest digest 直接當作 product manifest digest。

#### 符號連結與路徑安全邊界 (Symlink & Path Traversal Policy)
重用 S1 infrastructure 之 `RepoCorpusResolver` 機制，實作憑證的檔案解析遵循以下嚴格原則：
1. **符號連結安全排除 (Symlink Blob Exclusion)**：Git tree 中 mode `120000` 之符號連結於物化階段一律略過（Skip/Exclude），絕不作為合法證據 blob 載入。若預期憑證為符號連結，因其未進入物化清冊，將按規則判定為 `EVIDENCE_MISSING`，不會進入評估階段。
2. **邊界逃逸即刻阻斷 (Path Traversal Fail-Closed)**：候選選取器（`candidate_selectors`）或路徑若包含路徑穿越運算子（如 `..` 或絕對路徑）企圖逃逸產品 Repo 邊界，系統即刻視為安全違規並 Fail-Closed (Exit 1)。


---

### 4.3 Static Evidence & Verification Models

#### `EvidenceLocator` 與 `EvidenceRef`
```python
@dataclass(frozen=True)
class EvidenceLocator:
    """Precise locator for structured static evidence in product repo."""

    kind: str                             # "yaml_path" | "json_pointer" | "file_existence"
    value: str                            # e.g. "jobs.security.steps[1].uses" or "package-lock.json"


@dataclass(frozen=True)
class EvidenceRef:
    """Immutable reference to an authoritative static evidence artifact in product repo."""

    repo_path: str                        # Relative to product repo root
    content_digest: str                   # SHA-256 of the target file
    locator: EvidenceLocator              # Precise location inside file
    resolved_node_paths: tuple[str, ...] = () # Concrete RFC 6901 node addresses; empty for file existence
    matched_snippet: str | None = None    # Pilot invariant: always None; never serialize source text
```

#### 機械化判定枚舉 (`ImplementationEvidenceVerdict`)
```python
class ImplementationEvidenceVerdict(str, Enum):
    EVIDENCE_FOUND = "EVIDENCE_FOUND"               # 候選檔案存在且通過 Assertion
    EVIDENCE_MISSING = "EVIDENCE_MISSING"           # 候選集合完全為空（找不到任何符合路徑的檔案）
    EVIDENCE_DISCREPANCY = "EVIDENCE_DISCREPANCY"   # 候選檔案存在，但未通過 Assertion
    RULE_NOT_APPLICABLE = "RULE_NOT_APPLICABLE"     # 規則顯式宣告為 NOT_APPLICABLE
```

#### 機械化判定演算法矩陣與 Evidence Capture 規則
針對單一規則的判定與憑證捕捉完全機械化：
1. 若 `rule.applicability.status == "NOT_APPLICABLE"`：
   👉 判定為 `RULE_NOT_APPLICABLE`；`evidence_refs` **嚴格為空**。
2. 根據 `candidate_selectors` 於產品 Repo Authority Surface 中搜尋匹配檔案：
   - 若**未找到任何候選檔案**：
     👉 判定為 `EVIDENCE_MISSING`；`evidence_refs` **嚴格為空**。
   - 若**找到一個或多個候選檔案**：
     - 若 `candidate_quantifier == CandidateQuantifier.ANY`：
       - 若至少有一個候選檔案滿足 `assertion`：
         👉 判定為 `EVIDENCE_FOUND`；`evidence_refs` **保存所有通過 Assertion 的 passing candidates**。
       - 若所有候選檔案皆不滿足 `assertion`：
         👉 判定為 `EVIDENCE_DISCREPANCY`；`evidence_refs` **保存所有被比對但失敗的 failing candidates**，`discrepancy_details` 記錄差異。
     - 若 `candidate_quantifier == CandidateQuantifier.ALL`：
       - 若所有候選檔案皆滿足 `assertion`：
         👉 判定為 `EVIDENCE_FOUND`；`evidence_refs` **保存全部通過之 candidates**。
       - 若有任一候選檔案不滿足 `assertion`：
         👉 判定為 `EVIDENCE_DISCREPANCY`；`evidence_refs` **保存所有未通過 Assertion 之 failing candidates**，`discrepancy_details` 記錄具體檔案差異。

#### 型別狀態不變性約束 (Verdict-Specific Field Invariants)
每一筆 `ImplementationVerificationItem` 在建立時必須符合以下合法組合，違者拋出領域異常：
- **`EVIDENCE_FOUND`**：
  - `evidence_refs`: 必須為非空元組 (`len > 0`)
  - `discrepancy_details`: 嚴格為 `None`
  - `applicability_reason`: 嚴格為 `None`
- **`EVIDENCE_MISSING`**：
  - `evidence_refs`: 嚴格為空元組 (`len == 0`)
  - `discrepancy_details`: 嚴格為 `None`
  - `applicability_reason`: 嚴格為 `None`
- **`EVIDENCE_DISCREPANCY`**：
  - `evidence_refs`: 必須為非空元組 (`len > 0`)
  - `discrepancy_details`: 必須為非空字串
  - `applicability_reason`: 嚴格為 `None`
- **`RULE_NOT_APPLICABLE`**：
  - `evidence_refs`: 嚴格為空元組 (`len == 0`)
  - `discrepancy_details`: 嚴格為 `None`
  - `applicability_reason`: 必須為非空字串

> **領域合約保護 (Illegal Domain State Protection)**：諸如 `EVIDENCE_MISSING + evidence_refs 非空` 或 `EVIDENCE_DISCREPANCY + discrepancy_details 為 None` 等組合皆為非法領域狀態。領域層建構子必須主動拋出例外攔截，嚴禁由下游 renderer 自行隱藏或猜測。


```python
@dataclass(frozen=True)
class ImplementationVerificationItem:
    """Result of verifying one rule against product repository."""

    expectation_id: str
    expectation_digest: str
    task_id: str
    rule_id: str
    rule_digest: str
    verdict: ImplementationEvidenceVerdict
    evidence_refs: tuple[EvidenceRef, ...]
    discrepancy_details: str | None = None
    applicability_reason: str | None = None
    explanation: str = ""
```

#### 聚合根與雙邊出處衍生屬性 (`ImplementationVerificationRecord`)
```python
class RepositoryIdentityStatus(str, Enum):
  VERIFIED = "VERIFIED"
  UNVERIFIED = "UNVERIFIED"  # Identity evidence unavailable; eligible for explicit opt-in only

@dataclass(frozen=True)
class ImplementationVerificationRecord:
    """Aggregate root for product repository implementation verification."""

    verification_id: str
    # Policy Provenance Surface
    policy_assessment_identity: PolicyAssessmentIdentity
    policy_snapshot_integrity_verified: bool
    policy_repository_identity_status: RepositoryIdentityStatus
    policy_unverified_reason_codes: tuple[str, ...]

    # Product Provenance Surface
    product_target_source_type: str
    product_target_repo: str
    product_target_commit: str
    product_manifest_digest: str
    product_corpus_digest: str
    product_snapshot_integrity_verified: bool
    product_repository_identity_status: RepositoryIdentityStatus
    product_unverified_reason_codes: tuple[str, ...]

    # Digest Identifiers for Rules & Expectations
    expectation_set_digest: str
    ruleset_digest: str

    # Pure Non-Aggregated Items (Exact 1:1 mapping with admitted expectation-to-rule edges)
    verified_items: tuple[ImplementationVerificationItem, ...]

    # Mandatory Canonical Cannot-Claim Boundary (Strict Non-Empty Set)
    claim_boundary: tuple[str, ...]

    @property
    def policy_provenance_verified(self) -> bool:
        """Derived only from admitted policy snapshot and identity status."""
        return self.policy_snapshot_integrity_verified and (
            self.policy_repository_identity_status == RepositoryIdentityStatus.VERIFIED
        )

    @property
    def product_provenance_verified(self) -> bool:
        """Derived only from admitted product snapshot and identity status."""
        return self.product_snapshot_integrity_verified and (
            self.product_repository_identity_status == RepositoryIdentityStatus.VERIFIED
        )

    @property
    def provenance_verified(self) -> bool:
        """Derived read-only property: true iff BOTH policy and product are verified."""
        return self.policy_provenance_verified and self.product_provenance_verified
```

#### 聚合根領域不變性約束 (Aggregate Root Invariants)
1. **強制性不能宣稱邊界約束 (Mandatory Canonical Cannot-Claim Boundary)**：
   `claim_boundary` 必須為非空 tuple，且必須精確包含 §7 所定義之 5 項不可宣稱聲明（canonical cannot-claim 邊界條款）。聚合根建構時若缺少任一條款、存在多餘條款或字串篡改，即屬非法領域狀態（Invalid Domain State），即刻 Fail-Closed（拋出 `ValueError` / Exit 1）。嚴禁設為空 tuple（`= ()`），亦不可靠下游 renderer 事後補填，必須在 aggregate root 建立時即完成約束。
2. **邊界邊全覆蓋與恰好唯一不變性 (Exact 1:1 Edge Mapping Invariant)**：
   `verified_items` 必須與輸入之 `expectation_set` 宣告的所有 `(expectation, rule_id)` 邊形成嚴格的雙向 1:1 映射：
   - 設期望集合中所有 Expectation 的 `verification_rule_ids` 邊總數為 $N = \sum |\text{expectation.verification\_rule\_ids}|$，則 `verified_items` 之長度必須**恰好等於 $N$**。
   - 每個 `(expectation_id, rule_id)` 組合在 `verified_items` 中**必須恰好出現一次**：
     - 嚴禁漏掉任何邊（包含判定為 `EVIDENCE_MISSING` 或 `RULE_NOT_APPLICABLE` 的合法負向項目，均必須作為獨立 item 存在）。
     - 嚴禁出現重複項（Duplicate Items）。
     - 嚴禁塞入未在 `expectation_set` 中宣告之未經授權的邊或異質項目（Foreign Items）。
   - `verified_items` 之排序固定依 `(task_id, expectation_id, rule_id)` 字典序遞增排序。
3. **邊界負載身分綁定不變性 (Edge Payload Identity Binding Invariant)**：
   對 `verified_items` 中的每一筆 `ImplementationVerificationItem` item，令 $E = \text{expectation\_set}[\text{item.expectation\_id}]$ 且 $R = \text{ruleset}[\text{item.rule\_id}]$，必須同時嚴格滿足以下出處與不可變身分綁定條件：
   - `item.task_id == E.task_id`（任務 ID 必須與所屬 Expectation 嚴格一致）
   - `item.task_id == R.task_id`（任務 ID 必須與所屬 Rule 嚴格一致）
   - `item.expectation_digest == E.expectation_digest`（期望 SHA-256 摘要必須與 admitted Expectation 語意摘要嚴格一致）
   - `item.rule_digest == R.rule_digest`（規則 SHA-256 摘要必須與 admitted Rule 語意摘要嚴格一致）
   - `item.rule_id in E.verification_rule_ids`（規則 ID 必須嚴格隸屬於 Expectation 宣告之規則參照清單中）
   若任何一項欄位身分或摘要不符，即屬破壞不可變身分鏈（Immutable Identity Chain）之非法領域狀態（Invalid Domain State），引擎必須即刻 Fail-Closed（拋出 `ValueError` / Exit 1），嚴禁產出報表。
4. **出處狀態與原因代碼一致性 (Provenance Status Invariants)**：
   `*_snapshot_integrity_verified`、`*_repository_identity_status` 與 `*_unverified_reason_codes` 只能由 policy/product admission result 建構，不接受 CLI 或 serialized report 輸入直接指定。`*_snapshot_integrity_verified` 在可序列化的 record 中必須為 true；false 代表 admission failure，不能建立 record。合法狀態：
   - Snapshot integrity false（missing/malformed manifest、unreadable pinned commit、authority/digest mismatch、invalid corpus）一律 admission error，無 `ImplementationVerificationRecord`，與 opt-in 無關。
   - Snapshot integrity true 且 repository identity status 為 `VERIFIED` 時，該側 `*_unverified_reason_codes` 必須為空。
   - Snapshot integrity true 且 identity evidence 不可得時，status 為 `UNVERIFIED`；只有明確提供 `--allow-unverified-provenance` 才能建立 report，該側 reason codes 必須恰含 `REPOSITORY_IDENTITY_UNVERIFIED`。
   - `MISMATCH` 不是 record status；已確認 repo 身分與宣告 target 不一致時必須直接 admission fail，任何 opt-in 均不能放行。
   - 任何其他 status/reason 組合（包括 `VERIFIED` 卻有 reason、`UNVERIFIED` 卻無 reason、未知 reason code）都是非法領域狀態並 fail closed。
   - Policy side 的 `policy_assessment_identity` 必須包含 assessment ID 與原始 S1 manifest 綁定的五個 target values（`source_type`, `repo`, `commit`, `manifest_digest`, `corpus_digest`）；product side 的 `source_type`、target 與 digests 必須與成功解析、驗證及物化的 Product Manifest/Snapshot 一致。不得同時保存可互相矛盾的 canonical identity 副本。


---

## 5. 出處信任邊界與 Fail-Closed 門禁合約 (Dual Provenance & Fail-Closed)

### 5.1 負向事實判定 (Exit Code 0)
- **情境**：雙邊出處均合法通過驗證，但產品 Repo 缺少 Lockfile 或未配置 CodeQL。
- **結果**：判定為 `EVIDENCE_MISSING` 或 `EVIDENCE_DISCREPANCY`。
- **程序**：正常結束並輸出事實報表，Exit Code 為 0。負向事實是檢驗程序成功的成果，不是系統故障。

### 5.2 系統出處異常阻斷 (Fail-Closed, Exit Code 1)
以下任一情境破壞輸入/authority 邊界，引擎必須即刻中止（Fail-Closed, Exit 1），嚴禁輸出看似事實之報表：
1. **雙邊出處未完全通過且無 Opt-In**：若 policy 或 product repository identity status 為 `UNVERIFIED`，且未顯式指定 `--allow-unverified-provenance`，必須阻斷。Opt-in 只適用於輸入結構有效、manifest/snapshot 已物化且完整性 digest 一致，但 remote/repository identity 等外部身分證據不可得的情況。已確認 identity `MISMATCH` 直接 fail closed，不允許 opt-in。任何 manifest/corpus digest、fixed commit、authority surface 不一致，malformed/missing manifest、無法讀取 pinned commit、path traversal、無效 expectation/rule 或 S1 source link mismatch，不得降格為 identity uncertainty。
2. **Authority Surface 逃逸**：候選路徑或規則企圖透過路徑穿越（如 `..` 或絕對路徑）逃脫產品 Repo 邊界（註：Git 符號連結則由 Resolver 於物化階段自動安全略過排除，視為未進入清冊）。

3. **無效規則或未定義 Expectation**：Expectation 參照之 `policy_finding_id` 於 Policy 報告中不存在，或 Rule 使用未知之 Matcher / 不支援之 YAML Path 語法。
4. **完整性約束破壞**：偵測到重複之 `rule_id` / `expectation_id`，或懸空參照、Task ID 不一致。

### 5.3 CLI Opt-In 與出處揭露合約 (`--allow-unverified-provenance`)
- **無 `--allow-unverified-provenance` 旗標 (預設)**：
  - `policy_repository_identity_status == UNVERIFIED` 或 `product_repository_identity_status == UNVERIFIED`
  - 👉 系統即刻以 **Exit Code 1** 阻斷。
  - 👉 嚴禁產出任何部分或未驗證之報表檔案（no verification report）。
- **有顯式 `--allow-unverified-provenance` 旗標 (Opt-In)**：
  - 只有符合 §5.2 #1 的 identity-only uncertainty 才允許產出報表（Exit Code 0）；完整性、結構與邊界錯誤即使 opt-in 仍 Exit 1。
  - 報表必須**獨立分開揭露**兩端出處狀態：`policy_provenance_verified` 與 `product_provenance_verified`。
  - 聚合根之衍生屬性 `provenance_verified` 必然為 `False`（`policy AND product`）。
  - Markdown 與 JSON 報表必須置頂渲染醒目的 **UNVERIFIED PROVENANCE** 警示橫幅，明確宣告整體出處未受完整驗證，不得被誤讀為 fully verified result。
  - identity-only uncertainty 使用固定 reason code `REPOSITORY_IDENTITY_UNVERIFIED`；manifest、fixed commit 與 corpus integrity 已驗證的欄位仍維持各自明確狀態，不得把缺 manifest 或 digest mismatch 表示成此 reason code。

### 5.4 Report Serialization 與 Atomicity
- Evaluator 必須先建立完整且通過領域 invariant 的 `ImplementationVerificationRecord`，renderer 不得修補、推測或隱藏非法狀態。
- Admission、manifest/corpus resolution、expectation/rule integrity 或 evaluator 遇到 fatal error 時，必須在第一次 report write 前返回 Exit 1。若指定 file output，採同目錄 temporary file + atomic replace；失敗時移除 temporary file，既有目標檔保持原 bytes，原本不存在的目標檔仍不存在。
- 成功輸出 item 順序固定為 `(task_id, expectation_id, rule_id)`；evidence refs 固定依 `(repo_path, locator.kind, locator.value, resolved_node_paths)` 排序。JSON 欄位順序不具語意，但同一 validated input 的 JSON/Markdown renderer bytes 必須 deterministic。
- `discrepancy_details` 僅允許 §4.1 定義的 sanitized code/path；不得輸出 candidate raw content、expected/observed 值或 matched snippet。五項 `claim_boundary` 必須於 `ImplementationVerificationRecord` 聚合根建構時強制包含並驗證完整性，renderer 僅負責原樣映射輸出，呼叫者不得移除、缺漏或替換。

---

## 6. 多規則不聚合與無自動優先級不變性 (Invariants)

1. **多規則不聚合不變性 (No Task-Level Roll-Up Invariant)**：
   當一項 Task 對應多條驗證規則時，報告必須**如實輸出每一條規則的獨立判定項**。引擎嚴禁自行合成為「`Task PW.4.4: PARTIAL`」或「`Task PW.4.4: FAILED`」。
2. **優先級正交不變性 (Verdict Orthogonality Invariant)**：
   `EVIDENCE_MISSING` 或 `EVIDENCE_DISCREPANCY` 是技術客觀事實，**嚴禁自動指派為 `HIGH` 優先級**。是否需要開立佇列項目或由誰負責，完全屬於下游獨立的 Review Queue Projection 與人類審查裁量權。

---

## 7. 絕對不可宣稱之邊界 (Cannot-Claim Boundaries)

S2 驗證報表與資料模型必須強制附加以下免責宣告：
1. **不保證工具執行成效 (No Tool Effectiveness Claim)**：配置了 CodeQL 或 Trivy 僅證明具備該憑證，不保證工具在 CI 成功執行，亦不保證代碼零漏洞。
2. **不保證執行環境安全 (No Execution Environment Security Claim)**：靜態腳本正確，不保證 GitHub Actions Runner 或 CI Host 未遭竄改。
3. **不保證相依套件安全 (No Component Safety Claim)**：存在 `package-lock.json` 不代表所有第三方套件已經過安全審查或無已暴露 CVE。
4. **不保證發佈產物完整性 (No Release Integrity Guarantee)**：存在簽章或 checksum 腳本，不保證發佈產物未在傳輸或部署中遭到中間人攻擊。
5. **不保證法規或組織合規 (No Compliance or Conformance Claim)**：本驗證僅為靜態憑證之客觀投影，絕不構成 NIST SP 800-218 合規證明。

---

## 8. 行為驅動開發場景 (BDD Scenarios)

### Scenario 1: Direct Implementation Evidence Match via YAML Path Locator
**Given** 一個針對 `PO.3.1` 的合法實作預期 `EXP-PO31-01`  
**And** 產品 Repo 之 `.github/workflows/security.yml` 包含 `jobs.security.steps[1].uses: github/codeql-action/analyze@v2`
**And** 比對規則 `RULE-PO31-SAST` 指定 `YAML_PATH_EQUALS`，expected value 為 `{kind: STRING, value: "github/codeql-action/analyze@v2"}`，且 `candidate_quantifier == ANY`
**When** 執行實作憑證驗證時  
**Then** 輸出判定為 `EVIDENCE_FOUND`  
**And** `evidence_refs` 包含 passing candidate（路徑、檔案 SHA-256 與 `locator: yaml_path`），且 `discrepancy_details` 為 `None`  
**And** 報表明確宣告不保證 CodeQL 實際執行成效。

### Scenario 2: Missing Implementation Evidence Produces Bounded Negative Verdict
**Given** 一個針對 `PW.4.4` 的實作預期 `EXP-PW44-01`，要求 `dependency_lockfile`  
**And** 產品 Repo 之 authority surface 內不存在任何符合候選規則之 lockfile  
**When** 執行實作憑證驗證時  
**Then** 輸出判定為 `EVIDENCE_MISSING`  
**And** `evidence_refs` 嚴格為空，且 `discrepancy_details` 為 `None`  
**And** 驗證程序成功完成，Exit Code 為 0  
**And** 判定不自動指派 `HIGH` 優先級，維持事實與審查決策正交。

### Scenario 3: Evidence Discrepancy Detection via Assertion Failure
**Given** 政策預期要求使用簽章工具 Cosign 進行 release integrity 驗證（`PS.2.1`）  
**And** 比對規則 `RULE-PS21-COSIGN` 搜尋 `.github/workflows/release.yml`，且指定 `YAML_PATH_EQUALS` 斷言 `jobs.release.steps[0].uses` 的 expected value 為 `{kind: STRING, value: "sigstore/cosign-installer@v3"}`
**And** 產品 Repo 存在 `.github/workflows/release.yml`，但該步驟實際為 `actions/checkout@v4`（未配置 Cosign 簽章）  

**When** 執行實作憑證驗證時  
**Then** 候選檔案存在但斷言不通過，輸出判定為 `EVIDENCE_DISCREPANCY`  
**And** `evidence_refs` 保存 failing candidate，且 `discrepancy_details` 使用 sanitized `VALUE_MISMATCH` code，不包含實際 expected/observed value 或 source snippet。

### Scenario 4: Explicit Rule Not Applicable Bounded by Input
**Given** 一項適用於 Python 專案之相依性掃描規則 `RULE-PW44-POETRY`  
**And** 該規則之 `applicability` 顯式設定為 `status: NOT_APPLICABLE`，理由為 "No Python component"  
**When** 執行實作憑證驗證時  
**Then** 輸出判定為 `RULE_NOT_APPLICABLE`  
**And** `evidence_refs` 嚴格為空，且 `applicability_reason` 記錄該不適用理由。

### Scenario 5: Dual Provenance Failure Fails Closed
**Given** 任一 `*_repository_identity_status` 為 `RepositoryIdentityStatus.UNVERIFIED`
**And** 未帶入 `--allow-unverified-provenance` 旗標  
**When** 執行實作憑證驗證時  
**Then** 系統即刻中止並以 Exit Code 1 結束，拋出出處錯誤  
**And** 絕不輸出任何驗證報表檔案（no verification report），防止未經驗證的出處被誤用。

### Scenario 6: Multiple Rules Do Not Collapse into Task Verdict
**Given** 針對任務 `PW.4.4` 關聯了兩條獨立規則：  
  - `RULE-PW44-LOCKFILE`（檢驗 Lockfile 存在）  
  - `RULE-PW44-SCA`（檢驗 CI 內相依性掃描 Step）  
**And** 產品 Repo 中 Lockfile 存在（判定為 `EVIDENCE_FOUND`），但 CI 中無相依性掃描（判定為 `EVIDENCE_MISSING`）  
**When** 執行實作憑證驗證時  
**Then** 報表精確產出兩個獨立的 `ImplementationVerificationItem`  
**And** 系統**嚴禁將 `PW.4.4` 自動合成為 `PARTIAL` 或 `FAILED`**，亦不自動指派任何行動優先級。

### Scenario 7: Identity-Only Provenance Uncertainty Is Explicitly Opted In
**Given** Policy assessment 通過結構、finding link、manifest digest 與 policy `CorpusSnapshot` 完整性驗證
**And** 該 finding 的 `company_source_ref` path 經 policy `CorpusSnapshot` 驗證為成員
**And** Product Manifest、fixed commit、authority surface 與 product corpus digest 均存在且一致
**And** Product Repository 的 remote identity evidence 不可得（`product_repository_identity_status = RepositoryIdentityStatus.UNVERIFIED`，reason=`REPOSITORY_IDENTITY_UNVERIFIED`）
**And** 顯式提供 `--allow-unverified-provenance` 旗標
**When** 執行實作憑證驗證時  
**Then** 系統正常產生報表，Exit Code 為 0  
**And** 報表獨立且分別標註 `policy_repository_identity_status = RepositoryIdentityStatus.VERIFIED` 與 `product_repository_identity_status = RepositoryIdentityStatus.UNVERIFIED`，且兩側 snapshot integrity 均為 verified
**And** 衍生屬性 `provenance_verified` 必然為 JSON `false`
**And** 報表置頂渲染 UNVERIFIED 警示橫幅，明確宣告整體出處未受完整驗證，不得被誤讀為 fully verified result。  
**And** 包含測試變體（Test Variant）：若未帶入 `--allow-unverified-provenance` 旗標，系統即刻以 Exit Code 1 阻斷。

### Scenario 8: Missing Product Manifest Is Not an Opt-In Case
**Given** Product Manifest 缺失，因此無法確定 commit authority surface 或 product manifest digest
**And** 即使提供 `--allow-unverified-provenance` 旗標
**When** 執行 provenance admission 時
**Then** 系統以 Exit Code 1 fail closed
**And** 不建立 report 或 temporary output；若目標檔已存在，其原 bytes 保持不變。

### Scenario 9: Selector ANY/ALL and Structured Node Quantification Are Distinct
**Given** 兩個 candidate files 依 path 排序，其中一個 YAML path wildcard 命中多個 nodes，另一個 candidate 的 assertion 不符合
**When** 以 `ANY` 評估一次並以 `ALL` 評估一次
**Then** `ANY` 在任一 file candidate 通過時為 `EVIDENCE_FOUND`，refs 列出所有 passing files 及其 concrete node paths
**And** `ALL` 因至少一個 file candidate 失敗而為 `EVIDENCE_DISCREPANCY`，refs 只列 failing file 及其 concrete node paths
**And** 同一 file 內 wildcard 多個 node 的比較採「至少一個 node 相等」規則，不改變跨檔案的 ANY/ALL 量化。

### Scenario 10: Typed Matcher Values Do Not Coerce
**Given** YAML/JSON evidence node 為 integer `1`
**And** 一條 rule 的 expected value 是 `{kind: STRING, value: "1"}`
**When** 執行 `YAML_PATH_EQUALS` 或 `JSON_POINTER_EQUALS`
**Then** 該 candidate 不相等並產生 sanitized `VALUE_MISMATCH`
**And** 另一條 expected value `{kind: INTEGER, value: 1}` 才可通過
**And** discrepancy output 不包含 observed value `1` 或完整 source snippet。

### Scenario 11: Invalid Digest or Duplicate Structured Keys Fails Before Output
**Given** expectation/rule set 存在 digest 不符、duplicate ID，或候選 YAML/JSON 有 duplicate keys 其中任一情形
**When** 執行 admission/evaluation，且 file output 路徑已指定
**Then** 系統以 Exit Code 1 fail closed，不產出 report
**And** 新目標檔不存在、既有目標檔 bytes 不變、同目錄不留下 temporary file。

### Scenario 12: Confirmed Repository Identity Mismatch Cannot Be Opted In
**Given** Product Manifest 格式有效且 snapshot 可物化，但經核對的 remote identity 與 manifest 宣告 repo 不同（admission identity result=`MISMATCH`，不建立 record）
**And** 顯式提供 `--allow-unverified-provenance` 旗標
**When** 執行 provenance admission 時
**Then** 系統仍以 Exit Code 1 fail closed
**And** 不建立 report 或 temporary output，既有 output bytes 保持不變。

