# S2-B0 候選程式對照

B0 只回答現有 WIP 哪些可以沿用、哪些必須修正；沒有移植 production code，也沒有接受整份 WIP。實作與合併順序依 [slice plan](s2-b-slice-plan.md)。

## 固定依據

- 公開 main：`a5a32163e153b247e5714399ce3d615f70937229`。
- 唯一行為依據：[凍結 S2-A](s2-a-implementation-evidence-spec.md)，Git blob 與 `dece98a8513000ea3e2e63391eabca2b6b9add3f` 相同；SHA-256 `55360c62ff986cfffe8cd8afaf09d75827f3a8c057e543792f63dea09bca6759`。
- 候選：`wip/s2-b-implementation-candidates`，`663caca91a7eb06b10a7c1e5a27f10caf97ad9b7`。下表行號只指此 commit。
- 候選附帶的 S2-A 比凍結版舊，不移植其規格、治理、hook 或 memory 變更；不 merge/cherry-pick 整個 WIP。

## 處置與驗收

REUSE 表示已有可重播的符合證據，仍須通過當刀 regression；FIX 表示保留主體並修缺口；REWRITE 表示該部分的假設／測試 oracle 必須換掉；DEFER 表示由後續 slice 實作，本次沒有驗證完成。

| 風險／規格 | 候選位置與現有證據 | 缺口或未驗證部分 | 處置／owner | 驗收 |
| --- | --- | --- | --- | --- |
| Policy admission，§4.1 | `implementation_contracts.py:721` 實際 S1 admission，`:657/:677` identity/finding/source 比對；tests `:380/:477/:498` | `:424` 的 admission token 不足以防止 replace 後的 policy source 改寫及重算 digest | FIX / B2 | 原始 manifest + 真實合成 Git snapshot；已 admission 的模型替換 policy source 也要拒絕 |
| IDs、digest、Task、evidence-kind，§4.1 | `implementation_contracts.py:159/:193/:543` 的 shape/serializer/IDs；tests `:241/:247` 固定 golden | admission `:693–702` 尚未核對 kind；`implementation_evaluator.py:239` 僅做 rule kind 屬於 declared kinds 的單向檢查；contracts `:356` 接受空 selector 模型在重新計算 digest 後繞過 admission | FIX / B2 | evidence-kind 雙向完整性、未知 key、duplicate ID、跨 Task、篡改模型全部拒絕 |
| YAML/JSON/path/typed scalar，§4.1 matcher | `implementation_matchers.py:138–149` integer resolver；16 個 matcher tests | `012`、`0b10`、`1_000` 的 implicit Core 解析不符規格；既有 numeric test 也使用錯誤 oracle | FIX resolver + REWRITE numeric oracle / B1 | 以 YAML 官方 Core resolution 表及 frozen scalar/path 規則建立 pass/fail；保留 timestamp 不可比較的 frozen 應用規則 |
| Product snapshot，§4.2 | `validate_product_target_manifest.py`、`product_corpus_resolver.py`；22 個 tests，固定 commit 與 golden bytes/digests、exclude、identity、Git symlink mode 拒絕均執行 | snapshot 篡改、完整 path 邊界與新 frozen semantics 仍需補測；OS symlink 建立在 Windows 跳過 | REUSE manifest/Git materializer；FIX admission integrity / B3 | 工作目錄變更不能影響 pinned bytes；拒絕越界、錯 digest；Linux CI 執行 OS symlink fixture |
| Four verdicts、refs、locator、sanitized output，§4.3 | `implementation_evaluator.py:169/:254/:290/:319`；tests `:275/:295/:329/:375` | `:119/:124` item 接受可變 list refs；`:146/:158` discrepancy path 可越界或與 refs 不符 | FIX / B4 | constructor 拒絕非法狀態與 raw-value 洩漏；refs、locator、順序、file 與 node 量化分開 |
| Identity uncertainty vs integrity，§5 | 候選未有完整 dual provenance orchestrator | `UNVERIFIED` opt-in 不能吞掉 manifest 缺失、digest 錯誤或確認身分 mismatch | DEFER / C1 | frozen Scenarios 5/7/8/11/12，default 拒絕與明確 opt-in 分開 |
| Shared S1 resolver | `repo_corpus_resolver.py` 的 Protocol/Generic 註記，32 insertions / 7 deletions；runtime body 無改動 | 暫無證據需要整份 type refactor 才能讀 Product manifest | DEFER necessity decision / B3 | 只保留實際需要的最小相容修改；完整 S1 resolver/orchestrator regression 不退化 |
| Aggregate/CLI/serialization，§4.3/§5 | WIP 尚無完整 record、CLI、atomic output | 尚未執行 scenarios 1–12 的完整兩 repo E2E，不能將 unit PASS 稱為 S2 完成 | DEFER / C1–C2 | record 綁所有 identity/digest；CLI 合法負向 Exit 0、非法 Exit 1 且舊輸出不變 |

Core numeric expected values 來自 [YAML 1.2.2 官方規格 §10.3.2](https://yaml.org/spec/1.2.2/#1032-tag-resolution)，其規範行為與 1.2 相同。decimal 允許前導零；binary 與含底線的 plain scalar 不在 implicit Core numeric 規則中，應解析為 string。B1 不擴張至任意 YAML dialect。

## 實際執行證據

候選以 Git archive `core.autocrlf=false` 匯出到隔離暫存目錄，不讀原本 dirty checkout 的程式。

- `python -X utf8 -m unittest discover -s tests -p test_implementation_*.py -v`：43 run / 43 pass。
- `python -X utf8 -m unittest discover -s tests -p test_product_*.py -v`：22 run / 21 pass / 1 Windows OS symlink privilege skip。合計 65 run / 64 pass / 1 skip。
- 獨立 matcher probe：`012 → INTEGER 12`、`0b10 → STRING "0b10"`、`1_000 → STRING "1_000"` 均應通過，但候選三項均 false。這說明舊測試全過仍可能使用錯誤 expected value。
- 獨立 contracts/evaluator probe：缺少已宣告 kind 的 rule、admitted 空 selector、admitted source 篡改、可變 item refs、越界／不相符 discrepancy path，五項候選均接受；列入 B2/B4 regression。
- 尚未執行：移植後 regression、完整 aggregate/CLI、真實產品 Pilot。以上只是候選診斷，不是正式 S2 或產品驗證結果。

獨立審查在原生 Linux 另跑 contracts/evaluator 27/27 PASS 並重現上述五項缺口。既有 evaluator tests `:423/:494` 只保留舊 digest，需補重算 digest 的篡改案例；contract test `:316` 的適用性 rejection 也被舊 digest 擋住，不能視為必填理由已驗證。B2 須保存實際 policy admission 的 identity/integrity/reason，讓 C1 可直接使用，不重新猜測 provenance。

## 依賴與 Scenario ownership

`B1 matchers → B2 policy/rules → B3 product snapshot → B4 items → C1 record → C2 CLI/E2E → P1 real Pilot`。

B2 不依賴 product repo；B3 不需要 evaluator。WIP evaluator imports 這些後續模組，因此不能為了讓 B1 import 成功就搬完整 WIP。

| Frozen Scenario | 最早驗證層 | 完整驗收層 |
| --- | --- | --- |
| 1 YAML match | B1 / B4 | C2 |
| 2 Missing evidence | B4 | C2 |
| 3 Discrepancy | B4 | C2 |
| 4 Not applicable | B2 / B4 | C2 |
| 5 Unverified rejected by default | C1 | C2 |
| 6 Multiple rules, no Task rollup | B4 / C1 | C2 |
| 7 Identity-only opt-in | C1 | C2 |
| 8 Missing Product Manifest still fatal | B3 / C1 | C2 |
| 9 ANY/ALL files vs wildcard nodes | B1 / B4 | C2 |
| 10 Typed scalar, no coercion | B1 | C2 |
| 11 Duplicate/integrity failure before write | B1 / B2 / B3 / C1 | C2 |
| 12 Confirmed identity mismatch cannot opt-in | B2 / B3 / C1 | C2 |

## B1 最小移植清單

只新增 `tools/implementation_matchers.py` 與 `tests/test_implementation_matchers.py`。使用現有 PyYAML，不新增 dependency/schema/CLI。保留 enum、strict scalar/assertion 與五種 matcher；修 Core resolver 並補 specification-derived regression，重播舊候選應失敗、新程式應通過。驗證 duplicate keys、single document、recursive alias、invalid grammar、RFC 6901、wildcard node order、typed comparison、sanitized output；不讀產品 repo 或自動產生人類 policy expectations。

B0 的 PR 只交付本紀錄與 roadmap/PLAN/canonical milestone companion。B0 合併後再開始 B1；待每刀最新 PR head review、CI 與合併完成才繼續。真實 P1 的產品／commit／人類規則尚待使用者指定，不從既有 COVERED 推導。
