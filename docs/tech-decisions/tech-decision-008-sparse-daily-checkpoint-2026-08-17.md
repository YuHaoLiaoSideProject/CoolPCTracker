# 開發方案決策文件：#008 sparse-daily-and-checkpoint（稀疏異動日誌 + 週全量 Checkpoint）

> **性質**：架構層資料組織評估（tech-assessment-generator 引導，非互動模式產出）
> **對應**：GitHub Issue **#15** `feat(P1): daily/ 改為稀疏異動日誌 + 週全量 checkpoint`
> **範圍**：`data/`（真相層）、`scripts/version_data.py`（衍生層）、`crawler/`（store/main）、`.gitignore`／workflow、測試與 BDD、遷移
> **上游文件**：`docs/interaction-flows/008-sparse-daily-and-checkpoint.md`（主輸入）、`docs/tech-decisions/tech-decision-資料拆檔方案-2026-08-17.md`（背景：現行 daily/ 每日價格點檔契約 v2）
> **決策方式**：基於上游文件 + 現行程式碼實測推導，**不提問**；所有決策點（D1–D4）由評估者給定推薦結論，待實作前的 spec/review 階段正式確認

---

## 📌 決策摘要

| 項目 | 內容 |
|------|------|
| **最終方案** | **方案 S「稀疏 delta + 週 checkpoint + 回放重建」**：`data/daily/{YYYYMMDD}.json` 語意改為「**異動日誌**」——只寫當日真正異動（`changed`+`new`）商品的 `{id: price}`，平價日（無異動）**不寫檔案**；新增 `data/checkpoints/{YYYYMMDD}.json` = **每 7 天（距上次 ≥7 天）全量價格快照** `{id: price}`（等同現行 daily 全量），作為自癒錨點與回放上限；`version_data.build_trends` 改為「**最新 checkpoint（全量起點）＋ 回放之後稀疏異動 → 逐日 carry forward**」重建完整 `history`；對外 API 面（items/daily/trends/index）**完全不變** |
| **決策日期** | 2026-08-17 |
| **決策前提** | ① 歷史價格點不可刪（004 趨勢圖／003 漲跌徽章）；② 全靜態 GitHub Pages、無後端；③ issue #15 已定案的資料模型與 store/version_data/main 改動方向為基礎，本文件在此之上補足取捨、邊界與遷移細節 |
| **核心效益** | daily 從 ~35KB/天 → **1–2KB/天（異動日）**、平價日零寫入；一年 `data/daily` 由 ~12.5MB 降至 **<1MB**；`data/checkpoints` 新增 52×35KB ≈ **1.8MB/年**；合計一年 repo raw 由 ~12.5MB+ 降至 **~2.8MB**（+ checkpoint 後 ~1.8MB）＝「舊 12.5MB → 新 ~2.8MB」，**~78% 縮減**；git diff 不再有整檔 noise；delta 遺失最多回放 7 天即可自癒 |
| **共識程度** | ✅ 非互動推導，共識待 spec/review 階段確認（決策點 §6.3） |

---

## 1. 需求回顧

### 1.1 使用者／Issue 訴求（原始陳述）

> 「讓 `data/daily/` 只存『價格/狀態真的異動的商品』（稀疏 delta），平價日不寫入，並以每 7 天的全量快照 `data/checkpoints/{YYYYMMDD}.json` 作為歷史回溯錨點，同時解決 `data/items/{g}.json` 因 last_seen 天天變而每日整檔重寫、git diff 全是 noise 的問題。」

**拆解出的痛點**：
- **痛點 A（daily/ 無限累積）**：現行契約 v2（`tech-decision-資料拆檔方案`）`data/daily/{YYYYMMDD}.json` 每日寫入**全部** ~1448 筆商品 `{id: price}`（實測 20260815/16/17 各 ~35KB），含平價日。一年 ~12.5MB，且每天整檔重寫、git diff 全檔 noise。
- **痛點 B（items/{g} 的 last_seen noise）**：`crawler/apply()` 對所有商品每日更新 `last_seen`，`store.save()` 每日整檔重寫 `data/items/{g}.json`，即使價格沒變，git diff 每天也整檔跳動。
- **隱含前提**：歷史不可刪、維持全靜態架構、repo 體積可控、單人維護、每日單次爬蟲。

### 1.2 需求假設（評估者由上游文件與現況推導）

| 假設 | 內容 | 依據 |
|------|------|------|
| H1 | 歷史價格點必須可重建（趨勢圖 004、漲跌徽章 003） | 資料拆檔文件 §決策前提① |
| H2 | 對外 API 契約（items/{g} + daily + trends/{id} + index）**不變**，前端零改動 | 上游 IF §6「保留 daily/ 原名」、避免大量 refactor；version_data 現行輸出 |
| H3 | checkpoint 是**真相層內部錨點**，**不回放到 api/（前端不需）** | api/trends 已預先組裝完整歷史；回放只需 data/checkpoints |
| H4 | 平價日應**零 git 變動**（不寫 daily、不重寫 items）以根除 noise | issue 核心；workflow 以 version_data `changed` 控制 commit |
| H5 | `build_trends` 輸出必須與現行全量回放**完全等價**（equivalence test） | 上游 IF §5／驗收：`api/trends` 與改動前一致 |

### 1.3 非需求
- ❌ 不是把歷史丟掉／不是引入 DB／不是改變對外 API 面
- ❌ 不是把 `data/items/{g}.json` 也切成每日檔（O5 已被資料拆檔決策否決；本 issue 不再重開）
- ❌ 不是把 checkpoint 暴露給前端消費

---

## 2. 現況量化診斷（2026-08-17 實測）

### 2.1 現行 daily/ 是「全量」而非稀疏

```
data/daily/20260815.json   35,526 B
data/daily/20260816.json   35,552 B
data/daily/20260817.json   35,351 B
```

- 三檔皆 ~35KB、各含 ~1448 筆（每日全量）。`crawler/main.py` 以
  `write_daily(day, {item.id: item.price for item in unique_today ...})` 寫入**全部今日商品**。
- `.gitignore` 已放行 `data/daily/**`、`data/items/**`；尚無 `data/checkpoints/`。

### 2.2 每日噪音兩處來源

| 來源 | 觸發 | 現況 |
|---|---|---|
| **daily/** 全量 | 每日寫入全量 `{id:price}`（含平價日） | 每日 ~35KB 全檔重寫 |
| **items/{g}/ last_seen** | `apply()` 對每商品 update `last_seen` → `save()` 整檔重寫 | 每日整檔重寫、git 全檔 noise |

### 2.3 一年成長總帳（現況 vs 目標）

| 項目 | 現況（契約 v2） | 方案 S 目標 | 縮減 |
|---|---|---|---|
| `data/daily/` 年度 | ~12.5MB（365×35KB） | **<1MB**（僅異動日 ~1–2KB） | ~92% |
| `data/checkpoints/`（新增） | — | ~1.8MB（52×35KB） | +1.8MB |
| `data/items/{g}` | 每分類每日重寫 | 僅**實質異動分類**重寫 | 平價日零 |
| **真相層合計/年** | ~12.5MB+ | **~2.8MB** | **~78%（淨減）** |
| git diff（平價日） | daily 全檔 + items 全檔 noise | **零檔案** | 根除 |

> 註：checkpoint 每 7 天一檔（~35KB 全量）＝每年 ~180KB×... 更正：52 週 × 35KB ≈ 1.8MB。trends 仍由 `api/`（deploy 時重建、不進版控）承載，本文件不重複計算。

---

## 3. 候選方案

### 方案 S（推薦）：稀疏 delta + 週 checkpoint + 回放重建
依 issue #15 定案方向深化。核心機制三件套：
1. **稀疏 daily**：`write_daily` 只收 `changed+new` 的 `{id:price}`；平價日不寫檔。
2. **週 checkpoint**：`write_checkpoint` 距上次 ≥7 天寫一檔全量 `{id:price}`；首次 run seed 一檔。
3. **回放重建**：`build_trends` 以最新 checkpoint 為全量起點，回放之後稀疏異動「逐日 carry forward」填滿每日平價點，輸出完整 `history`；checkpoint 之前若有殘留 daily（遷移相容）走 legacy 全量回放。

### 方案 L（保守）：維持現行每日全量，僅加上 checkpoint 錨點
daily 仍全量寫入（v2 現狀），純新增週 checkpoint，`build_trends` 仍全量回放（checkpoint 僅供自癒／災難復原）。
- **優點**：改動最小、`build_trends` 幾乎不動、無 carry-forward 等價風險。
- **缺點**：**痛點 A（daily 全量 35KB/天 + git noise）完全沒解決**；只有痛點 B（可搭配 items gating）與自癒略微改善。一年 daily 仍 ~12.5MB。
- 結論：只做到「checkpoint 自癒」，犧牲 issue 的核心動機（稀疏、git 節省），不達標。

### 方案 P（激進）：稀疏 daily + 每商品獨立 checkpoint / 索引化
把 checkpoint 依商品切細（`checkpoints/商品id.json`）或用 SQLite／壓縮檔管理歷史。
- **優點**：回放成本與儲存最低、理論最省。
- **缺點**：引入每商品多檔（回歸 1448×N 檔問題）或非純 JSON 真相層，**違反「純靜態、純標準庫、單檔可稽核」的專案定位**；與 v2 已定案的 `{id:price}` 單檔契約不一致。過度設計。

---

## 4. 權衡評估

### 4.1 權衡矩陣（1–5 分，5 最佳）

| 維度 | L 保守 | **S 稀疏+checkpoint** | P 激進 |
|---|:---:|:---:|:---:|
| 🎯 需求符合度（稀疏＋消 noise） | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| ⚡ 開發成本（改動範圍） | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 🔧 維護成本（長期） | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| 📦 repo 體積（1 年後） | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 🗂️ git diff 可讀性（平價日） | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 🔒 回歸風險（equivalence） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 🧭 與 v2 契約相容 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **總分** | **23** | **30** | **24** |

### 4.2 關鍵取捨

**取捨 #1：carry-forward 的「消失商品（gone）」尾巴**
- 稀疏 daily 只記「有異動商品」，不記「誰還活著（unchanged alive）」。因此 checkpoint 之間若某商品變 gone，回放 carry-forward 會在 up-to-7 天內**持續輸出其最後價格**，直到下一個 checkpoint（全量）將它移除。
- 對策：以「最新 checkpoint 的 alive 集合」做 carry-forward 基準；gone 只在中途消失的商品有 ≤7 天暫存尾巴，下一次 checkpoint 自動校正（自癒 IF §5）。等價測試以「不出現中途消失」的受控資料驗證 S 與 legacy 完全一致，單獨文件化此邊界。**接受（單人專案、gone 低頻、7 天自校正）**。

**取捨 #2：checkpoint 日是否也寫稀疏 daily**
- 選項（a）checkpoint 日仍正常寫稀疏 daily（daily 序列連續、`latest daily` 檔名邏輯不破）＋ 補一份全量 checkpoint（內容 ⊇ 當日異動）；選項（b）checkpoint 日不寫稀疏 daily（省一份冗餘，但 daily_files 序列斷一檔）。
- **決策（D3）：取（a）**——daily 序列完整、workflow 依賴 `filename`（最新 daily 檔名）產 commit message，維持連續性最穩；冗餘僅 checkpoint 日一份、可忽略。

**取捨 #3：`build_trends` 對「最新 checkpoint 之前的舊 daily」處理（遷移）**
- 上線時既有 `data/daily/` 仍是**全量檔**（20260815/16/17）。這些檔「每檔即一組全量當日價」，回放當天＝把該商品該日設為檔內值——語意與稀疏一致（甚至更強）。因此可**完整保留**作為 legacy 回放源，不破壞等價。
- **決策（D4 遷移）**：seed 一份 checkpoint（取現有**最舊全量 daily** 的內容），**保留所有既有 daily 全量檔**（不刪除、不歸檔）供 `build_trends` 以全量語意回放；status==failed 防線下不寫、不遷移。非破壞式、等價可驗證（§6.2）。

**取捨 #4：items/{g}.json 的 last_seen 每日重寫（痛點 B）**
- `last_seen` 在前端僅為被動欄位（`useItems.ts` 透過型別帶過、無漲跌計算依賴）；卡片漲跌徽章以 `history` 末 2 點計算。
- **決策（D2）**：`store.save()` 對「**本 run 無實質異動（new/changed/refreshed/gone/status）的某分類**」**跳過重寫該分類檔**（純平價日不重寫 items）。`last_seen` 在平價日不更新（保留最後一次異動日），語意可接受；有實質異動的分類照常重寫。→ 根除痛點 B。

---

## 5. 決策理由

### 5.1 為什麼選方案 S
1. **正面解決 issue 兩個痛點**：daily 稀疏化（~35KB→1–2KB、平價日零寫入）＋ items gating（平價日不重寫）＝git diff 全面淨化，一年 repo 成長由 ~12.5MB+ 降至 ~2.8MB（~78% 淨減）。
2. **全量 checkpoint 提供自癒＋回放錨點**：build_trends 以所有 checkpoint 依序 chain 全量重置 carrier，delta 遺失/損壞時 carry forward 補齊（無缺口日），最壞延遲 ≤7 天（平價持續 7 天無異動時無法分辨），下一 checkpoint 全量校正（D6）；同時把回放 compute cost 固定在 <1ms、把「完整價格真相」週期性落盤，兼顧可稽核。
3. **對外零衝擊、與 v2 契約相容**：api 面（items/daily/trends/index）與前端完全不動；`daily/` 保留原名（僅語意改「異動」，docstring 註明）；維護成本與單人專案定位一致。

### 5.2 為什麼放棄其他方案
| 方案 | 放棄理由 |
|---|---|
| **L 保守** | 只加 checkpoint、不改稀疏——痛點 A（daily 全量、git noise）原封不動，違背 issue 核心動機；checkpoint 成為「孤兒錨點」但 daily 還是 12.5MB/年。 |
| **P 激進** | 每商品切檔／非純 JSON 真相層，回歸 1448×N 檔與「純靜態＋標準庫」定位；過度設計、單人專案不划算。 |
| （沿用 O5 拆每日 items） | 資料拆檔決策已否決（無消費者、crawler 重構成本最高），本 issue 不再重開。 |

### 5.3 分階段執行策略
| 階段 | 內容 | 依賴 |
|---|---|---|
| **Phase 1** | version_data `build_trends` 回放核心（checkpoint + 稀疏 carry-forward + legacy 相容）+ 等價測試 | —（可先做，獨立於 crawler） |
| **Phase 2** | crawler store `write_daily` 收稀疏 + 新增 `write_checkpoint` + `save` items gating；main 改呼叫與 checkpoint 調度 | Phase 1 的語意模型 |
| **Phase 3** | 遷移腳本（seed checkpoint（最舊）+ 保留所有 legacy daily）、`.gitignore`/workflow（`data/checkpoints/**` 入庫、changed 判定含 checkpoint）、BDD/文件同步 | Phase 2 |
| **Phase 4** | 回歸：`tests/test_crawl_workflow.py` 等價、`test_gitignore`、store/main/version_data 全套 | Phase 1–3 |

---

## 6. 行動計畫

### 6.1 目標資料模型（方案 S 定稿）

```
data/                        # 真相層（crawler 唯一寫入者）
  items/{g}.json             # （不變）目前狀態快照；history 序列化截最近 ≤2 點（D1 定稿：維持現策略）；
                             #   save 對「無實質異動的分類」跳過重寫（D2）
  meta.json                  # （不變）
  daily/YYYYMMDD.json        # 【語意改為稀疏異動】{item_id: price}，只含當日 changed+new（價格存在者）；
                             #   平價日不寫檔（D3）；仍 compact 原子寫
  checkpoints/YYYYMMDD.json  # 【新增】全量價格快照 {item_id: price}；距上次 checkpoint ≥7 天寫一份；
                             #   首次 run seed 一份；crawler 唯一寫入者（D4 遷移 seed 由遷移腳本）

api/                         # 對外層（version_data 組裝；完全不變）
  items/{g}.json             # 鏡像（不變）
  daily/YYYYMMDD.json        # 鏡像（稀疏內容；不變結構）
  trends/{item_id}.json      # 【輸出改】完整歷史由「checkpoint + 稀疏回放 carry-forward」重建（Phase 1）
  index.json                 # categories[] + daily_files[] + trends_prefix（不變；不含 checkpoint）
```

### 6.2 任務拆分

| # | 任務 | 檔案 | 依賴 |
|---|------|------|------|
| T1 | `build_trends` 重建：**所有 checkpoint 依序 chain**（各全量重置 carrier）＋ 其間稀疏 carry-forward（全窗口逐日重建）；無 checkpoint → legacy 全量回放；輸出與現行等價 | `scripts/version_data.py` | — |
| T2 | `build_trends` 等價測試（合成 legacy 全量 ↔ checkpoint+稀疏 → 同輸出）；含「中途消失商品」邊界 case | `scripts/tests/test_version_data.py`、`tests/test_crawl_workflow.py` | T1 |
| T3 | `store.write_daily` 語意改稀疏（只收 changed+new；空 map 不寫檔）；保留現簽名、docstring 註明異動語意 | `crawler/store.py`、`crawler/tests/test_store.py` | — |
| T4 | 新增 `store.write_checkpoint(day, full_price_map)`（原子、compact、`data/checkpoints/YYYYMMDD.json`） | `crawler/store.py`、`crawler/tests/test_store.py` | T3 |
| T5 | `store.save` items gating：無實質異動分類不重寫（D2，`last_seen` 平價日不更新） | `crawler/store.py`、`crawler/tests/test_store.py`、`crawler/tests/test_main.py` | T3 |
| T6 | `main`：`write_daily` 改傳 `changed+new` 的 `{id:price}`（非空才寫）；新增 checkpoint 調度（首 run seed、≥7 天寫） | `crawler/main.py`、`crawler/tests/test_main.py` | T4/T5 |
| T7 | 遷移腳本 `scripts/migrate_checkpoints.py`：seed checkpoint（**最舊全量 daily** 內容）、**保留所有既有 daily** 為 legacy（不刪除不歸檔）、防線（failed/status 不遷移） | `scripts/`（新增）、`scripts/tests/` | T4 |
| T8 | `.gitignore` + workflow：`data/checkpoints/**` 入庫（`test_gitignore` 補斷言）；version_data changed 判定含「新 checkpoint」；commit message 處理 | `.gitignore`、`.github/workflows/crawl.yml`、`tests/test_gitignore.py` | T6/T7 |
| T9 | BDD／文件同步：008 IF、README「資料/API 組織」、流水 `docs/bdds/*`、`docs/development/*`（若有對應） | `docs/**`、`README.md` | T6/T7 |
| T10 | 回歸全套（crawler / scripts / workflow / gitignore）+ 等價驗證 | `tests/` | T1–T9 |

### 6.3 決策點（非互動推導，待 spec/review 正式確認）

| 決策點 | 選項 | 評估者結論（待確認） |
|---|---|---|
| **D1** items/{g} history 截斷策略 | a) **維持 ≤2 點（現狀）**；b) 改「只保留最近 checkpoint 之後的異動點」 | ✅ **a 維持 ≤2 點**：漲跌徽章只需末 2 點，且「checkpoint 截斷」反可能讓平價週後徽章失去前次異動基準；重審後現策略已足 |
| **D2** items/{g} 每分類平價日是否重寫 | a) 照舊每日重寫；b) **僅實質異動分類重寫** | ✅ **b（gating）**：根除痛點 B；`last_seen` 平價日不更新（保留最後異動日，前端為被動欄位、可接受） |
| **D3** 純平價日是否產 daily 檔 | a) 寫空 `{}`；b) **不寫檔** | ✅ **b 不寫檔**：才達成「平價日零 git 變動」；checkpoint 日仍照常寫稀疏 daily（daily 序列連續） |
| **D4** 遷移策略 | a) seed checkpoint＝**最舊**全量 daily；保留**所有**既有 daily 為 legacy 全量回放源（不刪除）；b) seed＝最新 daily＋刪更早檔 | ✅ **a（非破壞式）**：seed=最舊全量 daily 為歷史錨點；保留所有舊 daily 供 `build_trends` 全量回放（刪除任一舊日會導致該日歷史遺失，違反 P0 等價保證）；隨時間推移 legacy daily 自然縮減（不再新增全量 daily） |
| **D5** checkpoint 是否上 api/ | a) data/ 內部僅供回放；b) 鏡像 api/checkpoints/ | ✅ **a**：前端無需 checkpoint（trends 已預組裝）；維持 api/ 契約不變 |
| **D6** gone 商品中途消失的回放尾巴 | a) 接受 ≤7 天暫存尾巴（下個 checkpoint 自校正）；b) 引入 alive 集合補正 | ✅ **a（接受並文件化）**：單人專案、gone 低頻、7 天自癒；等價測試以受控資料驗證 S 與 legacy 完全一致 |

---

## 7. 風險登錄

| 風險 | 可能性 | 影響 | 緩解 |
|------|--------|------|------|
| `build_trends` 回放邏輯與現行全量回放在某些資料下不等價 | 中 | 高 | T2 等價測試（合成 legacy↔S 雙向）＋ T10 回歸；`history` 升冪、carry-forward 為純函數可單測 |
| 稀疏 daily 後 version_data「changed / filename（最新 daily）」判定失準 | 中 | 中 | changed 增加「新 checkpoint」判準；checkpoint 日正常寫稀疏 daily 維持 `filename` 連續 |
| 平價日 gating 後 `last_seen` 停滯被誤解（前端展示） | 低 | 低 | `last_seen` 為被動欄位（useItems.ts 無計算依賴）；文件化語意「最近異動/錨點日」；meta.crawled_at 仍為每日 |
| checkpoint 日爬取失敗（status=failed） | 中 | 低 | 健康檢查防線（IF §5）：不寫 items/不寫 checkpoint；下次成功 run 距上次 ≥7 天仍成立 → 自動補寫（自癒） |
| 遷移（seed checkpoint）與既有 daily 併存造成回放重複點 | 低 | 中 | legacy 全量檔「當天＝全量覆寫」語意與稀疏相容；checkpoint 與 legacy daily 同日不並存（seed 用日期錯開／回放去重防護 bucket 末筆同日期） |
| repo 體積因 checkpoint 增 ~1.8MB/年 | 確定 | 低 | 相比舊 daily 12.5MB/年少 ~78%；可接受；checkpoint 為真相層固定 7 天節奏 |
| 同檔案同日併發（cron / 手動）寫 checkpoint | 低 | 中 | 原子寫入（tempfile+os.replace）；workflow 既有 concurrency group 防護 |

---

## 📝 決策後續

- 本文件已存至 `docs/tech-decisions/tech-decision-008-sparse-daily-checkpoint-2026-08-17.md`，應納入版本控制。
- **決策待確認**：§6.3 六個決策點（D1–D6）為非互動推導結論，建議在 development-spec-generator／loop-review 階段正式確認後展開 Phase 1–4。
- 實作以現行契約（README「資料/API 組織」、development/BDD）為準；對外 API 面保持不變為硬性約束。
- 建議 1 個月後回顧：repo 成長率（應降至 ~2.8MB/年）、平價日 git 變動（應為零）、回放等價是否持續成立。
