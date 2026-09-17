# S1-A Target Manifest Specification

## 目的 (Purpose)
定義真實儲存庫（Target Repository）文件涵蓋度審查的目標規格清單（Target Manifest）。
本規格回答核心問題：
> **「我要 review 哪一個 repo、哪一個 commit、哪些檔案才算 authoritative SSDLC？」**

---

## 領域模型與欄位定義 (Domain Model & Fields)

| 區塊 (Section) | 欄位 (Field) | 型別 (Type) | 必填 (Required) | 說明與約束 (Constraints) |
| :--- | :--- | :--- | :---: | :--- |
| **`target`** | `repo` | `string` | 是 | 儲存庫識別名稱、路徑或 URL，不可為空。 |
| | `commit` | `string` | 是 | 嚴格 40-character 十六進制 SHA-1 hash（`^[0-9a-fA-F]{40}$`）。**禁止**動態 branch 名稱（如 `main`）或 HEAD，確保不可變性（Immutability）。 |
| **`authority_surface`** | `include` | `list[string]` | 是 | 權威文件路徑 glob 模式清單，**必須至少包含一個元素**。 |
| | `exclude` | `list[string]` | 否 | 排除路徑 glob 模式清單（如草稿、封存檔案）。 |
| **`baseline`** | `framework` | `string` | 是 | 治理標準基準，必須為 `NIST_SP_800_218`。 |
| | `version` | `string` | 是 | 基準版本，必須為 `"1.1"`。 |
| **`mode`** | `read_only` | `boolean` | 是 | 審查執行模式，**必須固定為 `true`**，防止意外寫入或狀態污染。 |

---

## 行為驅動開發場景 (BDD Scenarios)

### 場景 1: 正確的 Target Manifest 通過驗證
```gherkin
Given 一份結構完整且合規的 Target Manifest YAML
And target.repo 為非空字串
And target.commit 為合法的 40 字元 SHA 雜湊
And authority_surface.include 為非空清單
And baseline.framework 為 "NIST_SP_800_218" 且 version 為 "1.1"
And mode.read_only 為 true
When 執行 validate_target_manifest 驗證
Then 驗證結果必須成功 (exit code 0)，無任何錯誤
```

### 場景 2: 使用動態 Branch 或格式錯誤之 Commit SHA 觸發 Fail-Closed
```gherkin
Given Target Manifest 中的 target.commit 設定為 "main" 或短 hash (如 "83da91f")
When 執行 validate_target_manifest 驗證
Then 驗證必須失敗 (exit code 1)
And 錯誤訊息必須明確指出 commit 必須為 40 字元的完整 SHA
```

### 場景 3: 未提供權威 Include 路徑表面觸發 Fail-Closed
```gherkin
Given Target Manifest 中的 authority_surface.include 為空清單或缺失
When 執行 validate_target_manifest 驗證
Then 驗證必須失敗 (exit code 1)
And 錯誤訊息必須明確指出 authority_surface.include 不可為空
```

### 場景 4: 非唯讀模式 (read_only != true) 觸發 Fail-Closed
```gherkin
Given Target Manifest 中的 mode.read_only 為 false 或非布林值
When 執行 validate_target_manifest 驗證
Then 驗證必須失敗 (exit code 1)
And 錯誤訊息必須明確指出 mode.read_only 必須為 true
```

---

## 宣稱邊界 (Claim Boundaries)
1. **靜態合約驗證**：本規格僅驗證 Target Manifest 文件本身之資料結構與約束，**不保證**遠端儲存庫是否存在或是否能成功 clone。
2. **無語意推論**：本規格**不對** include 模式所匹配到的文件內容進行 AI 審查或涵蓋度判定。
