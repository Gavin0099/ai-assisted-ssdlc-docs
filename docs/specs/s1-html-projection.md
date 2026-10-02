# REPORT-4D — 本地 HTML 閱讀版

本刀將 REPORT-4B 的固定資料與 REPORT-4C 的三份 Markdown 接到既有共用 HTML 模板。原 Markdown 逐位元保留；HTML 使用同一份 assessment、report data 與 lifecycle，不重新判題。

## 固定流程

1. 用 REPORT-4A loader 檢查 lifecycle、report data、assessment、corpus 與明確授權的 auxiliary source。
2. 依固定 REPORT-4C 模板、日期、標題及來源連結取得預期 Markdown。以 digest 和 actual opened handle 檢查三份輸入，任何不一致即拒絕產出。
3. 用共用 `s1-assessment-web.html` 的配色、導覽、六欄表與八欄問題詳情投影既有內容。
4. 在獨立閱讀目錄保留三份相同 Markdown 與 HTML；相對來源連結必須仍相同。既有不同輸出不覆寫，相同輸出可重跑。

REPORT-4C 模板的「只產生 Markdown」是該版本的歷史停止點。HTML 另以醒目說明標示本次轉換，不能修改原文來掩蓋版本關係。

## 維度與來源

- Verdict、evidence strength、Action group／priority 來自已記錄資料；COVERED 不表示問題消失、strong、accepted 或 synced。
- 接受及同步狀態來自已驗證的 lifecycle；不能從報告的自由文字猜測。
- 範圍篩選只用既有 `scope_labels`。未保存標籤時顯示「未記錄範圍標籤」，可用 ID／路徑搜尋，不由檔名推填。
- 八欄問題詳情及全部技術內容保留。原 Action 的完整修訂句、basis 與 tracking 仍在技術附錄。
- E-13 的 auxiliary source 仍是 auxiliary，不加入 corpus 份數、digest 或 authority 統計。
- HTML 包含來源指紋與 reader version。生成紀錄另保存工具／模板指紋、Markdown 指紋及獨立 lifecycle 狀態。
- HTML 為離線文件，無 CDN、遠端字型或網路資料請求；未公開發布。

## 結構化報告入口

從 repo 根目錄執行，輸出目錄須獨立於資料、Markdown 與模板目錄。

```powershell
python -X utf8 -m tools.generate_assessment_html `
  --report-root experiments/s1-company-pilot/report-4b/branch-16 `
  --markdown-dir experiments/s1-company-pilot/report-4c/branch-16-reviewed `
  --out-dir experiments/s1-company-pilot/report-4d/branch-16-preview `
  --date 2026-10-02 --title '公司 SSDLC Pilot' `
  --allow-auxiliary-source docs/SSDLC-deliverables-overview.md
```

舊人工 Markdown 的入口仍為 `tools/generate_assessment_web.py`，保留舊格式測試。結構化報告使用上面的 adapter，不能略過資料 admission 與 Markdown 綁定。

## 驗證與限制

相關測試驗證輸入不一致、未授權 auxiliary、輸出重疊、相對連結失效及既有不同輸出會拒絕；也檢查跳脫字元、危險 HTML、來源不改動、維度分離及 deterministic output。

本次 browser 工具禁止開啟 `file://`。因此只完成產物、結構／來源／JavaScript 靜態檢查，Codex 檔案面板開啟請求回傳 queued；不宣稱已完成桌面／手機視覺或互動 QA。這份產物為本地候選，下一個 gate 是實際閱讀與操作確認。

轉換與結構檢查不證明判定正確、公司實際執行、核准權限、人工接受、同步完成或公開交付。
