# 來源固定與報告產出操作

這份參考用於執行 skill 的來源固定與轉換步驟。規則與模板從 reporting repo 讀取，不複製到本 skill，也不把既有某一版報告的結論當成 golden answer。

## 取得共用資源

`scripts/workflow.py resources` 會列出 reporting repo 根目錄、rubric、presentation contract、S1 manifest／corpus contract、report data contract、三份 Markdown／HTML 模板和現有 generator 的完整路徑。明示 `--reporting-repo` 時必須使用該位置；缺資源就失敗，不偷偷改用其他 repo。

模板註解的版本提示若落後，以實際讀取的 presentation contract 為準；模板提示不作為報告內容或另一套規則。Rubric 連到 S0 的正式 contract，機器合約查驗需要時讀該來源，不以範例結果代替；使用者限制讀取範圍時遵守限制並說明未查驗部分。

Repo 原始 skill 在 `.agents/skills/ssdlc-assessment-report/`；本機 Codex 安裝副本通常在 `$CODEX_HOME/skills/ssdlc-assessment-report/`，未設定 CODEX_HOME 時為 `~/.codex/skills/ssdlc-assessment-report/`。其他 agent 直接讀 repo 的 `SKILL.md`。模板及正式規則仍只由 reporting repo 維護。

目前工作環境的 reporting repo 是 `E:/BackUp/Git_EE/ai-assisted-ssdlc-docs`。這是位置提示，執行前仍要確認；換環境用當次明示的路徑。

## 固定 target 版本

先看 target repo 的狀態並解析使用者指定 ref，例如以下命令的路徑與 ref 換成本次值。

```powershell
git -C <target-repo> status --short
git -C <target-repo> rev-parse --verify <user-ref>^{commit}
```

PowerShell 執行時把 ref 參數作單一字串傳入，例如 `'branch-name^{commit}'`。保存完整 SHA；branch 名只是導覽，評估固定於這個 SHA。有 dirty work 也可以從 Git objects 做唯讀評估，不 checkout、reset 或 stash 來清工作目錄。找不到指定 ref 時說明缺少來源，不自行選另一分支。

確認 baseline 正式版本與 Task 清單。Target Manifest 定義 source_type、repo、commit、include／exclude、baseline 與 read_only；Task 清單另從 assessment／附錄或使用者取得。現有 schema 支援的版本以 `schemas/target-manifest.schema.yaml` 為準，使用者要分析不同基準時先指出工具支援邊界，不自動改 schema。

新 manifest 固定 SHA、實際 repo 身分與授權範圍；同來源格式整理沿用原 manifest。新 source／corpus 使用 contract §9 的新版本目錄，保留前版。建立目錄後，從 reporting repo 工作目錄執行既有工具。

```powershell
python -X utf8 tools/validate_target_manifest.py <本次manifest.yaml>
python -X utf8 tools/repo_corpus_resolver.py <本次manifest.yaml> --repo-path <target-repo> --export-json <本次輸出目錄>/<report-id>-corpus-metadata.json --summary
```

metadata 是 resolver 的真實輸出，不手填文件數、SHA 或 digest。新輸出路徑不能蓋掉舊版本；同範圍重新輸出時先確認固定 SHA 與 digest 相同。

## 讀取 corpus 的實際內容

Resolver 的 CLI 輸出成員清單與 metadata，不等於 agent 已讀內容。可以從固定 commit 用 `git show` 讀特定成員，或在 reporting repo 以 Python API 取得 `snapshot.files` 中的 `relative_path`、`content`、`content_hash`。

```python
from tools.repo_corpus_resolver import resolve_corpus_from_manifest
snapshot = resolve_corpus_from_manifest(manifest_path, repo_path=target_repo_path)
for document in snapshot.files:
    # 逐份閱讀 document.content，並記錄實際閱讀範圍。
    # 成員與指紋只證明來源固定，不證明語意判斷。
    pass
```

沒有必要為了讀取建立另一份 source repo checkout。需要暫存來源時保存至明示的暫存目錄，不把未審閱文件寫成已閱讀。重審可用固定前後 SHA 的 diff，加讀受影響內容與相關要求；清楚標示哪些沒有全文重讀。

## 分析工作底稿

在技術附錄或本次暫存底稿逐題保存要求、來源、直接缺口、改善及判斷理由。對跨文件問題先確認它們指同一產品／設計／release；版本尚未確定就保留條件，不混成確定缺陷。

新問題用新穩定 ID；既有問題逐項追蹤延續、部分改善、已解決或本輪未重現。改名、整併、刪檔或 placeholder 消失，都不足以證明執行／修訂完成。

工程修正單收錄全部可執行項，附錄保存每項八欄理由。主管摘要最後寫，從已成立的判斷取重點。先按共用模板完成 Markdown，再按 human-report-writing 參考修文字。不得讓文風改掉事實或判定。

## 結構化資料的固定產出入口

依已 frozen 的 REPORT-3B contract 保存 assessment、`report-data.json` 與 `review-lifecycle.json`。這是 agent 分析結果的 authoring 階段，工具沒有自動讀文件並判題，也不從舊 Markdown 猜測 gap、Action 或接受決定。

白話修文在資料定稿前完成。資料與來源固定後，使用本次明示的日期與標題，不預設 Pilot 的產品、份數、Task 數或 verdict。

```powershell
python -X utf8 <skill目錄>/scripts/workflow.py --reporting-repo <reporting-repo> project --report-root <資料根目錄> --lifecycle review-lifecycle.json --out-dir <新的版本目錄> --date <YYYY-MM-DD> --title <本次標題>
```

有 corpus 外的工程修正來源時，逐項加 `--allow-auxiliary-source <已明確授權的來源路徑>`。不要從 sidecar 自動授權，不把 auxiliary 加入 coverage corpus。詳見 reporting repo 的 report data contract。

助手以 argument list、reporting repo cwd 呼叫既有 `tools.generate_assessment_markdown` 與 `tools.generate_assessment_html`。本次版本目錄下的 `markdown/` 和 `reading/` 必須與輸入／模板分離；reading 內有相同三份 Markdown 和單一 HTML。完整 JSON 回傳四個交付路徑、兩階段來源指紋、接受／同步狀態。只成功產 Markdown 時回傳非零及 partial，保留已完成部分，不覆寫既有不同輸出。

生成 Markdown 如需改文字，回到 authoring 並建立新的資料版本，重新驗證與產出；不繞過 exact-byte binding。修文不授權改基準 machine assessment、接受或同步。

## 舊人工 Markdown 的轉換入口

三份 Markdown、metadata 放在同一版本目錄，report-id 與 STATUS 相同。技術附錄保留 metadata 的完整 commit／corpus digest；Action 用 `[E-01](<實際附錄檔名>#e-01)`，附錄有唯一 `<a id="e-01"></a>` 和 `### E-01 — ...`。這些標記是固定格式，保留它們的標點。

新檔案依 contract 命名，既有技術附錄可保留歷史名稱。Task 標題與 15 欄依共用模板，不另發明機器欄位。產出工具會拒絕不支援／不一致的輸入；它沒有自動分析功能。

```powershell
python -X utf8 <skill目錄>/scripts/workflow.py --reporting-repo <reporting-repo> render --summary <summary.md> --actions <actions.md> --technical <technical.md> --metadata <corpus-metadata.json> --output <report-id-report.html>
```

助手以 argument list 呼叫既有轉換器，路徑相對於呼叫當下位置解析，不用拼接 shell 字串。HTML 必須放在三層報告同一版本目錄，避免跨磁碟相對連結無法建立。它不改 Markdown、metadata 或 assessment，也不負責建立新的 manifest。

## 驗證與交付

驗證先檢查報告一致性，再看網頁。Browser 檢查以讀取與操作為限；列印樣式可以模擬，不直接送實體列印、外部發布或寫回處理狀態。產出失敗時保留既有檔案並解釋已完成與未完成的部分。Browser 工具拒絕本機檔案時，不換協定、服務或 browser surface 繞過；留下未驗證項目，提供本地檔案供人閱讀。

公開工具測試使用合成 fixture，不依賴公司 repo 或內部報告。真實 migration 保真測試保留在 `local_tests/`，明確準備本地資料後才執行；不是被略過的公開 unit tests，也不以合成測試冒充真實資料驗證。

最終固定給四個實際入口，網頁在前，三份 Markdown 依摘要／六欄修正單／完整附錄排序。保留當次人工狀態、未同步 machine assessment 的說明，以及真正未驗證的範圍。
