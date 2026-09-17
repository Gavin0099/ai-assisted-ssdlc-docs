# S1-A Target Manifest Specification

## 目的 (Purpose)
定義真實儲存庫（Target Repository）文件涵蓋度審查的目標規格清單（Target Manifest）。
本規格回答核心問題：
> **「我要 review 哪一個 repo、哪一個 commit、哪些檔案才算 authoritative SSDLC？」**

---

## 領域模型與欄位定義 (Domain Model & Fields)

| 區塊 (Section) | 欄位 (Field) | 型別 (Type) | 必填 (Required) | 說明與約束 (Constraints) |
| :--- | :--- | :--- | :---: | :--- |
| **`target`** | `source_type` | `string` | 是 | 儲存庫來源型別，目前嚴格限定支援 `local_git` 與 `github`。 |
| | `repo` | `string` | 是 | 儲存庫識別名稱或路徑，語法依 `source_type` 嚴格綁定：<br>- `github`：**僅接受** `owner/repo` 格式（如 `Gavin0099/company-ssdlc`），不接受 URL 或協議頭。<br>- `local_git`：本機檔案路徑（如 `E:/Company/company-ssdlc` 或相對路徑），**禁止** `owner/repo` 格式。 |
| | `commit` | `string` | 是 | 嚴格 40-character 十六進制 SHA-1 hash（`^[0-9a-fA-F]{40}$`）。**禁止**動態 branch 名稱（如 `main`）或 HEAD，確保不可變性（Immutability）。 |
| **`authority_surface`** | `include` | `list[string]` | 是 | 權威文件路徑 glob 模式清單，**必須至少包含一個元素**。 |
| | `exclude` | `list[string]` | 否 | 排除路徑 glob 模式清單（如草稿、封存檔案）。 |
| **`baseline`** | `framework` | `string` | 是 | 治理標準基準，必須為 `NIST_SP_800_218`。 |
| | `version` | `string` | 是 | 基準版本，**必須為純字串 `"1.1"`**（禁止 YAML float/numeric 隱式轉換）。 |
| **`mode`** | `read_only` | `boolean` | 是 | 審查執行模式，**必須固定為 `true`**，防止意外寫入或狀態污染。 |

---

## Authority Surface Glob 語意分層 (Glob Semantics Layering)

為了維持規格邊界並使 S1-B 職責單純化，Glob 規則嚴格區分為「S1-A 靜態 pattern 邊界約束」與「S1-B Resolver 物化執行承諾」：

### 1. S1-A 靜態 Pattern 邊界約束 (Enforced by S1-A Validator)
- **相對路徑原則 (Relative Only)**：所有 pattern 一律相對於 Target Repo 根目錄，**禁止絕對路徑**（如 Unix `/` 開頭或 Windows `C:` 磁碟機代號）。
- **禁止目錄穿越 (No Directory Traversal)**：Pattern 內**禁止包含 `..`**，防止解析時跳出儲存庫範圍。
- **正斜線正規化 (Normalized Separator)**：統一採用正斜線 `/`，**禁止包含反斜線 `\`**。

### 2. S1-B 物化執行承諾 (S1-B Materialization Obligations)
- **排除優先權 (Exclude Always Wins)**：`include` 收集候選檔案後，凡符合 `exclude` 規則者一律排除。
- **純一般常規檔案 (Regular Files Only)**：僅物化常規檔案，**不跟隨符號連結 (Symlinks)**。
- **確定性排序與 Digest (Deterministic Ordering & Hashing)**：物化後之檔案清單一律按字母排序並計算 SHA-256 形成整體 Corpus Digest。

---

## 行為驅動開發場景 (BDD Scenarios)

### 場景 1: 正確的 Target Manifest 通過驗證
```gherkin
Given 一份結構完整且合規的 Target Manifest YAML
And target.source_type 為 "local_git" 且 repo 為本機路徑，或 source_type 為 "github" 且 repo 為 "owner/repo"
And target.commit 為合法的 40 字元 SHA 雜湊
And authority_surface.include 為非空清單且符合相對路徑約束
And baseline.framework 為 "NIST_SP_800_218" 且 version 為字串 "1.1"
And mode.read_only 為 true
When 執行 validate_target_manifest 驗證
Then 驗證結果必須成功 (exit code 0)，無任何錯誤
```

### 場景 2: source_type 與 repo 格式不匹配觸發 Fail-Closed
```gherkin
Given Target Manifest 中的 target.source_type 為 "github" 但 repo 為本地路徑 "E:/local/repo"
When 執行 validate_target_manifest 驗證
Then 驗證必須失敗 (exit code 1)
And 錯誤訊息必須指出 github source_type 必須為 "owner/repo" 格式
```

### 場景 3: Schema 本身規則缺失觸發 Fail-Closed
```gherkin
Given Schema 檔案缺失 commit_format 或 glob-boundary 規則
When 執行 validate_target_manifest 驗證
Then 驗證必須拋出 Schema 異常並失敗 (exit code 1)
And Validator 嚴禁私自採用程式碼預設值 (No silent fallback)
```

### 場景 4: 浮點數版本 (numeric version: 1.1) 觸發 Fail-Closed
```gherkin
Given Target Manifest 中的 baseline.version 未加引號被解析為 float 1.1
When 執行 validate_target_manifest 驗證
Then 驗證必須失敗 (exit code 1)
And 錯誤訊息必須明確指出 version 必須為字串型別，禁止數值型別
```
