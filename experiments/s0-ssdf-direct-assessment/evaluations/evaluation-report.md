# S0-D: AI Semantic Evaluation Report

## 1. 執行背景與評估目的 (Executive Summary)

本評估報告為 **Phase S0 (NIST SSDF Direct Assessment)** 的驗收核心產出。
主要目標為驗證：
**在具備 S0-A 契約約束（Assessment Contract）與 S0-C 確定性檢驗器（Boundary Linter）的護欄下，AI 是否能直接以權威規範（NIST SP 800-218 SSDF v1.1）作為 Authoritative Baseline，對企業真實風格之政策文件（`sample-company-ssdlc.md`）進行語意審查，並產出高品質、無幻覺、不跨越 Claim Boundary 的結構化評估？**

---

## 2. 評估輸入與基準對照 (Evaluation Setup)

- **Authoritative Baseline**: `references/nist-ssdf/v1.1/tasks.yaml`（7 個代表性任務：PO.1.2, PO.3.1, PS.2.1, PW.1.1, PW.4.4, PW.8.1, RV.1.3）。
- **Target Document**: `experiments/s0-ssdf-direct-assessment/fixtures/sample-company-ssdlc.md`。
- **Contract Boundary**: `experiments/s0-ssdf-direct-assessment/assessment-contract.md`。
- **Ground Truth**: `experiments/s0-ssdf-direct-assessment/golden/expected-assessment.yaml`。
- **Candidate Under Test**: `experiments/s0-ssdf-direct-assessment/evaluations/candidate-assessment-001.yaml`。

---

## 3. S0-C 機械式邊界檢驗結果 (Deterministic Boundary Check)

執行指令：
```powershell
python tools/validate_ssdf_assessment.py experiments/s0-ssdf-direct-assessment/evaluations/candidate-assessment-001.yaml
```

**檢驗結果**:
```text
ssdf_assessment: PASS
```

### 檢驗指標覆蓋情形：
1. **Schema & Envelope Integrity**: 通過。包含 `id`、`baseline`（嚴格對齊 `NIST_SP_800_218_v1.1`）、`target`、`scope_tasks` 與 `claim_boundary`。
2. **Task ID Reference Integrity**: 通過。7 個 finding 均為合法之 Task ID，無無效或跨 task 複合 ID。
3. **Anchor Traceability**: 通過。7 個 finding 的 `company_source_ref` 均精確定位至 `sample-company-ssdlc.md` 之標題 anchor。
4. **Vocabulary Conformity**: 通過。`coverage_verdict`、`evidence_strength`、`review_queue_recommendation` 嚴格使用白名單詞彙。
5. **Cannot Claim Boundary Enforcement**: 通過。審查者撰寫之文字中無肯定句形式之合規、安全、無漏洞宣稱，無無分母百分比，且每個 finding 均附有獨立的 `cannot_claim`。

---

## 4. 語意評估比對矩陣 (Semantic Comparison Matrix)

將 Candidate (`candidate-assessment-001.yaml`) 與 S0-B Golden (`expected-assessment.yaml`) 進行逐項比對：

| Task ID | Task 名稱 | Golden Verdict | Candidate Verdict | Golden RQ Rec | Candidate RQ Rec | 語意吻合度 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PO.1.2** | Define Security Requirements | `PARTIAL` | `PARTIAL` | `needs_changes` | `needs_changes` | 100% (完全吻合) |
| **PO.3.1** | Implement Supporting Toolchains | `PARTIAL` | `PARTIAL` | `needs_changes` | `needs_changes` | 100% (完全吻合) |
| **PS.2.1** | Verify Release Integrity | `PARTIAL` | `PARTIAL` | `needs_changes` | `needs_changes` | 100% (完全吻合) |
| **PW.1.1** | Risk / Threat Modeling | `PARTIAL` | `PARTIAL` | `needs_changes` | `needs_changes` | 100% (完全吻合) |
| **PW.4.4** | Third-Party Component Reuse | `PARTIAL` | `PARTIAL` | `needs_changes` | `needs_changes` | 100% (完全吻合) |
| **PW.8.1** | Executable Code Testing | `PARTIAL` | `PARTIAL` | `needs_changes` | `needs_changes` | 100% (完全吻合) |
| **RV.1.3** | Vulnerability Disclosure & Intake | `PARTIAL` | `PARTIAL` | `needs_changes` | `needs_changes` | 100% (完全吻合) |

---

## 5. 關鍵缺口捕捉度分析 (Gap Recall Analysis)

針對 `sample-company-ssdlc.md` 中刻意埋入的「模糊條款」與「弱控制」，檢視 AI 是否精確指出：

### 1. PO.1.2（安全需求定義）
- **Golden Gap**:
  - 「All software shall be secure」為高階目標，非具體可驗收需求。
  - 「Projects with known security requirements」形成被動式記錄，缺乏系統化辨識流程。
  - 例外審批僅工程主管同意，無審查週期與紀錄生命週期。
- **Candidate 表現**: 完全捕捉上述 3 點，指出模糊宣稱、被動前提條件與缺乏紀錄機制。

### 2. PO.3.1（工具鏈支援）
- **Golden Gap**:
  - 工具使用屬選配（「may be enabled when appropriate」）。
  - 授權團隊各自選工具，缺乏最低功能基準與整合標準。
  - 失敗僅建議審查（「should be reviewed」），缺少處置與阻擋門檻。
- **Candidate 表現**: 完全捕捉，特別點出選配性質與缺乏 blocking gates。

### 3. PS.2.1（發行完整性驗證）
- **Golden Gap**:
  - 程式碼簽章附帶條件（「when applicable」）。
  - Checksum 僅於客戶要求時提供，非主動提供給下游驗證。
  - 未定義金鑰管理與簽署流程。
- **Candidate 表現**: 完全捕捉，強調提供驗證資訊給軟體取得者（acquirers）應為主動而非客戶索取。

### 4. PW.1.1（安全設計與風險塑模）
- **Golden Gap**:
  - 威脅建模為選配（「may be used when the reviewer considers it necessary」）。
  - 設計審查觸發條件（「complex security-sensitive features」）缺乏客觀定義。
  - 審查結果僅記錄於專案筆記，缺乏可追溯之緩解措施連結。
- **Candidate 表現**: 完全捕捉，指認出主觀自由心證與筆記式紀錄之脆弱性。

### 5. PW.4.4（第三方元件重複使用）
- **Golden Gap**:
  - 對「業界已廣泛使用之開源元件」給予免審查豁免。
  - 依賴項維護依賴軟性期望（「should use」、「where possible」）。
  - 例外缺乏結構化處置，未維護元件風險未被處理。
- **Candidate 表現**: 完全捕捉，明確辨識出 blanket exemption（全面豁免）的嚴重風險。

### 6. PW.8.1（可執行程式碼安全測試）
- **Golden Gap**:
  - 測試範圍允許由專案團隊依排程與資源妥協。
  - 具體測試型態（DAST, Pentest）為選配（「may include」）。
  - 問題修復為非強制性（「when practical」）。
- **Candidate 表現**: 完全捕捉，指出以專案時程作為測試範疇考量的政策漏洞。

### 7. RV.1.3（漏洞通報與處置）
- **Golden Gap**:
  - 依賴一般客服管道而非專屬通報途徑。
  - 評估與修復缺乏 SLA（「as soon as reasonably practical」）。
  - 外部揭露採個案處理，未定義流程與 PSIRT 角色。
- **Candidate 表現**: 完全捕捉，指出缺乏專屬管道與缺乏明確服務承諾（SLA）。

---

## 6. 推論邊界與歸屬審核 (Basis & Attribution Audit)

1. **Normative vs Derived Guidance 分立**:
   - Candidate 在每個 finding 中，均將 `nist_normative`（直接引述 NIST SP 800-218 v1.1 任務宗旨）與 `local_derived_guidance`（本地導引問題）明確分開。
   - 沒有將「必須具備 SBOM」、「必須使用 HSM 儲存金鑰」、「必須使用特定掃描工具」等技術細節假借 NIST 之名列為 normative requirement。
2. **Reviewer Inference 邊界守護**:
   - 針對文件第 9 節（Records 允許 email 確認），AI 能辨識其屬於 auditability / durability 議題，而非 NIST SSDF 7-task 的直接 normative 要求，守住了不越界推論的界線。
3. **Claim Boundary 完整性**:
   - 所有 finding 均宣告了對應之 `cannot_claim`，明確禁止因政策條款涵蓋而推導出「已合規」、「安全無虞」或「漏洞已修復」之結論。

---

## 7. 差量與異常分析 (Discrepancy Analysis)

- **Missed Gaps (遺漏缺口)**: `0`。Golden 中界定的主要政策脆弱點在 Candidate 中均有明確對應。
- **False Positives (誤報缺口)**: `0`。未將合法條款誤判為缺口。
- **Hallucinated Requirements (虛構規範)**: `0`。所有作為 normative basis 的要求均有 NIST SP 800-218 任務背書。
- **Overclaiming (過度宣稱)**: `0`。完全通過 S0-C Claim Scanner 檢驗。

---

## 8. S0 Exit Condition 判定 (Conclusion)

根據 S0-A、S0-B、S0-C 與 S0-D 的完整實驗成果：

1. **直接評估假設成立**:
   AI 能夠直接以權威規範（NIST SSDF）為 Authoritative Baseline，在不發明內部過渡 catalog（Normalized Practice Catalog）的情況下，對企業政策文件進行精準、客觀且具備可追溯性的差距分析。
2. **雙層防線有效**:
   - S0-C Linter 成功阻斷了語法結構、引用合法性與過度宣稱（Claim Boundary）。
   - S0-A 契約成功引導 AI 明確區分 `nist_normative`、`local_derived_guidance` 與 `reviewer_inference`，徹底解決了 LLM 容易「將自身最佳實踐推論冒充為規範條文」的核心痛點。
3. **S0 成果達成 Exit Condition**:
   - S0-A: Assessment Contract 完備。
   - S0-B: Golden Fixture 建立。
   - S0-C: Boundary Validator 上線並經單元測試與 CI 驗證。
   - S0-D: AI 語意評估完成，差距分析驗證通過。

**結論：Phase S0 圓滿完成，具備向後續階段（如多框架擴展或領域特定設定檔 Domain Profiles）推進的堅實基礎。**
