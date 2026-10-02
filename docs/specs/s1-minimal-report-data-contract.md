# REPORT-3B — Minimal Report Data Contract

版本：0.1｜2026-10-02｜狀態：ACCEPTED / FROZEN（完成使用者指定的四項修正）

**本 contract 保留 assessment 本體，用獨立補充資料完成報告。** D1 放 Task semantic supplement，D2 放 report/action，D3 放 source/corpus，D4 放 review lifecycle。四類資料各有用途，不能濃縮成「是否通過」或變成一個新的 assessment schema。

這次完成資料 contract，沒有建立實際 `report-data.json`、`review-lifecycle.json`、可執行 schema 或 Python model；沒有修改 validator、Review Engine、HTML converter、queue 或 S2，也沒有轉寫／同步 REPORT-2 人工結果。使用者 review 指定的兩個必要修正與兩個 clarification 已納入；依其修完後 freeze 的指示，本文作為下一刀的實作依據。接受此 contract 不代表接受 REPORT-2 的人工判定或證明新模型已可執行。

依據為已接受的 REPORT-3A、REPORT-1 rubric、呈現規則 v1.4、[S0 contract](../../experiments/s0-ssdf-direct-assessment/assessment-contract.md) 與 [S1-D 維度保留規則](s1-d-review-engine-spec.md)。遇到衝突時保留既有 verdict、basis、evidence strength、queue 與 cannot claim，不能以新報告格式覆蓋。

交付說明：前三份文件及 branch-16 人工報告屬先前本地審閱資料，未納入這次 REPORT-4A PR，因此保留名稱與歷史來源描述，移除尚未交付的相對連結。以下 v0.1 欄位、限制與 C1～C8 未變更；REPORT-4A 的實作進度另見 [驗證說明](report-4a-validation-notes.md)。

## 1. 最小邊界與資料來源

REPORT-3 系列共用原則是 **REPORT-4 若必須重新做 semantic inference 才能產生欄位，就算 NEED**。分析／審查階段負責記錄分類、結論與改法；renderer 只讀已記錄資料，查表、排序、計數與排版。

| 資料 | 放哪裡 | 負責什麼 |
| --- | --- | --- |
| 選定的 assessment | 沿用 S0／S1 contract 的獨立檔案 | 保存完整 Task 結果與原有各評估維度 |
| Task supplement、Action、Source authority | 同版本報告目錄的 `report-data.json`，內部分成三組紀錄 | 補足 D1～D3，不覆寫 assessment |
| 人工接受／機器同步關係 | 同目錄的 `review-lifecycle.json` | 引用前述內容，保存 D4；不承載 verdict |
| 三層 Markdown、HTML | 沿用既有檔名、模板與呈現規則 | 輸出與閱讀入口；網頁不寫回資料 |

將 lifecycle 分開，是為了讓接受紀錄能綁定 assessment 與 report data 的固定內容，避免把接受證明寫回它自己要證明的內容指紋。這兩份補充資料不是新的審查引擎，也不是議題管理平台。

共同引用 `ArtifactRef` 僅含 `path` 與 `sha256`：位置用來取得已授權的本地檔案，SHA-256 綁定其原始 bytes。相對位置以引用檔所在目錄解析；不能只靠檔名或 report ID 證明是同一版本。I/O 仍須遵守既有安全邊界，不因此授權讀取任意私人檔案。實際檔案不可取得或指紋不同時，不能把該引用當作已核驗。

**ArtifactRef 的 path 只允許相對路徑，禁止 absolute path（含磁碟機／UNC／根目錄路徑）及 `..` 路徑段。** 允許的 report root 由呼叫端依已授權範圍固定，不能由 sidecar 自行擴大；解析後的實體檔案必須仍在該 root 內，不得藉 symlink、junction 或 path traversal 越界。違反時須在讀取檔案內容前拒絕。公司 `source_ref` 是來源 locator，不能拿它直接開啟任意工作目錄檔案。

`report-data.json` 的最小 envelope 如下，不複製 assessment 的 target 或結果：

| 欄位 | 內容 |
| --- | --- |
| `contract_version` | 本 contract 採 `0.1`；只表示報告補充 contract，不改 assessment 版本 |
| `report_id` | 沿用該次報告識別；相同 ID 不等於相同內容或相同 corpus |
| `assessment_ref` | 本次畫面要顯示的完整、結構化 assessment 的 ArtifactRef |
| `corpus_metadata_ref` | 既有 corpus metadata 的 ArtifactRef；commit、manifest／corpus digest 須與選定 assessment 相符，供文件成員與指紋查表 |
| `task_supplements` | D1 紀錄；依選定 assessment 的 finding ID 綁定 |
| `actions` | D2 紀錄，或 `null` 表示尚未整理 |
| `auxiliary_sources` | 本次已明確授權且固定的輔助來源清單；每筆含檔案層級 `source_ref` 與固定本地副本的 `artifact_ref`，沒有時為 `[]`；只供 D2 location 查找，不擴大 assessment corpus |
| `source_authority` | D3 紀錄；每個 corpus 成員有一筆，可明示未收集 |
| `retained_content_refs` | 需原樣保留的既有摘要／逐份評語／歷史附錄 ArtifactRef 清單；不拿其中自由文字推定 Task 或 Action |

選定 assessment 的 `id`、baseline、repo、commit、manifest／corpus digest、Task 範圍與原值都從它本身取得。已有人工結果但尚未形成這種結構化檔案時，不能假裝 `assessment_ref` 已存在，也不能以 Markdown 覆寫舊 machine assessment 的值。

assessment 與 corpus 的來源驗證仍沿用 S1-C／S1-D 既有邊界；metadata 的自報值相符，不取代實際來源驗證，也不新增 quote/span 能力。retained content 須標示它原本的範圍，歷史內容不納入本次 Task／Action 統計，不覆蓋本次結果。

## 2. D1 — Task semantic supplement 放在 sidecar

**本 contract 選 sidecar，不改 assessment schema。** 它只記錄 assessment 沒有的分類及明確來源關係；不存在獨立的 coverage override。

| 欄位 | 最小內容與限制 |
| --- | --- |
| `finding_id` | 選定 assessment 中的一個 task finding；不能只用 Task ID 對上不同版本 |
| `document_refs` | 審查者明確列出的相關公司文件／段落；用於 D3 顯示，不能從 rationale 猜主要來源 |
| `gap_items` | 已確認分類的缺口清單；`[]` 表示在記錄的範圍內未發現，`null` 表示尚未完成拆分 |
| `improvement_items` | 已確認分類的可選改善清單；`[]` 表示本次未另列，`null` 表示尚未完成拆分 |

每個 gap／improvement item 只含 `text`、`source_refs`、`basis_refs`。`source_refs` 使用既有 contract 允許的公司來源參照；缺少內容的理由仍沿用 finding 的 rationale，不造出不存在的檔案或段落。`basis_refs` 是同一 finding 原始 basis 陣列的整數索引清單，以 0 起算，須在範圍內；引用綁定 assessment 原始 bytes，不能指向排序後的另一份 review view。依據仍沿用三種 basis，不新增第四種。

缺口的分類紀錄必須有既有 NIST Task 要求與來源對照支持；只有 reviewer inference 不足以建立必要要求。Improvement 不得單獨降低 verdict。沒有來源可確認而記為 UNRESOLVED 時，保留原 cannot claim；不得把資料不足寫成「無缺口」。`<corpus>#unmentioned` 僅沿用 S1-C 已允許的 finding 情況，不擴大為任意觀察的來源。

每個 task finding 最多一筆 supplement；新格式完整輸出須能對應所有選定 task findings。缺少一筆或分類為 `null`，顯示尚未整理，不能當成 `[]`。`document_refs` 的檔案部分必須對到同 corpus；只有行號／段落定位並不宣稱 quote/span 已驗證。

**Renderer 不得由 rationale 自行推論 Gap / Improvement，也不得根據 basis、queue、Action 或 verdict 重新分類。** 分類與原 verdict 若在語意上有爭議，留給審查者處理；renderer 不自行修正任何一側。

兩份已記錄資料仍須符合基本 consistency invariant：`COVERED + gap_items 非空`，以及 `PARTIAL + gap_items = []`，都直接矛盾，必須拒絕完整產出並交回審查。這是在檢查既有紀錄，不是由 verdict 推導 gap；validator／renderer 不得自動清空 gap、補 gap 或改判。`gap_items = null` 仍表示未完成拆分，按 §6 處理，不當作無缺口。

## 3. D2 — Engineer Action 是獨立紀錄

Action 沒有 `task_id` 必填或 `coverage_verdict` 欄位。它可與零個、一個或多個 finding／observation 有追溯關係，但這個關係不使 Action 變成 NIST 正式要求。

| 欄位 | 最小內容與限制 |
| --- | --- |
| `action_id` | 沿用穩定 E-01～E-14 等 ID；只在同一報告追蹤系統內識別，不因改名重編 |
| `group`、`kind` | 明列 A／B／C，以及人類可讀的問題性質；不是 Task 判定 |
| `priority`、`priority_reason` | 報告已明列的 P1／P2 等值與理由，或兩者均 `null`；不由 queue urgency／verdict 映射 |
| `scope_labels` | 審查者明列的產品／範圍標籤；只供閱讀篩選，不證明正式適用性 |
| `finding_refs` | 選定 assessment 中的 finding／observation ID 清單；可為 `[]` |
| `locations` | 每筆含 `source_ref`、`source_scope`（`corpus`／`auxiliary`）及已撰寫的 `display_text`，明列檔案及段落；檔案部分須對到指定 scope 的固定來源 |
| `basis` | 沿用既有 basis record 形狀與三種值；公司原文另由 locations／規則出處歸屬 |
| `details` | 下列七項已撰寫內容；不能由 renderer 抽取自由文字後再猜改法 |
| `tracking` | `null` 或已有的追蹤敘述與 `evidence_refs`；僅有「已解決」文字不足以證明結案 |

`source_scope: corpus` 只能引用選定 corpus 成員；`source_scope: auxiliary` 只能引用 `auxiliary_sources` 中唯一對應的檔案，由其 ArtifactRef 取得已固定的 bytes。清單由作者／審查者依本次已授權範圍記錄，保留來源版本與授權範圍的追溯；列入清單本身不授權新增來源或讀任意檔案。未列入、scope 不明或引用失配時拒絕，不能從目前工作目錄補找。

輔助來源只支援 Action 的位置與修正理由，不因此成為 assessment corpus member，不參與 NIST coverage、corpus digest、D1 文件對照或 D3 corpus authority 計數。例如 branch-16 的 E-13 可用 `source_scope: auxiliary` 引用 `docs/SSDLC-deliverables-overview.md`；固定版本與獨立 SHA-256 沿用原技術附錄的「輔助來源（不列入 32 份 corpus）」表。coverage corpus 仍為原 32 份；本刀不建立實際輔助副本或修改來源清單。

`details` 使用呈現規則已規定的七個標籤作鍵：`規則依據與效力`、`目前哪裡有問題`、`要修改或補什麼`、`完成確認方式`、`適用條件與待確認事項`、`對判定的影響與不能宣稱`，另保留 `修訂句`。修訂句由作者寫好；renderer 不生成新的修改建議。

八欄附錄中的「問題編號與性質」由 ID、group、kind、已記錄 priority／tracking 組成；「文件與位置」由 locations 顯示；其餘六欄直接使用同名 details。六欄修正單的映射固定如下：

| 修正單欄位 | 資料來源 |
| --- | --- |
| ID | `action_id`，連到同一 Action 附錄 |
| 類型 | `kind` |
| 哪裡有問題 | `locations.display_text`，附原 source ref |
| 現在的問題 | `details.目前哪裡有問題` |
| 要怎麼改 | `details.要修改或補什麼` |
| 怎樣算改完 | `details.完成確認方式` |

`actions: []` 表示本次已整理而未列可執行項；`actions: null` 表示未整理。沒有 A／B／C 某一類時按已記錄 group 計數並顯示本次未列，不能用資料缺失宣稱沒有問題。位置、改法或完成條件仍不清楚的觀察留在 retained appendix，不造出 Action。

規則依據與效力須包含適用要求與公司／NIST 出處；草稿缺陷不能寫成違反已生效規範。B 類只要求找真實受控紀錄並補追溯，不代填測試結果或批准。Action 修完、priority 消失、改名或找不到 placeholder，都不自動代表 coverage 改判、實作已完成或核准成立。

## 4. D3 — 每份來源一筆 authority record

`source_authority` 對選定 assessment 的完整 corpus 各保存一筆；無法取得 corpus 成員清單時，不能宣稱明細完整。狀態是來源觀察，不是組織核准系統的查驗結果。

D2 的 auxiliary sources 不加入這份 corpus authority 明細或總數；若報告需說明輔助來源狀態，須另外標示其輔助範圍。

| 欄位 | 最小內容與限制 |
| --- | --- |
| `path` | corpus metadata 的同一路徑；commit／content hash 沿用既有來源，不再複製到每個 Task |
| `state` | `draft`、`under_review`、`approved`、`unspecified`，或 `null` 表示未收集 |
| `raw_status` | 實際看到的原文；未收集或讀過但未標示時為 `null` |
| `status_source_ref` | 看到狀態或確認未標示的文件位置／審閱紀錄；`unspecified` 必須有這個依據，不能只由 raw_status 缺值推定 |
| `approval_ref` | 正式核准／生效證明的 ArtifactRef，或 `null`；標頭 Approved 不自動產生這份證明 |

非 `null` state 是作者已記錄的辨識結果。缺少、重複或跨 corpus 的 path 不能默認補入；`state: null` 要明示「未收集」，與 `unspecified` 的「已讀但未標示」分開。

renderer 按明確 state 計數，只顯示「本次來源辨識為 Draft／Under Review／Approved」等限定語。存在未收集紀錄時，Approved 的已辨識數須同時顯示未收集份數；不能只顯示 Approved＝0 造成全 corpus 已掃描的印象。全部未收集時明示無法統計核准狀態，不展示零值假裝完成。

Task authority 由 D1 document_refs 查這份明細，corpus 總數可共用顯示，不重複儲存。文件 Mandatory、Approved 標示或 approval_ref 的存在，都不能單獨推出組織政策已正式生效；要保留該證明實際支持的範圍與 cannot claim。

## 5. D4 — 審閱流程保存結果之間的關係

`review-lifecycle.json` 引用已固定的 report data；它可以更新審閱關係而不修改 D1～D3 或原 assessment。接受文件要明確指出接受哪一版內容，不能只寫某個 report ID 已接受。

| 欄位 | 最小內容與限制 |
| --- | --- |
| `report_data_ref` | 固定 report-data 檔案的 ArtifactRef；畫面結果來自該檔 assessment_ref |
| `machine_baseline_ref` | 比較用的原 machine assessment ArtifactRef，或 `null` 表示未提供；不是畫面的替代結果 |
| `review_recommendation` | 原報告已記錄的文件 review 意見與理由，或 `null`；CHANGES_REQUESTED 是建議，不是接受／拒絕事件 |
| `acceptance_ref` | 下述結構化 acceptance decision record 的 ArtifactRef，或 `null`；須綁定 report-data 及選定 assessment 的指紋，不能只引用一般接受文字 |
| `sync` | 下述最小同步紀錄；與人工接受、queue、coverage 分開 |

`sync` 只含 `state`、`target_ref`、`decision_ref`、`verification_ref`。state 的三種值為 `not_checked`、`not_synced`、`synced`，屬報告生命週期，不加入 verdict 或 queue vocabulary。

**這三種 lifecycle 證明引用必須指向可機器判定的 JSON decision／verification record。** ArtifactRef 只固定檔案 bytes；通過指紋比對不代表內容就是接受、同步授權或同步成功。依引用用途驗證以下最小結構，缺欄位、未知 decision／result、綁定不符或不支持所宣稱狀態時拒絕；不得從一般 Markdown、聊天文字或自由文字自行推斷。

| 引用 | 結構化紀錄的必要內容 |
| --- | --- |
| `acceptance_ref` | `decision: accepted`、`report_data_sha256`、`assessment_sha256`、`evidence_ref`；兩個指紋必須對到本次 report data 與其選定 assessment。這是接受證明，其他 decision 不符合此引用用途；尚無有效接受紀錄時用 `null` |
| `sync.decision_ref` | `decision: synchronize`、`report_data_sha256`、`assessment_sha256`、`target_sha256`、`evidence_ref`；記錄對這版內容與指定 target 的明確同步授權／動作，不由同步結果反推授權 |
| `sync.verification_ref` | `result: matched` 或 `not_synced`、`report_data_sha256`、`assessment_sha256`、`target_sha256`、`evidence_ref`；綁定實際讀取的 target bytes，並按下列完整內容對照核驗，不能只相信自報 result |

`evidence_ref` 是支持該人工決策／同步動作／核驗紀錄的 ArtifactRef；可追到原始紀錄，但其自由文字不承擔 machine decision。接受與授權須來自使用者／具權限審查者的實際決定，agent 不得為了通過 validation 自行填入。這個最小 contract 不引入簽章或身分系統；結構、指紋與交叉引用通過，只支持紀錄及版本關係，不證明決策人身分、權限或紀錄真實性。

- `not_checked`：尚未核查；其他三個引用為 `null`。不能顯示「已確認未同步」。
- `not_synced`：已知這份人工內容尚未同步到指定 target；target_ref 與 verification_ref 必須存在，decision_ref 可為 `null`。結論只限這份內容與這個 target，不推定所有地方都未同步。
- `synced`：三個引用都必須存在，decision_ref 記錄明確同步授權／動作，verification_ref 支持實際 target 內容與選定結果對應。兩份檔案可有不同 assessment ID，但 baseline、repo、commit、manifest／corpus digest、Task 範圍與實際傳入的結果必須逐項對得上；不能只比 verdict 或日期。

`synced` 只接受 verification 的 `matched`，且完整對照實際相符；`not_synced` 只接受有核驗支持的 `not_synced`。state、結構化 decision／result 與對照結果互相矛盾時拒絕，不自動改 state；同範圍結果相符也不自行證明曾執行同步動作。decision 的 `target_sha256` 綁定授權／動作所針對的核驗 target 版本；若有另行保留更新前版本，需另外留在 evidence，不把舊指紋當成本次 target。

`acceptance_ref: null` 時，畫面維持 `HUMAN REVIEW DRAFT`，意思是這份輸出沒有附可核驗的接受依據，不推定人類從未看過。非 null 但結構或引用無效時須報錯，不能悄悄降回草稿掩蓋錯誤。只有有效結構化紀錄明列 `decision: accepted` 且接受同一版 report-data 與 assessment 時，才可呈現「人工報告已接受」。輸入內容改變後舊 acceptance 不適用新內容；只改排版仍須保留可追溯的同一組資料綁定。這不表示 release approval、risk acceptance 或 machine 同步。

比較用 machine 的來源身分與畫面 assessment 不同時，標示來源／範圍不同，只作歷史對照。記錄未同步或接受草稿不會自動建立一份 machine 更新；沒有 machine baseline 時顯示未提供，不冒充首次沒有歷史結果。renderer 不修改上述輸入與狀態，輸出 Markdown／HTML 的寫檔編排另屬 REPORT-4。

## 6. 相容性、資料不足與既有 branch-16

舊 assessment、manifest、corpus digest、Review Engine、queue projection 與既有 Markdown→HTML 路徑原樣保留。新資料只進未來的報告讀取路徑，不交給會丟棄未知欄位的舊 assessment parser，也不把新欄位混入 assessment.yaml。

沒有 sidecar 時，舊報告仍可閱讀；不得假裝有完整新格式資料。新路徑遇到指紋錯誤、不同 corpus 被錯接、重複 ID、找不到指定 finding、未授權 auxiliary、路徑越界、gap／verdict 矛盾或無效 lifecycle decision record，應拒絕 validation，停止該次完整產出並保留舊檔。已明示的 `null` 則可顯示為不完整預覽，不預填為空清單、已接受或已完成，也不宣稱完整三層報告已交付。

既有 branch-16 人工報告是 32-file／`d59640c6ff279579d2daa74c50deae97201a08a7` 的七題 COVERED／weak 建議；舊 machine 是 18-file／`7e6204a6db02e612569d28f9790b2dd52bc22ba2` 的七題 PARTIAL，其中 PW.4.4 是 medium。兩組來源不能合併為同一次改判。

目前人工 32-file 結果尚未形成可核驗的獨立結構化 assessment，D1～D4 的實際資料也尚未建立。要在後續授權下轉寫，須依原紀錄逐欄保留語意、身分與草稿狀態，另形成使用既有 S0／S1 contract 的人工結果檔案；不覆寫舊 machine，不重判、不捏造核准，也不把這件事稱為同步完成。完整來源明細與 gap／improvement 拆分須由作者／審查者確認，不能由 renderer 遷移。

本次不遷移任何實際資料，也不把下列案例當成已實作 fixture。

## 7. REPORT-4A 的 acceptance requirements

以下沿用 REPORT-3A 的案例；都是後續實作的預期結果，本刀僅做 contract 桌面核對。

| Case | 必須能表達／拒絕的事 |
| --- | --- |
| C1 PW.4.4＋E-05 | 選定人工結果 COVERED／weak、D1 gap＝[]／improvement＝[]、E-05 A／P1、文件 review CHANGES_REQUESTED、草稿且未同步可同時成立；E-05 finding_refs 可為 []，不虛構 PW.4.4 關係 |
| C2 Action／queue 不污染 verdict | COVERED 不消除 Action，不升級 evidence，不接受報告；needs_changes／CHANGES_REQUESTED 不改成 PARTIAL，也不寫回 queue；COVERED＋非空 gap、PARTIAL＋gap＝[] 必須拒絕，不自動修正任一側 |
| C3 缺分類／缺 Action | 缺 supplement、gap／improvement＝null、actions＝null 明示未整理；不從 rationale／basis 推定；與已確認 [] 分開 |
| C4 來源狀態未知 | state＝null 不計成 unspecified／Draft；未收集時 Approved＝0 不能單獨顯示；有依據的 unspecified 與未收集分開 |
| C5 不同結果來源 | 舊 18-file machine 與新 32-file human 各自保留指紋、範圍與值；相同七題或畫面生成成功都不能證明已同步 |
| C6 接受與同步證明缺失 | 三種證明引用只接受指定結構化紀錄；僅有 Markdown／聊天文字或檔案存在、decision／result 缺漏或未知、未綁定新內容、沒有明確同步動作、target 指紋不合或結果不相符，都不能展示接受／同步成功；非 null 的無效引用須拒絕 |
| C7 Optional PW.8.1 | 直接保留 assessment cannot_claim 的 PciSd／ISP Tool 限制，不外推公司所有產品；scope_labels 只供閱讀分類 |
| C8 不覆寫歷史與來源邊界 | E-13 可引用已授權且固定的 auxiliary overview，保持 32-file corpus、digest 與 authority 計數不變；未列入來源、scope 錯接、ArtifactRef absolute path／..／symlink 或 junction 越界須拒絕。來源變更仍沿用新版本目錄與穩定 ID；錯誤輸入保留舊報告與原 assessment |

C1 須先有獨立、已記錄的人工結構化結果才能執行；不能用假 assessment_ref 或舊機器結果做出七題 COVERED。C4 的 30 Draft／1 Under Review／1 unspecified／0 identified Approved 只能在同 corpus 的逐來源辨識紀錄已完整支持時生成，不能照範例預填。

**停止點：REPORT-3B ACCEPTED / FROZEN。** 四項修正完成後依使用者指定收束，不再開 REPORT-3C。本次 freeze 僅接受資料 contract，不代表 C1～C8 已執行或工具已實作。

下一刀為 **REPORT-4A — Contract Models + Validation Only**：只實作這兩份補充資料的 parse、模型、cross-reference 與 fail-closed validation，將既有 C1～C8 轉成可執行的正反案例；先不產 Markdown／HTML，不做實際報告資料 migration，不同步 REPORT-2，不修改 assessment contract／queue／S2。REPORT-4A 尚未開始；正式實作依該刀工作範圍進行，不由本次 contract freeze 代替 runtime 證據，也不授權 commit／push 或發布。
