---
name: ssdlc-assessment-report
description: "分析或重審 SSDLC repository 文件，將有來源的發現轉成工程師可執行的修正單、三層 Markdown 與統一配色的離線網頁。用於指定分支 review、Pilot 更新、產品文件補充及既有報告轉網頁；以 ai-assisted-ssdlc-docs 的 rubric、模板及工具為依據。"
---

# SSDLC 分析與報告

讓工程師看完就知道哪個檔案哪個段落有問題、要怎麼改，以及怎樣確認改完。交付同一來源版本的主管摘要、工程師六欄修正單、完整技術附錄與離線網頁。

此 skill 是執行入口。正式判定依 reporting repo 中的 REPORT-1 rubric 與既有 S0／S1 contract；格式依 `docs/specs/s1-report-presentation-contract.md`。不在 skill 裡另外定義一套 verdict 或 schema。

## 先確認任務與工作位置

區分 **新分析／換分支重審**、**已有結構化資料的產出** 與 **舊人工 Markdown 的整理／轉網頁**。新分析依授權對照固定來源，將結果記入既有 assessment、report data 與 lifecycle contract；結構化產出使用 `project`，舊人工 Markdown 使用 `render`。兩個產出入口都保留已記錄的判定，不自動 migration、接受或同步。使用者指定 slice 或 review gate 時依其指示。

分清兩個 repo，不能拿其中一個的 HEAD 代替另一個。

- **Reporting repo** 是 `ai-assisted-ssdlc-docs`，提供規則、模板、來源解析及 HTML 轉換工具。
- **Target repo** 是本次要分析的公司 SSDLC repo，由使用者指定；報告綁定其分支解析後的固定 commit。

先讀各工作目錄適用的 `AGENTS.md`、PLAN 與必要治理文件，保留既有 dirty work。使用本 skill 的 [定位／轉換助手](scripts/workflow.py) 找到 reporting repo 的資源；repo 內可從目前位置解析，本機安裝版在別的目錄執行時以 `--reporting-repo` 明示。找不到時請求正確位置，不自動 clone 或更新框架。

```powershell
python -X utf8 <skill目錄>/scripts/workflow.py --reporting-repo <reporting-repo完整路徑> resources
```

讀取助手列出的 rubric、presentation contract、三份 Markdown 模板及 HTML 模板；結構化流程再讀 report data contract 與 Markdown／HTML projection spec。操作與兩種入口見 [workflow.md](references/workflow.md)。整理文字前讀 [human-report-writing.md](references/human-report-writing.md)；轉網頁前讀 [web-presentation.md](references/web-presentation.md)。

## 1. 固定來源與閱讀範圍

確認 target repo、使用者指定分支／commit、正式基準版本、Task 清單、manifest 的 include／exclude，以及前版報告。Task 範圍優先沿用使用者指定或上一輪 assessment／附錄；Target Manifest 本身不含 `scope_tasks`。找不到範圍時先釐清，可以繼續清點文件，不猜造完整 SSDF 評估。

用既有 resolver 從固定 Git commit 取得 corpus 與真實 metadata。直接讀該版本的檔案內容，不把 target 工作目錄的未提交內容混入。記錄全文閱讀、diff＋相關條文、指紋相同而沿用，以及實際未讀的部分。必要的輔助索引另列，不混進 corpus 分母。

新來源／範圍保留舊報告並依 contract §9 建立新版本目錄。不要照抄範例的文件份數、產品、日期、Task 數、核准狀態或 digest。

## 2. 先分析，再決定要交給工程師的問題

讀正式 Task 原文並以 Task ID 定位；只有頁碼不夠。未提供該版本原文時查官方來源，不用記憶或 notional examples 拼成 mandatory checklist。

每題分清正式要求、公司文件條文、實際找到的內容與審查者推論。依 rubric 分開 Task Coverage Gap 與 Improvement Opportunity；改善建議不能單獨降低 coverage。

沿用既有五種 verdict、三種 basis，並獨立保存 coverage、implementation evidence strength、authority context、review recommendation、source refs 與 Cannot Claim。不由 coverage 自動換算 queue、優先級或證據強度。

對照需求、威脅模型、風險、SBOM、測試、發布與引用的一致性，找到具體位置與依據。缺實際紀錄寫成「本次範圍內證據待補」，不能推成從未執行。相對於公司草稿的缺漏，不能寫成違反已生效規範。

溝通分工沿用 **NIST SSDF＝要做什麼、OWASP SAMM＝成熟到哪、ISO／IEC＝管理／標準化**。沒有指定標準／模型、版本與實際評估，不給 SAMM 分數或 ISO 符合性結論。

## 3. 把 finding 翻成工程修正單

固定分成 A 文件要修改、B 證據要補、C 改善建議。每項保留穩定 ID 與來源，回答哪裡有問題、目前哪裡不一致、要改什麼、怎樣確認。B 優先找既有真實紀錄並補受控引用，不能重新寫一份漂亮報告就宣稱完成。

每項都能完成這句話才交給工程師。

> 請修改 ___ 文件的 ___ 段落，因為目前 ___；改成／補上 ___；完成後用 ___ 確認。

無法指出位置、依據、改法或確認方式的觀察留在附錄待釐清，不湊 Action。沒有項目時明寫本次未列。

## 4. 先定稿文字，再產三層 Markdown

先保存完整技術理由與 Task 紀錄，再整理六欄修正單，最後濃縮主管摘要；交付的閱讀順序仍是摘要、修正單、附錄。使用共用模板，不另造章節、表格或少一層。

- 摘要用 contract 的四個固定章節，篇幅與已有事實相稱。
- 修正單固定六欄 **ID／類型／哪裡有問題／現在的問題／要怎麼改／怎樣算改完**，每個 ID 連至附錄同名小寫錨點。
- 附錄保留 rubric 的完整 Task 欄位、每個 Action 的八項完整依據、逐份觀察、前版追蹤、來源指紋與限制。

三份使用同一 report-id、固定來源與 STATUS。新人工分析尚未接受時標 `HUMAN REVIEW DRAFT`；純轉換沿用來源狀態。已存在的 `assessment.yaml` 不自動更新。

結構化流程先在 authoring 階段整理 `assessment_rationale`、Action details 等既有文字，再固定來源與指紋。用具體主語與動作，刪掉重複結論、空泛管理用語與無來源例子；核對數字、否定、條件、verdict、basis 與 Cannot Claim。來源引文不改寫，基準 machine assessment 不覆寫。

定稿後由固定 renderer 產出 Markdown，不再手改生成檔。若預覽後還需改文字，回到已授權的 authoring 階段建立新資料版本、更新相依引用並重新驗證產出；既有接受／同步紀錄不能借用到新指紋，也不能只改 digest 讓改過的 Markdown 通過。舊人工報告則在其來源 Markdown 修文，保留舊格式與狀態，再用 `render`。

## 5. 用固定版型產出網頁

按 [web-presentation.md](references/web-presentation.md) 使用共用 HTML 模板。保留深藍導覽、淺色內容區、藍色互動與琥珀色提醒，三層入口、六欄表／手機卡片、八欄詳情與完整附錄。數字與狀態由當次來源取得。

已有合約資料時使用固定入口；助手先呼叫已存在的 Markdown generator，再驗證其內容並產出 HTML。日期、資料根目錄、輸出版本與 auxiliary 授權均由本次工作明示。

```powershell
python -X utf8 <skill目錄>/scripts/workflow.py --reporting-repo <reporting-repo完整路徑> project --report-root <資料根目錄> --out-dir <新的報告版本目錄> --date <YYYY-MM-DD> --title <本次標題>
```

輸出版本下 `markdown/` 保存三份生成 Markdown，`reading/` 保存三份逐位元相同的 Markdown 與 HTML；同版本來源連結必須有效。資料合法但不完整也不能假裝完成。HTML 階段失敗時保留已產出的 Markdown、回傳非零 exit code 與 `partial`，不宣稱四份交付完成。

只有舊人工 Markdown 使用以下入口，不在純轉換時擅自移植成新 assessment。

```powershell
python -X utf8 <skill目錄>/scripts/workflow.py --reporting-repo <reporting-repo完整路徑> render --summary <本次摘要.md> --actions <本次修正單.md> --technical <本次技術附錄.md> --metadata <本次既有corpus-metadata.json> --output <本次report-id-report.html>
```

HTML 是同版本資料與 Markdown 的離線閱讀投影。來源不一致時指出真正缺口，保留既有檔案；不改判定、狀態或指紋來勉強通過。生成 HTML 不直接編輯成另一套結果。這些工具只驗證與呈現，沒有自動做 semantic assessment。

## 6. 檢查與交付

完成 contract §8 核對。逐項確認三層的版本、數字、結果、狀態、Action ID、限制與連結相同；文字清楚到工程師能直接開始處理。

在瀏覽器確認桌面／手機可讀、搜尋與產品／A／B／C 篩選正確、空分類如實呈現、八項詳情與附錄跳轉可用。有現成瀏覽器測試環境就執行相稱檢查；無法檢查時如實說明，不為普通報告轉換安裝大套工具。沒有修改 renderer／模板時，不因每次產報告就重跑整個 repo 測試。

完成回覆先給白話結論及 **網頁報告**，再依序連到 **主管摘要／工程師六欄修正單／完整技術附錄**，說明草稿／接受／機器同步狀態。只給 verdict、findings 或計畫不算完整交付。

只授權報告工作時，停在報告交付。不得自動改公司文件、補造測試／核准、改 validator／schema／Review Engine、開始 S2、commit／push、對外發布或傳送訊息。這些動作依當次使用者授權另行執行。
