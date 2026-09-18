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

---

## S1-B 物化演算法與合約 (S1-B Materialization Algorithm & Contract)

Repo Corpus Resolver 在指定 commit SHA 下物化權威文件時，必須保證以下演算法之確定性與安全性：

1. **Commit SHA 凍結確認與儲存庫身分驗證 (Commit & Source Verification)**:
   - 驗證目標儲存庫是否存在該 40 字元 commit SHA，若 commit 不存在或儲存庫無效立即 Fail-Closed。
   - **GitHub 來源身分綁定**：若 `source_type == "github"`，必須驗證本機儲存庫之 remote `origin` URL 確切包含並綁定宣告之 `owner/repo`，未設定或身分不符立即 Fail-Closed，防止來源偽冒。
2. **零工作目錄污染與原始路徑讀取 (Zero Working-Tree Checkout & Raw Path Parsing)**:
   - 透過 `git -c core.quotepath=false ls-tree -r -z --full-tree <commit>` 直接以二進位讀取 NUL (`\0`) 分隔之物件記錄。
   - 檔名不做 C-quoting，支援中文及空格檔名（如 `policy/安全政策.md` 與 `policy/code review.md`），檔名路徑強制以嚴格 UTF-8 解碼。
3. **過濾非檔案物件 (Regular Files Only)**:
   - 僅接受常規 `blob`，排除目錄樹與符號連結（Git mode `120000`），防止符號連結引發任意檔案讀取或路徑逃逸。
4. **權威表面篩選與語意子集 (Authority Surface Filtering & Glob Subset v1)**:
   - Glob 模式嚴格限定為 **Supported Glob Subset v1**：僅支援 `*`、`**`、`?`。任何包含 `[`、`]`、`{`、`}`、`!` 等未支援語法之模式一律 Fail-Closed 阻斷。
   - 候選路徑必須符合 `authority_surface.include` 之 glob 模式。
   - 若定義 `authority_surface.exclude`，凡符合 exclude 模式之候選路徑一律予以排除（Exclude Always Wins）。
5. **嚴格純文字與非二進位保證 (Strict Text & Binary Rejection)**:
   - 讀取之二進位串流若包含 NUL byte (`\x00`) 或除 TAB (`\t`)、LF (`\n`)、CR (`\r`) 以外之 C0 控制字元，立即判定為二進位檔案並拋出異常阻斷（Fail-Closed）。
   - 內容必須可成功以嚴格 UTF-8 解碼。
6. **禁止空文件庫 (Non-Empty Corpus Guarantee)**:
   - 若 include 模式未匹配任何檔案，或匹配之檔案全數被 exclude 排除導致物化檔案數為 0，立即 Fail-Closed 拋出異常，防止 downstream 審查引擎對空文件庫產出錯誤結論。
7. **確定性排序與整體指紋 (Deterministic Sorting & Corpus Digest)**:
   - 物化後之檔案集合一律依 `relative_path`（正斜線路徑字串）升序排序。
   - 全體數位指紋計算公式：
     `corpus_digest = SHA256(sum_i(f"{file_i.relative_path}\t{file_i.content_hash}\n"))`
   - 確保相同 commit 與 manifest 產出的指紋具備嚴格數學可重現性。

### 場景 5: 成功於指定 Commit SHA 物化 CorpusSnapshot（含中文與空格路徑）
```gherkin
Given 一份合法的 Target Manifest 指向 repo 且 commit 為特定 40 字元 SHA
And repo 包含中文檔名 "policy/安全政策.md" 與空格檔名 "policy/code review.md"
And authority_surface 定義 include: ["policy/**"] 與 exclude: ["archive/**"]
When 執行 RepoCorpusResolver.resolve() 物化儲存庫
Then 回傳不可變的 CorpusSnapshot
And 所有檔案路徑（包含中文及空格）完整還原且內容正確解碼
And snapshot.corpus_digest 必須不為空且可穩定重現
```

### 場景 6: Exclude 規則優先於 Include (Exclude Always Wins)
```gherkin
Given authority_surface 定義 include: ["docs/**"] 與 exclude: ["docs/drafts/**"]
And repo 在 docs/drafts/ 有檔案 "docs/drafts/draft.md"
When 執行物化解析
Then 物化後的 snapshot 檔案清單中絕對不得包含 "docs/drafts/draft.md"
```

### 場景 7: 符號連結 (Symlinks) 略過不物化
```gherkin
Given repo 在指定 commit 下包含指向儲存庫外部或敏感檔案之 symlink "policy/link.md"
When 執行物化解析
Then 物化後的 snapshot 檔案清單中必須排除 "policy/link.md"
And 不得拋出異常亦不得讀取符號連結指向之實體檔案
```

### 場景 8: 空文件庫或二進位/NUL 檔案觸發 Fail-Closed
```gherkin
Given authority_surface.include 未匹配任何檔案，或檔案全數被 exclude 排除
When 執行物化解析
Then 必須拋出 CorpusResolverError 拒絕產生空文件庫

Given 權威文件包含 NUL 位元組 (b"a\x00b") 或 C0 控制字元
When 執行物化解析
Then 必須拋出 CorpusResolverError 拒絕二進位檔案
```
