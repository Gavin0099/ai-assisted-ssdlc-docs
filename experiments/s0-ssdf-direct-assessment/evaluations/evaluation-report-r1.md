# S0-D-r1: Blind Generator + Independent Evaluator Report

## 1. 執行綜述 (Executive Summary)

本報告為 **Phase S0 (NIST SSDF Direct Assessment)** 的最終驗證產出。
依據 Review 指示，本輪評估捨棄了先前「同一上下文先讀 Golden 再生 Candidate」之污染流程，改採嚴格的 **Blind Generator + Independent Evaluator** 實驗架構：
1. **實體目錄與檔案集隔離 (Procedural & Directory File-Set Isolation)**：在獨立目錄 `C:\Temp\s0-blind-run-20260917\` 中僅放置 3 個權威輸入檔與中性 Prompt，無 `.git`、無 `golden/`、無歷史評估報告。
2. **全新獨立 Session (Fresh Blind Generator)**：由全新的 Subagent 獨立運行，未繼承母會話的討論脈絡。
3. **不可變凍結 (Candidate Immutability)**：Candidate 一次性生成並經 SHA-256 凍結，絕無事後人工編修。
4. **凍結 Evaluator Rubric (20 Golden Gap Atoms)**：依據 Golden `expected-assessment.yaml` 實際內容，建立並凍結 20 個 rationale-level gap atoms，徹底剔除先前任意湊成 21 個時誤入的非標準要求（如 PS.2.1 key lifecycle）。
5. **獨立 Evaluator 嚴格分軌核對**：評估者依據 Rubric 逐項比對 Gap Recall，並將 SLA、PSIRT、專屬通報管道、SBOM、DAST 等作為「Unsupported Attribution Probes」進行一級硬指標查核。

---

## 2. 運行與環境憑證 (Run Provenance)

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
  rubric_sha256: 73c3a359fedaf296530b0985d2e27cbc68a83ddd907a679927ceda2ade2e7038

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
  prior_conversation_isolation: isolated_fresh_subagent_session
```

---

## 3. 確定性硬閘門檢驗 (Deterministic Hard Gates)

| 檢驗項目 | 檢驗命令或方式 | 門檻標準 | 實際結果 | 狀態 |
| :--- | :--- | :--- | :--- | :--- |
| **S0-C Linter** | `python tools/validate_ssdf_assessment.py candidate-assessment-002.yaml` | `exit code 0 (PASS)` | `ssdf_assessment: PASS` | **PASS** |
| **Scope Completeness** | `set(candidate task IDs) == set(scope_tasks)` | 7/7 任務完全吻合 | 7/7 任務一一對應 | **PASS** |
| **Candidate Immutability** | `SHA-256(isolated_raw) == SHA-256(repo_copy)` | Exact byte match | `bcc2771e... == bcc2771e...` | **PASS** |
| **Unsupported Normative Attribution** | 逐項檢查 `nist_normative` 內容是否超越權威文本 | `0` | `0` | **PASS** |
| **Unsupported Derived Attribution** | 逐項檢查 `local_derived_guidance` 是否混入推論 | `0` | `0` | **PASS** |
| **Overclaims** | Claim Scanner 檢測禁止詞彙（否定句保護） | `0` 違法肯定句 | `0` | **PASS** |

---

## 4. 20 個 Golden Gap Atoms 逐項對照表 (Gap Recall = 20/20)

依據 `experiments/s0-ssdf-direct-assessment/evaluation-rubric/golden-gap-atoms-v1.yaml`：

| Atom ID | Task ID | Golden Expected Semantic | Candidate-002 獨立對應實質內容 | 判定 |
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

**Gap Recall 計算**:
$$\text{Gap Recall} = \frac{20 \text{ Matched Atoms}}{20 \text{ Golden Atoms}} = 100\%$$

---

## 5. 歸屬探針審查 (Unsupported Attribution Probes)

針對先前容易被 AI「以業界最佳實踐偷渡為規範要求」的常見探針進行嚴格審核：

1. **SLA / Timelines (RV.1.3)**:
   - `nist_normative`: 僅引用維護通報與修復政策及流程。未提 SLA。
   - `local_derived_guidance`: 嚴格對照 tasks.yaml 的 3 個問題（intake/triage, roles, operational process）。未提 SLA。
   - `reviewer_inference`: 未濫用。在 `assessment_rationale` 中客觀指出政策條文「fixed as soon as practical」過於籠統。
   - **判定**: **Clean Attribution (No Unsupported Attribution)**。
2. **Dedicated Channel / RFC 9116 / security.txt (RV.1.3)**:
   - Candidate 將其放置於 `basis[reviewer_inference]`，並在 `cannot_claim` 明確宣告：「This task finding does not require specific PGP keys, security.txt, or bug bounty programs in this S0 scope.」
   - **判定**: **Clean Attribution (Correctly Isolated as Inference)**。
3. **Software Bill of Materials / SBOM (PW.4.4)**:
   - Candidate 將 SBOM 放置於 `basis[reviewer_inference]`，並在 `cannot_claim` 明確宣告：「This task finding does not establish that an SBOM is required by NIST PW.4.4.」
   - **判定**: **Clean Attribution (Correctly Isolated as Inference)**。
4. **DAST / Dynamic Testing (PW.8.1)**:
   - Candidate 將 DAST 放置於 `basis[reviewer_inference]`，規範層面僅要求「executable-code testing」。
   - **判定**: **Clean Attribution (Correctly Isolated as Inference)**。
5. **Key Management / Lifecycle (PS.2.1)**:
   - Candidate 僅在推論層指出簽署發布 portal 建議，並在 `cannot_claim` 註明：「A code-signing policy statement does not prove key protection or verification behavior.」未假借 NIST 名義要求 HSM。
   - **判定**: **Clean Attribution (Correctly Isolated as Inference)**。

---

## 6. 綜合能力評估矩陣 (Performance Metrics Summary)

- **Scope Task Completeness**: `7 / 7` (100%)
- **Verdict Agreement**: `7 / 7` (100% - 全數為 `PARTIAL` 且 Review Queue 為 `needs_changes`)
- **Golden Gap Recall**: `20 / 20` (100% - 完整捕捉 20 個 rationale-level atoms)
- **Unsupported Normative Attribution**: `0` (硬指標達成)
- **Unsupported Derived Attribution**: `0` (硬指標達成)
- **Overclaim Count**: `0` (硬指標達成)
- **Candidate Immutability**: `Verified (SHA-256 Match)`
- **Blindness & Isolation Evidence**: `Adequate (C:\Temp Procedural & File-set Isolation)`

---

## 7. 結論與 Remote CI 交付狀態

1. **實質能力驗證**:
   本輪 S0-D-r1 在真正隔離、不可變凍結與忠實 20-atom Rubric 下，成功證明了：
   - AI 在無答案提示下，能精確指認出企業真實政策中的所有 20 個脆弱點。
   - AI 能嚴守契約邊界，將 SBOM、security.txt、DAST、金鑰保護等實踐明確區分為 `reviewer_inference`，徹底解決了先前將工程直覺混入 `local_derived_guidance` 的 attribution 漏洞。
2. **交付邊界確認 (Local vs Remote CI)**:
   - **Local Evidence**: Linter PASS，全專案 63 題單元測試 PASS。
   - **Remote CI Evidence**: 需透過開立 Pull Request 觸發 GitHub Actions。在 Remote CI 執行通過前，不將本地測試等同於 CI 通過。
3. **Phase S0 Exit 判定**:
   本評估報告已完備所有硬閘門與客觀度量，供 Repository Owner 進行最終 Exit 決策。
