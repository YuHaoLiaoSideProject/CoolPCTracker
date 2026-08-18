# Dashboard Items — 測試計畫

> **對應 BDD**：`docs/bdds/017-dashboard-items.feature`
> **操作流程**：`docs/interaction-flows/017-dashboard-items.md`
> **技術決策**：`docs/tech-decisions/017-dashboard-items.md`
> **開發規格**：`docs/development/017-dashboard-items.md`
> **測試日期**：2026-08-17

---

## 1. 測試範圍總覽

> 本功能為**純前端**（Vue 3 composable + 元件 + 路由），資料來源為靜態 JSON，由現有 `useItems` singleton 載入，無後端 API 新增，故無後端單元測試。

| 層級 | 範圍 | 工具 | 負責 |
|------|------|------|------|
| 單元測試 | `composables/useDashboard.ts`（排序 + Top 10 + 歷史最低價計算 + extractCurrentPrice） | Vitest + @vue/test-utils | 前端 |
| 元件測試 | `components/DashboardCard.vue`（精簡版商品卡片：名稱、價格、歷史最低價、🥇 徽章、規格 chips、已下架標籤） | Vitest + @vue/test-utils + happy-dom | 前端 |
| 元件測試 | `components/DashboardSkeleton.vue`（全頁骨架屏：Tab 佔位 + 列表佔位 + shimmer 動畫） | Vitest + @vue/test-utils + happy-dom | 前端 |
| 整合測試 | `views/DashboardView.vue`（Tab 切換 + useDashboard 整合 + ErrorState + EmptyState + 骨架屏轉場） | Vitest + @vue/test-utils + happy-dom | 前端 |
| 端對端測試 | 完整 Dashboard 操作流程（導覽進入、資料載入、Tab 切換、Top 10 排序、卡片點擊、錯誤重試） | Playwright | 前端 |
| 手動驗證 | 骨架屏動畫流暢度、懶載入 chunk 大小、多分類同時失敗 UX、無登入訪問 | 手動 | QA |

---

## 2. 後端單元測試

> **不適用**：本功能為純前端，資料來源為靜態 JSON（`api/items/{g}.json`），無後端 API 改動。

---

## 3. 前端單元測試

### 3.1 composables/useDashboard.ts — 排序 + Top 10 + 歷史最低價

**Mock 策略**：直接 import `useDashboard` 純函數，傳入 `ref<Item[]>` 和 `ref<string | null>`，無需 mock 外部依賴。測試 `dashboardItems` computed 的排序、截斷、isLowest/lowestPrice 計算，以及 `extractCurrentPrice` 輔助函數。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-D01 | 正常排序：商品按價格由低到高排列 | `items` ref 含 5 筆商品（價格：9990、8990、10990、7990、9490）；`categoryId` ref 為 `'CPU'`（所有商品同分類） | 取得 `dashboardItems` 值 | 依序為 7990、8990、9490、9990、10990（升冪） |
| F-D02 | Top 10 截斷：超過 10 筆僅顯示前 10 名 | `items` ref 含 15 筆商品（不同價格） | 取得 `dashboardItems` 值 | `dashboardItems.length === 10`；僅含最便宜的 10 筆 |
| F-D03 | 不足 10 筆時顯示全部 | `items` ref 含 3 筆商品 | 取得 `dashboardItems` 值 | `dashboardItems.length === 3`；全部顯示 |
| F-D04 | null 價格（空 history）排到最後 | `items` 含 3 筆：A（price=9990，history 有值）、B（history 為空，currentPrice=null）、C（price=8990） | 取得 `dashboardItems` 值 | 排序為 C(8990)、A(9990)、B(null)；null 排最後 |
| F-D05 | 空 items 陣列回傳空 | `items` ref 為空陣列 `[]`；`categoryId` ref 為 `'CPU'` | 取得 `dashboardItems` 值 | `dashboardItems` 為空陣列 |
| F-D06 | categoryId 為 null 時回傳空 | `items` ref 含商品；`categoryId` ref 為 `null` | 取得 `dashboardItems` 值 | `dashboardItems` 為空陣列 |
| F-D07 | extractCurrentPrice 取 history 最後一筆 p | 商品 history 為 `[{d:'2026-01-01',p:8990},{d:'2026-01-02',p:9490}]` | 調用 `extractCurrentPrice(item)` | 回傳 `9490`（最後一筆） |
| F-D08 | extractCurrentPrice 空 history 回傳 null | 商品 history 為 `[]` | 調用 `extractCurrentPrice(item)` | 回傳 `null` |
| F-D09 | isLowest 標記：最便宜商品 isLowest=true | `items` 含 3 筆同分類商品（價格 7990、8990、9990） | 取得 `dashboardItems` | 第 1 筆（7990）的 `isLowest === true`；其餘 `isLowest === false` |
| F-D10 | isLowest 為 false 當無歷史最低價資料 | `items` 含 3 筆商品但所有商品 history 為空 | 取得 `dashboardItems` | 所有 `isLowest === false`（categoryLowest 無資料） |
| F-D11 | lowestPrice 正確反映分類歷史最低價 | `items` 含 3 筆商品（價格 7990、8990、9990） | 取得 `dashboardItems` | 所有項目的 `lowestPrice === 7990` |
| F-D12 | 歷史最低價與 usePriceHistory.stats.low 一致性 | 商品 history 含多筆價格 `[{p:9990},{p:8990},{p:7990}]` | 取得 `dashboardItems` 中該商品的 `lowestPrice` | `lowestPrice === 7990`（等價於 `Math.min(...history.map(p=>p.p))`） |
| F-D13 | 多分類混合：僅計算目前選中分類的 Top 10 | `items` 含 5 筆 CPU + 5 筆顯示卡（不同價格）；`categoryId` 為 `'CPU'` | 取得 `dashboardItems` | 僅含 5 筆 CPU 商品（按價格排序）；顯示卡商品不出現 |
| F-D14 | 切換分類後 dashboardItems 更新 | 初始 `categoryId` 為 `'CPU'`，`dashboardItems` 含 CPU 商品 | 將 `categoryId` 改為 `'顯示卡'` | `dashboardItems` 更新為顯示卡分類的商品 |
| F-D15 | 多個商品同價時 isLowest 標記所有同價商品 | `items` 含 3 筆商品（價格 8990、8990、9990） | 取得 `dashboardItems` | 前 2 筆（8990、8990）中最低價商品 `isLowest === true` |

**智能補充測試（非 BDD 直接推導）**：

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-D16 | 單一商品時正常回傳 | `items` 含 1 筆商品 | 取得 `dashboardItems` | `dashboardItems.length === 1`；`isLowest === true` |
| F-D17 | 全部商品 history 為空時 currentPrice 皆為 null | `items` 含 3 筆商品（history 皆為空） | 取得 `dashboardItems` | 所有 `currentPrice === null`；依 sort 規則 null 排最後 |
| F-D18 | 計算效能：1000 筆商品排序 <1ms | `items` 含 1000 筆商品（隨機價格） | 取得 `dashboardItems`（觸發 computed） | 回傳時間 <1ms（同步 computed，無非同步） |

### 3.2 components/DashboardCard.vue — 精簡版商品卡片

**Mock 策略**：使用 `@vue/test-utils` 的 `mount`，直接傳入 props。`usePriceDelta` 和 `specChipTexts` 透過 `vi.mock` 控制回傳值。`router.push` 透過 `vi.mock('vue-router')` 模擬。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-C01 | 正常商品顯示名稱與價格 | props: `item`（name='Intel i5', status='in_stock'）、`isLowest=false`、`lowestPrice=8990` | mount DashboardCard | DOM 包含「Intel i5」文字；顯示格式化價格（如 `NT$ 9,490`） |
| F-C02 | 歷史最低價顯示 | props: `lowestPrice=8990`、`currentPrice=9490`（currentPrice !== lowestPrice） | mount DashboardCard | DOM 包含「歷史最低」文字 + 格式化最低價 |
| F-C03 | 歷史最低價與目前價格相同時不顯示歷史最低 | props: `lowestPrice=9490`、`currentPrice=9490` | mount DashboardCard | DOM 不包含「歷史最低」文字 |
| F-C04 | isLowest=true 時顯示 🥇 徽章 | props: `isLowest=true`、`item.status='in_stock'` | mount DashboardCard | DOM 包含「🥇」emoji |
| F-C05 | isLowest=false 時不顯示 🥇 徽章 | props: `isLowest=false` | mount DashboardCard | DOM 不包含「🥇」emoji |
| F-C06 | 已下架商品顯示「已下架」標籤 | props: `item`（status='gone'） | mount DashboardCard | DOM 包含「已下架」文字；不顯示目前價格 |
| F-C07 | 已下架商品不顯示目前價格 | props: `item`（status='gone'）、`currentPrice=null` | mount DashboardCard | DOM 不包含價格數字；顯示「已下架」替代文字 |
| F-C08 | 已下架商品不顯示 🥇 徽章 | props: `item`（status='gone'）、`isLowest=true` | mount DashboardCard | DOM 不包含「🥇」emoji |
| F-C09 | 點擊卡片觸發路由導航 | props: `item`（id='item-001'） | 模擬點擊卡片元素 | `router.push` 被呼叫，參數為 `/product/item-001` |
| F-C10 | 鍵盤 Enter 鍵觸發路由導航 | props: `item`（id='item-001'） | 模擬 focus + 按下 Enter 鍵 | `router.push` 被呼叫，參數為 `/product/item-001` |
| F-C11 | 規格 chips 正確顯示 | props: `item`（spec 含 brand='Intel'、model='i5-13600K'）；mock `specChipTexts` 回傳 `['Intel', 'i5-13600K']` | mount DashboardCard | DOM 包含 2 個 `.chip` 元素 |
| F-C12 | 無規格 chips 時不顯示 chips 區塊 | props: `item`（spec 為空）；mock `specChipTexts` 回傳 `[]` | mount DashboardCard | DOM 不包含 `.dc-specs` 區塊 |
| F-C13 | 卡片具有無障礙屬性 | props: `item`（name='Intel i5'） | mount DashboardCard | 元素具有 `role="button"`、`tabindex="0"`、`aria-label` 屬性 |
| F-C14 | 空 history 商品 currentPrice 顯示「—」 | props: `item`（history 為空）、`status='in_stock'` | mount DashboardCard | DOM 包含「—」（無價格時的 fallback） |

### 3.3 components/DashboardSkeleton.vue — 全頁骨架屏

**Mock 策略**：使用 `@vue/test-utils` 直接 mount，無需 mock。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-SC01 | 渲染 5 個 Tab 佔位 | — | mount DashboardSkeleton | DOM 包含 5 個 `.ds-tab` 元素 |
| F-SC02 | 渲染 10 個卡片佔位 | — | mount DashboardSkeleton | DOM 包含 10 個 `.ds-card` 元素 |
| F-SC03 | 佔位元素具有 shimmer 動畫 class | — | mount DashboardSkeleton | 所有 `.ds-tab` 和 `.ds-card` 元素具有 `shimmer` class |
| F-SC04 | 容器具有 aria-hidden 屬性 | — | mount DashboardSkeleton | 根元素具有 `aria-hidden="true"` |
| F-SC05 | 佔位數量正確（Tab 5、卡片 10） | — | mount DashboardSkeleton | Tab 佔位數 === 5；卡片佔位數 === 10 |

### 3.4 views/DashboardView.vue — 整合測試

**Mock 策略**：mock `useItems` composable 控制 `items`、`categories`、`activeCategoryId`、`loading`、`error`、`retry`、`loadCategory`、`itemToCategory` 的回傳值。mock `useDashboard` 驗證整合行為。使用 `@vue/test-utils` 的 `mount` + `flushPromises`。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-V01 | 載入中顯示骨架屏 | mock `useItems`: `loading=true`、`error=null`、`dashboardItems=[]` | mount DashboardView | DOM 包含 `DashboardSkeleton` 元件 |
| F-V02 | 錯誤狀態顯示 ErrorState | mock `useItems`: `error={kind:'fetch-failed'}`、`loading=false` | mount DashboardView | DOM 包含 `ErrorState` 元件 |
| F-V03 | 正常狀態顯示 Tab 列表 | mock `useItems`: `categories=[{id:'cpu',name:'CPU'},{id:'gpu',name:'顯示卡'}]`、`loading=false`、`error=null` | mount DashboardView | DOM 包含 2 個 `.tab-btn` 元素 |
| F-V04 | 正常狀態顯示商品列表 | mock `useDashboard` 回傳 `dashboardItems` 含 3 筆 | mount DashboardView | DOM 包含 3 個 `DashboardCard` 元件 |
| F-V05 | 空狀態顯示 EmptyState | mock `useDashboard`: `dashboardItems=[]`；`categories` 有值 | mount DashboardView | DOM 包含 `EmptyState` 元件 |
| F-V06 | Tab 點擊觸發 loadCategory | mock `useItems`: `categories=[{id:'cpu'},{id:'gpu'}]` | 點擊第 2 個 Tab（顯示卡） | `loadCategory` 被呼叫，參數為 `'gpu'` |
| F-V07 | 預設選取第一個分類 | mock `useItems`: `categories=[{id:'cpu'},{id:'gpu'}]`、`activeCategoryId=null` | mount DashboardView + flushPromises | `loadCategory` 被呼叫，參數為 `'cpu'`（第一個分類） |
| F-V08 | 選中 Tab 具有 active class | mock `useItems`: `activeCategoryId='cpu'`、`categories=[{id:'cpu',name:'CPU'}]` | mount DashboardView | `id='cpu'` 的 Tab 按鈕具有 `active` class |
| F-V09 | 骨架屏與正常內容互斥顯示 | mock `useItems`: `loading=true`、`dashboardItems=[]` | mount DashboardView | 顯示 `DashboardSkeleton`；不顯示 Tab 列表和商品列表 |
| F-V10 | 錯誤狀態與正常內容互斥顯示 | mock `useItems`: `error={kind:'fetch-failed'}` | mount DashboardView | 顯示 `ErrorState`；不顯示 Tab 列表和商品列表 |
| F-V11 | 重試按鈕觸發 retry | mock `useItems`: `error={kind:'fetch-failed'}`、`retry=vi.fn()` | mount DashboardView → 找到 ErrorState → 模擬觸發 retry | `retry` 函數被呼叫 |
| F-V12 | categories 變化後自動選取第一分類 | mock `useItems`: `categories` 初始為空、`activeCategoryId=null` | 將 `categories` 更新為 `[{id:'cpu'}]` + flushPromises | `loadCategory` 被呼叫，參數為 `'cpu'` |

---

## 4. 端對端測試（Playwright）

> E2E 測試以**真實瀏覽器**為環境，使用 `page.route` 模擬 API 回應，`page.evaluate` 注入預設資料。`@smoke` / `@p0` 場景優先。

### 4.1 Dashboard 主要流程

| # | 測試名稱 | 操作步驟 | 預期結果 | 來源 BDD |
|---|---------|---------|---------|----------|
| E2E-01 | 透過導覽列進入 Dashboard @smoke | 1. 前往首頁 `/`<br>2. 點擊導覽列「Dashboard」連結 | 1. URL 變為 `/#/dashboard`<br>2. 顯示全頁骨架屏（`.dashboard-skeleton`）<br>3. 各分類 Tab 佔位和卡片佔位可見 | #1 透過導覽列進入 Dashboard |
| E2E-02 | 透過直接訪問 URL 進入 Dashboard @smoke | 1. 直接訪問 `/#/dashboard` | 1. 顯示全頁骨架屏<br>2. 骨架屏淡出後顯示 Tab 列表 | #2 透過直接訪問 URL 進入 Dashboard |
| E2E-03 | 資料載入成功後顯示分類與商品 @smoke | 1. 前往 `/#/dashboard`<br>2. 等待骨架屏淡出 | 1. 骨架屏消失<br>2. 顯示分類 Tab 列表<br>3. 第一個分類 Tab 為選取狀態<br>4. 顯示該分類的商品列表 | #3 資料載入成功後顯示分類與商品 |
| E2E-04 | 商品列表按價格低到高排序並顯示前 10 名 @smoke | 1. 前往 `/#/dashboard`<br>2. 等待資料載入<br>3. 取得商品列表中所有價格 | 1. 商品按價格由低到高排列<br>2. 最多顯示 10 筆商品<br>3. 第 1 名商品顯示 🥇 徽章 | #4 商品列表按價格低到高排序並顯示前 10 名 |
| E2E-05 | 商品卡片顯示完整資訊 | 1. 前往 `/#/dashboard`<br>2. 等待資料載入<br>3. 檢視第一張卡片 | 1. 卡片顯示商品名稱<br>2. 顯示目前價格（千分位格式，如 `NT$ 9,490`）<br>3. 顯示歷史最低價<br>4. 顯示規格摘要（chips） | #5 商品卡片顯示完整資訊 |
| E2E-06 | 點擊商品卡片進入詳情頁 @smoke | 1. 前往 `/#/dashboard`<br>2. 等待資料載入<br>3. 點擊任一商品卡片 | 1. URL 導航至 `/product/{id}`<br>2. 顯示商品詳情頁面 | #6 點擊商品卡片進入詳情頁 |
| E2E-07 | 切換分類查看不同分類的商品 | 1. 前往 `/#/dashboard`<br>2. 等待資料載入（預設 CPU）<br>3. 記錄目前商品列表<br>4. 點擊「顯示卡」Tab | 1. Tab 切換成功<br>2. 商品列表更新為顯示卡分類<br>3. 商品按價格由低到高排序<br>4. 最多顯示 10 筆 | #7 切換分類查看不同分類的商品 |

### 4.2 錯誤處理

| # | 測試名稱 | 操作步驟 | 預期結果 | 來源 BDD |
|---|---------|---------|---------|----------|
| E2E-08 | API 載入失敗顯示錯誤頁面 @error-handling | 1. `page.route` 攔截 `**/api/items/**` 回傳 500<br>2. 前往 `/#/dashboard` | 1. 顯示錯誤頁面<br>2. 錯誤訊息為「無法載入資料」<br>3. 顯示「重試」按鈕 | #8 API 載入失敗顯示錯誤頁面 |
| E2E-09 | 點擊重試按鈕重新載入資料 @error-handling | 1. `page.route` 攔截 API 回傳 500<br>2. 前往 `/#/dashboard`<br>3. 等待錯誤頁面顯示<br>4. `page.route` 恢復正常回應<br>5. 點擊「重試」按鈕 | 1. 顯示載入狀態<br>2. API 重新被呼叫<br>3. 正常顯示 Tab 列表和商品列表 | #9 點擊重試按鈕重新載入資料 |
| E2E-10 | 分類無商品時顯示空狀態 @error-handling | 1. `page.route` 攔截特定分類 API 回傳空陣列 `[]`<br>2. 前往 `/#/dashboard`<br>3. 切換到該分類 | 1. 顯示空狀態<br>2. 空狀態訊息為「暫無商品資料」<br>3. 顯示對應圖示 | #10 分類無商品時顯示空狀態 |

### 4.3 邊界情況

| # | 測試名稱 | 操作步驟 | 預期結果 | 來源 BDD |
|---|---------|---------|---------|----------|
| E2E-11 | 歷史新低價商品顯示徽章 @edge-case | 1. `page.route` 回傳商品資料（含 history，目前價格 === 歷史最低價）<br>2. 前往 `/#/dashboard` | 1. 該商品卡片顯示「🥇」徽章<br>2. 不顯示「歷史最低」文字（因 currentPrice === lowestPrice） | #13 歷史新低價商品顯示徽章 |
| E2E-12 | 已下架商品顯示下架標籤 @edge-case | 1. `page.route` 回傳商品資料（含 status='gone' 的商品）<br>2. 前往 `/#/dashboard` | 1. 該商品顯示「已下架」標籤<br>2. 不顯示目前價格<br>3. 不顯示 🥇 徽章 | #14 已下架商品顯示下架標籤 |
| E2E-13 | 多個分類同時載入失敗 @edge-render | 1. `page.route` 攔截所有 `**/api/items/**` 回傳 500<br>2. 前往 `/#/dashboard` | 1. 顯示錯誤頁面<br>2. 錯誤訊息為「無法載入資料」<br>3. 顯示「重試」按鈕 | #15 多個分類同時載入失敗 |
| E2E-14 | 分類商品數少於 10 筆時顯示全部 @edge-case | 1. `page.route` 回傳僅 3 筆商品的分類資料<br>2. 前往 `/#/dashboard` | 1. 顯示 3 筆商品（全部顯示）<br>2. 不足 10 筆時不顯示額外佔位 | #11 分類商品數少於 10 筆時顯示全部 |
| E2E-15 | 價格格式化顯示千分位 @edge-case | 1. `page.route` 回傳商品價格為 15800<br>2. 前往 `/#/dashboard` | 1. 價格顯示為「NT$ 15,800」（千分位） | #12 價格格式化顯示千分位 |

### 4.4 商業規則

| # | 測試名稱 | 操作步驟 | 預期結果 | 來源 BDD |
|---|---------|---------|---------|----------|
| E2E-16 | Dashboard 無需登入即可訪問 @business-rules | 1. 清除所有登入狀態<br>2. 直接訪問 `/#/dashboard` | 1. 正常顯示 Dashboard 頁面<br>2. 無登入提示或重導向 | #16 Dashboard 無需登入即可訪問 |
| E2E-17 | 每個分類最多顯示前 10 名最便宜商品 @business-rules | 1. `page.route` 回傳某分類含 15 筆商品<br>2. 前往 `/#/dashboard` | 1. 該分類僅顯示 10 筆商品<br>2. 第 11–15 筆不顯示 | #17 每個分類最多顯示前 10 名最便宜商品 |
| E2E-18 | 商品按價格由低到高排序 @business-rules | 1. `page.route` 回傳商品（價格打亂順序）<br>2. 前往 `/#/dashboard`<br>3. 取得所有卡片價格 | 1. 第 1 件價格 <= 第 2 件價格<br>2. 第 2 件價格 <= 第 3 件價格<br>3. 依此類推 | #18 商品按價格由低到高排序 |
| E2E-19 | 預設選取第一個分類 @business-rules | 1. 前往 `/#/dashboard`<br>2. 等待資料載入 | 1. 第一個分類 Tab 為選取狀態<br>2. 自動載入該分類的商品 | #19 預設選取第一個分類 |
| E2E-20 | 最便宜商品標示金牌徽章 @business-rules | 1. `page.route` 回傳商品資料<br>2. 前往 `/#/dashboard`<br>3. 等待資料載入 | 1. 第 1 名商品（最便宜）顯示 🥇 徽章<br>2. 其餘商品不顯示 🥇 | #20 最便宜商品標示金牌徽章 |

### 4.5 風險對應測試（Tech Decision §7）

| # | 測試名稱 | 操作步驟 | 預期結果 | 對應風險 |
|---|---------|---------|---------|---------|
| E2E-21 | Tab 快速切換不導致 stale data @risk | 1. 前往 `/#/dashboard`<br>2. 快速連續點擊 5 個不同 Tab（間隔 <100ms）<br>3. 等待最後一個 Tab 載入完成 | 1. 最終顯示最後點擊的分類商品<br>2. 無顯示前一個分類的商品（無 stale data） | loadCategory 併發（快速切換 Tab） |
| E2E-22 | 骨架屏→列表轉場動畫流暢 @risk | 1. 前往 `/#/dashboard`<br>2. 以 `page.video` 或觀察 DOM 變化 | 1. 骨架屏先顯示<br>2. 資料載入後骨架屏淡出<br>3. 商品列表淡入<br>4. 無 layout shift（骨架屏與列表佔同高度） | 骨架屏→列表轉場動畫不流暢 |

---

## 5. 手動驗證（真實環境）

| # | 情境 | 驗證步驟 | 預期 |
|---|------|---------|------|
| MAN-01 | 骨架屏 shimmer 動畫流暢 | 1. 開啟 Chrome DevTools → Performance<br>2. 前往 `/#/dashboard`<br>3. 記錄骨架屏動畫 | shimmer 動畫流暢（60fps）；無 jank |
| MAN-02 | 懶載入 chunk 大小合理 | 1. 建置專案（`npm run build`）<br>2. 檢查 `dist/` 輸出中 Dashboard 相關 chunk | DashboardView chunk < 10KB gzipped（Tech Decision §7 預估） |
| MAN-03 | 多分類同時失敗 UX | 1. 模擬網路斷線<br>2. 前往 `/#/dashboard`<br>3. 觀察錯誤頁面 | 錯誤頁面清晰可讀；重試按鈕可點擊；無殘留骨架屏 |
| MAN-04 | 無登入狀態訪問 Dashboard | 1. 清除所有登入狀態（cookies、localStorage）<br>2. 直接訪問 `/#/dashboard` | 正常顯示 Dashboard；無登入提示；無重導向 |
| MAN-05 | Tab 列表在小螢幕上可橫向滾動 | 1. Chrome DevTools → 切換至 mobile（375px 寬）<br>2. 前往 `/#/dashboard`<br>3. 檢視 Tab 列表 | Tab 列表可橫向滾動；所有 Tab 可見可點擊 |
| MAN-06 | 大量分類（10+）時 Tab 列表效能 | 1. 手動注入 15 個分類<br>2. 前往 `/#/dashboard`<br>3. 快速切換 Tab | Tab 切換流暢（<100ms）；無明顯延遲 |
| MAN-07 | 商品詳情頁導航正確 | 1. 前往 `/#/dashboard`<br>2. 點擊不同分類的商品卡片<br>3. 確認導航至正確的詳情頁 | 每張卡片導航至對應的 `/product/{id}` 詳情頁 |

---

## 6. 測試環境

| 項目 | 需求 |
|------|------|
| Node.js 版本 | ≥ 22.x（與專案 .nvmrc 一致） |
| Vitest 版本 | 3.2.x |
| @vue/test-utils 版本 | 2.4.x |
| happy-dom 版本 | 專案現有版本（元件測試 DOM 環境） |
| Playwright 版本 | 1.62.x |
| 測試瀏覽器（Playwright） | Chromium（主要）、Firefox、WebKit（Safari） |
| 測試 OS | macOS（開發）；CI Ubuntu latest |
| Vite 版本 | 6.0.x |
| TypeScript 版本 | 5.6.x |

---

## 7. 缺陷追蹤模板

| 欄位 | 說明 |
|------|------|
| ID | BUG-DI-XXX（DI = Dashboard Items） |
| 測試案例 | 對應以上測試編號（F-D01、F-C01、F-SC01、F-V01、E2E-01、MAN-01 等） |
| 嚴重程度 | P0（阻擋：Dashboard 頁面無法載入、排序完全錯誤、路由失效） / P1（主要：Top 10 截斷錯誤、歷史最低價計算錯誤、Tab 切換異常） / P2（次要：骨架屏動畫瑕疵、格式化不一致、徽章顯示異常） |
| 重複步驟 | 逐步操作 |
| 預期 vs 實際 | 對照 |
| 環境 | OS / Browser / 版本 / 網路狀況 |

---

## 8. 覆蓋率自我檢查

| BDD Scenario | 測試案例 | 是否覆蓋 |
|--------------|----------|:--------:|
| #1 透過導覽列進入 Dashboard | E2E-01 | ✅ |
| #2 透過直接訪問 URL 進入 Dashboard | E2E-02 | ✅ |
| #3 資料載入成功後顯示分類與商品 | E2E-03, F-V01→F-V03 | ✅ |
| #4 商品列表按價格低到高排序並顯示前 10 名 | E2E-04, F-D01~D05 | ✅ |
| #5 商品卡片顯示完整資訊 | E2E-05, F-C01~C03, F-C11~C12 | ✅ |
| #6 點擊商品卡片進入詳情頁 | E2E-06, F-C09~C10 | ✅ |
| #7 切換分類查看不同分類的商品 | E2E-07, F-V06, F-D14 | ✅ |
| #8 API 載入失敗顯示錯誤頁面 | E2E-08, F-V02 | ✅ |
| #9 點擊重試按鈕重新載入資料 | E2E-09, F-V11 | ✅ |
| #10 分類無商品時顯示空狀態 | E2E-10, F-V05 | ✅ |
| #11 分類商品數少於 10 筆時顯示全部 | E2E-14, F-D03 | ✅ |
| #12 價格格式化顯示千分位 | E2E-15, F-C01 | ✅ |
| #13 歷史新低價商品顯示徽章 | E2E-11, F-C04~C05 | ✅ |
| #14 已下架商品顯示下架標籤 | E2E-12, F-C06~C08 | ✅ |
| #15 多個分類同時載入失敗 | E2E-13, MAN-03 | ✅ |
| #16 Dashboard 無需登入即可訪問 | E2E-16, MAN-04 | ✅ |
| #17 每個分類最多顯示前 10 名最便宜商品 | E2E-17, F-D02 | ✅ |
| #18 商品按價格由低到高排序 | E2E-18, F-D01 | ✅ |
| #19 預設選取第一個分類 | E2E-19, F-V07 | ✅ |
| #20 最便宜商品標示金牌徽章 | E2E-20, F-D09 | ✅ |

**全部 20 個 BDD Scenario 已覆蓋。**

### 風險覆蓋率

| Tech Decision 風險 | 測試案例 | 是否覆蓋 |
|--------------------|----------|:--------:|
| useItems singleton 載入分類時機與 Dashboard 預設分類不同步 | F-V07, F-V12, E2E-19 | ✅ |
| 歷史最低價計算與 usePriceHistory.stats.low 不一致 | F-D12 | ✅ |
| loadCategory 併發（快速切換 Tab）導致 stale data | E2E-21 | ✅ |
| 骨架屏→列表轉場動畫不流暢 | E2E-22, MAN-01 | ✅ |
| Dashboard 路由懶載入 chunk 過大 | MAN-02 | ✅ |

**全部 5 個 Tech Decision 風險已有對應測試。**

### 測試案例統計

| 測試層級 | 數量 | ID 前綴 |
|---------|:----:|---------|
| useDashboard 單元測試 | 18 | F-D |
| DashboardCard 元件測試 | 14 | F-C |
| DashboardSkeleton 元件測試 | 5 | F-SC |
| DashboardView 整合測試 | 12 | F-V |
| E2E 測試 | 22 | E2E |
| 手動驗證 | 7 | MAN |
| **合計** | **78** | — |
