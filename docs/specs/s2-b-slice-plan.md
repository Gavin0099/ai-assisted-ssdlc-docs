# S2 下一步與切片規劃

狀態為 **AUTHORIZED SERIAL DELIVERY**。使用者已授權逐刀實作、PR、獨立審查、Codex review 與通過後合併；每刀合併後從最新 main 開始下一刀。授權不代表 WIP 程式已接受，也不能替代真實 Pilot 的必要輸入。

## 目前位置

- B0 已由 PR #21 合併於 `df57edb`；B1 已由 PR #22 合併於 `ef0015c`，各自的 exact-head review、CI 與 main 檢查皆通過。目前進入 B2，後續維持逐刀 gate。

- REPORT-4E 工具已合併；全域 skill 已安裝並重新產出真實報告。網頁視覺／互動仍待人工驗收，另外追蹤，不阻擋純靜態 S2 core 的開發。
- S2-A 已凍結。`origin/main` 的規格 Git blob 與 `dece98a8513000ea3e2e63391eabca2b6b9add3f` 相同。
- 本次讀取的 main 為 `a5a32163e153b247e5714399ce3d615f70937229`，候選為 `wip/s2-b-implementation-candidates` 的 `663caca91a7eb06b10a7c1e5a27f10caf97ad9b7`。
- WIP 已有 matcher、contract、product manifest／resolver、evaluator 與測試；其內附規格比凍結版舊。[B0 對照紀錄](s2-b0-candidate-audit.md) 保存本次符合證據、缺口及後續處置。

正式行為依 [凍結 S2-A](s2-a-implementation-evidence-spec.md)。本規劃不改它，也不將舊 WIP 規格當成新實作的依據。

## 開發順序與每刀停止點

| Slice | 要解決的問題 | 主要範圍 | 驗收後的停止點 |
| --- | --- | --- | --- |
| **S2-B0 — WIP 對照與移植清單** | 現有候選哪些可用、哪些缺檢查、測試是否真的驗證凍結規格？ | 規格／候選函式／測試對照；建立 REUSE、FIX、REWRITE、DEFER 清單與依賴圖。 | 交付對照紀錄與第一刀檔案清單；不移植程式。 |
| **S2-B1 — 基礎型別與封閉 Matcher** | YAML／JSON 是否會因型別或 parser 行為而判錯？ | Matcher enum、typed scalar、assertion、五種 matcher、path grammar 與 sanitized result；候選位置 `tools/implementation_matchers.py`。 | 合成 pass/fail fixtures 通過；不讀產品 repo、不做政策 admission 或 evaluator。 |
| **S2-B2 — 規則與政策來源 Admission** | 規則能否確實連到同一版政策 finding，且不能憑旗標相信來源？ | Expectation／Rule 模型、canonical digest、唯一 ID、參照與 evidence-kind 完整性；重用 S1 驗證鏈核對 policy identity／corpus；候選位置 `tools/implementation_contracts.py`。 | 非法來源、digest、跨 Task 參照與多義 finding 均拒絕；不讀產品 evidence、不產報告。 |
| **S2-B3 — Product Manifest 與固定 Corpus** | 工具是否只讀指定 commit 與允許範圍的檔案？ | Product manifest parser/schema、include/exclude、Git object materialization、snapshot integrity；候選位置 `tools/validate_product_target_manifest.py`、`tools/product_corpus_resolver.py`。 | 未提交變更不影響結果，越界拒絕、symlink 不納入；不執行規則或發出最終報告。 |
| **S2-B4 — Mechanical Evaluator** | 找到、缺少、不符與不適用是否會被混成同一種結果？ | 四種 verdict、selector 與 ANY/ALL、refs、node locator、sanitized discrepancy、deterministic item ordering；候選位置 `tools/implementation_evaluator.py`。 | 每條 rule 有獨立且合法的 item；不自動合成 Task verdict、priority 或 queue；不建立 CLI/UI。 |
| **S2-C1 — 雙邊來源與完整 Record** | policy/product 的身分與完整性可否分開核對並綁到同一份結果？ | Orchestrator、聚合 record、雙邊 provenance；identity-only uncertainty 可 opt-in，確認 mismatch／digest 錯誤仍拒絕。 | 合成雙 repo 驗證完整 record 與五項 claim boundaries；不寫報告檔、不接 HTML。 |
| **S2-C2 — CLI、JSON／Markdown 與 Golden E2E** | 使用者執行一次，能否得到可重現且不掩飾錯誤的結果？ | CLI、deterministic renderer、atomic file output、合成 Golden E2E；覆蓋 S2-A Scenario 1–12。 | 合法負向結果 Exit 0，非法輸入 Exit 1 且既有輸出不變；不使用公司真實 repo、不接 S1 HTML。 |
| **S2-P1 — 真實產品 Pilot** | 已驗證工具能否在固定真實範圍內提供有來源的結果？ | 先固定有效 S1 assessment、policy/product commits、manifest 與人類明確制定及核可的 expectation/rule，再執行。 | 保存逐 rule 事實、限制與獨立人工判讀；不改產品、不觸發 CI、不自動修正或同步 S1。 |

B0 先確認模組依賴；若候選有跨 slice 的 imports，只移植當刀需要的基礎型別與 helper，不能為了讓 import 成功一次搬完整 WIP。上表是工作邊界，新增 module 或拆檔需求須由 B0 對照提出理由。

每刀都先完成相稱測試與獨立 review，開 PR 並處理 Codex findings；最新 head 的審查與 CI 通過後才合併。合併 gate 關閉後繼續下一刀，不逐刀重問授權。真實 Pilot 若缺產品版本或人類制定的規則，保持待輸入，不由 AI 補猜。對照與規劃不代表下一刀已被執行。

## B0 最初授權範圍與停止點

**目的**是將現有候選對照凍結規格，形成可執行的移植順序，不重新設計 S2。

允許讀 main 與候選 Git objects、核對既有測試、在隔離環境執行相稱的候選測試，並新增一份短對照紀錄。

每個對照項目至少保存：規格條款、候選位置、現有符合證據、缺口／未驗證部分、處置、所屬 slice、驗收案例。REUSE 需要符合證據；既有測試通過仍須核對 expected value 是否來自凍結規格。沒有執行的案例明寫 NOT RUN。

必須核對下列風險：

1. Policy assessment、manifest、corpus 的實際驗證鏈；不得相信輸入的 `provenance_verified: true`。
2. Expectation／Rule 的 digest、ID、Task 與 evidence-kind 參照完整性。
3. YAML 1.2、duplicate keys、單文件、typed scalar、wildcard 與 ANY/ALL 的區別。
4. Product authority surface、固定 commit、symlink、Git bytes 與 snapshot integrity。
5. 四種 evidence verdict 的欄位 invariant、locator、sanitized discrepancy 與順序。
6. Identity-only opt-in 與已確認 mismatch／完整性錯誤的區分。
7. Shared S1 resolver 的候選修改是否必要，以及會影響哪些 S1 regression tests。
8. S2-A Scenario 1–12 各自應在哪一刀驗證；不得因舊 WIP 只有部分案例就縮小驗收。

禁止直接 merge/cherry-pick 整個 WIP、改凍結 S2-A、S1 assessment/schema、REPORT-3B、report renderer、queue、治理框架或 hooks。不要搬入 WIP 的舊規格或治理變更，不使用真實產品執行紀錄，不以本次 review 宣稱產品有做到 SSDLC。

**完成條件**：上述八項有位置、處置與證據界線，Scenario 1–12 完成 ownership mapping，第一個實作 slice 的依賴／檔案／測試清單明確。B0 不含 B1 程式；B0 審查、CI 與合併完成後，另外開 B1 branch。

## 真實 Pilot 前的兩個界線

目前人工報告是 32-file corpus，舊 machine assessment 是 18-file corpus。真實 S2 必須明確選擇並驗證政策 assessment identity；不能用 HTML 上的 7 COVERED 冒充已同步的 machine assessment，也不要求先自動將舊結果改成 COVERED。

S2-A 的 scope 是 `PO.3.1`、`PW.4.4`、`PS.2.1` 三題與靜態 repo evidence。安全工具配置存在，不代表 CI 已成功執行；lockfile 存在，不代表套件安全；簽章腳本存在，不代表 release 已完成簽章。真實執行紀錄的驗證需另定範圍，不能在這系列偷偷擴進來。
