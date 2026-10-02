# REPORT-4A — Models + Validation 交付與驗證

2026-10-02｜REPORT-4A 實作與測試；PR review／合併狀態以本次 PR 的 current head、Codex review 與 CI 為準。

依據為 [frozen REPORT-3B v0.1](s1-minimal-report-data-contract.md)。本刀新增兩個 production modules，沿用 Python strict parser／dataclass 模式，未新增 YAML schema。只用最小合成 fixtures，沒有建立 REPORT-2／branch-16 真實 sidecar，也沒有資料 migration、Markdown／HTML projection 或 queue／S2 變更。依使用者的 PR／review／條件式合併指示，從 main 隔離交付；不帶入原目錄的 S2 提交、治理更新或其他報告／UI 工作。

## 入口與資料責任

| 入口 | 用途 |
| --- | --- |
| [report_data_contract.py](../../tools/report_data_contract.py) 的 `parse_report_data(value)` | 純結構解析，保留 null／空清單；不代表交叉引用或 I/O 已驗證 |
| 同模組的 `load_report_data(relative_path, report_root, authorized_auxiliary_sources=...)` | 驗證所有固定引用、既有 assessment、corpus identity、D1～D3 與來源關係；回傳模型與完整度 |
| [review_lifecycle_contract.py](../../tools/review_lifecycle_contract.py) 的 `parse_review_lifecycle(value)` 及 decision parsers | 純結構解析；文件 review 意見不會轉成人工接受 |
| 同模組的 `load_review_lifecycle(relative_path, report_root, authorized_auxiliary_sources=...)` | 載入 report data，驗證接受／同步紀錄、內容指紋及實際 target 對照；不寫回任何檔案 |

`report_root` 與 auxiliary allowlist 由呼叫端依已授權範圍提供；sidecar 清單不能自行授權新增來源。所有 ArtifactRef 相對於引用檔所在目錄解析，先檢查 root containment，再開啟 descriptor 並核對實際 handle 的 regular-file 與所在位置，最後讀 bytes 與核對 SHA-256。Windows 使用 GetFinalPathNameByHandleW，Linux 使用 `/proc/self/fd`；無法取得 handle metadata 時在讀內容前拒絕。這防止檢查後、開啟前被 symlink／junction 替換；後續讀取仍使用同一個 handle。來源 locator 只在 corpus／auxiliary 清單中查找，不直接拿去開公司工作目錄檔案。

Handle adapter 位於既有 ArtifactStore infrastructure。Windows 分支先確認 OS；WinDLL 明列 stdcall，HANDLE／LPWSTR／DWORD 參數與 DWORD 回傳採系統 ABI。W API 寫入 Python 配置的 UTF-16 buffer，呼叫期間借用 file handle 與 buffer，不轉移所有權或保留 pointer。Python context manager 負責成功／拒絕時關閉 descriptor；原生 API 失敗轉為 OSError，再由既有 admission error boundary 拒絕。純模型不接收 native pointer，也不配置或釋放 native 記憶體。這是既有 containment contract 的 adapter 修正，未引入新的資料格式或權限來源。

既有 `CorpusSnapshot.to_dict()` 不含 repo。新 adapter 讀 assessment 的 `target.manifest_path` 所指固定 manifest，核對既有 canonical manifest digest、commit 與 authority surface，取得 repo 後再與 assessment／metadata 對照；manifest 也必須在允許的 report root 內。metadata 成員指紋、數量與 bytes 總數須一致，不能把 manifest 排除的 auxiliary 檔案冒充 corpus 成員。沒有改舊 metadata exporter 或 assessment contract。

幾個未完全定名的文字容器採最小 shape：Action `tracking` 用 `statement`／`evidence_refs`；lifecycle `review_recommendation` 用 `opinion`／`reason`。D3 `status_source_ref` 可引用 corpus 文件位置，或使用 ArtifactRef 指向固定審閱紀錄。這些文字不會被推論成結案、接受或核准。

## PASS、未整理與拒絕

- 結構或引用無效時丟出 `ReportContractError`，不回傳成功 bundle，不修改輸入，也不將錯誤偷偷降成草稿。
- 合法 null 或缺 Task supplement 會留下 `ReportValidation.incomplete`，`complete=False`；與已整理的空清單分開。D3 缺／多／重複 corpus 成員則直接拒絕。
- Lifecycle 的 `accepted=True` 只表示指定結構化接受紀錄及同版內容綁定通過。它不代表 release approval、risk acceptance、審查者身分／權限查證，或真實同步動作已執行。
- Sync 比對保留完整結果、basis 原始順序、cannot claim、evidence、queue、scope 及來源身分；允許 assessment ID、導航用 manifest_path，以及既有 S1 contract 正規化的 provenance SHA 大小寫不同，ArtifactRef 仍綁各自原始 bytes。相同 verdict 不足以通過。`not_synced` 必須有明確核驗紀錄，內容相同可與未發生同步事件同時成立；相同內容不自動顯示 synced，缺明確動作紀錄仍拒絕 synced。
- 本刀不做 authority 計數文案、舊報告轉寫或任何報告呈現；未收集旗標與 scope 限制交給後續 projection 保留。

## C1～C8 的 executable matrix

測試在 [Report Data tests](../../tests/test_report_data_contract.py) 與 [Lifecycle tests](../../tests/test_review_lifecycle_contract.py)。所有決策／證據／文件皆為合成內容，fixtures 在 TemporaryDirectory 建立並回收。

| Case | 本刀已執行的驗證 |
| --- | --- |
| C1 | COVERED／weak、E-05 A／P1、CHANGES_REQUESTED、未接受且未同步同時成立；不虛構 finding 關係 |
| C2 | Action／queue／improvement 不改 verdict 或 evidence；gap／verdict 矛盾拒絕且輸入原樣保留 |
| C3 | null、空清單與缺 supplement 分開；不重新分析 rationale |
| C4 | 未收集與 unspecified 分開，未收集會明示 incomplete；缺／多／重複 authority path 拒絕；核准引用存在不改觀察狀態 |
| C5 | 歷史 machine 保留不同 corpus 與值；即使 verdict 一樣，repo／commit／digest／Task 範圍／其他結果不同也拒絕 synced |
| C6 | 只有自由文字、存在一個檔案、缺欄位／未知 decision、舊接受紀錄、內容綁定失配、證據指紋錯誤及 state／result 矛盾皆拒絕 |
| C7 | PW.8.1 範圍限制與 cannot claim 原樣保留；Action 閱讀標籤不轉成公司適用性 |
| C8 | 合成 E-13 可引用已授權固定 auxiliary，不改 corpus／digest／authority 分母；錯接 scope、私加來源、absolute／..／symlink／junction 越界拒絕；歷史文字與輸入不覆寫 |

## 驗證結果

初版 50 項新測試跨兩個環境執行。Codex review 修正增加 4 項，共 54 項，含路徑檢查後實際替換目錄的競態、handle metadata 不可用、內容相同但未同步，以及三種 provenance SHA 大小寫。Windows 原生 symlink 仍受系統權限限制；Linux symlink 與 Windows junction 分別實測。最新計數與結果見 PR current head 的 CI 及綁定修正 commit 的 receipt。

- 新 contract tests：`python -X utf8 -m unittest discover -s tests -p 'test_*contract.py' -v`。PR 分支重新執行；Linux CI 也會透過既有完整 discovery 執行。
- 完整 regression：`python -X utf8 -m unittest discover -s tests -p 'test_*.py'`。此指令是既有 CI 的測試入口，新測試不需要另一份 workflow。
- 前次本地 S0／S1 專項回歸共 168 項通過；六個暫存副本 guard mutations 皆被對應測試偵測。guard 涵蓋 hash、root containment、gap invariant、manifest scope、acceptance binding 及完整 sync comparison；不宣稱窮盡所有錯誤。
- 前次本地 receipts／logs 保留在原工作目錄的 `artifacts/reporting/report-4a-*`，不當作這次 PR head 或遠端 CI 的證據，也未納入 PR。首次 regression harness 的檔名錯誤已修正，其失敗 log 仍保留；該次未執行測試。

交付 gate 是同一版 PR head 的 Codex review、無未解 P0／P1 及必要 CI 通過；完成後才依使用者授權合併。REPORT-4B 真實資料 migration、REPORT-4C Markdown projection、REPORT-4D HTML wiring 均未開始。本刀驗證支持上述結構、引用與邊界行為，不證明 semantic reasoning、Git／quote/span provenance、公司實際執行、人工身分／權限或核准真實性。
