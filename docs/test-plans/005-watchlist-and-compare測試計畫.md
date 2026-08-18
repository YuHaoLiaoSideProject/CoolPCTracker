# 追蹤清單與比價 — 測試計畫

> **對應 BDD**：`docs/bdds/005-watchlist-and-compare.feature`
> **操作流程**：`docs/interaction-flows/005-watchlist-and-compare.md`
> **開發規格**：`docs/development/005-watchlist-and-compare.md`
> **測試日期**：2026-08-16

---

## 1. 測試範圍總覽

> 本功能為**純前端**（localStorage + sessionStorage），無任何後端 API 新增，故無後端單元測試。

| 層級 | 範圍 | 工具 | 負責 |
|------|------|------|------|
| 單元測試 | `utils/storage.ts`（storage 可用性探測、版本化讀寫、Quota 錯誤轉換、corrupt 自癒） | Vitest + jsdom | 前端 |
| 單元測試 | `utils/compare.ts`（`specColumnsFor`、`buildCompareRows`、`findCheapestIds` 純函數） | Vitest | 前端 |
| 單元測試 | `composables/useWatchlist.ts`（localStorage 讀寫、去重、排序、價差快照、錯誤處理） | Vitest + jsdom | 前端 |
| 單元測試 | `composables/useCompare.ts`（sessionStorage 讀寫、同分類檢查、2–6 上下限） | Vitest + jsdom | 前端 |
| 單元測試 | `components/Sparkline.vue`（7 日截取、資料不足判斷、SVG 渲染） | Vitest + @vue/test-utils + happy-dom | 前端 |
| 端對端測試 | 完整追蹤清單管理流程（加入/移除/排序/空狀態/錯誤） | Playwright | 前端 |
| 端對端測試 | 完整比價流程（勾選/同分類/上限/結果表/最便宜/清除） | Playwright | 前端 |
| 手動驗證 | localStorage/sessionStorage 跨裝置不存活、清除瀏覽器資料遺失、多瀏覽器相容 | 手動 | QA |

---

## 2. 前端單元測試

### 2.1 utils/storage.ts — storage 可用性探測與版本化讀寫

**Mock 策略**：使用 `vi.fn()` 模擬 `Storage.prototype`，覆蓋 `window.localStorage` / `window.sessionStorage`。`jsdom` 預設支援 storage，需測試封鎖情境時用 `vi.spyOn` 讓 `setItem` 拋出 `DOMException`。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-S01 | storage 可用時 isStorageAvailable 回傳 true | `window.localStorage` 正常可用 | 調用 `isStorageAvailable('local')` | 回傳 `true`，且測試 key 已被清除（不污染） |
| F-S02 | storage 被封鎖時 isStorageAvailable 回傳 false | `localStorage.setItem` 拋出 `DOMException` | 調用 `isStorageAvailable('local')` | 回傳 `false` |
| F-S03 | readVersioned 讀取到有效版本化資料 | localStorage 含 `{ version: 1, items: [...] }` | 調用 `readVersioned('local', key, 1)` | 回傳 `{ ok: true, value: { version: 1, items: [...] } }` |
| F-S04 | readVersioned 版本不符時回傳 null | localStorage 含 `{ version: 0, items: [...] }` | 調用 `readVersioned('local', key, 1)` | 回傳 `{ ok: true, value: null }`（觸發 migrate） |
| F-S05 | readVersioned JSON 損毀時回傳 corrupt 錯誤 | localStorage 含非法字串 `"not-json"` | 調用 `readVersioned('local', key, 1)` | 回傳 `{ ok: false, error: { kind: 'corrupt', ... } }` |
| F-S06 | readVersioned 損毀後 quarantineCorrupt 備份 | localStorage 含非法字串 `"not-json"` | 調用 `readVersioned` 觸發 corrupt | 原 key 被刪除；備份 key `{key}.corrupt-{ts}` 存在且值為原始字串 |
| F-S07 | writeVersioned 成功寫入版本化資料 | localStorage 空白 | 調用 `writeVersioned('local', key, 1, payload)` | 回傳 `{ ok: true }`；`localStorage.getItem(key)` 為序列化後的 `{ version: 1, ... }` |
| F-S08 | writeVersioned 觸發 QuotaExceededError | `localStorage.setItem` 拋出 `QuotaExceededError` | 調用 `writeVersioned('local', key, 1, payload)` | 回傳 `{ ok: false, error: { kind: 'quota-exceeded', ... } }` |
| F-S09 | writeVersioned storage 不可用時回傳 unsupported | `isStorageAvailable` 回傳 `false` | 調用 `writeVersioned('local', key, 1, payload)` | 回傳 `{ ok: false, error: { kind: 'unsupported', ... } }` |
| F-S10 | removeKey 正常刪除 key | localStorage 含 key | 調用 `removeKey('local', key)` | `localStorage.getItem(key)` 為 `null` |
| F-S11 | readVersioned 讀取空 key（無資料）回傳 null | localStorage 不含 key | 調用 `readVersioned('local', key, 1)` | 回傳 `{ ok: true, value: null }` |

### 2.2 utils/compare.ts — 比較表純函數

**直接 import 純函數，無需 mock。**

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-C01 | specColumnsFor('CPU') 回傳 CPU 規格欄位 | — | 調用 `specColumnsFor('CPU')` | 回傳含 brand/model/cores/threads/base_ghz/turbo_ghz/tdp_w 的欄位陣列 |
| F-C02 | specColumnsFor('顯示卡') 回傳顯示卡規格欄位 | — | 調用 `specColumnsFor('顯示卡')` | 回傳含 brand/model/vram 等欄位 |
| F-C03 | specColumnsFor('記憶卡') 回傳輕量欄位 | — | 調用 `specColumnsFor('記憶卡')` | 回傳僅 brand/model 等基礎欄位 |
| F-C04 | buildCompareRows 建構並排比較表 | 2 件商品含 price、spec | 調用 `buildCompareRows(items)` | 首列 key 為 `price`（label 為「目前價格」）；各商品值並排；格式化為 NT$ 千分位 |
| F-C05 | buildCompareRows 中已下架商品 price 為 null | 1 件 in_stock、1 件 gone（price=null） | 調用 `buildCompareRows(items)` | gone 商品的 price 列顯示「—」 |
| F-C06 | buildCompareRows spec 缺值時顯示「—」 | 商品 A 有 cores，商品 B 無 cores | 調用 `buildCompareRows(items)` | B 的 cores 欄位值為「—」 |
| F-C07 | findCheapestIds 單一最低價 | 3 件商品分別 9990、8990、10990 | 調用 `findCheapestIds(items)` | 回傳 `['id-b']`（8990 那筆） |
| F-C08 | findCheapestIds 同價並列標示 | 2 件商品價格皆為 9990 | 調用 `findCheapestIds(items)` | 回傳 2 個 id（兩者皆標最便宜） |
| F-C09 | findCheapestIds 排除 gone 商品 | 1 件 in_stock（9990）、1 件 gone（null） | 調用 `findCheapestIds(items)` | 回傳 `['id-a']`（僅有價格的 a） |
| F-C10 | findCheapestIds 全部 gone 時回傳空陣列 | 2 件商品皆 gone | 調用 `findCheapestIds(items)` | 回傳 `[]` |
| F-C11 | buildCompareRows 空陣列 | items 為 `[]` | 調用 `buildCompareRows([])` | 回傳 `[]` |

### 2.3 composables/useWatchlist.ts — 追蹤清單管理

**Mock 策略**：測試前以 `vi.stubGlobal('localStorage', ...)` 或直接 mock `utils/storage.ts` 的 `readVersioned` / `writeVersioned` / `isStorageAvailable`，控制各種 storage 情境。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-W01 | 新增追蹤成功 | storage 可用，商品不在清單 | `add('id-a', 9990)` | 回傳 `{ ok: true }`；`items.value` 含 `id-a`；`items.value[0].lastPriceSnapshot === 9990` |
| F-W02 | 新增追蹤時 isTracked 正確反映 | 已加入 `id-a` | 調用 `isTracked('id-a')` | 回傳 `true`；`isTracked('id-b')` 回傳 `false` |
| F-W03 | 重複加入回傳 already-tracked 且不重複 | 已加入 `id-a` | 再次 `add('id-a', 9990)` | 回傳 `{ ok: false, reason: 'already-tracked' }`；`items.value` 仍僅 1 筆 |
| F-W04 | storage 不可用時回傳 storage-unavailable | `isStorageAvailable` 回傳 `false` | `add('id-a', 9990)` | 回傳 `{ ok: false, reason: 'storage-unavailable' }`；`items.value` 空 |
| F-W05 | quota 超過時回傳 quota-exceeded 且 rollback | `writeVersioned` 回傳 `quota-exceeded` | `add('id-a', 9990)` | 回傳 `{ ok: false, reason: 'quota-exceeded' }`；`items.value` 空（ref 被 rollback） |
| F-W06 | 移除商品成功 | 已加入 `id-a`、`id-b` | `remove('id-a')` | `items.value` 僅含 `id-b` |
| F-W07 | 移除不存在的商品不報錯 | 清單為空 | `remove('id-x')` | `items.value` 仍為空；不拋異常 |
| F-W08 | 重新排序後 items 順序正確 | 已加入 A、B、C | `reorder(['C', 'A', 'B'])` | `items.value[0].id === 'C'`、`items.value[1].id === 'A'`、`items.value[2].id === 'B'` |
| F-W09 | 重新排序後寫回 localStorage | 已加入 A、B、C | `reorder(['C', 'A', 'B'])` | `writeVersioned` 被呼叫且參數含新順序 |
| F-W10 | updatePriceSnapshot 更新快照與時間 | `id-a` 的 `lastPriceSnapshot` 為 9990 | `updatePriceSnapshot('id-a', 8990)` | `items.value.find(i => i.id === 'a').lastPriceSnapshot === 8990`；`priceSnapshotAt` 為新的 ISO 時間 |
| F-W11 | hydrate 讀取已有的 localStorage 資料 | localStorage 含 v1 追蹤資料（A、B） | 新建 composable 實例 | `items.value` 含 2 筆，id 分別為 A、B |
| F-W12 | hydrate 損毀資料時自癒重置 | localStorage 含非法 JSON | 新建 composable 實例 | `items.value` 為空；`error.value` 為 null（corrupt 由 storage 層處理） |
| F-W13 | hydrate 時 storage 不可用設置 error | `isStorageAvailable` 回傳 `false` | 新建 composable 實例 | `error.value.kind === 'unsupported'`；`items.value` 為空 |
| F-W14 | error 清除 | `error.value` 非 null | `clearError()` | `error.value === null` |
| F-W15 | 模組級單例（多處呼叫返回同一 ref） | 已在 A 處 `add('id-x', 100)` | 在 B 處呼叫 `useWatchlist()` | `isTracked('id-x')` 為 `true`（共享同一份 state） |

### 2.4 composables/useCompare.ts — 比價選取管理

**Mock 策略**：mock `utils/storage.ts` 控制 sessionStorage 行為。

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-P01 | 新增比價選取成功 | sessionStorage 空白，無已選 | `add({ id: 'a', category: 'CPU' })` | 回傳 `{ ok: true }`；`selected.value` 含 1 筆；`count.value === 1` |
| F-P02 | category 計算正確 | 已選 1 件 CPU 商品 | 讀取 `category.value` | 為 `'CPU'`；空選取時為 `null` |
| F-P03 | canStart 至少 2 件才為 true | 已選 1 件 | 讀取 `canStart.value` | 為 `false`；選第 2 件後為 `true` |
| F-P04 | isFull 達 6 件時為 true | 已選 6 件 | 讀取 `isFull.value` | 為 `true` |
| F-P05 | 跨分類加入被拒絕 | 已選 1 件 CPU 商品 | `add({ id: 'b', category: '顯示卡' })` | 回傳 `{ ok: false, reason: 'different-category' }`；`selected.value` 不變 |
| F-P06 | 達 6 件上限後再加被拒絕 | 已選 6 件 | `add({ id: 'g', category: 'CPU' })` | 回傳 `{ ok: false, reason: 'max-6' }`；`selected.value` 仍為 6 件 |
| F-P07 | 同分類正常加入（未滿 6 件） | 已選 1 件 CPU | `add({ id: 'b', category: 'CPU' })` | 回傳 `{ ok: true }`；`count.value === 2` |
| F-P08 | remove 移除選取中的商品 | 已選 A、B、C | `remove('B')` | `selected.value` 含 A、C |
| F-P09 | clear 清空所有選取 | 已選 3 件 | `clear()` | `selected.value === []`；`count.value === 0` |
| F-P10 | isSelected 正確反映 | 已選 A、B | `isSelected('A')` 為 `true`；`isSelected('C')` 為 `false` |
| F-P11 | hydrate 從 sessionStorage 恢復 | sessionStorage 含 v1 比價資料（A、B、C） | 新建 composable 實例 | `selected.value` 含 3 筆；`count.value === 3` |
| F-P12 | hydrate 損毀時自癒 | sessionStorage 含非法 JSON | 新建 composable 實例 | `selected.value` 為空 |
| F-P13 | storage 不可用時 add 回傳 storage-unavailable | `isStorageAvailable('session')` 回傳 `false` | `add({ id: 'a', category: 'CPU' })` | 回傳 `{ ok: false, reason: 'storage-unavailable' }` |
| F-P14 | toggle 已選時移除 | 已選 A | `toggle({ id: 'A', category: 'CPU' })` | 回傳 `{ ok: true, removed: true }`；`selected.value` 為空 |
| F-P15 | toggle 未選時加入 | 空選取 | `toggle({ id: 'A', category: 'CPU' })` | 回傳 `{ ok: true }`；`selected.value` 含 A |
| F-P16 | 模組級單例共享 state | 在路由 A 呼叫 `useCompare` 並 `add` | 在路由 B 呼叫 `useCompare` | 同一份 `selected` ref（SPA 跨路由保留） |

### 2.5 components/Sparkline.vue — 迷你趨勢元件

| # | 測試名稱 | Given | When | Then |
|---|---------|-------|------|------|
| F-SP01 | 7 日以上歷史顯示 SVG 圖表 | `points` 含 10 筆歷史（7 點以上的 `{ d, p }`） | mount Sparkline | render SVG `polyline` 元素；`points` 屬性長度為 7 |
| F-SP02 | 正確截取最近 7 日 | `points` 含 10 筆歷史 | mount Sparkline | 渲染的 polyline 點數為 7（取最後 7 筆） |
| F-SP03 | 歷史不足 2 日顯示「資料不足」 | `points` 含 1 筆歷史 | mount Sparkline | 不渲染 SVG 圖表；文字包含「資料不足」 |
| F-SP04 | 正好 2 日歷史顯示 SVG | `points` 含 2 筆歷史 | mount Sparkline | render SVG 圖表（最低門檻 2 點可繪製） |
| F-SP05 | 空陣列顯示「資料不足」 | `points` 為 `[]` | mount Sparkline | 文字包含「資料不足」 |

---

## 3. 端對端測試（Playwright）

> E2E 測試以 **真實瀏覽器** 為環境，localStorage/sessionStorage 由瀏覽器原生管理。以 `page.evaluate` 注入預設資料、以 `page.route` 模擬 API 回應。`@smoke` 場景優先。

### 3.1 追蹤清單管理

| # | 測試名稱 | 操作步驟 | 預期結果 | 來源 BDD |
|---|---------|---------|---------|----------|
| E2E-01 | 從商品列表加入追蹤 @smoke | 1. 前往商品列表頁<br>2. 找到「Intel i5-13600K」<br>3. 點擊「加入追蹤」按鈕<br>4. 重新整理頁面 | 1. 按鈕變為「已追蹤」<br>2. 出現「已加入追蹤」提示<br>3. 重新整理後「Intel i5-13600K」仍在追蹤清單（按鈕仍為「已追蹤」） | 從商品列表加入追蹤 |
| E2E-02 | 從商品詳情頁加入追蹤 | 1. 前往「ASUS TUF RTX 4070」詳情頁<br>2. 點擊「加入追蹤」<br>3. 前往列表頁確認 | 1. 詳情頁按鈕變為「已追蹤」<br>2. 列表頁該商品也顯示「已追蹤」 | 從不同入口加入追蹤（詳情頁） |
| E2E-03 | 已追蹤商品不重複加入 | 1. 前往已追蹤商品的詳情頁<br>2. 確認按鈕已為「已追蹤」<br>3. 前往「我的追蹤」頁確認 | 1. 按鈕維持「已追蹤」<br>2. 追蹤清單中該商品僅 1 筆 | 已在追蹤清單的商品不重複加入 |
| E2E-04 | 從追蹤清單頁移除商品 @smoke | 1. 確保追蹤清單有「商品A」和「商品B」<br>2. 前往「我的追蹤」頁<br>3. 點擊「商品A」的「移除」按鈕<br>4. 重新整理頁面 | 1. 「商品A」從清單消失<br>2. 「商品B」仍在且順序不變<br>3. 重新整理後「商品A」仍不在 | 從追蹤清單頁移除商品 |
| E2E-05 | 從列表頁移除已追蹤商品 | 1. 確保「Intel i5-13600K」在追蹤清單<br>2. 在列表頁找到該商品<br>3. 點擊「已追蹤」按鈕 | 1. 按鈕變回「加入追蹤」<br>2. 該商品從追蹤清單移除 | 從列表頁移除已追蹤商品 |
| E2E-06 | 追蹤清單顯示價格、價差與迷你趨勢 | 1. 追蹤清單有「Intel i5-13600K」（上次快照 9990、現價 9490）<br>2. 前往「我的追蹤」頁 | 1. 顯示商品名稱與目前價格 9,490 元<br>2. 價差顯示「-500 元」且為跌價樣式（綠色）<br>3. 迷你趨勢圖顯示 | 檢視追蹤清單的價格、價差與迷你趨勢 |
| E2E-07 | 價差基準為上次查看價格 @business-rules | 1. 追蹤清單有商品A（上次快照 10000、現價 10500）<br>2. 前往「我的追蹤」頁<br>3. 確認價差為「+500」<br>4. 關閉再重新開啟「我的追蹤」頁 | 1. 第一次顯示「+500 元」（漲價樣式）<br>2. 第二次顯示「0 元」（快照已被更新為 10500） | 價差以「上次查看價格」為基準 |
| E2E-08 | 迷你趨勢僅顯示最近 7 日 | 1. 追蹤商品有 10 日歷史<br>2. 前往「我的追蹤」頁 | 1. 迷你趨勢圖僅包含 7 個數據點 | 迷你趨勢僅顯示最近 7 日歷史 |
| E2E-09 | 拖曳排序追蹤清單 | 1. 追蹤清單有 A、B、C<br>2. 前往「我的追蹤」頁<br>3. 將 C 拖曳至第一位<br>4. 重新整理頁面 | 1. 順序變為 C、A、B<br>2. 重新整理後順序維持 C、A、B | 拖曳排序追蹤清單 |
| E2E-10 | 追蹤清單為空時顯示引導 @edge-case | 1. 清空所有追蹤<br>2. 前往「我的追蹤」頁 | 1. 顯示空狀態說明<br>2. 顯示「去逛逛」按鈕<br>3. 不顯示任何商品列 | 追蹤清單為空時顯示引導 |
| E2E-11 | 追蹤商品已下架 @edge-case | 1. 追蹤清單有「商品X」<br>2. 模擬商品X 不在當日資料中（status=gone）<br>3. 前往「我的追蹤」頁 | 1. 該商品顯示「已下架」標示<br>2. 價格欄顯示「—」 | 追蹤的商品已下架 |
| E2E-12 | 迷你趨勢歷史資料不足 @edge-case | 1. 追蹤清單有「商品A」（僅 1 日歷史）<br>2. 前往「我的追蹤」頁 | 1. 迷你趨勢顯示「資料不足」<br>2. 不顯示圖表 | 迷你趨勢歷史資料不足 |
| E2E-13 | localStorage 封鎖時加入追蹤失敗 @error-handling | 1. 以 CDP 覆寫 `localStorage.setItem` 拋出異常<br>2. 點擊「加入追蹤」 | 1. 提示「瀏覽器未開放本機儲存，無法使用追蹤功能」<br>2. 商品不加入清單<br>3. 頁面不當機（正常顯示） | 瀏覽器不支援 localStorage 時加入追蹤失敗 |
| E2E-14 | localStorage 空間已滿 @error-handling | 1. 以 CDP 注入大資料填滿 localStorage 至接近 5MB<br>2. 嘗試加入新追蹤 | 1. 提示「儲存空間已滿，無法新增追蹤項目」<br>2. 原有追蹤清單內容不受影響 | localStorage 空間已滿時無法新增追蹤 |
| E2E-15 | 商品資料載入失敗時追蹤頁顯示錯誤 @error-handling | 1. `page.route` 攔截 API 回傳 500<br>2. 前往「我的追蹤」頁 | 1. 顯示「資料載入失敗」<br>2. 顯示「重新載入」按鈕<br>3. localStorage 追蹤資料仍存在 | 商品資料載入失敗時追蹤頁顯示錯誤狀態 |

### 3.2 比價

| # | 測試名稱 | 操作步驟 | 預期結果 | 來源 BDD |
|---|---------|---------|---------|----------|
| E2E-16 | 從列表勾選同類商品比價並標示最便宜 @smoke | 1. 在顯示卡列表頁勾選「顯卡A」（8990）與「顯卡B」（9990）<br>2. 點擊「開始比價」 | 1. 進入比價結果頁<br>2. 比較表並排顯示兩商品價格與規格<br>3. 「顯卡A」標示「最便宜」 | 從列表勾選同類商品產出比較表並標示最便宜 |
| E2E-17 | 從詳情頁加入比價 | 1. 前往「Intel i5-13600K」詳情頁<br>2. 點擊「加入比價」<br>3. 檢視 CompareBar | 1. 比價選取清單含「Intel i5-13600K」<br>2. 畫面顯示「已選 1/6」 | 從不同入口加入比價（詳情頁） |
| E2E-18 | 比價少於 2 件無法開始 @edge-case | 1. 僅勾選 1 件商品<br>2. 檢視「開始比價」按鈕 | 1. 「開始比價」按鈕維持停用（disabled）<br>2. 提示「請至少選擇 2 件商品進行比價」 | 比價選取少於 2 件無法開始 |
| E2E-19 | 比價超過 6 件上限 @edge-case | 1. 已勾選 6 件顯示卡<br>2. 嘗試勾選第 7 件 | 1. 第 7 件商品無法被勾選（disabled）<br>2. 提示「最多只能比較 6 件商品」<br>3. 已選的 6 件不受影響 | 比價選取超過 6 件上限 |
| E2E-20 | 比價僅限同分類 @business-rules | 1. 已勾選 1 件 CPU<br>2. 嘗試勾選 1 件顯示卡 | 1. 系統拒絕加入<br>2. 提示「比價僅限同類商品」<br>3. 原 CPU 商品選取不受影響 | 比價僅限同分類商品 |
| E2E-21 | 多件同價並列標示最便宜 @business-rules | 1. 勾選「顯卡A」與「顯卡B」<br>2. 兩者價格皆為 9990<br>3. 點擊「開始比價」 | 1. 比價表中兩商品皆標示「最便宜」 | 多件同價商品並列標示最便宜 |
| E2E-22 | 比較表依分類顯示對應規格 @business-rules | 1. 勾選 2 件 CPU 商品<br>2. 點擊「開始比價」 | 1. 比較表含價格欄位<br>2. 顯示 CPU 規格欄位（核心數、執行緒、基礎時脈、超頻時脈、TDP）<br>3. 各商品數值並排 | 比較表依分類顯示對應規格欄位 |
| E2E-23 | 從比價結果表加入追蹤 | 1. 完成「顯卡A」與「顯卡B」比價<br>2. 在比價表中點擊「顯卡A」的「加入追蹤」 | 1. 「顯卡A」加入追蹤清單<br>2. 按鈕變為「已追蹤」 | 從比價結果表加入追蹤 |
| E2E-24 | 清除比價 | 1. 已勾選 3 件商品<br>2. 點擊「清除比價」 | 1. 比價選取清單清空<br>2. 各商品勾選框回到未勾選狀態 | 清除比價選取 |
| E2E-25 | 比價清單含已下架商品 @edge-case | 1. 勾選「顯卡A」與「顯卡B」比價<br>2. 模擬「顯卡B」已下架<br>3. 前往比價結果頁 | 1. 「顯卡B」欄位標示「已下架」<br>2. 最便宜僅在有價格的「顯卡A」上計算 | 比價清單中的商品已下架 |
| E2E-26 | 比價選取跨頁面瀏覽保留 | 1. 在列表頁勾選 2 件商品<br>2. 前往詳情頁<br>3. 回到列表頁 | 1. 勾選狀態仍維持<br>2. CompareBar 顯示「已選 2/6」 | 比價選取跨頁面瀏覽保留 |
| E2E-27 | 關閉分頁後比價選取清空 | 1. 勾選 3 件商品<br>2. 關閉分頁<br>3. 重新開啟網站 | 1. 比價選取清空<br>2. CompareBar 不顯示 | 關閉分頁 sessionStorage 清空 |

### 3.3 跨瀏覽器 localStorage 存活期 E2E

| # | 測試名稱 | 操作步驟 | 預期結果 |
|---|---------|---------|---------|
| E2E-28 | Chrome：關閉再開啟分頁保留追蹤 | 1. Chrome 加入 2 件追蹤<br>2. 關閉分頁<br>3. 開新分頁前往「我的追蹤」 | 追蹤清單仍有 2 件 |
| E2E-29 | Firefox：關閉再開啟分頁保留追蹤 | 同 E2E-28（Firefox） | 同上 |
| E2E-30 | Safari：關閉再開啟分頁保留追蹤 | 同 E2E-28（Safari / WebKit） | 同上 |
| E2E-31 | Chrome 無痕模式：追蹤清單關閉即消失 | 1. Chrome 無痕模式加入追蹤<br>2. 關閉無痕視窗<br>3. 開新無痕視窗 | 追蹤清單為空（無痕模式 localStorage 不持久） |
| E2E-32 | 跨瀏覽器追蹤不共享 | 1. Chrome 加入追蹤 A<br>2. Firefox 前往「我的追蹤」 | Firefox 追蹤清單為空（本機專屬） |

---

## 4. 手動驗證（真實環境）

| # | 情境 | 驗證步驟 | 預期 |
|---|------|---------|------|
| MAN-01 | 清除瀏覽器資料後追蹤清單遺失 | 1. 加入若干追蹤<br>2. 瀏覽器設定 → 清除本機資料<br>3. 重新開啟網站 | 追蹤清單為空 |
| MAN-02 | 追蹤清單跨裝置不存活 | 1. 電腦 A 加入追蹤<br>2. 手機 B 開啟同網站 | 手機 B 追蹤清單為空 |
| MAN-03 | 比價選取跨裝置不共享 | 1. 電腦 A 勾選比價<br>2. 手機 B 開啟同網站 | 手機 B 無比價選取 |
| MAN-04 | 追蹤清單大量商品（>100 件）不影響效能 | 1. 手動加入 100+ 件追蹤<br>2. 瀏覽「我的追蹤」頁<br>3. 拖曳排序 | 頁面載入正常（<1s）；拖曳流暢；localStorage 未超限 |
| MAN-05 | iOS Safari 追蹤清單行為 | 1. iPhone Safari 加入追蹤<br>2. 關閉 Safari App<br>3. 重新開啟 | 追蹤清單保留（Safari 正常模式支援 localStorage） |
| MAN-06 | Android Chrome 追蹤清單行為 | 1. Android Chrome 加入追蹤<br>2. 關閉 App<br>3. 重新開啟 | 追蹤清單保留 |

---

## 5. 測試環境

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

## 6. 缺陷追蹤模板

| 欄位 | 說明 |
|------|------|
| ID | BUG-WC-XXX（WC = Watchlist & Compare） |
| 測試案例 | 對應以上測試編號（F-S01、E2E-01、MAN-01 等） |
| 嚴重程度 | P0（阻擋：追蹤無法寫入/讀取、比價崩溃） / P1（主要：價差計算錯誤、最便宜標示錯誤） / P2（次要：UI 樣式瑕疵、toast 文案不一致） |
| 重複步驟 | 逐步操作 |
| 預期 vs 實際 | 對照 |
| 環境 | OS / Browser / 版本 / localStorage 容量 |

---

## 7. 覆蓋率自我檢查

| BDD Scenario | 測試案例 | 是否覆蓋 |
|--------------|----------|:--------:|
| 從商品列表加入追蹤 | F-W01, F-W02, E2E-01 | ✅ |
| 從不同入口加入追蹤（列表頁） | F-W01, E2E-01 | ✅ |
| 從不同入口加入追蹤（詳情頁） | F-W01, E2E-02 | ✅ |
| 已在追蹤清單的商品不重複加入 | F-W03, E2E-03 | ✅ |
| 從追蹤清單頁移除商品 | F-W06, E2E-04 | ✅ |
| 從列表頁移除已追蹤商品 | F-W06, E2E-05 | ✅ |
| 檢視追蹤清單的價格、價差與迷你趨勢 | F-W10, F-SP01~SP05, E2E-06 | ✅ |
| 價差以「上次查看價格」為基準 | F-W10, E2E-07 | ✅ |
| 迷你趨勢僅顯示最近 7 日歷史 | F-SP01~SP02, E2E-08 | ✅ |
| 拖曳排序追蹤清單 | F-W08~W09, E2E-09 | ✅ |
| 追蹤清單為空時顯示引導 | E2E-10 | ✅ |
| 瀏覽器不支援 localStorage 時加入追蹤失敗 | F-W04, F-S02, E2E-13 | ✅ |
| localStorage 空間已滿時無法新增追蹤 | F-W05, F-S08, E2E-14 | ✅ |
| 追蹤的商品已下架 | E2E-11 | ✅ |
| 迷你趨勢歷史資料不足 | F-SP03~SP05, E2E-12 | ✅ |
| 商品資料載入失敗時追蹤頁顯示錯誤狀態 | E2E-15 | ✅ |
| 從列表勾選同類商品產出比較表並標示最便宜 | F-C04~C10, E2E-16 | ✅ |
| 從不同入口加入比價（列表頁） | F-P01, E2E-16 | ✅ |
| 從不同入口加入比價（詳情頁） | F-P01, E2E-17 | ✅ |
| 比價選取少於 2 件無法開始 | F-P03, E2E-18 | ✅ |
| 比價選取超過 6 件上限 | F-P04, F-P06, E2E-19 | ✅ |
| 比價僅限同分類商品 | F-P05, E2E-20 | ✅ |
| 多件同價商品並列標示最便宜 | F-C08, E2E-21 | ✅ |
| 比較表依分類顯示對應規格欄位 | F-C01~C03, E2E-22 | ✅ |
| 從比價結果表加入追蹤 | F-W01, E2E-23 | ✅ |
| 清除比價選取 | F-P09, E2E-24 | ✅ |
| 比價清單中的商品已下架 | F-C05, F-C09, E2E-25 | ✅ |

**全部 25 個 BDD Scenario 已覆蓋，含 3 個 Scenario Outline 的 5 列 Examples（E2E-02、E2E-17 涵蓋兩入口）。**

---

## 8. storage Mock 策略說明

本功能核心在 localStorage/sessionStorage，以下為 E2E 與 Unit Test 的 Mock 策略差異：

### Unit Test（Vitest + jsdom）

| 策略 | 用法 |
|------|------|
| `vi.mock('@/utils/storage')` | mock 底層 storage 函數，精確控制 `isStorageAvailable` / `readVersioned` / `writeVersioned` 的回傳值，隔離 composable 邏輯 |
| `window.localStorage`（jsdom 原生） | jsdom 預設支援 localStorage，可直接讀寫（無容量限制） |
| `vi.spyOn(Storage.prototype, 'setItem').mockImplementation(...)` | 模擬 `QuotaExceededError`（`throw new DOMException('Quota exceeded', 'QuotaExceededError')`） |
| `vi.spyOn(window, 'localStorage', 'get').mockReturnValue(...)` | 模擬 storage 完全不可用（`isStorageAvailable` 回傳 false） |

### E2E（Playwright）

| 策略 | 用法 |
|------|------|
| `page.evaluate(() => localStorage.setItem(...))` | 注入預設追蹤資料（跳過 UI 操作直接準備測試前置狀態） |
| `page.route('**/api/items/**', ...)` | 模擬 API 回應（商品資料 500、空資料、含 gone 商品的資料） |
| `page.addInitScript(() => { Object.defineProperty(window, 'localStorage', ...) })` | 模擬 localStorage 封鎖（E2E-13） |
| `page.evaluate(() => { for(let i=0; i<...; i++) localStorage.setItem('fill-'+i, '...'.repeat(1000)) })` | 填滿 localStorage 模擬 Quota exceeded（E2E-14） |
| 多瀏覽器 `test.use({ browserName: ... })` | Chromium / Firefox / WebKit 分別測試 localStorage 存活期（E2E-28~E2E-32） |
