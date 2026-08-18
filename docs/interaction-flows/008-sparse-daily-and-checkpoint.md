# Interaction Flow：008 稀疏異動日誌 + 週全量 Checkpoint

> 對應 GitHub Issue：`#15 feat(P1): daily/ 改為稀疏異動日誌 + 週全量 checkpoint`
> 角色：**系統自動**（crawler 每日排程 + version_data.py 版本化重建）+ **維護者**（遷移、除錯、review）

---

## 1. 功能概述

**一句話描述**：讓 `data/daily/` 只存「價格/狀態真的異動的商品」（稀疏 delta），平價日不寫入，並以每 7 天的全量快照 `data/checkpoints/` 作為歷史回溯錨點，大幅縮減儲存與 git noise，同時確保完整歷史可重建。

**核心價值**：
- 解決 `daily/` 每日整檔重寫（~35KB/天、含平價日 ~1440 筆）的無限累積問題
- 從一年 ~12MB+ 降至 <1MB（異動檔）+ ~1.8MB/年（52×35KB checkpoint）
- 同時解決 `items/{g}.json` 因 `last_seen` 天天變而每日整檔重寫、git diff 全是 noise 的問題
- 全量 checkpoint 確保即使某天 delta 丟失，最多回放 7 天即可補回（自癒能力）

---

## 2. 使用者與場景

| 項目 | 內容 |
|------|------|
| **角色** | ① **系統自動**：`crawler/main.py` 每日排程（GitHub Actions cron）自動執行 ② **系統自動**：`scripts/version_data.py` 接續重建對外 API ③ **維護者**：專案擁有者，執行遷移、除錯、review |
| **觸發入口** | ① 每日 06:00 UTC cron 自動觸發爬蟲（主要） ② 維護者在 GitHub Actions 頁面點擊「Run workflow」手動補爬 ③ 遷移腳本由維護者手動執行一次（一次性） |
| **前置條件** | ① `crawler/store.py` 的 diff 已能辨識 `changed_items` / `new_items` / `unchanged_ids` ② 既有 `data/daily/` 全量檔存在（需遷移）或尚無 checkpoint（首次 run 需補） ③ `data/items/` 分類檔為目前狀態快照 |
| **使用情境** | 每日爬蟲自動寫入稀疏異動檔；每 7 天自動寫入全量 checkpoint；版本化重建時由「所有 checkpoint chain + 回放 delta」計算完整歷史；遷移腳本在部署後執行一次 |

---

## 3. 操作流程圖

```mermaid
flowchart TD
    Cron([每日 06:00 UTC cron 自動觸發]) --> Fetch[抓取 9 個分類頁<br/>m-list.php?G=1,3,4,5,6,7,8,9,12]
    Manual([維護者 Run workflow 補爬]) --> Fetch
    Fetch --> Diff[diff 辨識<br/>new / changed / refreshed<br/>unchanged / gone / carryover]
    Diff --> Sparse[寫入稀疏異動檔<br/>data/daily/{YYYYMMDD}.json<br/>只含異動+新增商品 {id: price}]
    Sparse --> Checkpoint{距上次 checkpoint<br/>≥ 7 天?}
    Checkpoint -- 否 --> Save[覆寫 items/{g}.json<br/>meta.json 更新]
    Checkpoint -- 是 --> Full[寫入全量快照<br/>data/checkpoints/{YYYYMMDD}.json<br/>等同舊 daily 全量 {id: price}]
    Full --> Save
    Save --> Version[version_data.py<br/>chain 所有 checkpoint<br/>+ 回放其間 delta]
    Version --> Trends[重建 api/trends/{id}.json<br/>逐日 carry forward 完整 history]
    Trends --> Done([結束])
    NoChk([首次 run：無 checkpoint]) --> Migrate[以最舊全量 daily 檔<br/>作為 checkpoint]
    Migrate --> Version

    NoChk --> NoChk2([無任何 daily 檔<br/>→ 純新增模式])
    NoChk2 --> Sparse

    style NoChk fill:#fff0f0,stroke:#e00
```

---

## 4. 逐步互動說明

### 步驟 1：觸發爬蟲執行

| | 描述 |
|---|------|
| **觸發** | GitHub Actions cron 每日 06:00 UTC 自動觸發；或維護者在 GitHub Actions 頁面點擊「Run workflow」手動補爬 |
| **操作前** | 系統上一個執行週期結束；維護者已開啟 workflow 頁面 |
| **系統回應** | workflow 啟動，進入 fetch → parse 階段 |
| **操作後** | 產生今日商品清單（含分類、spec、ID） |
| **下一步** | 步驟 2：diff 辨識異動 |

### 步驟 2：diff 辨識異動

| | 描述 |
|---|------|
| **觸發** | 系統自動執行 `store.diff()` |
| **操作前** | 已取得今日商品清單；`data/items/` 載入為上次狀態快照 |
| **系統回應** | 逐商品與上次比對，分為 `new_items` / `changed_items` / `refreshed_items` / `unchanged_ids` / `gone_ids` / `carryover_ids` |
| **操作後** | 得到異動分類結果 |
| **下一步** | 步驟 3：寫入稀疏異動檔 |

### 步驟 3：寫入稀疏異動檔

| | 描述 |
|---|------|
| **觸發** | 系統自動呼叫 `store.write_daily()` |
| **操作前** | 已取得 diff 結果（異動+新增商品） |
| **系統回應** | 只將「價格/狀態真的異動」的商品（`changed_items` + `new_items`，且價格存在）寫入 `data/daily/{YYYYMMDD}.json` 為 `{id: price}`；**平價日（unchanged）不寫入** |
| **操作後** | daily 檔只含當日真正異動的商品（稀疏） |
| **下一步** | 步驟 4：Checkpoint 調度判斷 |

### 步驟 4：Checkpoint 調度判斷

| | 描述 |
|---|------|
| **觸發** | 系統自動判斷今天是否為 checkpoint 日 |
| **操作前** | 已寫入稀疏 daily 檔 |
| **系統回應** | 檢查最近一次 checkpoint 日期：距今天 ≥ 7 天 → 今天是 checkpoint 日；否則不是 |
| **操作後** | 得到是否寫 checkpoint 的判斷結果 |
| **下一步** | 是 → 步驟 5：寫入全量快照；否 → 步驟 6：更新 items/meta |

### 步驟 5：寫入全量快照（Checkpoint 日）

| | 描述 |
|---|------|
| **觸發** | 判定今天是 checkpoint 日（距上次 ≥ 7 天） |
| **操作前** | 已寫入稀疏 daily 檔；判斷為 checkpoint 日 |
| **系統回應** | 將當日所有商品的全量價格寫入 `data/checkpoints/{YYYYMMDD}.json` 為 `{id: price}`（等同舊 daily 全量寫入） |
| **操作後** | 全量快照建立，作為未來回放的自癒錨點 |
| **下一步** | 步驟 6：更新 items/meta |

### 步驟 6：覆寫 items 並更新 meta

| | 描述 |
|---|------|
| **觸發** | 系統自動呼叫 `store.save()` + `store.write_meta()` |
| **操作前** | 已寫入 daily（+可能 checkpoint） |
| **系統回應** | 覆寫 `data/items/{g}.json` 各分類檔、更新 `data/meta.json`（crawled_at / total / status） |
| **操作後** | 目前狀態快照與 meta 皆為最新 |
| **下一步** | 步驟 7：版本化重建（version_data.py） |

### 步驟 7：版本化重建

| | 描述 |
|---|------|
| **觸發** | 爬蟲完成後，`scripts/version_data.py` 自動執行 |
| **操作前** | data/ 已有最新稀疏 daily、可能的新 checkpoint、最新 items |
| **系統回應** | 讀取**所有 checkpoint**（各全量快照）依序 chain 全量重置 carrier，其間稀疏異動檔逐日 carry forward，輸出完整 `history`（`[[d, p], ...]`） |
| **操作後** | 每個商品的完整歷史被重建，寫入 `api/trends/{id}.json` |
| **下一步** | 結束 |

### 步驟 8：（遷移）首次執行無 checkpoint

| | 描述 |
|---|------|
| **觸發** | 部署後首次 run，`data/checkpoints/` 尚不存在 |
| **操作前** | 既有 `data/daily/` 全量檔存在（或完全無資料） |
| **系統回應** | 若有舊全量 daily 檔 → 以**最舊**的全量 daily 檔 seed 一份 checkpoint；**保留所有**既有 daily 檔為 legacy 全量回放源（不刪除、不歸檔）；若無任何 daily 檔 → 純新增模式 |
| **操作後** | 既有資料不破壞（所有舊 daily 保留供全量回放），新資料結構就緒 |
| **下一步** | 步驟 7：版本化重建 |

---

## 5. 異常處理

| 錯誤情境 | 系統行為（看到的回饋） | 恢復路徑 |
|---------|------------------------|---------|
| **某天 delta 檔案遺失/損壞** | build_trends 以 checkpoint chain + delta carry forward 自動補齊遺失日（無缺口日）；最壞延遲 ≤7 天（平價持續 7 天無法分辨）；不需人工介入；下次 checkpoint 全量校正 |
| **首次 run 無 checkpoint**（已存在舊 daily 全量檔） | 以最舊的全量 daily 檔 seed 一份 checkpoint；保留所有舊 daily 為 legacy 回放源（不刪除） | 遷移腳本執行一次，之後自動 |
| **遷移前舊 daily 全量檔仍在** | build_trends 以 legacy 全量語意回放舊全量 daily；seed checkpoint 為最舊日；所有舊 daily 完整保留 | 遷移腳本一次完成 |
| **回放結果與舊方法不一致** | 新 `api/trends` 與改動前需完全等價（equivalence test） | 修正 build_trends 回放邏輯後重跑 version_data |
| **checkpoint 日當天爬取失敗**（status=failed） | 不覆寫 items、不寫 checkpoint；既有資料保持原狀（health check 防線） | 下次成功 run 再判斷 checkpoint 日 |

---

## 6. 邊界與限制

| 項目 | 內容 |
|------|------|
| **checkpoint 頻率** | 每 7 天一檔全量快照（或距上次 ≥ 7 天判定為 checkpoint 日） |
| **daily 語意** | 保留 `daily/` 原名，語意改為「異動」，docstring 註明，避免大量 refactor |
| **稀疏寫入範圍** | daily 只寫 `changed_items` + `new_items`（價格存在者）；平價日（unchanged）不寫入 |
| **回放上限** | 最多回放 7 天 delta（因為每 7 天有 checkpoint）；compute cost <1ms |
| **自癒能力** | build_trends 以所有 checkpoint chain + delta carry forward 補齊；delta 遺失時 carry forward 自動補點（無缺口日）；最壞延遲 ≤7 天，下一 checkpoint 全量校正 |
| **git 節省** | daily 從 ~35KB/天 → ~1-2KB/天；一年成長 12MB → <1MB（異動檔）+ 52×35KB checkpoint（~1.8MB/年） |
| **遷移範圍** | 遷移後首次 run 結果需與遷移前等價（BDD 回歸通過） |
| **items history truncation** | 維持最近 2 點（D1 定稿：漲跌徽章只需末 2 點） |

---

## 7. 驗收檢查清單

- [ ] `data/daily/{date}.json` 只含當日真正異動的商品（`changed` + `new`），不含平價日商品
- [ ] `data/checkpoints/{date}.json` 每 7 天出現一次全量快照（或首次 run 補一個）
- [ ] `api/trends/{id}.json` 的 history 與改動前完全一致（回放後 equivalence test）
- [ ] `items/{g}.json` 的 history truncation 策略已重審（維持 2 點或改為只保留 checkpoint 後異動點）
- [ ] 遷移腳本：以最舊全量 daily seed checkpoint + 保留所有舊 daily 為 legacy 回放源，不破壞既有資料
- [ ] 遷移後首次 run 結果與遷移前等價（BDD 回歸通過）
- [ ] 某天 delta 遺失時，build_trends 以 carry forward 補齊該日（無缺口日），最壞延遲 ≤7 天由下一個 checkpoint 全量校正自癒
- [ ] 平價日（無異動）不產生額外 daily 寫入，git diff 不再有整檔 noise
- [ ] checkpoint 日當天爬取失敗（failed）時不覆寫 items、不寫 checkpoint，既有資料保持原狀
