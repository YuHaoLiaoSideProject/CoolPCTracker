# 008 稀疏異動日誌 + 週全量 Checkpoint — 測試計畫

> **對應 BDD**：`docs/bdds/008-sparse-daily-and-checkpoint.feature`
> **操作流程**：`docs/interaction-flows/008-sparse-daily-and-checkpoint.md`
> **開發規格**：`docs/development/008-sparse-daily-and-checkpoint.md`
> **技術決策**：`docs/tech-decisions/tech-decision-008-sparse-daily-checkpoint-2026-08-17.md`
> **測試日期**：2026-08-18

---

## 1. 測試範圍總覽

| 層級 | 範圍 | 工具 | 負責 |
|------|------|------|------|
| 單元測試 | `crawler/store.py`（稀疏 write_daily、write_checkpoint、latest_checkpoint、earliest_daily、save gating） | pytest（Python 3.13） | 後端 |
| 單元測試 | `crawler/main.py`（sparse_prices 建構、`_decide_checkpoint` 調度、checkpoint 日全量寫入、failed 防線延伸、carryover/price-None 過濾） | pytest（Python 3.13） | 後端 |
| 單元測試 | `scripts/version_data.py`（`build_trends` checkpoint + 稀疏回放 carry-forward、legacy 全量相容、冪等、壞檔/遺失跳過、dedupe） | pytest（Python 3.13） | 後端 |
| 單元測試 | `scripts/migrate_checkpoints.py`（seed checkpoint、保留 7 天 delta、防線、冪等、非破壞） | pytest（Python 3.13） | 後端 |
| 整合／等價回歸 | legacy 全量 ↔ checkpoint+稀疏同輸出、遷移後首次 run 等價、workflow 結構斷言 | pytest（Python 3.13） | 後端 |
| 端對端測試 | **本功能零前端改動、對外 API 契約不變，不需要 E2E** | — | — |
| 手動驗證 | 真實環境 git diff noise 驗證、repo 體積統計、遷移腳本在正式 data 上執行後等價確認 | 手動 | 維護者 |

---

## 2. 後端單元測試

### 2.1 `crawler/store.py` — 稀疏 write_daily + checkpoint 讀寫 + save gating

| # | 測試名稱 | 來源 Scenario | Given | When | Then |
|---|---------|--------------|-------|------|------|
| SYS-STORE-01 | write_daily 以 sparse price_map 寫入 compact JSON | S1（價格異動日） | 有異動+新增商品 `{a1: 9990, b2: 7990}` | 呼叫 `write_daily(today, price_map)` | `data/daily/{YYYYMMDD}.json` 存在、內容為 `{item_id: price}`、compact JSON |
| SYS-STORE-02 | write_daily 空 map 不寫檔（平價日零 git 變動） | S2（平價日） | 無任何異動（空 map `{}`） | 呼叫 `write_daily(today, {})` | `data/daily/{YYYYMMDD}.json` **不存在**（非空檔） |
| SYS-STORE-03 | write_checkpoint 寫入全量 {id:price} compact JSON | S3（checkpoint 日） | 1449 筆商品全量價格 dict | 呼叫 `write_checkpoint(today, full_prices)` | `data/checkpoints/{YYYYMMDD}.json` 存在、內容為全量 `{id: price}`、compact |
| SYS-STORE-04 | write_checkpoint 原子寫入失敗不影響既有 checkpoint | Smart: dependency failure | 已有 `checkpoints/20260810.json` | `os.replace` 模擬 OSError | 既有 checkpoint 內容不變、無暫存檔殘留 |
| SYS-STORE-05 | latest_checkpoint 取日期最大者 | Smart: multiple checkpoints | `data/checkpoints/` 含 20260810.json 與 20260817.json | 呼叫 `store.latest_checkpoint()` | 回傳 `(date(2026,8,17), {...})` |
| SYS-STORE-06 | latest_checkpoint 無 checkpoint 檔回傳 None | Smart | `data/checkpoints/` 不存在 | 呼叫 `store.latest_checkpoint()` | 回傳 `None` |
| SYS-STORE-07 | latest_checkpoint 跳過損壞（非 8 位檔名、JSON 解析失敗） | S9（損壞跳過） | checkpoints 含 `bad.json`（格式錯）與 `20260817.json` | 呼叫 `store.latest_checkpoint()` | 回傳 20260817 的 date+prices，不拋例外 |
| SYS-STORE-08 | earliest_daily 取最小日期 | S12（純新增模式） | `data/daily/` 含 20260810.json 與 20260817.json | 呼叫 `store.earliest_daily()` | 回傳 `date(2026, 8, 10)` |
| SYS-STORE-09 | earliest_daily 無 daily 檔回傳 None | S12 | `data/daily/` 不存在 | 呼叫 `store.earliest_daily()` | 回傳 `None` |
| SYS-STORE-10 | save D2 gating：rewrite_g 給定時僅重寫指定分類 | Smart: D2 items gating | 有 CPU(g4) 與 顯示卡(g12) 兩分類商品 | `save(items, meta, rewrite_g={4})` | g4.json 重寫、g12.json mtime 不變 |
| SYS-STORE-11 | save D2 gating：rewrite_g=None 時照常全部重寫（既有相容） | Smart | 同上 | `save(items, meta, rewrite_g=None)` | g4.json 與 g12.json 皆重寫 |
| SYS-STORE-12 | write_checkpoint 與 write_daily 互不干擾 | S3 + S16（checkpoint 日同時寫 daily） | 同日有異動+checkpoint 條件成立 | 同日呼叫 write_daily + write_checkpoint | daily 與 checkpoints 各自存在、內容獨立 |

### 2.2 `crawler/main.py` — sparse_prices + checkpoint 調度 + 邊界

| # | 測試名稱 | 來源 Scenario | Given | When | Then |
|---|---------|--------------|-------|------|------|
| SYS-MAIN-01 | 稀疏 daily 只含 changed+new 且價格存在者 | S1（價格異動日） | 1449 筆中 3 changed + 2 new + 其餘 unchanged/carryover | run_crawler 執行完成 | `data/daily/{today}.json` 含 5 筆（3+2），不含平價/carryover |
| SYS-MAIN-02 | 平價日不產生 daily 檔 | S2（平價日） | 所有商品與昨日完全相同（0 異動、0 新增） | run_crawler 完成 | `data/daily/{today}.json` 不存在；`items/{g}` 與 `meta.json` 正常更新 |
| SYS-MAIN-03 | checkpoint 日寫入全量 checkpoint | S3（≥7 天 checkpoint） | 距上次 checkpoint ≥7 天；已寫入 sparse daily | run_crawler 判斷為 checkpoint 日 | `data/checkpoints/{today}.json` 存在、全量 `{id: price}` |
| SYS-MAIN-06-01 | `_decide_checkpoint`：3 天前 → 非 checkpoint | S6 Examples row 1 | `latest_cp_date = today - 3d` | `_decide_checkpoint(cp_date, today, earliest)` | 回傳 `False` |
| SYS-MAIN-06-02 | `_decide_checkpoint`：6 天前 → 非 checkpoint | S6 Examples row 2 | `latest_cp_date = today - 6d` | `_decide_checkpoint(cp_date, today, earliest)` | 回傳 `False` |
| SYS-MAIN-06-03 | `_decide_checkpoint`：7 天前（邊界）→ 是 checkpoint | S6 Examples row 3 | `latest_cp_date = today - 7d` | `_decide_checkpoint(cp_date, today, earliest)` | 回傳 `True` |
| SYS-MAIN-06-04 | `_decide_checkpoint`：12 天前 → 是 checkpoint | S6 Examples row 4 | `latest_cp_date = today - 12d` | `_decide_checkpoint(cp_date, today, earliest)` | 回傳 `True` |
| SYS-MAIN-07 | checkpoint 日爬取失敗：不寫 checkpoint、不覆寫 items | S7（failed 路徑） | checkpoint 日；爬取 status=failed | run_crawler 完成（return 1） | `data/checkpoints/{today}.json` 不存在；`data/items/{g}` 不被覆寫；`meta.status=failed` |
| SYS-MAIN-12 | 無 checkpoint 無 daily（純新增）：寫全部 new_items、不寫 checkpoint | S12（純新增模式） | `data/checkpoints/` 與 `data/daily/` 皆不存在；今日全為新商品 | 首次 run_crawler | `daily/{today}.json` 含全部新商品；無 checkpoint 產生 |
| SYS-MAIN-13 | carryover（失敗分類）商品不寫入 sparse daily | S13（carryover 排除） | 顯示卡分類抓取失敗（carryover）；其他分類有異動 | run_crawler 完成 | `daily/{today}.json` 不含 carryover 商品 |
| SYS-MAIN-14 | 異動商品 price=None 不寫入 sparse daily | S14（price None） | 商品 A 狀態異動但 price 解析為 None | run_crawler 完成 | `daily/{today}.json` 不含商品 A |
| SYS-MAIN-15-01 | changed + 價格存在 → 寫入 | S15 Examples row 1 | diff 有 changed_items 且 price 存在 | run_crawler 構建 sparse_prices | 該商品出現在 daily 中 |
| SYS-MAIN-15-02 | new + 價格存在 → 寫入 | S15 Examples row 2 | diff 有 new_items 且 price 存在 | run_crawler 構建 sparse_prices | 該商品出現在 daily 中 |
| SYS-MAIN-15-03 | changed + price=None → 不寫入 | S15 Examples row 3 | diff 有 changed_items 但 price=None | run_crawler 構建 sparse_prices | 該商品不在 daily 中 |
| SYS-MAIN-15-04 | new + price=None → 不寫入 | S15 Examples row 4 | diff 有 new_items 但 price=None | run_crawler 構建 sparse_prices | 該商品不在 daily 中 |
| SYS-MAIN-15-05 | refreshed + 價格存在 → 不寫入 | S15 Examples row 5 | diff 有 refreshed_items 且 price 存在 | run_crawler 構建 sparse_prices | refreshed 不在 sparse_prices 中 |
| SYS-MAIN-15-06 | unchanged → 不寫入 | S15 Examples row 6 | diff 有 unchanged_ids | run_crawler 構建 sparse_prices | unchanged 不在 sparse_prices 中 |
| SYS-MAIN-15-07 | carryover → 不寫入 | S15 Examples row 7 | diff 有 carryover_ids | run_crawler 構建 sparse_prices | carryover 不在 sparse_prices 中 |
| SYS-MAIN-15-08 | gone → 不寫入 | S15 Examples row 8 | diff 有 gone_ids | run_crawler 構建 sparse_prices | gone 不在 sparse_prices 中 |
| SYS-MAIN-16 | checkpoint 日無異動：daily 不產生、checkpoint 仍寫入 | S16（checkpoint 日平價） | checkpoint 日、0 異動、0 新增 | run_crawler 完成 | `daily/{today}.json` 不存在；`checkpoints/{today}.json` 存在（全量錨點） |
| SYS-MAIN-07-B | 失敗 run 後下次成功距上次 ≥7 天仍自動補寫 checkpoint | S7 恢復路徑 | checkpoint 日 failed；隔 8 天成功 run | run_crawler（第 9 天） | 第 9 天 write_checkpoint 正常執行 |

---

## 3. 前端單元測試

> **不適用**：本功能為純後端/資料流功能，零前端 UI 改動，對外 API 契約不變。

---

## 4. 腳本單元測試

### 4.1 `scripts/version_data.py` — build_trends checkpoint + 回放

| # | 測試名稱 | 來源 Scenario | Given | When | Then |
|---|---------|--------------|-------|------|------|
| SYS-VDT-01 | 所有 checkpoint chain + 稀疏 carry forward 重建完整 history | S4（回放重建） | checkpoint C1<C2 日全量 + C1~C2 間稀疏 delta | `build_trends(data_dir)` | history 日期升冪、每日一點；C1 carrier 重置 → delta carry → C2 carrier 重置 → carry；未異動商品 carry 前值；平價日亦有點（carry forward 補齊） |
| SYS-VDT-02 | build_trends 為純函數、冪等（同輸入 → 同輸出） | S4 | 同 SYS-VDT-01 數據 | 連續呼叫兩次 `build_trends()` | 兩次回傳 dict 深度相等 |
| SYS-VDT-03 | 無 checkpoint → legacy 全量回放（現行行為） | S12（純新增無 checkpoint） | 無 checkpoints/；有 daily 全量檔 | `build_trends(data_dir)` | 結果 = legacy 全量聚合（每檔全量覆寫該商品該日值） |
| SYS-VDT-04 | delta 遺失時 carry forward 補齊（無缺口日），最壞延遲 ≤7 天 | S8（delta 遺失自癒） | checkpoint C + daily C+1 存在但 C+2 遺失 | `build_trends()` | C+2 由 C+1 carrier carry forward 補齊（無缺口日），history 仍完整 |
| SYS-VDT-05 | delta 損壞（JSON 錯誤）跳過不崩潰 | S9（損壞跳過） | checkpoint C + daily C+1.json 格式損壞 | `build_trends()` | 不拋例外、以其餘有效 data 正常產出 |
| SYS-VDT-06 | legacy 全量 ↔ checkpoint+稀疏同輸出（等價基準） | S5（equivalence test） | 同一组 daily 全量檔：① legacy 路徑全量回放② 以最舊檔 seed checkpoint + 其餘為稀疏 delta 分別建構 | 兩個路徑分別 build_trends | 結果 dict 深度相等（逐商品逐點一致） |
| SYS-VDT-07 | 日期升冪、同日去重 | Smart | 同商品同日出現兩筆 | `build_trends()` | history 每 bucket 日期升冪、同日只留一點 |
| SYS-VDT-08 | checkpoint chain 前 legacy 全量 daily 正常回放 | S4 + S5 | checkpoint C；C 之前有 2 檔 legacy 全量 daily | `build_trends()` | C 之前的 legacy 全量 daily 以全量語意回放（每檔覆寫 carrier 全量） |
| SYS-VDT-09 | 每日 carry forward 未異動商品保留前值 | S4 | checkpoint C 含商品 A=100；C+1 daily 無 A；C+2 daily A=110 | `build_trends()` | C+1 點為 [C+1, 100]（carry）；C+2 點為 [C+2, 110]（更新） |
| SYS-VDT-10 | build_trends 純函數（不寫任何檔案） | Smart | 有 data_dir 含 daily + checkpoint | `build_trends()` | data/api 目錄無新增或變更檔案 |
| SYS-VDT-11 | 全部 daily 損壞或缺失 → 回傳空 dict | Smart | checkpoints 有、但所有 delta 全壞 | `build_trends()` | 回傳 `{}`（或僅含 checkpoint 日一點） |
| SYS-VDT-12 | flat checkpoint 日（無 daily、有 checkpoint）rebuild 正確 + changed 判定 | S16 + changed detection | 有 checkpoint C 日（無對應 daily），其他日正常 | `build_trends()` + version_data | `build_trends()` 輸出 C 日全量點；version_data `changed` 判定涵蓋新 checkpoint → api/trends 重建 |

### 4.2 `scripts/migrate_checkpoints.py` — 遷移腳本

| # | 測試名稱 | 來源 Scenario | Given | When | Then |
|---|---------|--------------|-------|------|------|
| SYS-MIG-01 | 遷移 seed 最舊全量 daily 為 checkpoint | S10（遷移 seed） | `data/daily/` 含舊全量檔 20260801～20260817 | 呼叫 `migrate(data_dir)` | `data/checkpoints/20260801.json` = 最舊全量 daily 內容；`seeded=True` |
| SYS-MIG-02 | 遷移保留所有 daily 為 legacy 回放源 | S10 | 同上 | 呼叫 `migrate(data_dir)` | 所有 daily 檔保留（kept_daily 長度=所有舊檔數量）；無任何 daily 被移動或刪除 |
| SYS-MIG-03 | 遷移防線：meta.status=failed 不執行 | S10 + tech-decision | `meta.json` 含 `"status": "failed"` | 呼叫 `migrate()` | `seeded=False`、`skipped="status=failed"`；checkpoints/ 不變 |
| SYS-MIG-04 | 遷移防線：total=0 不執行 | S10 + tech-decision | `meta.json` 含 `"total": 0` | 呼叫 `migrate()` | `seeded=False`、`skipped="total=0"`；checkpoints/ 不變 |
| SYS-MIG-05 | 遷移冪等：已遷移（checkpoints 存在）略過 | Smart | `data/checkpoints/` 已有 checkpoint | 再次呼叫 `migrate()` | `seeded=False`、`skipped="already_migrated"` |
| SYS-MIG-06 | 遷移非破壞：不刪除任何 daily 檔 | S10 | 有舊 daily | 呼叫 `migrate()` | 原 daily 檔皆完整保留（無 deleted、無 moved） |
| SYS-MIG-07 | 遷移後所有舊 daily 均保留在 data/daily/（不歸檔） | S10 | daily 含 17 天前的檔 | 呼叫 `migrate()` | 所有 daily 仍在 `data/daily/`（無 `daily_legacy_archive/` 目錄） |
| SYS-MIG-08 | 遷移後 build_trends 結果與遷移前 legacy 回放等價 | S11（遷移後等價） | 遷移前已知 build_trends legacy 輸出（基準） | 遷移 → build_trends | 結果與基準 dict 深度相等 |

---

## 5. 整合／等價回歸測試

| # | 測試名稱 | 來源 Scenario | Given | When | Then |
|---|---------|--------------|-------|------|------|
| INT-EQV-01 | 遷移後首次 run 的 api/trends 與遷移前完全等價 | S5（equivalence） | 遷移前 api/trends 基準結果已知 | 遷移腳本 → crawler → version_data | `api/trends/{id}.json` history 逐日逐點一致 |
| INT-EQV-02 | 遷移後首次執行以 checkpoint 回放 delta 等價 | S11（遷移回歸） | 遷移完成（checkpoint + legacy delta） | crawler → version_data | `api/trends` 與遷移前 legacy 全量回放完全一致 |
| INT-EQV-03 | 全日 legacy 全量 data（未遷移前）legacy 路徑正常 | Smart: regression baseline | 無 checkpoint、daily 皆為舊全量 | version_data | 舊 legacy 全量回放路徑輸出正確（無 regression） |

---

## 6. 手動驗證（真實環境）

| # | 情境 | 驗證步驟 | 預期 |
|---|------|---------|------|
| MAN-01 | 平價日 git diff 零噪音 | 真實環境觸發平價日跑完後 `git diff --stat data/daily` | 無變更（零檔案）；`items/{g}` 僅實質異動分類有 diff |
| MAN-02 | repo 體積成長驗證 | 部署後觀察 7~14 天 `du -sh data/daily data/checkpoints` | daily 每檔 ~1-2KB（非 35KB）；checkpoints 每 7 天 ~35KB |
| MAN-03 | 遷移腳本在正式 data 上執行 | 備份 → 執行 `migrate_checkpoints.py` → 執行 crawler → version_data → 對比 api/trends | trends 與遷移前完全一致；data/daily 保留 |
| MAN-04 | 真實 delta 遺失後自癒 | 手動刪除一個 daily delta → 執行 version_data → 檢查 api/trends | history 仍完整（缺失片段 ≤7 天）；不需人工介入 |
| MAN-05 | checkpoints 目錄確實被 git 追蹤 | `.gitignore` 檢查 + `git add` 後 `git status` | `data/checkpoints/**` 不被 gitignore 規避；可入庫 |

---

## 7. 測試環境

| 項目 | 需求 |
|------|------|
| Python 版本 | 3.13 |
| 測試框架 | pytest |
| 待測模組 | `crawler/store.py`、`crawler/main.py`、`scripts/version_data.py`、`scripts/migrate_checkpoints.py` |
| 測試檔案 | `crawler/tests/test_store.py`、`crawler/tests/test_main.py`、`scripts/tests/test_version_data.py`、`scripts/tests/test_migrate_checkpoints.py`（新）、`tests/test_crawl_workflow.py` |
| OS | macOS / Linux（CI Ubuntu） |
| 依賴 | 僅 Python 標準庫 + pytest（無新增第三方依賴） |
| fixtures | 繼承現有 `crawler/tests/fixtures/` HTML 檔；tmp_path 替代真實檔案系統 |

---

## 8. BDD Scenario ↔ 測試案例追溯矩陣

| BDD # | Scenario 摘要 | 標籤 | 對應測試案例 |
|:---:|--------------|------|------------|
| S1 | 價格異動日僅寫入異動與新增商品（稀疏 delta） | @smoke @happy-path @p0 | SYS-STORE-01、SYS-MAIN-01 |
| S2 | 平價日不產生額外 daily 寫入 | @happy-path @p0 | SYS-STORE-02、SYS-MAIN-02、MAN-01 |
| S3 | 距上次 checkpoint ≥7 天寫入全量快照 | @happy-path @p0 | SYS-STORE-03/04/05/12、SYS-MAIN-03 |
| S4 | 所有 checkpoint chain + delta carry forward 重建歷史 | @happy-path @p1 | SYS-VDT-01/02/09 |
| S5 | 遷移後首次 run 的 api/trends 完全等價 | @regression @p0 | SYS-VDT-06、INT-EQV-01 |
| S6 | checkpoint 日門檻邊界（3/6/7/12 天）4 Examples rows | @edge-case @boundary | SYS-MAIN-06-01/02/03/04 |
| S7 | checkpoint 日爬取失敗不覆寫、不寫 checkpoint | @error-handling @p0 | SYS-MAIN-07、SYS-MAIN-07-B |
| S8 | 某天 delta 遺失時 carry forward 補齊（無缺口日），自癒 ≤7 天 | @error-handling @p1 | SYS-VDT-04 |
| S9 | 某天 delta 損壞跳過不崩潰 | @error-handling @p1 | SYS-STORE-07、SYS-VDT-05 |
| S10 | 遷移腳本 seed checkpoint + 保留所有 daily | @business-rules @p0 | SYS-MIG-01/02/03/04/05/06/07 |
| S11 | 遷移後首次執行等價（回歸通過） | @business-rules @p0 | SYS-MIG-08、INT-EQV-02 |
| S12 | 首次執行純新增模式 | @edge-case @p0 | SYS-MAIN-12、SYS-VDT-03 |
| S13 | carryover 商品不寫入 sparse daily | @edge-case | SYS-MAIN-13 |
| S14 | 異動商品 price=None 不寫入 | @edge-case | SYS-MAIN-14 |
| S15 | 稀疏寫入範圍 changed+new 且價格存在 8 Examples rows | @business-rules | SYS-MAIN-15-01/02/03/04/05/06/07/08 |
| S16 | checkpoint 日無異動仍寫全量 checkpoint | @edge-case | SYS-MAIN-16、SYS-STORE-03/12 |

---

## 9. Scenario Outline Examples 展開追蹤

### S6 — checkpoint 日門檻邊界判定

| Examples 行 | daysAgo | isCheckpoint | 寫入行為 | 對應案例 |
|:---:|:---:|:---:|------|------|
| row 1 | 3 天前 | 非 | 不寫 checkpoint | SYS-MAIN-06-01 |
| row 2 | 6 天前 | 非 | 不寫 checkpoint | SYS-MAIN-06-02 |
| row 3 | 7 天前（邊界） | 為 | 寫入全量快照 | SYS-MAIN-06-03 |
| row 4 | 12 天前 | 為 | 寫入全量快照 | SYS-MAIN-06-04 |

### S15 — 稀疏寫入範圍

| Examples 行 | category | hasPrice | 寫入？ | 對應案例 |
|:---:|------|:---:|:---:|------|
| row 1 | changed_items | 價格存在 | 會 | SYS-MAIN-15-01 |
| row 2 | new_items | 價格存在 | 會 | SYS-MAIN-15-02 |
| row 3 | changed_items | 價格缺失 None | 不會 | SYS-MAIN-15-03 |
| row 4 | new_items | 價格缺失 None | 不會 | SYS-MAIN-15-04 |
| row 5 | refreshed_items | 價格存在 | 不會 | SYS-MAIN-15-05 |
| row 6 | unchanged_ids | 價格存在 | 不會 | SYS-MAIN-15-06 |
| row 7 | carryover_ids | 價格未知 | 不會 | SYS-MAIN-15-07 |
| row 8 | gone_ids | 無 | 不會 | SYS-MAIN-15-08 |

---

## 10. 測試案例統計

| 層級 | 案例數 | 說明 |
|------|:---:|------|
| `crawler/store.py` 單元 | 12 | write_daily 稀疏化、write_checkpoint、latest/earliest 讀取、save gating |
| `crawler/main.py` 單元 | 21 | sparse_prices、checkpoint 調度 4 列、failed 路徑（含恢復）、純新增、carryover/price-None、Outline 8 列、checkpoint 日平價 |
| `scripts/version_data.py` 單元 | 12 | build_trends chain 回放、冪等、legacy 兼容、損壞/遺失、dedupe、flat checkpoint 日 + changed 判定 |
| `scripts/migrate_checkpoints.py` 單元 | 8 | seed、保留、防線、冪等、非破壞、等價 |
| 整合等價回歸 | 3 | legacy↔sparse 等價、遷移等價 |
| 手動驗證 | 5 | git noise、repo 體積、正式環境遷移、自癒、gitignore |
| **合計** | **61** | 16 BDD Scenarios 全覆蓋（含 2 Outline 共 12 列 Examples） |

---

## 11. 缺陷追蹤模板

| 欄位 | 說明 |
|------|------|
| ID | BUG-008-XXX |
| 測試案例 | 對應以上 SYS-/INT-/MAN- 編號 |
| 嚴重程度 | P0（阻擋：checkpoint 未寫、daily 仍全量）/ P1（主要：等價 regression、回放錯誤）/ P2（次要：format/compact 不一致、archive 路徑） |
| 重啟步驟 | 逐步操作（引用 Given/When） |
| 預期 vs 實際 | 對照 Then |
| 環境 | Python 3.13 / pytest / OS |

---

## 12. 實作優先順序建議

依開發規格 §8 的 DAG 順序，測試建議同步實作：

| 順序 | 待寫測試 | 依賴 | 對應開發步驟 |
|:---:|---------|------|------------|
| 1 | SYS-VDT-01/02/03/06/07/08/09/10/11（build_trends 純函數） | 無（可先做） | 開發步驟 2/6 |
| 2 | SYS-STORE-01~09 + SYS-STORE-12（store checkpoint 讀寫） | 無 | 開發步驟 1 |
| 3 | SYS-MIG-01~08（migrate 腳本） | #1、#2 | 開發步驟 3 |
| 4 | SYS-STORE-10/11 + SYS-MAIN-15 系列 + SYS-MAIN-13/14（gating + 過濾） | #2 | 開發步驟 4 |
| 5 | SYS-MAIN-01~03 + 06~07 + 12 + 16 + 07-B（main 整合） | #2、#4 | 開發步驟 5 |
| 6 | INT-EQV-01/02/03（等價回歸） | #1、#5 | 開發步驟 8 |
| 7 | MAN-01~05（手動驗證） | #6 | 驗收 |
