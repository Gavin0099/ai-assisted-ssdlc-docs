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
| **`PS.2.1`**<br>Verify Release Integrity | 政策要求發佈產物具備雜湊清冊、簽章程序或校驗機制。 | 發佈工作流中的 Checksum 產出腳本、簽章配置（如 Sigstore/Cosign step）、Release Manifest 配置檔。 | `yaml_path`<br>`line_span` |

---

## 4. 領域模型與資料合約 (Domain Models & Contracts)

### 4.1 Anti-Corruption Layer Contracts

#### 權威性與完整性約束 (Expectation & Rule Authority Invariants)
1. **禁止自動合成 (No Auto-Synthesis)**：
   **嚴禁由 AI、推論引擎或 CLI 根據 `task_id`、`coverage_verdict` 或 derived guidance 自行拼湊或推導 `PolicyImplementationExpectation`**。每一筆 Expectation 必須由人類審查員顯式制定。
2. **來源身分強校驗 (Authority Matching)**：
   Expectation 之 `task_id`、`policy_finding_id` 與 `policy_source_ref` 必須嚴格存在於已驗證的 Layer 1 政策評估報告中，否則驗證程序即刻 Fail-Closed。
3. **參照完整性約束 (Referential Integrity)**：
   - `expectation_id` 集合內嚴禁重複 ID。
   - `rule_id` 集合內嚴禁重複 ID。
   - Expectation 中列出之 `verification_rule_ids` 必須 100% 存在於 Rule 集合中，嚴禁懸空參照 (Dangling Reference)。
   - Expectation 之 `task_id` 必須與所參照 Rule 之 `task_id` 嚴格一致，嚴禁跨 Task 誤掛。
   - **Fail-Closed 門禁**：若偵測到重複 ID、懸空參照或 Task ID 不一致，程序即刻中斷（Fail-Closed, Exit 1），嚴禁繼續執行。


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

#### S2 YAML Path Subset v1 語法合約
為保證跨執行環境與實作語言之唯一確定性，Pilot 階段僅支援受限語法子集：
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
禁止在驗證引擎中引入動態表達式或語言引擎（如 `"tech_stack == 'python'"`），改採人類/宣告者顯式輸入：
```python
@dataclass(frozen=True)
class RuleApplicability:
    """Explicit applicability status supplied by rule author or manifest."""

    status: str                           # "APPLICABLE" | "NOT_APPLICABLE"
    reason: str | None = None             # Required if NOT_APPLICABLE, None if APPLICABLE
```

#### Canonical Digest 演算法合約
`rule_digest`、`expectation_digest`、`ruleset_digest` 與 `expectation_set_digest` 必須嚴格依以下演算法計算：
1. **欄位過濾**：僅合約宣告之語意欄位參與序列化（明確排除任何 runtime/output-only metadata、執行時暫態、記憶體快取或除錯字串）。
2. **型別規範化**：Enum 欄位一律轉換為對應之 canonical 字串值。
3. **集合規範化**：
   - 作者有序陣列（如 path lists、steps、candidate_selectors）維持原作者定義順序。
   - 無序集合（如 ruleset 中的 rules、expectationset 中的 expectations）必須嚴格依照其主要鍵名（`rule_id` 或 `expectation_id`）進行字典序升冪排序。
4. **序列化格式**：使用 UTF-8 編碼之 Canonical JSON，指定 `sort_keys=True`，且無多餘空白分隔符號。
5. **雜湊輸出**：對 Canonical JSON 位元組串進行 SHA-256 運算，產出 64 碼十六進位字串。

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
    expected_value: str | None = None         # Target comparison value

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

#### Product Manifest Canonical Digest 規範
`product_manifest_digest` 與 S1 Target Manifest 採用相同之 Canonical JSON (`sort_keys=True`) + SHA-256 規範，但**僅包含 Product Target Manifest 自身的 4 個語意欄位**（`manifest_version`, `target`, `authority_surface`, `mode`），嚴格不包含 Policy baseline 欄位。

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
    """Flexible locator for structured and unstructured static evidence."""

    kind: str                             # "yaml_path" | "json_pointer" | "line_span" | "file_existence"
    value: str                            # e.g. "jobs.security.steps[1].uses" or "package-lock.json"

@dataclass(frozen=True)
class EvidenceRef:
    """Immutable reference to an authoritative static evidence artifact in product repo."""

    repo_path: str                        # Relative to product repo root
    content_digest: str                   # SHA-256 of the target file
    locator: EvidenceLocator              # Precise location inside file
    matched_snippet: str | None = None    # Optional bounded excerpt (not identity)
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
@dataclass(frozen=True)
class ImplementationVerificationRecord:
    """Aggregate root for product repository implementation verification."""

    verification_id: str
    # Policy Provenance Surface
    policy_target_repo: str
    policy_target_commit: str
    policy_manifest_digest: str
    policy_corpus_digest: str
    policy_provenance_verified: bool

    # Product Provenance Surface
    product_target_repo: str
    product_target_commit: str
    product_manifest_digest: str
    product_corpus_digest: str
    product_provenance_verified: bool

    # Digest Identifiers for Rules & Expectations
    expectation_set_digest: str
    ruleset_digest: str

    # Pure Non-Aggregated Items
    verified_items: tuple[ImplementationVerificationItem, ...]

    claim_boundary: tuple[str, ...] = ()

    @property
    def provenance_verified(self) -> bool:
        """Derived read-only property: true iff BOTH policy and product are verified."""
        return self.policy_provenance_verified and self.product_provenance_verified
```

---

## 5. 出處信任邊界與 Fail-Closed 門禁合約 (Dual Provenance & Fail-Closed)

### 5.1 負向事實判定 (Exit Code 0)
- **情境**：雙邊出處均合法通過驗證，但產品 Repo 缺少 Lockfile 或未配置 CodeQL。
- **結果**：判定為 `EVIDENCE_MISSING` 或 `EVIDENCE_DISCREPANCY`。
- **程序**：正常結束並輸出事實報表，Exit Code 為 0。負向事實是檢驗程序成功的成果，不是系統故障。

### 5.2 系統出處異常阻斷 (Fail-Closed, Exit Code 1)
以下任一情境破壞信任邊界，引擎必須即刻中止（Fail-Closed, Exit 1），嚴禁輸出看似事實之報表：
1. **雙邊出處未完全通過且無 Opt-In**：若 `policy_provenance_verified == False` 或 `product_provenance_verified == False`，且未顯式指定 `--allow-unverified-provenance`。
2. **Authority Surface 逃逸**：候選路徑或規則企圖透過路徑穿越（如 `..` 或絕對路徑）逃脫產品 Repo 邊界（註：Git 符號連結則由 Resolver 於物化階段自動安全略過排除，視為未進入清冊）。

3. **無效規則或未定義 Expectation**：Expectation 參照之 `policy_finding_id` 於 Policy 報告中不存在，或 Rule 使用未知之 Matcher / 不支援之 YAML Path 語法。
4. **完整性約束破壞**：偵測到重複之 `rule_id` / `expectation_id`，或懸空參照、Task ID 不一致。

### 5.3 CLI Opt-In 與出處揭露合約 (`--allow-unverified-provenance`)
- **無 `--allow-unverified-provenance` 旗標 (預設)**：
  - `policy_provenance_verified == False` 或 `product_provenance_verified == False`
  - 👉 系統即刻以 **Exit Code 1** 阻斷。
  - 👉 嚴禁產出任何部分或未驗證之報表檔案（no verification report）。
- **有顯式 `--allow-unverified-provenance` 旗標 (Opt-In)**：
  - 允許產出驗證報表（Exit Code 0）。
  - 報表必須**獨立分開揭露**兩端出處狀態：`policy_provenance_verified` 與 `product_provenance_verified`。
  - 聚合根之衍生屬性 `provenance_verified` 必然為 `False`（`policy AND product`）。
  - Markdown 與 JSON 報表必須置頂渲染醒目的 **UNVERIFIED PROVENANCE** 警示橫幅，明確宣告整體出處未受完整驗證，不得被誤讀為 fully verified result。

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
**And** 比對規則 `RULE-PO31-SAST` 指定 `YAML_PATH_EQUALS` 匹配該值，且 `candidate_quantifier == ANY`  
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
**And** 比對規則 `RULE-PS21-COSIGN` 搜尋 `.github/workflows/release.yml`，且斷言其 uses 必須包含 `sigstore/cosign-installer`  
**And** 產品 Repo 存在 `.github/workflows/release.yml`，但僅有產出 MD5 雜湊檔之 shell 腳本  
**When** 執行實作憑證驗證時  
**Then** 候選檔案存在但斷言不通過，輸出判定為 `EVIDENCE_DISCREPANCY`  
**And** `evidence_refs` 保存 failing candidate，且 `discrepancy_details` 明確記錄差異字串。

### Scenario 4: Explicit Rule Not Applicable Bounded by Input
**Given** 一項適用於 Python 專案之相依性掃描規則 `RULE-PW44-POETRY`  
**And** 該規則之 `applicability` 顯式設定為 `status: NOT_APPLICABLE`，理由為 "No Python component"  
**When** 執行實作憑證驗證時  
**Then** 輸出判定為 `RULE_NOT_APPLICABLE`  
**And** `evidence_refs` 嚴格為空，且 `applicability_reason` 記錄該不適用理由。

### Scenario 5: Dual Provenance Failure Fails Closed
**Given** 政策端出處無效（`policy_provenance_verified = False`）或產品端出處無效（`product_provenance_verified = False`）  
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

### Scenario 7: Dual Provenance Is Independently Visible
**Given** Policy Provenance 通過驗證（`policy_provenance_verified = True`）  
**And** 產品端未提供 Manifest（`product_provenance_verified = False`）  
**And** 顯式提供 `--allow-unverified-provenance` 旗標  
**When** 執行實作憑證驗證時  
**Then** 系統正常產生報表，Exit Code 為 0  
**And** 報表獨立且分別標註 `policy_provenance_verified: true` 與 `product_provenance_verified: false`  
**And** 衍生屬性 `provenance_verified` 必然為 `false`  
**And** 報表置頂渲染 UNVERIFIED 警示橫幅，明確宣告整體出處未受完整驗證，不得被誤讀為 fully verified result。  
**And** 包含測試變體（Test Variant）：若未帶入 `--allow-unverified-provenance` 旗標，系統即刻以 Exit Code 1 阻斷。

