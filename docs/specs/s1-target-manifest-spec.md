# S1-A Target Manifest Specification

## 目的 (Purpose)
定義真實儲存庫（Target Repository）文件涵蓋度審查的目標規格清單（Target Manifest）。
本規格回答核心問題：
> **「我要 review 哪一個 repo、哪一個 commit、哪些檔案才算 authoritative SSDLC？」**

---

## 領域模型與欄位定義 (Domain Model & Fields)

| 區塊 (Section) | 欄位 (Field) | 型別 (Type) | 必填 (Required) | 說明與約束 (Constraints) |
| :--- | :--- | :--- | :---: | :--- |
| **`target`** | `source_type` | `string` | 是 | 儲存庫來源型別，目前支援 `local_git` 與 `github`。 |
| | `repo` | `string` | 是 | 儲存庫識別名稱、路徑或 URL（`local_git` 為本機路徑；`github` 為 `owner/repo` 或 HTTPS URL），不可為空。 |
| | `commit` | `string` | 是 | 嚴格 40-character 十六進制 SHA-1 hash（`^[0-9a-fA-F]{40}$`）。**禁止**動態 branch 名稱（如 `main`）或 HEAD，確保不可變性（Immutability）。 |
| **`authority_surface`** | `include` | `list[string]` | 是 | 權威文件路徑 glob 模式清單，**必須至少包含一個元素**。 |
| | `exclude` | `list[string]` | 否 | 排除路徑 glob 模式清單（如草稿、封存檔案）。 |
| **`baseline`** | `framework` | `string` | 是 | 治理標準基準，必須為 `NIST_SP_800_218`。 |
| | `version` | `string` | 是 | 基準版本，**必須為純字串 `"1.1"`**（禁止 YAML float/numeric 隱式轉換）。 |
| **`mode`** | `read_only` | `boolean` | 是 | 審查執行模式，**必須固定為 `true`**，防止意外寫入或狀態污染。 |

---

## Authority Surface Glob 邊界語意 (Glob Semantics)
為了確保後續 S1-B Repo Corpus Resolver 能確定性物化檔案，Authority Surface 制定以下不可逾越的邊界規則：
1. **相對路徑原則**：所有 pattern 一律相對於 Target Repo 根目錄，**禁止絕對路徑**（如 `/etc/...` 或 `C:\...`）。
2. **禁止目錄穿越**：Pattern 內**禁止出現 `..`**，防止越界讀取儲存庫以外的檔案。
3. **路徑分隔符正規化**：統一採用正斜線 `/`（禁止包含 Windows 風格反斜線 `\`）。
4. **優先級語意**：`include` 優先收集候選，`exclude` 具備最高覆蓋權（Exclude Always Wins）。
5. **檔案限定**：僅物化常規檔案（Regular files），不跟隨符號連結（Symlinks）。
6. **確定性排序**：物化後之檔案清單與 Hash 一律按路徑字母升冪排序。

---

## 行為驅動開發場景 (BDD Scenarios)

### 場景 1: 正確的 Target Manifest 通過驗證
```gherkin
Given 一份結構完整且合規的 Target Manifest YAML
And target.source_type 為 "local_git" 或 "github"
And target.repo 為有效路徑或標識
And target.commit 為合法的 40 字元 SHA 雜湊
And authority_surface.include 為非空清單且符合相對路徑約束
And baseline.framework 為 "NIST_SP_800_218" 且 version 為字串 "1.1"
And mode.read_only 為 true
When 執行 validate_target_manifest 驗證
Then 驗證結果必須成功 (exit code 0)，無任何錯誤
```

### 場景 2: 浮點數版本 (numeric version: 1.1) 觸發 Fail-Closed
```gherkin
Given Target Manifest 中的 baseline.version 未加引號被解析為 float 1.1
When 執行 validate_target_manifest 驗證
Then 驗證必須失敗 (exit code 1)
And 錯誤訊息必須明確指出 version 必須為字串型別，禁止數值型別
```

### 場景 3: 不合規之 Glob Pattern 觸發 Fail-Closed
```gherkin
Given Target Manifest 中的 include 或 exclude 包含絕對路徑、".." 或反斜線 "\"
When 執行 validate_target_manifest 驗證
Then 驗證必須失敗 (exit code 1)
And 錯誤訊息必須明確指出非法路徑格式
```

### 場景 4: 未知或未支援之 source_type 觸發 Fail-Closed
```gherkin
Given Target Manifest 中的 target.source_type 為 "gitlab_api" (不在支援清單)
When 執行 validate_target_manifest 驗證
Then 驗證必須失敗 (exit code 1)
And 錯誤訊息必須明確指出不支援的 source_type
```
