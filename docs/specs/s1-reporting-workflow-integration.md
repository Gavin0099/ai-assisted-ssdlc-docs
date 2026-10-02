# REPORT-4E — 固定報告產出入口

Agent 先對照固定來源分析，依既有 assessment、REPORT-3B report data 與 lifecycle 合約記錄結果。保真修文在資料定稿前完成，工具接著驗證並產出三層 Markdown 與同版本離線 HTML。此入口不執行 semantic assessment、不修改 baseline machine assessment，也不自動接受或同步。

## 使用方式

從任何工作目錄執行，以當次 reporting repo、資料與輸出路徑替換參數。

```powershell
python -X utf8 <skill目錄>/scripts/workflow.py --reporting-repo <reporting-repo> resources
python -X utf8 <skill目錄>/scripts/workflow.py --reporting-repo <reporting-repo> project --report-root <資料根目錄> --out-dir <新版本目錄> --date <YYYY-MM-DD> --title <本次標題>
```

有已授權 auxiliary source 時逐項加 `--allow-auxiliary-source <source path>`；sidecar 不能自行授權。`--lifecycle` 預設為資料根目錄內的 `review-lifecycle.json`。

版本目錄內 `markdown/` 保存三份生成檔，`reading/` 保存逐位元相同的三份 Markdown 與 HTML。助手回傳四個實際交付入口、兩階段指紋及接受／同步狀態；日期不自動取今天，份數、產品與 Task 不套用 Pilot 預設。

舊人工報告使用 skill 的 `render`，保留原 Markdown／metadata 與判定，不為轉網頁自動 migration。

## 失敗與版本

- 資料 admission 或 Markdown 階段失敗，回傳非零 exit code；不開始 HTML 階段。
- HTML 階段失敗，回傳非零與 `partial`，保留已產 Markdown 和原有不同輸出；不宣稱四份交付完成。
- 同一輸入重跑結果與指紋一致；既有不同輸出不覆寫。
- 文字修改回到 authoring 並建立新資料版本，不手改生成 Markdown 或補 digest；接受／同步紀錄須重新綁定新資料，不能借用舊紀錄。
- 維持 COVERED／weak／P1／draft／not_synced 可同時存在，四個維度不互相換算；auxiliary 不加入 corpus 或 authority 統計。

## 測試與交付邊界

公開測試使用既有最小合成 assessment 加獨立 Action、auxiliary 與 lifecycle fixture，從實際 helper CLI 驗證成功、失敗、部分完成、相對路徑、重跑與舊格式。乾淨來源匯出不包含公司報告，也須能執行全部公開測試。

真實 company migration 的保真檢查移至本地 `local_tests/`，原測試檔逐位元保留。它需要明確準備的內部輸入，與公開 unit／contract suite 分開。公司報告、local tests 及其真實資料 receipt 均設為 Git ignored，不因工具交付而公開。

REPORT-4D 獨立技術 review 已核對實作；browser 工具拒絕 `file://`，因此桌面／手機實際畫面及互動仍未驗證。這項限制不被靜態檢查或合成測試取代，也不以換服務／協定／browser surface 繞過。HTML 仍提供本地檔案供人閱讀。

技術 review、生成及來源檢查不證明 NIST 推理正確、實作有效、核准權限、人工接受或同步；公開工具交付不授權公開內部公司文件。
