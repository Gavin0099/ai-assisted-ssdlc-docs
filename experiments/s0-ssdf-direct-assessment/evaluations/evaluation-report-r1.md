# S0-D-r1: Blind Generator + Independent Evaluator Report

## 1. 執行綜述與評估設計 (Executive Summary & Experimental Design)

本報告為 **Phase S0 (NIST SSDF Direct Assessment)** 的盲測驗證報告。
為解決初次評估中的 **Test Contamination** 與 **Attribution Drift** 問題，本輪評估採用 **Blind Generator + Independent Evaluator** 架構：

1. **檔案集與實體目錄隔離 (Procedural & Directory File-Set Isolation)**：
   在獨立工作環境（`C:\Temp\s0-blind-run-20260917\`）中僅提供 3 個必要文件（`tasks.yaml`, `sample-company-ssdlc.md`, `assessment-contract.md`）與中性提示詞 `generator-prompt-v1.txt`。環境內無 `.git`、無 `golden/`、無歷史報告。
2. **獨立 Session (Fresh Blind Generator)**：
   由全新 Subagent 獨立運行，未帶入母對話歷史討論。
3. **產出不可變凍結 (Candidate Immutability)**：
   產出之 `candidate-assessment-002.yaml` 經 SHA-256 凍結，絕無人工事後編修，直接提交 Linter 檢驗。
4. **凍結 Rubric (20 Golden Gap Atoms)**：
   建立並凍結 `experiments/s0-ssdf-direct-assessment/evaluation-rubric/golden-gap-atoms-v1.yaml`。忠實還原 Golden 實際內容（PS.2.1 僅 2 條，剔除先前硬湊 21 條時誤加的 key lifecycle）。NIST SP 800-218 v1.1 為唯一權威來源，Rubric 僅為本地評估標準。
5. **獨立 Evaluator 嚴格判讀**：
   由評估者對照 Rubric 進行 Gap Recall 語意核算，並深入審查 `assessment_rationale` 自由文本中的推論越界現象。

---

## 2. 運行憑證與隔離證據 (Run Provenance)

```yaml
generator:
  model: Gemini 3.8 Flash (Medium)
  subagent_conversation_id: 748af680-ce89-4bb7-9bbc-3e1eea19b39e
  generated_at: 2026-09-17T18:24:42+08:00
  prompt_file: experiments/s0-ssdf-direct-assessment/evaluations/generator-prompt-v1.txt
  prompt_sha256: cdca89a629666cefb9d4d9faeb41fee9ac63a49fd1f649bc35744d1262d258fa
  output_file: experiments/s0-ssdf-direct-assessment/evaluations/candidate-assessment-002.yaml
  output_raw_file: experiments/s0-ssdf-direct-assessment/evaluations/candidate-assessment.raw.yaml
  output_sha256: bcc2771e54536f72689a397dfbecc9d9d043e641f54082d8918dd379b4cdd5a4

evaluator_rubric:
  file: experiments/s0-ssdf-direct-assessment/evaluation-rubric/golden-gap-atoms-v1.yaml
  rubric_id: S0-GAP-ATOMS-V1
  atom_count: 20
  rubric_sha256: ac471d96780354162e9c02a35fe0135ae3f05e6d4cb65bbe44d6342779c17282

inputs:
  tasks_yaml_sha256: c14cca5c19cc7dab923cdfd30ede68210f9be5281d0e00a97c936c218fce78c1
  company_ssdlc_sha256: 24925f9de00b34a6179d7c3043ab7f9817ba16de746a992be88f49f2fea03a7e
  assessment_contract_sha256: 49b582b2322d32064479c51d6d900fdc273ac3b28334febb6735a951df839558

isolation:
  enforcement_method: procedural_and_directory_file_set_isolation
  isolated_working_directory: C:\Temp\s0-blind-run-20260917\
  allowed_inputs:
    - tasks.yaml
    - sample-company-ssdlc.md
    - assessment-contract.md
    - prompt.txt
  golden_available_to_generator: false
  prior_evaluation_available_to_generator: false
  prior_conversation_isolation: isolated_fresh_subagent_session_runtime_reported
```

---

## 3. 確定性檢驗結果 (Deterministic Linter Verification)

執行命令：
```powershell
python tools/validate_ssdf_assessment.py experiments/s0-ssdf-direct-assessment/evaluations/candidate-assessment-002.yaml
```

**結果**: `ssdf_assessment: PASS`

- **S0-C Required Fields & Types**: 7 筆 finding 之 `assessment_rationale` 均為非空字串清單（scalar string 已被 Linter 禁止），`identified_evidence` 均具備 `type` 與 `source_ref`。
- **Scope Completeness**: 候選檔案中包含的 Task IDs 與標頭宣告之 `scope_tasks` 1:1 完全對應（7/7）。
- **Claim Scanner**: 無非法之合規（compliant/conformance）、安全（safe）、修復完畢（remediated）或無分母百分比宣稱。
- **Candidate Immutability**: 經比對 `C:\Temp\s0-blind-run-20260917\candidate-assessment.raw.yaml` 與 repo 內檔案，SHA-256 完全一致。

---

## 4. 20 個 Golden Gap Atoms 比對 (Evaluator-Scored Gap Recall)

> [!NOTE]
> 本項比對為 Evaluator 依據 `golden-gap-atoms-v1.yaml` 所進行的語意判定，非確定性程式碼自動產出。

| Atom ID | Task ID | Golden Expected Semantic | Candidate-002 獨立對應內容 | 判定 |
| :--- | :--- | :--- | :--- | :--- |
| **PO12-G1** | PO.1.2 | 「All software shall be secure」為高階口號，非具體可測試需求。 | 「aspirational goal ... does not define concrete, testable security requirements.」 | **MATCH** |
| **PO12-G2** | PO.1.2 | 需求記錄限於「known requirements」，缺乏系統化主動辨識。 | 「limited to 'Projects with known security requirements', leaving process ... unspecified for all scoped software.」 | **MATCH** |
| **PO12-G3** | PO.1.2 | 維護僅綁定重大變更（should），例外缺乏結構化審查與週期。 | 「limited to major product changes using advisory wording ... exception approval lacks objective criteria and lifecycle records.」 | **MATCH** |
| **PO31-G1** | PO.3.1 | 工具類別有名稱但屬選配（may be enabled），未規定必要條件。 | 「uses permissive language ('may be enabled when appropriate') instead of specifying needed tool types based on defined risks.」 | **MATCH** |
| **PO31-G2** | PO.3.1 | 團隊各自選工具，未定義整合點或最低基準。 | 「delegated to individual teams without defining integration points into build systems or mandatory baseline configurations.」 | **MATCH** |
| **PO31-G3** | PO.3.1 | 工具失敗審查（should）缺少處置標準或阻擋門檻。 | 「requirement that tool failures 'should be reviewed before release' does not define triage criteria, release-blocking thresholds, or formal exception workflows.」 | **MATCH** |
| **PS21-G1** | PS.2.1 | 程式碼簽章附帶條件「when applicable」且未定義。 | 「conditioned on undefined applicability ('when applicable') without defining criteria ...」 | **MATCH** |
| **PS21-G2** | PS.2.1 | Checksum 僅依客戶要求提供，非獲取者預設驗證機制。 | 「provided only upon customer request ... failing to establish a default, systematic integrity verification mechanism for all software acquirers.」 | **MATCH** |
| **PW11-G1** | PW.1.1 | 威脅建模為選配，觸發條件留給審查者自由裁量。 | 「optional practice ('may be used when the reviewer considers it necessary') rather than a defined risk-modeling requirement.」 | **MATCH** |
| **PW11-G2** | PW.1.1 | 「complex security-sensitive features」未客觀定義觸發門檻。 | 「apply only to unspecified 'complex security-sensitive features' without objective thresholds.」 | **MATCH** |
| **PW11-G3** | PW.1.1 | 僅記於專案筆記，未定義風險如何連結緩解或追蹤處置。 | 「informal 'project notes' does not ensure that identified architectural risks are systematically linked to mitigations or tracked to closure.」 | **MATCH** |
| **PW44-G1** | PW.4.4 | 「stable」、「commonly adopted」非安全驗證客觀標準。 | 「rely on subjective concepts ('stable and commonly adopted') rather than defined security requirements or EOL evaluation.」 | **MATCH** |
| **PW44-G2** | PW.4.4 | 業界常用開源元件給予免審全面豁免，未一致驗證安全要求。 | 「explicitly exempts widely used open-source components from security review, directly bypassing the requirement to verify ...」 | **MATCH** |
| **PW44-G3** | PW.4.4 | 重大弱點例外未定義審查與紀錄生命週期。 | 「exceptions for critical vulnerabilities do not specify documentation or lifecycle requirements.」 | **MATCH** |
| **PW81-G1** | PW.8.1 | 未清楚區分可執行代碼測試與靜態審查之必要性。 | 「fails to specifically evaluate or select executable-code testing versus static review.」 | **MATCH** |
| **PW81-G2** | PW.8.1 | 測試範疇允許團隊依排程與資源妥協，缺乏最低標準。 | 「Testing scope and methodology selection are permissive ... and can be compromised by schedule or resource constraints without governance review.」 | **MATCH** |
| **PW81-G3** | PW.8.1 | 問題修復為「when practical」，發行前處置要求模糊。 | 「Remediation ... is non-mandatory and lacks defined timelines or gating ('should be tracked and resolved when practical').」 | **MATCH** |
| **RV13-G1** | RV.1.3 | 政策已辨識通報路徑與評估責任，非完全缺失。 | 「acknowledges vulnerability reporting and internal escalation ...」 | **MATCH** |
| **RV13-G2** | RV.1.3 | 修復為盡快、揭露為個案處理，缺乏明確營運流程。 | 「remediation commitments lack defined timelines ... ('fixed as soon as reasonably practical') ... external disclosure is handled ad hoc ('case by case') without documented disclosure processes ...」 | **MATCH** |
| **RV13-G3** | RV.1.3 | 未清楚定義協調整個通報與修復生命週期的角色與權責。 | 「without documented disclosure processes, public communication criteria, or designated roles.」 | **MATCH** |

**Evaluator-scored Gap Recall**:
$$\text{Evaluator-scored Gap Recall} = \frac{20 \text{ Matched Atoms}}{20 \text{ Golden Atoms}} = 100\%$$

**Verdict Agreement**:
$$\text{Verdict Agreement} = \frac{7 \text{ Matched Tasks}}{7 \text{ Scope Tasks}} = 100\% \quad (\text{全數判定為 PARTIAL，Review Queue 為 needs\_changes})$$

---

## 5. 核心研究發現：推論歸屬偏誤與自由文字逃逸 (Basis Attribution & The Semantic Escape Hatch)

> [!CAUTION]
> **重大發現：自由文本 `assessment_rationale` 成為 Reviewer 推論的語意逃逸通道 (Semantic Escape Hatch)**

在本次評估中，若僅檢視結構化之 `basis` 欄位：
- AI 成功將 SBOM、DAST、security.txt 等概念歸類為 `reviewer_inference`。
- 在 `nist_normative` 與 `local_derived_guidance` 中，AI 未假造未授權之條文。

**然而，深入審查 `assessment_rationale` 自由文字後，發現了明確的未標註推論滲透 (Unlabeled Reviewer Inference)**：

1. **PS.2.1 案例**:
   Candidate 在 rationale 中寫道：
   > 「Code signing is conditioned on undefined applicability ('when applicable') **without defining criteria or key protection controls**。」
   - *分析*：`key protection controls` 並非 NIST PS.2.1 或本地導引的明確要求（Golden `cannot_claim` 更明言不涵蓋 signing-key protection controls）。AI 在 rationale 中將其作為指責政策不全的依據。
2. **PW.8.1 案例**:
   Candidate 在 rationale 中寫道：
   > 「Remediation of discovered security issues is non-mandatory and lacks **defined timelines or gating** ('should be tracked and resolved when practical')。」
   - *分析*：本地導引僅要求「blocking or follow-up」，並非強制 gating，但 AI 自然地將「gating」視為缺口。
3. **RV.1.3 案例 (最直接的證據)**:
   Candidate 在 rationale 中明確指稱：
   > 「Vulnerability remediation commitments lack defined timelines, **severity-based remediation SLAs**, or tracking procedures ('fixed as soon as reasonably practical')。」
   - *分析*：Candidate 雖未把 SLA 寫入 `local_derived_guidance`，但**在 `assessment_rationale` 中直接指責政策缺少「severity-based remediation SLAs」**。NIST RV.1.3 與 Golden `cannot_claim` 明確聲明本審查不要求 remediation SLA。這證明 AI 在論述缺口時，仍自動將業界最佳實踐（SLA）帶入作為缺失判定。

### 歸屬審計結論：
- **Unsupported Normative Attribution (in `basis` section)**: `0` (PASS)
- **Unsupported Derived Attribution (in `basis` section)**: `0` (PASS)
- **Unlabeled Reviewer Inference in `assessment_rationale`**: **DETECTED (3 處: PS.2.1, PW.8.1, RV.1.3)**

### 架構啟示 (Architectural Limitation):
> **目前的資料模型中，`basis` 是 finding-level 的獨立清單，而 `assessment_rationale` 是另一組非結構化的字串清單，兩者之間缺少語句級的關聯綁定（Statement-to-Basis Linkage）。**
> 結構型 Linter 能阻斷顯式的 Forbidden Claim 關鍵詞，但無法檢驗 `assessment_rationale` 內的每一句話是否超越了所宣告的 Normative / Derived 邊界。未來若要杜絕此現象，需在 Schema 層引入結構化關聯（例如要求每句 rationale 均綁定對應的 basis ID）。

---

## 6. 綜合指標總結 (Summary of Metrics & Gates)

| 指標類別 | 指標名稱 | 實際度量 | 判定與說明 |
| :--- | :--- | :--- | :--- |
| **Hard Gate** | S0-C Linter 檢驗 | `PASS` | 通過語法、Schema 與 Claim Scanner 檢驗 |
| **Hard Gate** | Scope Completeness | `7 / 7` | 7 項任務 1:1 完整覆蓋 |
| **Hard Gate** | Candidate Immutability | `Verified` | 原始生成輸出 SHA-256 凍結，無人工編輯 |
| **Hard Gate** | Overclaim Count | `0` | 無合規、安全、無漏洞或無分母百分比宣稱 |
| **Attribution Audit** | Basis 結構區塊歸屬 | `PASS (0 越界)` | SBOM / DAST / security.txt 正確標記為 Inference |
| **Attribution Audit** | Rationale 自由文本歸屬 | **DETECTED (3 處)** | 在 PS.2.1 / PW.8.1 / RV.1.3 的 rationale 中滲透了 key protection / gating / SLA 推論 |
| **Capability Metric** | Verdict Agreement | `7 / 7 (100%)` | 7 項任務全數判定為 `PARTIAL` / `needs_changes` |
| **Capability Metric** | Evaluator-scored Gap Recall | `20 / 20 (100%)` | 20 個 Golden Gap Atoms 在無提示下均被獨立捕捉 |

---

## 7. 交付狀態與推進建議 (Delivery Status & Next Steps)

1. **Local Evidence Status**:
   - 本地 Linter 與 35 題 Linter 單元測試全數 PASS。
   - 全專案 63 題單元測試持續 100% PASS。
2. **Remote CI Status**:
   - 需透過在 GitHub 開立 Pull Request，方能觸發 GitHub Actions 執行並取得遠端驗證證據。
   - 本地單元測試不可替代 Remote CI 執行。
3. **Phase S0 狀態**:
   - `PLAN.md` 保持 `Phase S0 [ ]` 與 `S0-D [ ]`，明確標記為「Local verified, pending PR remote CI and owner exit decision」。
   - 由 Repository Owner 在檢視本份誠實且具備歸屬發現的評估報告，並於 Remote CI 通過後，進行最終之 S0 Exit 決策。
