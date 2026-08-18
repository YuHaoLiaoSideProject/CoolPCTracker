# Dashboard 分類切換 — 測試計畫

> **對應 BDD**：（由 interaction-flow 推導，未獨立建立 BDD 檔案）
> **操作流程**：`docs/interaction-flows/019-dashboard-categories.md`
> **開發規格**：（待產出）
> **測試日期**：2026-08-16

---

## 1. 測試範圍總覽

> 本功能為**純前端**（Tab 切換 + useItems + useDashboard 整合），無任何後端 API 新增，故無後端單元測試。

| 層級 | 範圍 | 工具 | 負責 |
|------|------|------|------|
| 單元測試 | `composables/useItems.ts`（分類參數切換、資料載入、取消前一次請求、空狀態處理） | Vitest + jsdom | 前端 |
| 單元測試 | `composables/useFilters.ts`（分組 chips 隨分類更新、分類 Tab 資料源） | Vitest + jsdom | 前端 |
| 單元測試 | `components/CategorySidebar.vue`（Tab 列表渲染、折疊/展開、分類切換事件） | Vitest + @vue/test-utils + happy-dom | 前端 |
| 整合測試 | Tab 切換 + useItems + useFilters 整合（切換分類 → 載入商品 → 更新 chips） | Vitest + @vue/test-utils + happy-dom | 前端 |
| 端對端測試 | Dashboard 分類切換完整流程（Tab 渲染、切換、spinner、商品更新、折疊） | Playwright | 前端 |
| 手動驗證 | 真實環境 Tab 操作、裝置相容、載入效能 | 手動 | QA |

---

## 2. 前端單元測試

### 2.1 composables/useItems.ts — 分類切換資料載入

**Mock 策略**：mock API 回應（fetch / axios），控制各分類回傳的商品資料。測試分類切換時取消前一次請求的行為。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-I01 | 初始載入預設分類商品 | API 回傳 CPU 分類 3 件商品 | 建立 useItems 實例，category 為 `'CPU'` | `items.value` 含 3 件；`loading.value === false` |
| F-I02 | 切換分類後載入新分類商品 | 已載入 CPU 分類 | 將 category 改為 `'記憶體'` | `loading.value` 短暫為 `true` 後變 `false`；`items.value` 為記憶體分類商品 |
| F-I03 | 切換分類時取消前一次請求 @error-handling | 已在載入 CPU 分類（請求尚未回應） | 快速切換到「顯示卡」分類 | CPU 分類的 API 請求被取消（AbortController abort 被呼叫）；僅顯示顯示卡分類資料 |
| F-I04 | 新分類無商品時顯示空狀態 @edge-case | API 回傳分類資料為空陣列 `[]` | 載入「SSD」分類 | `items.value` 為空陣列；`loading.value === false` |
| F-I05 | API 回傳錯誤時 items 為空且不崩溃 @error-handling | API 回傳 500 錯誤 | 載入「顯示卡」分類 | `items.value` 為空陣列；`error.value` 非 null；元件不崩溃 |
| F-I06 | 多次快速切換分類僅顯示最新結果 @business-rules | 依次快速切換 CPU → 記憶體 → 顯示卡（間隔 <100ms） | 等待所有請求完成 | `items.value` 僅含顯示卡分類資料；不會出現中間分類的資料殘留 |
| F-I07 | 切換回已載入過的分類時使用快取 @business-rules | 已載入 CPU 分類並快取 | 切換到記憶體再切回 CPU | 第二次載入 CPU 時直接使用快取，不重複呼叫 API |

### 2.2 composables/useFilters.ts — 分組 Chips 隨分類更新

**Mock 策略**：直接 import 純邏輯，或 mock 分類 metadata 資料源。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-F01 | CPU 分類 chips 顯示正確分組 | 分類為 `'CPU'` | 讀取 `filterGroups.value` | 含「品牌」「核心數」「TDP」等分組 |
| F-F02 | 記憶體分類 chips 含 DDR 規格分組 @business-rules | 分類為 `'記憶體'` | 讀取 `filterGroups.value` | 含「DDR 規格」分組（DDR3/DDR4/DDR5）與「容量」分組 |
| F-F03 | 切換分類後 chips 重置 | 已選取 CPU 分類的「Intel」chip | 分類改為「記憶體」 | 所有已選 chips 清空；`selectedFilters.value` 為空 |
| F-F04 | 分類 metadata 不存在時 chips 為空 @edge-case | 分類為未知分類 `'XYZ'` | 讀取 `filterGroups.value` | 為空陣列；不抛異常 |

### 2.3 components/CategorySidebar.vue — 分類 Tab 列表

**Mock 策略**：使用 `@vue/test-utils` mount 元件，mock `useItems` / `useFilters` composable。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-T01 | 正確渲染所有分類 Tab | categories 資料含 6 個分類 | mount CategorySidebar | 渲染 6 個 Tab 元素 |
| F-T02 | 預設選取第一個分類 @business-rules | categories 資料含 CPU、記憶體、顯示卡… | mount CategorySidebar | 第一個 Tab 具有 active 樣式（反白高亮） |
| F-T03 | 點擊 Tab 觸發分類切換事件 @smoke | 目前選取 CPU | 點擊「記憶體」Tab | emit `update:category` 事件，payload 為 `'記憶體'` |
| F-T04 | 切換後 Tab 高亮跟隨 | 目前選取 CPU | props.category 改為 `'記憶體'` | 「記憶體」Tab 具有 active 樣式；CPU Tab 移除 active 樣式 |
| F-T05 | 分類超過 5 個時顯示「更多 ▼」折疊 @edge-case | categories 資料含 8 個分類 | mount CategorySidebar | 僅顯示前 5 個 Tab；第 6~8 個隱藏；出現「更多 ▼」按鈕 |
| F-T06 | 點擊「更多」展開全部分類 | categories 資料含 8 個分類，折疊狀態 | 點擊「更多 ▼」 | 所有 8 個 Tab 皆顯示；按鈕文字變為「收起 ▲」 |
| F-T07 | 點擊「收起」折疊回 5 個 | 展開狀態，顯示 8 個 Tab | 點擊「收起 ▲」 | 僅顯示前 5 個 Tab；其餘隱藏 |
| F-T08 | 正好 5 個分類時不顯示「更多」 @edge-case | categories 資料含 5 個分類 | mount CategorySidebar | 所有 Tab 皆顯示；不出現「更多 ▼」 |
| F-T09 | 載入中時 Tab 切換顯示 loading 狀態 | 目前在載入新分類 | 檢查 Tab 狀態 | 目標 Tab 呈現 loading 樣式（如 spinner 或 opacity 變化） |
| F-T10 | Tab 列表可橫向滾動 @edge-case | 小螢幕寬度（320px） | mount CategorySidebar | Tab 列表可橫向捲動，不溢出容器 |

---

## 3. 整合測試（Tab + useItems + useFilters）

**Mock 策略**：使用 `@vue/test-utils` mount 包含 CategorySidebar + 商品列表的父元件，mock API 端點。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| INT-01 | 切換分類後商品列表正確更新 @smoke | Dashboard 已載入，顯示 CPU 商品 | 點擊「記憶體」Tab | API 被呼叫（參數含 category=記憶體）；商品列表顯示記憶體商品 |
| INT-02 | 切換分類後分組 chips 正確更新 @smoke | Dashboard 已載入，chips 為 CPU 規格 | 點擊「記憶體」Tab | chips 更新為 DDR3/4/5 + 容量分組 |
| INT-03 | 切換分類時 spinner 正確顯示與消失 | Dashboard 已載入 | 點擊「顯示卡」Tab → 等待 API 回應 | 切換瞬間 spinner 出現；API 回應後 spinner 消失；商品列表顯示顯示卡商品 |
| INT-04 | 快速連續切換分類僅顯示最終結果 | Dashboard 已載入 CPU 商品 | 快速依序點擊 記憶體 → 顯示卡 → SSD | 僅顯示 SSD 分類商品；不會閃現中間分類資料 |
| INT-05 | 分類無商品時空狀態正確顯示 @edge-case | API 回傳 SSD 分類資料為空 | 點擊「SSD」Tab | 顯示「暫無商品資料」空狀態提示；不顯示 spinner |
| INT-06 | Tab 載入失敗時不影響其他分類 @error-handling | API 回傳「顯示卡」分類 500 錯誤 | 點擊「顯示卡」Tab → 再點擊「CPU」Tab | 顯示卡顯示錯誤狀態；CPU 正常載入商品 |

---

## 4. 端對端測試（Playwright）

> E2E 測試以**真實瀏覽器**為環境。以 `page.route` 模擬 API 回應，控制各分類的商品資料。

| # | 測試名稱 | 操作步驟 | 預期結果 | 來源場景 |
|---|---------|---------|---------|----------|
| E2E-01 | Dashboard 載入後預設選取第一個分類 @smoke | 1. 前往 Dashboard 頁面<br>2. 等待骨架屏消失 | 1. 分類 Tab 列表顯示（CPU、記憶體、顯示卡…）<br>2. 第一個 Tab（CPU）反白高亮<br>3. 商品列表顯示 CPU 分類商品 | 步驟 1：檢視分類 Tab 列表 |
| E2E-02 | 點擊 Tab 切換分類 @smoke | 1. Dashboard 已載入（CPU 分類）<br>2. 點擊「記憶體」Tab | 1. 「記憶體」Tab 反白高亮<br>2. 顯示載入 spinner<br>3. spinner 消失後顯示記憶體商品<br>4. 分組 chips 更新為 DDR 規格 | 步驟 2：切換分類 |
| E2E-03 | 切換分類後分組 Chips 正確更新 @smoke | 1. Dashboard 已載入（CPU 分類，chips 含核心數/TDP）<br>2. 點擊「記憶體」Tab<br>3. 等待載入完成 | 1. chips 不再顯示 CPU 規格分組<br>2. chips 顯示「DDR 規格」「容量」等記憶體分組 | 步驟 2：切換分類（chips 更新） |
| E2E-04 | 切換分類時載入 spinner 正確顯示 @smoke | 1. Dashboard 已載入<br>2. 點擊「顯示卡」Tab | 1. Tab 反白高亮同時出現 spinner<br>2. API 回應後 spinner 消失<br>3. 商品列表顯示顯示卡商品 | 步驟 2：切換分類（spinner） |
| E2E-05 | 快速連續切換分類僅顯示最終結果 @business-rules | 1. Dashboard 已載入（CPU）<br>2. 快速依序點擊 記憶體 → 顯示卡（間隔 <200ms） | 1. 最終僅顯示顯示卡分類商品<br>2. 不會閃現記憶體分類資料<br>3. Tab 高亮在顯示卡 | 步驟 2 + 異常處理：取消上一個請求 |
| E2E-06 | 分類超過 5 個時折疊顯示 @edge-case | 1. API 回傳 8 個分類<br>2. 前往 Dashboard | 1. 僅顯示前 5 個 Tab<br>2. 出現「更多 ▼」按鈕<br>3. 第 6~8 個 Tab 隱藏 | 異常處理：分類 Tab 超過 5 個 |
| E2E-07 | 點擊「更多」展開全部分類 @edge-case | 1. Dashboard 顯示折疊的 Tab 列表 | 1. 點擊「更多 ▼」<br>2. 所有 8 個 Tab 皆顯示<br>3. 按鈕文字變為「收起 ▲」 | 異常處理：折疊展開 |
| E2E-08 | 點擊「收起」折疊 Tab 列表 @edge-case | 1. Tab 列表已展開（顯示 8 個） | 1. 點擊「收起 ▲」<br>2. 僅顯示前 5 個 Tab<br>3. 第 6~8 個隱藏 | 異常處理：折疊收起 |
| E2E-09 | 新分類無商品時顯示空狀態 @edge-case | 1. API 回傳「SSD」分類資料為空陣列<br>2. 點擊「SSD」Tab | 1. 顯示「暫無商品資料」空狀態<br>2. 不顯示 spinner<br>3. 其他分類 Tab 仍可正常切換 | 異常處理：新分類無商品 |
| E2E-10 | Tab 切換時間 < 1 秒 @business-rules | 1. Dashboard 已載入<br>2. 點擊「記憶體」Tab<br>3. 記錄 Tab 點擊到商品列表更新完成的時間 | 1. 從 Tab 點擊到商品列表顯示完成 < 1 秒<br>2. 包含 spinner 顯示/消失時間 | 驗收：切換分類時間 < 1 秒 |
| E2E-11 | 正好 5 個分類時不顯示「更多」@edge-case | 1. API 回傳 5 個分類<br>2. 前往 Dashboard | 1. 所有 5 個 Tab 皆顯示<br>2. 不出現「更多 ▼」按鈕 | 異常處理：邊界情況 |
| E2E-12 | 切換分類時顯示 loading 狀態 @smoke | 1. Dashboard 已載入（CPU）<br>2. 點擊「記憶體」Tab<br>3. 檢查 Tab 狀態 | 1. 「記憶體」Tab 在載入期間呈現在 loading 樣式<br>2. 載入完成後恢復正常 | 步驟 2 + 步驟 3：載入中狀態 |

---

## 5. 手動驗證（真實環境）

| # | 情境 | 驗證步驟 | 預期 |
|---|------|---------|------|
| MAN-01 | 多分類 Tab 操作流暢度 | 1. Dashboard 載入完成<br>2. 快速連續切換 5 個以上分類<br>3. 觀察 Tab 高亮、spinner、商品列表更新 | Tab 切換流暢，無卡頓；spinner 正確顯示/消失；商品列表正確更新 |
| MAN-02 | 小螢幕 Tab 列表可橫向捲動 | 1. 開啟瀏覽器開發者工具<br>2. 調整視窗至 320px 寬<br>3. 檢視 Tab 列表 | Tab 列表可橫向捲動，不溢出容器；「更多」按鈕仍可點擊 |
| MAN-03 | 網路慢速時 Tab 切換體驗 | 1. 開啟 Chrome DevTools → Network → Slow 3G<br>2. 切換分類 | Tab 高亮立即響應；spinner 持續顯示直到資料載入完成；不出现空白或错误 |
| MAN-04 | 分類 Tab 超過 5 個時折疊操作 | 1. 確認有 6 個以上分類<br>2. 點擊「更多」展開<br>3. 切換到第 6 個分類<br>4. 重新整理頁面 | 展開後可正常切換；重新整理後恢復折疊狀態 |
| MAN-05 | 多裝置 Tab 顯示一致性 | 1. 在桌面瀏覽器確認 Tab 列表<br>2. 在手機瀏覽器開啟同頁面 | Tab 列表顯示一致；分類順序相同；均可正常切換 |
| MAN-06 | Tab 列表無障礙鍵盤操作 | 1. 以 Tab 鍵在各分類間移動焦點<br>2. 以 Enter 鍵切換分類<br>3. 以方向鍵在 Tab 間移動 | 焦點可見；Enter 切換分類；方向鍵切換 Tab（符合 WAI-ARIA Tab Pattern） |

---

## 6. 測試環境

| 項目 | 需求 |
|------|------|
| Node.js 版本 | ≥ 22.x（與專案 .nvmrc 一致） |
| Vitest 版本 | 3.2.x |
| @vue/test-utils 版本 | 2.4.x |
| happy-dom 版本 | 專案現有版本（元件測試） |
| jsdom 版本 | Vitest 預設或專案現有（storage 相關測試） |
| Playwright 版本 | 1.62.x |
| 測試瀏覽器（Playwright） | Chromium、Firefox、WebKit（Safari） |
| 測試 OS | macOS（開發）；CI Ubuntu latest |

---

## 7. 缺陷追蹤模板

| 欄位 | 說明 |
|------|------|
| ID | BUG-DC-XXX（DC = Dashboard Categories） |
| 測試案例 | 對應以上測試編號（F-I01、E2E-01、MAN-01 等） |
| 嚴重程度 | P0（阻擋：Tab 切換完全失效、商品列表不更新） / P1（主要：spinner 不消失、chips 更新錯誤、折疊失效） / P2（次要：Tab 高亮樣式瑕疵、切換動畫不流暢） |
| 重複步驟 | 逐步操作 |
| 預期 vs 實際 | 對照 |
| 環境 | OS / Browser / 版本 / 網路速度 |

---

## 8. 覆蓋率自我檢查

> 對應 `docs/interaction-flows/019-dashboard-categories.md` 中所有場景。

| 來源場景 | 測試案例 | 是否覆蓋 |
|----------|----------|:--------:|
| 步驟 1：Dashboard 頁面載入後顯示分類 Tab 列表 | F-T01, F-T02, E2E-01 | ✅ |
| 步驟 1：預設選取第一個分類 | F-T02, E2E-01 | ✅ |
| 步驟 1：第一個 Tab 反白高亮 | F-T02, E2E-01 | ✅ |
| 步驟 2：點擊分類 Tab 切換分類 | F-T03, F-T04, E2E-02 | ✅ |
| 步驟 2：Tab 反白高亮 | F-T04, E2E-02 | ✅ |
| 步驟 2：顯示載入 spinner | E2E-04, E2E-12 | ✅ |
| 步驟 2：載入新分類商品 | F-I02, INT-01, E2E-02 | ✅ |
| 步驟 2：更新分組 Chips | F-F01~F-F02, INT-02, E2E-03 | ✅ |
| 步驟 3：Spinner 淡出，顯示新分類商品列表 | E2E-04 | ✅ |
| 異常：分類 Tab 超過 5 個 → 顯示「更多 ▼」折疊 | F-T05, E2E-06 | ✅ |
| 異常：點擊「更多」展開全部分類 | F-T06, E2E-07 | ✅ |
| 異常：點擊「收起」折疊回 5 個 | F-T07, E2E-08 | ✅ |
| 異常：正好好 5 個分類時不顯示「更多」 | F-T08, E2E-11 | ✅ |
| 異常：切換分類時取消上一個請求 | F-I03, F-I06, E2E-05 | ✅ |
| 異常：新分類無商品 → 空狀態「暫無商品資料」 | F-I04, INT-05, E2E-09 | ✅ |
| 驗收：切換分類時間 < 1 秒 | E2E-10 | ✅ |
| 驗收：Tab 載入中顯示 loading 狀態 | F-T09, E2E-12 | ✅ |
| 驗收：Tab 列表可橫向捲動（小螢幕） | F-T10, MAN-02 | ✅ |
| 整合：切換分類後商品列表 + chips 同步更新 | INT-01, INT-02, INT-03 | ✅ |
| 整合：快速連續切換僅顯示最終結果 | INT-04, E2E-05 | ✅ |
| 整合：分類載入失敗不影響其他分類 | INT-06, F-I05 | ✅ |
| 手動：多分類操作流暢度 | MAN-01 | ✅ |
| 手動：網路慢速時 Tab 切換體驗 | MAN-03 | ✅ |
| 手動：多裝置 Tab 顯示一致性 | MAN-05 | ✅ |
| 手動：Tab 列表無障礙鍵盤操作 | MAN-06 | ✅ |

**全部 21 個 interaction-flow 場景已覆蓋（3 個步驟 + 4 個異常處理 + 4 個驗收檢查 + 手動驗證），無遺漏。**
