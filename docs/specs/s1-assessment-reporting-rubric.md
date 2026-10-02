# S1 文件覆蓋判定與報告寫法

狀態：REPORT-1 FROZEN（2026-10-01）。使用者已接受合約內容，指定的三項文字小修已納入；不再重開本階段 review。

範圍：澄清既有 S0 / S1 合約；本文件不重判公司 Pilot 的七題，也不修改程式或資料格式。

報告要回答的是：**在這次讀過的文件裡，這個 NIST Task 要求的政策或流程，有沒有寫清楚？**
「還能做得更好」可以列為改善建議。只有直接影響 Task 要求的缺口，才能用來判定 PARTIAL。

## 1. 沿用哪些合約

本文件延續以下合約，不另建一套評估規則：

- [S0 assessment contract](../../experiments/s0-ssdf-direct-assessment/assessment-contract.md)：判定、證據強度、依據與宣稱限制。
- [S1-C corpus assessment spec](s1-corpus-assessment-spec.md)：固定評估範圍、版本與來源綁定。
- [S1-D review engine spec](s1-d-review-engine-spec.md)：報告必須分別保留判定、證據強度、審查建議、依據、宣稱限制與公司來源六個面向。
- [NIST SP 800-218 SSDF v1.1](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf)：Task 的正式要求。

本文件若與既有合約衝突，須修正本文件，不能默默改變原合約。NIST 要求須回到正式原文核對；本地的摘要與提問不能取代原文。

## 2. 五種判定，各自代表什麼

以下保留既有 `coverage_verdict` 五種值。判定對象是這次納入、讀過的文件範圍，不是整家公司。

| 判定 | 白話意思 | 使用邊界 |
| --- | --- | --- |
| `COVERED` | 文件已清楚定義這個 Task 要求的政策或流程。 | 仍可有改善空間；不代表已執行、有效、合規，或做到所有實作例子。 |
| `PARTIAL` | 有寫到，但某個與 Task 直接相關的重要要求，仍缺少或說不清楚。 | 必須指出這個缺口為何妨礙完整覆蓋，不能只列一般最佳實務。 |
| `MISSING` | 在已審閱範圍內，找不到這個 Task 的相關政策或流程。 | 有相關條文但不完整，應檢查是否為 PARTIAL；執行證據弱不等於 MISSING。 |
| `NOT_APPLICABLE` | 來源明確說明這個 Task 不適用，並交代理由。 | 審查者猜測不適用，或文件沒提到，都不足以使用此值。 |
| `UNRESOLVED` | 資料不足、矛盾或來源權威不清，現階段無法判定。 | 要說清楚還缺什麼資料或人工確認；不能當成 MISSING 的另一種寫法。 |

PARTIAL 是已能指出影響 Task 的缺口；UNRESOLVED 是現有材料不足以支持判定。兩者都要說明具體原因。
草稿尚未核准，本身不會自動導致 PARTIAL 或 UNRESOLVED。若條文彼此矛盾，且無法確認應依哪份條文判讀，才須考慮是否無法判定。

## 3. 哪些問題會影響判定

**Task Coverage Gap（影響覆蓋的缺口）**，是直接影響所選 Task 政策或流程要求的重要缺漏或不明確處。
每一個用來支撐 PARTIAL 的缺口，都要交代四件事：

1. NIST 這個 Task 真正要求的是什麼？
2. 公司文件目前寫了什麼？要能回查來源，並考慮同一範圍內其他文件是否已補足。
3. 哪個重要要求仍沒寫，或仍說不清楚？
4. 為什麼缺少這一點，就不能判為 COVERED？

若第四點說不出來，先不要把它當成降低判定的理由。可以保留為改善建議，或說明還需要查證。
不能只寫「沒有核准人、KPI、blocking gate 或 STRIDE，所以 PARTIAL」。必須證明缺少該項與這個 Task 的要求直接相關。
遇到「應／宜」、角色職責或交叉引用，要讀上下文與 Task 原文；不能只憑一個字或文件種類就降級。

**Improvement Opportunity（改善建議）**，是可以讓文件更清楚、治理更一致或更方便追查，但本身不是該 Task 覆蓋必要條件的建議。
例如指定核准角色、統一清冊欄位、補 KPI、升級通報流程、指定方法或改善引用，都可能屬於這一類。

**改善建議不得單獨把 COVERED 降為 PARTIAL。** 如果某項建議其實補的是 Task 必要要求，就要用上面的四個問題證明，再列為覆蓋缺口。
因此不存在一份通用的「核准人永遠只是改善」或「所有 Task 都要有 gate」清單；要逐題判讀。

報告中「finding」可泛指審查發現。真正需要分開的是「影響 Task 覆蓋的缺口」與「不影響覆蓋的改善」，不能把兩者混成一個降級理由。

## 4. NIST 的例子，不是逐項必做清單

NIST 的 Notional Implementation Examples 用來說明 Task 可以怎麼實作；沒有要求每個例子，或某個例子組合，都必須做到（NIST SP 800-218 v1.1，§2「The Secure Software Development Framework」的表格說明；印刷頁 4）。

少做一個例子，不會自動等於 PARTIAL。審查者要回到該 Practice / Task 的正式要求，說明文件究竟缺少什麼。
本地檢查問題與審查者建議，也不能只因為有用，就寫成「NIST 要求」。

## 5. 證據強度看的是「有沒有執行」

`evidence_strength` 沿用 `strong`、`medium`、`weak`，描述證據能多有力地支持「實際已執行這項做法」。它不評政策文字寫得清不清楚，也不取代覆蓋判定。

所以 `coverage_verdict: COVERED` 搭配 `evidence_strength: weak` 可以成立：文件把要求寫完整了，但若只有政策文字，通常仍不足以證明有人真的照做。

條文是否明確、有何矛盾，寫在「影響覆蓋的缺口」與「判定理由」即可。本文件不新增文字清晰度分數，也不重新定義證據強度。

## 6. 文件是否核准，另外交代

**Corpus Authority Context（文件核准與來源狀態）**是報告的說明區塊，沒有新增 machine-readable 欄位或判定值。
它回答的是「這些條文目前具有什麼文件地位」，與「文字是否涵蓋 Task」分開。

公司 Pilot 固定版本 `7e6204a6db02e612569d28f9790b2dd52bc22ba2` 的既有來源狀態如下；這裡只說明來源背景，不重新評估七題。

| 已審閱的 18 份文件 | 份數／說明 |
| --- | --- |
| Draft（草稿） | 16 |
| Under review（審核中） | 1；CORP-0005 |
| Approval status unspecified（未標示核准狀態） | 1；外部 GenesysLogic SSDLC Plan |
| 已審閱範圍內辨識出的已核准文件 | 0 |

白話摘要應寫：「在這次讀過的文件裡，沒有辨識出已核准的正式規範。」不能擴大成「公司沒有正式規範」，也不能把 18 份全部稱為草稿或直接標成 DRAFT-ONLY。
文件標示 `Mandatory`，也不足以單獨證明已核准或生效。

草稿可以在文字上完整涵蓋某個 Task；報告仍須明說不能據此宣稱公司已核准、已生效或已執行。
共同狀態可放在報告開頭，各 finding 明確引用該區塊；若某份文件狀態不同，則另外說明。

## 7. 每個結論都要說清楚出處

沿用三種 `basis`，不要新增或合併：

| 依據 | 報告怎麼說 |
| --- | --- |
| `nist_normative` | 說明正式 NIST Task 的要求，附 Task 與正式來源。只有這類依據可稱為 SSDF Task 要求。 |
| `local_derived_guidance` | 說明本地整理出的檢查問題或證據期待；不能說成 NIST 原文要求。 |
| `reviewer_inference` | 說明審查者的分析或建議，標明是非規範性推論。單靠推論不能證明缺少 NIST 要求。 |

公司文件的出處，另用既有 `company_source_ref`、`company_statement` 與 `identified_evidence` 保留。
報告要分清楚「公司原文寫什麼」與「審查者怎麼解讀」，也要分清楚政策文字和實際執行紀錄。「Company source」是來源歸屬，不是第四種 `basis`。

`assessment_rationale`、`review_queue_recommendation` 與 `cannot_claim` 都須保留，不能因新增兩個說明區塊而省略。
審查建議仍沿用 `pending`、`needs_changes`、`accepted`、`accepted_with_review_due`、`deferred`、`rejected`；它是另一個面向，不可用覆蓋判定或證據強度直接換算。

有明確 Task 歸屬的 `task_finding`，和沒有單一 Task 歸屬的 `non_normative_observation`，仍分開記錄。不能替一般觀察硬加 Task ID 或判定，讓它看起來是 NIST 要求。
來源路徑與 `<corpus>#unmentioned` 的使用限制，仍照 S1-C 合約，不因這份文件放寬。

## 8. 單題報告，用這個順序寫

報告開頭先交代評估範圍、固定版本、來源綁定與限制，再寫各題。以下是人類可讀的排版，不是新 YAML schema，也不要求現有引擎立刻產出這些欄位。

```text
發現編號與類型（finding_id / finding_type）：
評估項目（Task / task_id）：
NIST 這題要求什麼（NIST Task Expectation）：

公司文件寫了什麼（Company Document Statements）：
文件中找到的相關內容（Identified Document Evidence）：
公司文件出處（Company Source / company_source_ref）：

影響覆蓋的缺口（Task Coverage Gap）：
可以再改善的地方（Improvement Opportunity）：

文件覆蓋判定（Coverage Verdict / coverage_verdict）：
實際執行的證據強度（Evidence Strength / evidence_strength）：
文件核准與來源狀態（Corpus Authority Context）：

為什麼這樣判（Assessment Rationale / assessment_rationale）：
判斷依據（Basis）：NIST 正式要求／本地指引／審查者推論，分別標示。
建議如何安排人工審查（Review Queue Recommendation）：
這份結果不能證明什麼（Cannot Claim / cannot_claim）：
```

沒有發現覆蓋缺口，就寫「在本次範圍內未發現」，不要為了填滿欄位而把改善建議搬過來。來源不足而無法判斷，則寫出不足處，不能冒充「沒有缺口」。

Cannot Claim 用來限制讀者可從這份 finding 得出的結論，須依個案清楚寫出。
單靠文件比對，不能宣稱 NIST 合規、組織執行有效、產品或正式環境安全、修復完成、漏洞結案、控制有效、稽核就緒或證據齊全；沒有預先定義分母與方法，也不能換算完整 SSDF 覆蓋率或合規百分比。
來源沒有核准證明時，再加上「不能證明這些規範已核准或生效」。

## 9. PW.4.4：兩個純假設案例

**以下不是公司 Pilot 的真實 finding，不代表對它重新判定。**
共同假設：已讀完案例指定的文件範圍；只找到政策文字，沒有實際執行紀錄；核准狀態未提供。其他文件沒有補足案例所述缺口。

PW.4.4 的正式要求，包含在第三方元件的生命週期中，確認元件符合組織訂定的要求（NIST SP 800-218 v1.1，Task PW.4.4；印刷頁 13）。Task ID 是主要定位依據，頁碼只供輔助。只做導入前的一次檢查，不一定涵蓋後續要求。

下列 Review Queue Recommendation 是依案例情境做的獨立審查建議，不由 Coverage Verdict 自動換算；PARTIAL 不必然等於 needs_changes，COVERED 也不必然等於 accepted 或 pending。

### 案例 A：缺少生命週期內的持續確認

假設政策只要求：「所有第三方元件在導入前必須做一次漏洞檢查。」

- **公司出處**：假設文件 A 的第三方元件條款；不是實際 repo 路徑。
- **影響覆蓋的缺口**：有導入前檢查，卻沒有要求在後續使用期間持續確認元件是否符合組織要求。這直接缺少 Task 的生命週期部分。
- **改善建議**：可再指定負責角色，但不能把指定特定核准人混成上述缺口。
- **判定與理由**：`PARTIAL`；已涵蓋導入前檢查，未涵蓋生命週期內的持續確認。
- **實際執行的證據強度（Evidence Strength）**：`weak`；只有假設政策文字，沒有實際執行紀錄。
- **文件核准與來源狀態（Corpus Authority Context）**：核准狀態未知。
- **依據與審查建議**：Task 要求為 `nist_normative`，缺口理由須由該要求與假設條文的對照支持；角色建議為 `reviewer_inference`。建議 `needs_changes`，交由人工補清楚並審查。
- **不能證明**：已執行、已核准、合規或元件安全；也不能推出真實 Pilot 的判定。

### 案例 B：只缺指定某位核准人

假設政策已完整涵蓋元件生命週期內的要求符合性確認，並清楚要求：符合訂定的安全要求、定期檢視、監控已知漏洞、重新評估或替換停止維護的元件，以及依既定流程處理例外。
這是一組假設做法，用來說明邊界，並非新增 PW.4.4 必做清單。案例中唯一提出的問題，是未指定「由 Security Manager 核准」。

- **公司出處**：假設文件 B 的第三方元件條款；不是實際 repo 路徑。
- **影響覆蓋的缺口**：在上述假設範圍內未發現；僅缺特定核准職稱，尚不足以證明 Task 要求未覆蓋。
- **改善建議**：補上明確核准角色，讓責任更容易追查；除非能證明它對 Task 是重要必要要求，否則只列改善。
- **判定與理由**：在上述假設成立時為 `COVERED`；不能只因未指名 Security Manager 而降為 PARTIAL。這不決定真實 Pilot 的結果。
- **實際執行的證據強度（Evidence Strength）**：`weak`；文字覆蓋完整，仍沒有實際執行紀錄。
- **文件核准與來源狀態（Corpus Authority Context）**：核准狀態未知。
- **依據與審查建議**：Task 要求為 `nist_normative`；指定核准角色為 `reviewer_inference`。建議 `pending`，由人工確認假設與條文解讀，不因 COVERED 自動接受。
- **不能證明**：已執行、已核准、控制有效、合規或元件安全；仍可能有改善空間。

## 10. 本次停止點與後續交接

REPORT-1 只完成規則澄清，完成後停在 **REPORT-1 Review Gate**。七題目前的判定不變，也不預設之後一定維持或升級。
本次不修改 `assessment.yaml`、schema、validator、Review Engine、queue projection、S2 或 provenance；不新增自動語意判定。

後續各階段須先 review，再取得該階段工作授權；以下是交接條件，不是本次授權：

| 階段 | 接下來才做的事 |
| --- | --- |
| REPORT-2 | 逐題重審 PO.1.2、PO.3.1、PS.2.1、PW.1.1、PW.4.4、PW.8.1、RV.1.3，特別檢查 PO.3.1／PW.1.1／PW.4.4；不預設結果。改判時記錄 Previous Verdict、Reassessed Verdict、Reason for Change、Affected Source / Basis。 |
| REPORT-3 | 比較新版報告與現有 machine-readable contract，逐項回答「現有欄位能否清楚表達：YES／NO（NO-NEED／NEED）」。先分析，不因欄位看起來不整齊就改 schema；若確實需要改，另說明舊 assessment 的遷移方式。 |
| REPORT-4 | 依接受的 gap analysis，且取得工具修改授權後，才處理報表產生與必要的工具變更。 |

REPORT-2 若先改人工報告、尚未同步 `assessment.yaml`，須醒目標示 `STATUS: HUMAN REVIEW DRAFT`，並明說機器版仍保留舊判定，直到另行明確更新。不能讓兩份不同結果都自稱正式版本。

驗證器可檢查已實作的結構、合法用語、來源與依據歸屬、provenance 合約及跨欄位限制；不能單靠 PASS 證明審查者讀懂 NIST、正確區分缺口與改善，或判定在語意上一定正確。
目前 S1 的來源驗證只保證檔案屬於固定文件範圍及指紋綁定，不保證章節錨點、行號或逐字引文已核對。REPORT-1 沒有擴大這項能力。

Provenance wording、manifest 外置、tool version 三項工具議題繼續留待後續評估，不混入 REPORT-1～2。

## 11. Review 核對清單

- 保留五種判定與三種 `basis`，沒有取代既有 S0 / S1 合約。
- 缺口與改善分開；改善不得單獨降低判定，NIST 實作例子不是必做清單。
- 證據強度仍指實際執行證據；核准狀態與覆蓋判定分開。
- 保留公司來源、判定理由、審查建議與 Cannot Claim。
- PW.4.4 使用純假設案例；沒有重判真實七題，也沒有修改 schema、程式或 S2。

這份清單供人工 review 使用。REPORT-1 已依使用者的接受條件完成小修並 freeze；這項接受不代表任何真實 Pilot 判定已被驗證。文件格式檢查也不能取代語意審查。
