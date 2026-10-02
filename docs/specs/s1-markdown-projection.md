# REPORT-4C — 確定性三層 Markdown

本刀只呈現 REPORT-3B / REPORT-4A 已記錄並驗證的資料。不更改判定、不做人工接受或同步，不產生新 HTML。原始公司資料與產出仍只保留在本地。

## 入口與分工

`tools/assessment_markdown.py` 是純文字投影，不讀檔、不取現在時間。`tools/generate_assessment_markdown.py` 負責完整 lifecycle admission、讀取三份固定模板、來源導覽與一次交付三份新檔。

```powershell
python -X utf8 -m tools.generate_assessment_markdown --report-root experiments/s1-company-pilot/report-4b/branch-16 --lifecycle review-lifecycle.json --out-dir experiments/s1-company-pilot/report-4c/branch-16 --date 2026-10-02 --title "公司 SSDLC Pilot" --allow-auxiliary-source docs/SSDLC-deliverables-overview.md
```

Auxiliary allowlist 由呼叫者明確給定；JSON 不能自行授權。產出日期只代表檔案產生日期，不代表重新審閱日期。

## 固定結果

- `<report-id>-summary.md` 保留結論、工程師要處理什麼、建議處理順序、詳細 NIST 判定四節。
- `<report-id>-actions.md` 保留 A 改文件／B 補證據／C 改善建議，以及 ID、類型、哪裡有問題、現在的問題、要怎麼改、怎樣算改完六欄。
- `<report-id>-technical-review.md` 保留八節技術附錄與每題十五個欄位。每項 Action 的原修法、條件、規則效力、basis、追蹤及修訂句都保存。

三份模板位於 `templates/s1-assessment-{summary,actions,technical-review}.md`。機器模板沿用人類報告的固定章節與欄位，僅將手填提示改成明確的投影 slots；章節或必要 slot 不符即拒絕。

同一份資料、模板、導覽位置、title 與日期產生相同 bytes。未提供結構化的上一輪人工 verdict 時，明示未取得，連到保留來源；歷史 machine assessment 另列來源，不冒充同一 corpus 的改判。

## 拒絕與保留規則

- REPORT-4A admission 失敗或資料整理尚未完成時，不交付完整三層；`null` 不能當成已檢查的 `[]`。
- 原 rationale 原樣呈現，不從自由文字重新分類 Gap、Improvement、Action、scope label 或 finding 關係。
- 接受與同步各自呈現；依 presentation v1.4 §3，未接受或尚未同步時保留 HUMAN REVIEW DRAFT。若已有有效接受紀錄，正文仍明寫人工報告已接受，並另列同步狀態；此呈現草稿標示不會取消接受決策。有接受紀錄不代表 release／risk approval。
- 原 cannot-claim 與 assessment claim boundary 保存；COVERED、weak、P1 與審查意見可以同時成立。
- 動態文字轉成安全的 Markdown 文字，不讓內嵌 HTML、表格或標題改掉固定結構。Task ID 是主要定位，原文頁碼與行號仍只作原記錄。
- 輸出目錄與輸入 bundle／模板互不包含；拒絕 symlink／junction 輸出。不同內容不能覆蓋已存在的報告，相同三檔重跑才是 no-op。
- 三檔全部完成投影後才 staging；寫入失敗不留下可誤認為完成的半套輸出。來源與現有報告不回寫。
- 寫檔支援 Windows／Linux。Windows 在寫入期間持有禁止刪除／搬移的 directory chain handles；Linux 使用 O_NOFOLLOW directory descriptors 與相對 open／rename。寫入前驗證實際開啟的檔案身分，不靠單次 path pre-check；其他平台的 I/O 先拒絕。
- Staging handle 保留到真正發佈。Windows 用 FileRenameInfo 由原 handle 改名，Linux 由 directory descriptor 發佈並核對 inode；最後再次核對發佈目錄身分、三檔清單及實際 bytes。錯接目錄或內容不符時不能回報 created。

Linux 寫檔的資格驗證使用原生 `/tmp` filesystem。WSL `/mnt/c` 的 DrvFs 已重現 relative directory rename 後 descriptor 無法重新定位的錯誤，工具會拒絕完成，這個 mount 尚未納入可用輸出環境；Windows 原生寫檔不受此測試限制影響。固定輸入可從已授權的 mounted bundle 讀入，測試不修改原資料。

入口驗證不證明 NIST 推理正確、quote/span、產品實際執行或核准權限。網頁接線屬 REPORT-4D；這刀沒有發佈到公開 repository。
