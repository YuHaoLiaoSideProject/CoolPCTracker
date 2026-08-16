# 003 列表＋搜尋篩選 — 篩選功能 E2E 測試報告

- 日期：2026-08-15（UTC）
- 測試範圍：規格篩選（SpecFilterPanel / useFilters / specFilter / ProductList 空狀態）
- 測試工具：Playwright（`@playwright/test` 1.62.1，chromium 1234 headless shell）
- 測試檔：`web/e2e/003-filtering.spec.ts`、oracle helper `web/e2e/helpers/oracle.ts`
- 設定檔：`web/playwright.config.ts`（webServer 以 `vite dev` 於 `http://localhost:5200/CoolPCTracker/` 啟動）

## 執行環境

| 項目 | 值 |
| --- | --- |
| OS | Linux MiniServer 6.12.75 aarch64（Raspberry Pi） |
| Node | v22.23.1 |
| npm | 10.9.8 |
| @playwright/test | 1.62.1 |
| 瀏覽器 | chromium 1234（headless shell，快取既有，未另行下載） |
| Vite | 6.4.3 |
| Vue | 3.5.41 |
| 資料檔 | `data/items.v2.json`（1447 筆，dev server 由 `web/public/data/items.v2.json` 服務，內容一致） |
| 執行命令 | `cd web && npx playwright test` |

## 結果摘要

**10 passed / 0 failed**（耗時 57.8s，單 worker 循序）

| # | 情境 | 結果 |
| --- | --- | --- |
| 1 | 單一規格篩選 VRAM≥12G（oracle 88 筆、名稱集合全等） | ✅ PASS |
| 2 | 單一規格篩選 瓦數≥750W（真資料無 `wattage_w` → 空狀態） | ✅ PASS |
| 3 | 單一規格篩選 CPU核數≥8（oracle 24 筆、名稱集合全等） | ✅ PASS |
| 4 | 多條件 AND：VRAM≥12G 且 瓦數≥750W → 空狀態（資料缺口） | ✅ PASS |
| 5 | 多條件 AND（非平凡交集）：CPU核數≥8 且 TDP≥120W（oracle 17 筆） | ✅ PASS |
| 6 | 搜尋「RTX 5070」＋ VRAM≥12G（oracle 17 筆、名稱集合全等） | ✅ PASS |
| 7 | 清除全部條件 → 完整集合（1447 筆、搜尋框清空、chips 移除） | ✅ PASS |
| 8 | 篩選組合無結果 VRAM≥24G 且 瓦數≥1200W → 空狀態＋「清除篩選」可清除 | ✅ PASS |
| 9 | 邊界值納入（≥ 語意）：vram 恰 12G 商品命中 VRAM≥12G | ✅ PASS |
| 10 | 無規格欄位商品靜默排除、頁面不報錯（無 `.spec-err`／無 pageerror） | ✅ PASS |

## 各情境詳細

斷言採「真資料 oracle」策略：測試開頭讀取 `data/items.v2.json`，以鏡像
`useItems.normalizeSpec`＋`search.ts`＋`specFilter.ts` 的邏輯動態計算期望集合，
再與 DOM 渲染結果比對（筆數 + 商品名稱集合全等），不寫死會隨資料漂移的筆數。

### 1. 單一規格篩選 VRAM≥12G
- 操作：下拉選 `VRAM`、輸入 12、點「套用篩選」。
- 預期：chips 顯示「VRAM≥12G」、命中 88 筆、每筆 `vram_gb >= 12`。
- 實際：88 筆，名稱集合與 oracle 全等。✅

### 2. 單一規格篩選 瓦數≥750W
- 預期（依資料計算）：oracle = 0 筆（**資料檔無任何 `wattage_w` 欄位**，見「關鍵發現」）。
- 實際：chips「瓦數≥750W」、0 筆、空狀態「沒有符合條件的商品」。✅
- 判定：屬**資料缺口**，非前端 bug（前端「缺欄位靜默排除」行為正確）。

### 3. 單一規格篩選 CPU核數≥8
- 預期：24 筆（`cores` 值 8/10/12/16/20/24/28/32/64/96 之總和）。
- 實際：24 筆，名稱集合全等。✅

### 4. 多條件 AND：VRAM≥12G 且 瓦數≥750W
- 預期：因 `wattage_w` 全缺，交集 = 0。
- 實際：兩 chips 並存、0 筆、空狀態列出 2 個條件。✅（AND 交集邏輯本身另以情境 5 驗證）

### 5. 多條件 AND（非平凡交集）：CPU核數≥8 且 TDP≥120W
- 補充情境：因資料中各規格欄位幾乎依分類互斥，`VRAM≥12G ∧ 瓦數≥750W` 為空是資料所致；
  改用真資料中存在非空交集的 `cores≥8 ∧ tdp_w≥120`（17 筆）驗證 AND 收斂語意。
- 預期：17 筆；實際：17 筆，名稱集合全等。✅

### 6. 搜尋與篩選同時作用：搜尋「RTX 5070」＋ VRAM≥12G
- BDD 範例關鍵字「RTX 4070」在真資料中 0 筆（見「關鍵發現」），改用實際存在的
  「RTX 5070」（搜尋命中 33 筆）作為關鍵字，驗證「搜尋 ∧ 篩選」管線。
- 預期：`RTX 5070 ∧ vram_gb≥12` = 17 筆；實際：17 筆，名稱集合全等。✅

### 7. 清除全部條件
- 操作：搜尋「RTX 5070」→ 套用 VRAM≥12G → 點「清除全部條件」。
- 預期：回到 1447 筆、搜尋框清空、chips 移除、「清除全部條件」按鈕隱藏。
- 實際：全部符合。✅

### 8. 篩選組合無結果
- 操作：VRAM≥24G → 瓦數≥1200W。
- 預期：空狀態「沒有符合條件的商品」＋列出 2 條件＋「清除篩選」按鈕可清除回完整集合。
- 實際：符合，清除後回 1447 筆、chips 清空。✅

### 9. 邊界值納入（≥ 語意）
- 以真資料中 `vram_gb === 12` 的商品（共 22 筆，樣本「華擎 ARC B580 Challenger 12G …」）
  套用 VRAM≥12G，驗證恰等於門檻者被納入。
- 實際：樣本商品名稱出現於結果。✅

### 10. 無規格欄位商品靜默排除、頁面不報錯
- 套用 VRAM≥12G 後：88 筆（173 筆有 `vram_gb` 中 ≥12 者；其餘 1274 筆缺欄位被排除）。
- 挑一筆無 `vram_gb` 的 CPU 商品驗證其**不出現**於結果；無 `.spec-err`、無
  「資料載入失敗／資料格式錯誤」、無空狀態、無未捕捉 pageerror。✅

## 失敗明細

本次執行 **0 失敗**，故無「實際 vs 預期」對照可列，亦無需判定「測試選取器錯誤」或
「前端 bug」。所有斷言一次通過。

## 關鍵發現

1. **真資料筆數 1,447 ≠ BDD 宣稱 1,449**：`data/meta.json` 的 `total` 為 1449，
   但 `items` 陣列實際 1,447 筆（`data/items.json`、`items.v2.json`、`web/public/data/items.v2.json`
   均為 1,447）。屬資料／BDD 描述不一致，非前端 bug。測試以實際資料檔為準。

2. **資料無 `wattage_w`（電源瓦數）欄位**：9 大分類不含「電源」，`spec_parser` 未產出任何
   `wattage_w`。因此「瓦數≥750W」及含瓦數的 AND 情境在真資料下**必然為空集合**。
   這是資料缺口，前端「缺欄位商品靜默排除」行為正確（已由情境 2/4/8 驗證空狀態呈現）。

3. **BDD 範例關鍵字「RTX 4070」不存在於真資料**：資料中無任何商品名稱/規格含「4070」
   （RTX 型號為 3050/3060/5050/5060/5070/5080/5090 等）。故搜尋＋篩選情境改用實際存在
   的「RTX 5070」驗證。屬資料漂移，非 bug。

4. **BDD 提及「XC-5500 隨機贈品主機」不存在**：真資料無此商品；「無規格欄位」以缺
   `vram_gb` 的 CPU 商品代為驗證靜默排除（情境 10）。

5. **`>=`（大於等於）邊界語意正確**：真資料中 22 筆 `vram_gb === 12` 商品皆命中
   VRAM≥12G（情境 1/9），與 `specFilter.matchesCondition`（`v >= threshold`）一致。

## 結論

規格篩選功能在**真資料**下 10 項 E2E 情境全數通過，未發現前端實作 bug。
「瓦數≥750W」與「RTX 4070」等 BDD 範例無法以非空結果演示，主因是**資料缺口**
（缺 `wattage_w`、無 4070 型號），建議後續於 crawler 資料涵蓋電源分類或於
測試資料補入 `wattage_w` 樣本，使該等 happy-path 情境可獲非空驗證。
