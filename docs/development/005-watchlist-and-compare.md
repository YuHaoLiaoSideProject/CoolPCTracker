# 追蹤清單與比價（watchlist-and-compare）— 開發規格

> **對應 Roadmap**：Phase 1（前端 P1）— 技術決策 §4.1 初期任務「追蹤清單（localStorage）+ 比價（多選比較表）」
> **技術決策**：`docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md`
> **操作流程**：`docs/interaction-flows/005-watchlist-and-compare.md`
> **BDD**：`docs/bdds/005-watchlist-and-compare.feature`
> **測試計畫**：待產出（`docs/test-plans/005-watchlist-and-compare測試計畫.md`，由 test-plan-generator 產生）
> **狀態**：設計完成，待開發

---

## 概述

讓訪客免註冊、免後端，在本機瀏覽器維護個人商品追蹤清單（localStorage），並將最多 6 件同類商品並排比價（sessionStorage）、自動標示最便宜。核心包含：

1. **`useWatchlist` composable**：追蹤清單的 localStorage 讀寫、版本化遷移、錯誤處理（不可用／空間滿／資料損毀），與價差快照基準管理。
2. **`useCompare` composable（比價選取）**：比價選取的 sessionStorage 讀寫、同分類檢查、2–6 件上下限管理。
3. **`utils/compare` 純函數模組**：依主分類規劃比較表欄位、建構並排比較表、計算最便宜標示（含同價並列、排除已下架）。
4. **`WatchlistView`**：我的追蹤頁（名稱／現價／價差／迷你趨勢／拖曳排序／空狀態／錯誤狀態）。
5. **`CompareView`**：比價結果頁（規格並排比較表、最便宜標示、加入追蹤、清除比價）。
6. **共用元件**：`WatchlistButton`、`CompareToggle`、`CompareBar`、`Sparkline`，供 003（列表）／004（詳情）整合。

**一句話**：以 localStorage + sessionStorage 在純靜態站上提供「個人價格追蹤」與「購買前同類比價決策」能力，無任何後端改動。

---

## 1. 資料依賴與整合點

### 1.1 資料來源契約（items.json，與 001/003 共用）

本功能不新增任何後端 API，僅**讀取**同 origin 的 `data/items.json`（由 001 爬蟲產生、003 前端基礎負責載入）。本規格用到以下欄位（與技術決策 §3.4 一致）：

```jsonc
// data/items.json（本功能讀取契約，欄位以 001 產出為準）
{
  "meta": { "crawled_at": "2026-08-15T06:00:00Z" },
  "items": [
    {
      "id": "3f9a1c2b8e4d5f6a",   // 主鍵：sha256(主分類 + 正規化名稱) 前 16 位 hex（001 產生），跨日穩定
      "category": "CPU",                  // 主分類：比價同分類檢查依據
      "name": "Intel i5-13600K ...",
      "spec": { "brand": "Intel", "model": "i5-13600K", "cores": 14, /* … */ },
      "status": "in_stock",               // in_stock / gone（下架）
      "history": [ ["2026-08-15", 9990] ]  // compact [d,p] 陣列（001 格式決策）；僅異動時 append
    }
  ]
}
```

- **目前價格** = `history` 最後一筆的 `p`；`status === 'gone'` 時視為無目前價格（顯示「—」）。
- **迷你趨勢** = `history` 尾端 7 筆（不足 2 筆時顯示「資料不足」）。
- ⚠️ 原始 JSON 的 `history` 為 compact 陣列 `["2026-08-15", 9990]`（001 格式決策），`useItems`（003）載入層正規化為 `{ d, p }` 後元件使用（與 003/004 同一契約）。

### 1.2 與 003 / 004 的整合點（預留契約）

本功能**不直接改寫** 003/004 檔案，但定義以下整合契約，供 003/004 開發時嵌入（詳見 §2.7）：

| 整合點 | 提供方 | 消費方 | 契約內容 |
|--------|--------|--------|----------|
| 商品列表每列「加入追蹤」按鈕 | 005：`WatchlistButton.vue` | 003：`ProductCard` / `ProductList` | props: `{ id, price }`；內部以 `useWatchlist` 決定「加入追蹤／已追蹤」狀態 |
| 商品列表每列「加入比價」勾選框 | 005：`CompareToggle.vue` | 003：`ProductCard` | props: `{ id, category }`；達 6 件上限時自動停用 |
| 頁面常駐「已選 N/6」浮動列 | 005：`CompareBar.vue` | 003：Layout（App 層級掛載） | 顯示已選計數、「開始比價」「清除比價」按鈕 |
| 詳情頁「加入追蹤／加入比價」按鈕 | 005：`WatchlistButton` / `CompareToggle` | 004：`ProductDetailView` | 同上，形態改為按鈕（`variant="button"` prop） |
| 導覽列「我的追蹤」入口 | 005：路由 `/watchlist` | 003：Navbar | 連結 + 追蹤數 badge（`useWatchlist().items.length`） |
| 比價結果路由 | 005：路由 `/compare` | 003：`router/index.ts` | `{ path: '/compare', name: 'compare' }` |
| 商品資料共用載入 | 003：`useItems()` | 005：`WatchlistView` / `CompareView` | 005 以 `useItems()` 為契約引用，實作以 003 為準 |

> ⚠️ 003/004 尚未實作前，005 內部先以 **mock 資料源介面**（`useItems()` 假名 + 相容 items.json 結構的 fixture）開發並通過 Vitest 測試，待 003 落地後替換為真實載入。

---

## 2. 前端實作規格

### 2.1 檔案改動總覽

```
web/src/
├── types/
│   └── watchlist.ts                ← 新增：WatchlistItem、WatchlistStorageV1、CompareSelectionItem、StorageError
├── utils/
│   ├── storage.ts                  ← 新增：storage 可用性探測、版本化讀寫、錯誤轉換（unsupported/quota/corrupt）
│   └── compare.ts                  ← 新增：比較表純函數（欄位規劃、buildCompareRows、findCheapestIds）
├── composables/
│   ├── useWatchlist.ts             ← 新增：追蹤清單管理（localStorage + 快照基準）
│   └── useCompare.ts               ← 新增：比價選取管理（sessionStorage + 同分類 + 2–6 上限）
├── components/
│   ├── WatchlistButton.vue         ← 新增：「加入追蹤／已追蹤」切換按鈕（列表/詳情/比價共用）
│   ├── CompareToggle.vue           ← 新增：「加入比價」勾選框/按鈕（列表/詳情共用）
│   ├── CompareBar.vue              ← 新增：已選 N/6 浮動列（開始比價 / 清除比價）
│   └── Sparkline.vue               ← 新增：迷你趨勢 SVG（003 列表卡片亦可共用）
├── views/
│   ├── WatchlistView.vue           ← 新增：我的追蹤頁
│   └── CompareView.vue             ← 新增：比價結果頁
└── router/
    └── index.ts                    ← 修改：新增 /watchlist、/compare 路由
```

### 2.2 資料型別定義（types/watchlist.ts）

```typescript
// web/src/types/watchlist.ts

/** 追蹤清單項目：只存最小資訊，單筆 < 1KB（全站 1,449 件全追蹤仍遠低於 5MB 上限） */
export interface WatchlistItem {
  id: string                    // 商品 id（與 items.json 主鍵一致）
  addedAt: string               // 加入時間（ISO 8601）
  lastPriceSnapshot: number     // 上次查看價格快照（價差基準；加入時以當下價格初始化）
  priceSnapshotAt: string       // 快照時間（ISO 8601）
}

/** localStorage 版本化包裹：key = `coolpc.watchlist.v1` */
export interface WatchlistStorageV1 {
  version: 1
  items: WatchlistItem[]
}

/** 比價選取項目：存於 sessionStorage（關閉分頁即清空） */
export interface CompareSelectionItem {
  id: string                    // 商品 id
  category: string              // 主分類（同分類檢查依據）
  selectedAt: string            // 選取時間（ISO 8601）
}

/** 比價選取版本化包裹：key = `coolpc.compare.v1` */
export interface CompareSelectionStorageV1 {
  version: 1
  items: CompareSelectionItem[]
}

/** storage 錯誤分類（UI 依 kind 顯示對應文案） */
export type StorageErrorKind = 'unsupported' | 'quota-exceeded' | 'corrupt'

export interface StorageError {
  kind: StorageErrorKind
  message: string
}

/** 常數：比價上下限（BDD：最少 2 件、最多 6 件） */
export const MIN_COMPARE = 2
export const MAX_COMPARE = 6
```

### 2.3 utils/storage.ts — storage 讀寫底層

職責：封裝 localStorage/sessionStorage 的**可用性探測**、**版本化讀寫**、**錯誤分類**（BDD 錯誤情境全數由此層捕捉）。UI 不直接觸碰 `window.localStorage`。

```typescript
// web/src/utils/storage.ts
import type { StorageError } from '@/types/watchlist'

export type StorageArea = 'local' | 'session'

/** 探測 storage 是否可用（隱私模式/停用儲存 → false）。探測不污染資料：寫入即刪除測試 key */
export function isStorageAvailable(area: StorageArea): boolean

/** 版本化讀取：版本不符 → 交由呼叫端 migrate；JSON 解析失敗 → corrupt 錯誤 */
export function readVersioned<T>(
  area: StorageArea, key: string, version: number
): { ok: true; value: T | null } | { ok: false; error: StorageError }

/** 版本化寫入：setItem 拋 QuotaExceededError → quota-exceeded 錯誤；storage 不可用 → unsupported */
export function writeVersioned<T>(
  area: StorageArea, key: string, version: number, value: T
): { ok: true } | { ok: false; error: StorageError }

/** 刪除 key（移除追蹤/清除比價） */
export function removeKey(area: StorageArea, key: string): void

/** 損毀自癒：將無法解析的原值備份到 `{key}.corrupt-{ts}` 後刪除原 key（保留現場、不當機） */
export function quarantineCorrupt(area: StorageArea, key: string, raw: string): void
```

### 2.4 composables/useWatchlist.ts — 追蹤清單管理

職責：追蹤清單的單一資料來源（模組級單例 state，列表/詳情/追蹤頁共用同一份 reactive 清單）、localStorage 持久化、價差快照基準管理。return 介面供所有呼叫端使用。

```typescript
// web/src/composables/useWatchlist.ts
import { computed, ref, type Ref } from 'vue'
import { isStorageAvailable, readVersioned, writeVersioned, type StorageError } from '@/utils/storage'
import type { WatchlistItem } from '@/types/watchlist'

const STORAGE_KEY = 'coolpc.watchlist'
const STORAGE_VERSION = 1

export type AddResult =
  | { ok: true }
  | { ok: false; reason: 'already-tracked' }              // 重複加入：不寫入（BDD 不重複新增）
  | { ok: false; reason: 'storage-unavailable' }          // → 「瀏覽器未開放本機儲存，無法使用追蹤功能」
  | { ok: false; reason: 'quota-exceeded' }               // → 「儲存空間已滿，無法新增追蹤項目」

export function useWatchlist(): {
  items: Ref<WatchlistItem[]>              // 依使用者排序的追蹤項目
  isTracked: (id: string) => boolean
  add: (id: string, currentPrice: number) => AddResult
  remove: (id: string) => void
  reorder: (orderedIds: string[]) => void
  updatePriceSnapshot: (id: string, price: number) => void
  error: Ref<StorageError | null>          // unsupported / quota-exceeded / corrupt
  clearError: () => void
} {
  const items = ref<WatchlistItem[]>([])
  const error = ref<StorageError | null>(null)

  // hydrate()：首次載入時
  //   1. isStorageAvailable('local') === false → error.unsupported，items 保持空
  //   2. readVersioned → JSON 解析失敗 → quarantineCorrupt 備份後重置為空（自癒）
  //   3. version !== 1 → 預留 migrate 掛鉤（目前無舊版，直接重置）
  //   4. 逐筆驗證 shape（id/addedAt/快照為有效型別）→ 無效項目略過
  function hydrate(): void { /* … */ }

  function isTracked(id: string): boolean { /* items 內含該 id */ }

  // add()：
  //   1. isTracked → 回傳 already-tracked（不寫入、不產生重複）
  //   2. 先以 { id, addedAt: now, lastPriceSnapshot: currentPrice } 更新本機 ref
  //   3. writeVersioned 失敗（quota/unavailable）→ rollback ref，回傳對應錯誤
  function add(id: string, currentPrice: number): AddResult { /* … */ }

  // remove()：本機 ref 移除 + writeVersioned（寫入失敗亦接受：移除屬安全方向，僅吞錯誤）
  function remove(id: string): void { /* … */ }

  // reorder()：以 orderedIds 重排本機 ref + 寫回（拖曳排序後刷新維持；BDD：僅本機有效）
  function reorder(orderedIds: string[]): void { /* … */ }

  // updatePriceSnapshot()：以目前價格更新「上次查看快照」並寫回 → 下次價差基準
  //   呼叫時機：① add（以加入當下價初始化）② 開啟 WatchlistView 時（對所有 in_stock 商品）
  function updatePriceSnapshot(id: string, price: number): void { /* … */ }

  hydrate()
  return { items, isTracked, add, remove, reorder, updatePriceSnapshot, error, clearError }
}
```

**價差基準規則**（BDD @business-rules「價差以『上次查看價格』為基準」）：
- 首次加入：`lastPriceSnapshot = 加入當下價格`。
- 每次開啟「我的追蹤」頁：對每個 `in_stock` 商品以目前價格 `updatePriceSnapshot` 並寫回 localStorage，**顯示完價差後才更新**（當次畫面仍顯示「現價 − 上次快照」，下次開啟以此為新基準）。
- 在列表／詳情頁點「加入追蹤」按鈕**不**更新快照（維持「上次查看」語意）。

### 2.5 composables/useCompare.ts — 比價選取管理

職責：比價選取清單的單一資料來源（sessionStorage，同分頁跨路由保留、關閉分頁清空）、同分類檢查、2–6 件上下限。

```typescript
// web/src/composables/useCompare.ts
import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { isStorageAvailable, readVersioned, writeVersioned } from '@/utils/storage'
import { MAX_COMPARE, MIN_COMPARE, type CompareSelectionItem } from '@/types/watchlist'

const STORAGE_KEY = 'coolpc.compare'
const STORAGE_VERSION = 1

export type CompareAddResult =
  | { ok: true }
  | { ok: false; reason: 'different-category'; message: '比價僅限同類商品' }  // BDD 跨分類拒絕
  | { ok: false; reason: 'max-6'; message: '最多只能比較 6 件商品' }           // BDD 6 件上限
  | { ok: false; reason: 'already-selected' }
  | { ok: false; reason: 'storage-unavailable' }

export function useCompare(): {
  selected: Ref<CompareSelectionItem[]>
  category: ComputedRef<string | null>     // 已選商品的主分類（空選取為 null）；同分類檢查基準
  count: ComputedRef<number>
  isFull: ComputedRef<boolean>             // count === 6 → 列表其餘勾選框停用
  canStart: ComputedRef<boolean>           // MIN ≤ count ≤ MAX → 「開始比價」可用
  add: (item: { id: string; category: string }) => CompareAddResult
  remove: (id: string) => void
  toggle: (item: { id: string; category: string }) => CompareAddResult | { ok: true; removed: true }
  clear: () => void
  isSelected: (id: string) => boolean
} {
  const selected = ref<CompareSelectionItem[]>([])

  // hydrate()：sessionStorage 讀取 + 版本化驗證（corrupt → 備份後重置）
  // 生命週期：同分頁跨路由保留；關閉分頁 sessionStorage 自動清空（無需額外清理）

  // add()：
  //   1. 已選達 MAX_COMPARE → max-6（原選取不受影響）
  //   2. selected 非空且 category 與第一筆不同 → different-category（拒絕加入）
  //   3. 更新 ref + writeVersioned（失敗 → rollback + storage-unavailable）
  function add(item: { id: string; category: string }): CompareAddResult { /* … */ }

  function remove(id: string): void { /* … */ }
  function clear(): void { /* 清空 ref + removeKey(session) */ }
  function isSelected(id: string): boolean { /* … */ }

  return { selected, category, count, isFull, canStart, add, remove, toggle, clear, isSelected }
}
```

### 2.6 utils/compare.ts — 比較表純函數

職責：把「已選商品 × items.json」合併後的輸入轉成比較表；所有邏輯為純函數，便於 Vitest 單元測試（對應 BDD 比較表場景）。

```typescript
// web/src/utils/compare.ts

/** 比較表輸入：由呼叫端（CompareView）依 selected + items.json 解析 */
export interface CompareItem {
  id: string
  name: string
  category: string
  price: number | null          // status === 'gone' → null（無目前價格）
  status: 'in_stock' | 'gone'
  spec: Record<string, string | number | null>
}

/** 比較表一列：第一欄為欄位名稱，其餘各欄並排對應商品值（缺值 → 「—」） */
export interface CompareRow {
  key: string
  label: string
  values: Array<string | null>
}

/** 依主分類回傳比較欄位：深解析分類多欄，輕量分類僅基礎欄位 */
//   CPU：品牌/型號/核心數/執行緒/基礎時脈/超頻時脈/TDP/腳位
//   顯示卡：品牌/型號/VRAM/晶片/TDP 等
//   記憶體：品牌/型號/容量/頻率/時序
//   SSD/HDD：品牌/型號/容量/介面/速度
//   套裝/準系統/劈發價組合區/記憶卡：品牌/型號（輕量）
//   ⚠️ 確切欄位以 001 spec_parser 產出的 spec key 為準，本表為基準規劃（不存在的 key 自動略過）
export function specColumnsFor(category: string): Array<{ key: string; label: string }>

/** 建構比較表：首列「目前價格」，接著規格欄位；價格格式化為 NT$ 千分位 */
export function buildCompareRows(items: CompareItem[]): CompareRow[]

/** 最便宜商品 id 集合：僅在 price !== null（in_stock）中取最低價；同價時全部並列回傳 */
export function findCheapestIds(items: CompareItem[]): string[]
```

### 2.7 共用元件（components/）

| 元件 | props | 行為 |
|------|-------|------|
| `WatchlistButton.vue` | `id: string`, `price: number \| null` | 依 `isTracked(id)` 顯示「加入追蹤／已追蹤」；點擊切換；success/錯誤 toast（文案見 §6） |
| `CompareToggle.vue` | `id: string`, `category: string`, `variant?: 'checkbox' \| 'button'` | 列表用勾選框、詳情頁用按鈕；`isFull && !checked` 時 disabled（BDD 第 7 件無法勾選） |
| `CompareBar.vue` | —（內部用 `useCompare`） | 頁面底部/頂部浮動列：已選 N/6 計數、「開始比價」（`canStart` 為 false 時停用並提示「請至少選擇 2 件商品進行比價」）、「清除比價」 |
| `Sparkline.vue` | `points: Array<{ d: string; p: number }>` | 迷你趨勢 SVG（無需 ECharts）；由父層決定 7 日截取與「資料不足」判斷 |

### 2.8 views/WatchlistView.vue — 我的追蹤頁

資料流：`useWatchlist().items`（localStorage）＋ `useItems()`（items.json）→ 合併為列資料（名稱／現價／價差／迷你趨勢／下架狀態）。

```vue
<script setup lang="ts">
// web/src/views/WatchlistView.vue
import { computed, onMounted } from 'vue'
import { useWatchlist } from '@/composables/useWatchlist'
import { useItems } from '@/composables/useItems'        // ← 003 契約：共用資料載入（items/meta/loading/error/retry/isStale）
import Sparkline from '@/components/Sparkline.vue'

interface WatchRow {
  id: string
  name: string
  price: number | null               // gone → null（顯示「—」）
  diff: number | null                // 現價 − lastPriceSnapshot；gone → null
  history7: Array<{ d: string; p: number }>   // 最近 7 日（不足 2 日 → 顯示「資料不足」）
  status: 'in_stock' | 'gone'
}

const { items, remove, reorder, updatePriceSnapshot, error: storageError, clearError } = useWatchlist()
const { items: productItems, loading, error: loadError, retry: reload } = useItems()   // ← 003 契約：items/meta/loading/error/retry/isStale

// 合併 localStorage 追蹤項目 × items.json：
//   - 商品存在且 in_stock → 取 history 末筆為現價，diff = price − lastPriceSnapshot
//   - 商品不存在或 gone    → 標示「已下架」，price = null、diff = null（不自動清除，供手動移除）
const rows = computed<WatchRow[]>(() => { /* … */ })
const isEmpty = computed(() => rows.value.length === 0)

onMounted(() => {
  // 價差基準更新：顯示前先用「上次快照」計算價差；顯示後對 in_stock 商品
  // updatePriceSnapshot(id, price) 以現價更新快照並寫回 localStorage（下次為新基準）
  // （實作：渲染完成後執行；若 storage 錯誤則忽略，不影響畫面）
})
</script>

<template>
  <!-- 三種狀態：loadError → 「資料載入失敗」+ 重新載入（BDD @error-handling）
       isEmpty   → 空狀態說明 + 「去逛逛」按鈕（導向分類頁）（BDD @edge-case）
       正常      → 追蹤清單列（可拖曳排序、移除、點擊進詳情） -->
</template>
```

**排序**：採用 HTML5 drag & drop（拖曳把手），鬆手後 `reorder(orderedIds)` 寫回 localStorage（刷新維持；僅本機有效）。

### 2.9 views/CompareView.vue — 比價結果頁

資料流：`useCompare().selected`（sessionStorage）＋ `useItems()` → 解析 `CompareItem[]` → `buildCompareRows` / `findCheapestIds`。

```vue
<script setup lang="ts">
// web/src/views/CompareView.vue
import { computed } from 'vue'
import { useCompare } from '@/composables/useCompare'
import { buildCompareRows, findCheapestIds, type CompareItem } from '@/utils/compare'
import WatchlistButton from '@/components/WatchlistButton.vue'

const { selected, count, clear } = useCompare()
const { items: productItems, loading, error: loadError, retry: reload } = useItems()   // ← 003 契約：items/meta/loading/error/retry/isStale

// 依 selected 解析商品：命中 items.json 且 in_stock → price = 末筆歷史價；
// 下架/不存在 → status='gone'、price=null（比較表該欄標示「已下架」）
const compareItems = computed<CompareItem[]>(() => { /* … */ })

// 比較表：第一欄欄位名稱，其餘各欄並排商品；缺值顯示「—」
const rows = computed(() => buildCompareRows(compareItems.value))
// 最便宜：排除 gone（price===null）後取最低價；同價全部回傳 → 並列標示「最便宜」
const cheapestIds = computed(() => findCheapestIds(compareItems.value))

// 直接以 URL 進入且選取不合法（<2 或 >6）：顯示提示與「返回列表」連結，不渲染表格
const isInvalidSelection = computed(() => count.value < 2 || count.value > 6)

function onClearCompare(): void {
  clear()
  // 返回來源頁（router.back()）；history 無來源時導向列表首頁
}
</script>

<template>
  <!-- 表格：<table class="compare-table"> 首列為「目前價格」+ 規格欄位
       thead 商品名 sticky；每欄商品：最便宜 → 標「最便宜」badge、gone → 「已下架」
       每欄含 WatchlistButton（加入追蹤）與「前往詳情」連結
       頂部：「清除比價」按鈕 -->
</template>
```

### 2.10 路由（router/index.ts 修改）

```typescript
// web/src/router/index.ts（修改，新增兩條路由）
{ path: '/watchlist', name: 'watchlist', component: () => import('@/views/WatchlistView.vue') },
{ path: '/compare', name: 'compare', component: () => import('@/views/CompareView.vue') },
```

---

## 3. 資料合約（Data Contract）

> 本功能**純前端、無後端**，故以資料合約取代 API 合約（§3 per SKILL 模板）。無任何新增 endpoint。

| 儲存層 | Key | 內容 | 生命週期 | 用途 |
|--------|-----|------|----------|------|
| localStorage | `coolpc.watchlist.v1` | `{ version: 1, items: WatchlistItem[] }` | 永久（單瀏覽器、本機專屬，不跨裝置/不雲端同步；清除瀏覽器資料即遺失） | 追蹤清單 |
| sessionStorage | `coolpc.compare.v1` | `{ version: 1, items: CompareSelectionItem[] }` | 同分頁跨路由保留；關閉分頁即清空 | 比價選取 |
| fetch（同 origin） | `data/items.json` | 見 §1.1 讀取契約 | 每日爬蟲更新 | 商品資料（003 共用載入） |

- **版本化規則**：key 內含 `.v{n}` 前綴 + payload 內含 `version` 欄位；讀取時版本不符 → 走 migrate 掛鉤（目前無舊版）。**v0 相容**：若偵測到無版本包裹的舊格式（純 id 陣列，即 IF §1 所述 key `coolpc.watchlist`），自動遷移為 v1（`addedAt=now`、快照補 `null` → 首次開頁補快照）。實際 storage key 由 `writeVersioned` 以 `${key}.v${version}` 組合（`coolpc.watchlist.v1` / `coolpc.compare.v1`，與上表一致）。
- **損毀自癒**：JSON 解析失敗 → 原值備份至 `coolpc.watchlist.corrupt-{ts}` 後重置為空，頁面不當機。

---

## 4. 資料流

```
data/items.json ──fetch──▶ useItems()（003）──▶ WatchlistView / CompareView
                                                    ▲
localStorage   ◀──read/write── useWatchlist ──▶ 列表/詳情按鈕（WatchlistButton）
(coolpc.watchlist.v1)                              │
                                                    └─▶ WatchlistView（價差/迷你趨勢）
sessionStorage ◀──read/write── useCompare ──▶ 勾選框/浮動列（CompareToggle/CompareBar）
(coolpc.compare.v1)                              │
                                                    └─▶ CompareView（比較表）
```

**主流程 B 順序**：勾選 → `useCompare.add`（同分類檢查＋上限）→ sessionStorage 寫入 → `CompareBar` 顯示 N/6 → 點「開始比價」（`canStart` 校驗）→ 路由 `/compare` → `CompareView` 解析商品 → `buildCompareRows` 並排 + `findCheapestIds` 標最便宜。

**主流程 A 順序**：點「加入追蹤」→ `useWatchlist.add`（去重＋錯誤處理）→ localStorage 寫入 → 各入口按鈕狀態即時反映 → 開啟 `/watchlist` → 合併 items.json → 顯示價差（現價 − 快照）→ 渲染完更新快照基準。

---

## 5. 儲存生命週期

| 事件 | useWatchlist | useCompare |
|------|--------------|------------|
| 頁面載入 | `hydrate()` 從 localStorage 讀取 | `hydrate()` 從 sessionStorage 讀取 |
| 跨路由（SPA 內） | 模組級單例 state 保留 | 模組級單例 state 保留 |
| 重新整理分頁 | 重新 hydrate，資料不變 | 重新 hydrate，資料不變 |
| 關閉分頁／分頁 | localStorage 保留（本機永久） | sessionStorage 清空 |
| 清除瀏覽器資料 | 遺失（本機專屬限制） | 遺失（預期行為） |
| 資料損毀 | corrupt 錯誤 → 備份後重置，不當機 | 同上 |

---

## 6. 邊界條件處理

### 6.1 追蹤清單

| # | 情境 | BDD 來源 | 處理機制 | 使用者回饋 |
|---|------|----------|----------|------------|
| 1 | 重複加入已在清單的商品 | @business-rules「已在追蹤清單的商品不重複加入」 | `useWatchlist.add` 先 `isTracked` 檢查 → 回傳 `already-tracked`，**不寫入** | 按鈕維持「已追蹤」；toast「該商品已在追蹤清單」；清單僅 1 筆 |
| 2 | 瀏覽器不支援／封鎖 localStorage | @error-handling「瀏覽器不支援 localStorage 時加入追蹤失敗」 | `isStorageAvailable('local') === false` → `error = unsupported`；add 回傳 `storage-unavailable`，不寫入任何資料 | 「瀏覽器未開放本機儲存，無法使用追蹤功能」；頁面不當機 |
| 3 | localStorage 空間已滿（寫入失敗） | @error-handling「localStorage 空間已滿時無法新增追蹤」 | `writeVersioned` 捕捉 `QuotaExceededError` → `error = quota-exceeded`；add **先更新 ref 後寫入，失敗 rollback**（UI 與 storage 一致） | 「儲存空間已滿，無法新增追蹤項目」；原有清單不受影響 |
| 4 | 追蹤商品已下架（不在當日 items.json 或 status=gone） | @edge-case「追蹤的商品已下架」 | 合併時商品不存在/gone → `price=null`、`diff=null`；**不自動清除**，供手動移除 | 標示「已下架」；價格欄顯示「—」 |
| 5 | 迷你趨勢歷史不足 2 日 | @edge-case「迷你趨勢歷史資料不足」 | `history.length < 2` → 不渲染 Sparkline | 顯示「資料不足」 |
| 6 | 迷你趨勢僅顯示最近 7 日 | @business-rules「迷你趨勢僅顯示最近 7 日歷史」 | 截取 `history` 尾端 7 筆（`history.slice(-7)`） | 圖表僅含 7 日資料 |
| 7 | 價差基準 | @business-rules「價差以『上次查看價格』為基準」 | `diff = 現價 − lastPriceSnapshot`；開頁渲染後以現價更新快照並寫回 | 漲：`+500 元` 漲價樣式；跌：`-500 元` 跌價樣式；持平：灰 |
| 8 | 追蹤清單為空 | @edge-case「追蹤清單為空時顯示引導」 | `rows.length === 0` → 空狀態 | 空狀態說明 +「去逛逛」按鈕（導向分類頁）；不顯示任何商品列 |
| 9 | 商品資料載入失敗 | @error-handling「商品資料載入失敗時追蹤頁顯示錯誤狀態」 | `error`（003 useItems 提供）→ 錯誤區塊 | 「資料載入失敗」+「重新載入」按鈕；localStorage 追蹤資料不受影響 |
| 10 | 移除商品 | @happy-path「從追蹤清單頁移除」「從列表頁移除」 | `remove(id)`：ref 移除 + 寫回 | 按鈕變回「加入追蹤」；剩餘商品維持原順序；刷新後仍為移除狀態 |
| 11 | 拖曳排序 | @happy-path「拖曳排序追蹤清單」 | `reorder(orderedIds)` 寫回 localStorage | 即時重排；刷新維持；僅本機有效 |

### 6.2 比價

| # | 情境 | BDD 來源 | 處理機制 | 使用者回饋 |
|---|------|----------|----------|------------|
| 12 | 選取少於 2 件 | @edge-case「比價選取少於 2 件無法開始」 | `canStart = count ≥ MIN_COMPARE`；按鈕 `disabled` | 「開始比價」維持停用；提示「請至少選擇 2 件商品進行比價」 |
| 13 | 選取超過 6 件上限 | @edge-case「比價選取超過 6 件上限」 | `add()` 檢查 `count ≥ MAX_COMPARE` → 拒絕；`isFull` 使其餘勾選框停用 | 第 7 件無法勾選；提示「最多只能比較 6 件商品」；已選 6 件不受影響 |
| 14 | 跨分類勾選 | @business-rules「比價僅限同分類商品」 | `add()` 比對 `category`（第一筆為基準）不同 → 拒絕 | 提示「比價僅限同類商品」；勾選框回未勾選；原選取不受影響 |
| 15 | 多件同價 | @business-rules「多件同價商品並列標示最便宜」 | `findCheapestIds` 回傳**全部**達最低價的 id | 同價商品皆標示「最便宜」 |
| 16 | 比較表欄位依分類 | @business-rules「比較表依分類顯示對應規格欄位」 | `specColumnsFor(category)`：CPU 顯示核心數/執行緒/基礎時脈/超頻時脈/TDP 等；輕量分類僅基礎欄位 | 第一欄欄位名稱，各商品數值並排於對應欄位 |
| 17 | 比價清單含已下架商品 | @edge-case「比價清單中的商品已下架」 | 解析時 `status='gone'` → `price=null`；`findCheapestIds` **排除** `price===null` | 該欄標示「已下架」；最便宜僅在仍有價格的商品上計算 |
| 18 | 直接以 URL 進入比價頁且選取不合法 | （IF 異常衍生；比價結果頁防護） | `isInvalidSelection`（<2 或 >6）→ 不渲染表格 | 顯示提示與「返回列表」連結 |
| 19 | sessionStorage 不可用 | （IF §5 異常 1 的比價對應） | `isStorageAvailable('session') === false` → add 回傳 `storage-unavailable` | 提示本機儲存不可用，無法使用比價功能；頁面不當機 |
| 20 | 清除比價 | @happy-path「清除比價選取」 | `clear()` 清空 ref + 刪 sessionStorage key | 選取清空、勾選框回未勾選、返回來源頁 |
| 21 | 比價選取跨頁面瀏覽 | @happy-path「從不同入口加入比價」+ IF §6 生命週期 | sessionStorage 同分頁跨路由保留 | 列表 → 詳情 → 列表勾選狀態維持；關分頁即清空 |

### 6.3 BDD Scenario 完整對照表（覆蓋確認）

| BDD Scenario | 對應章節 |
|--------------|----------|
| 從商品列表加入追蹤（@smoke @happy-path） | §2.7 WatchlistButton、§2.4 add |
| 從不同入口加入追蹤（@happy-path） | §2.7 WatchlistButton（列表/詳情共用） |
| 已在追蹤清單的商品不重複加入（@business-rules） | §6.1 #1 |
| 從追蹤清單頁移除商品（@smoke @happy-path） | §6.1 #10 |
| 從列表頁移除已追蹤商品（@happy-path） | §6.1 #10、§2.7 |
| 檢視追蹤清單的價格、價差與迷你趨勢（@happy-path） | §2.8 WatchlistView |
| 價差以「上次查看價格」為基準（@business-rules） | §6.1 #7 |
| 迷你趨勢僅顯示最近 7 日歷史（@business-rules） | §6.1 #6 |
| 拖曳排序追蹤清單（@happy-path） | §6.1 #11 |
| 追蹤清單為空時顯示引導（@edge-case） | §6.1 #8 |
| 瀏覽器不支援 localStorage 時加入追蹤失敗（@error-handling） | §6.1 #2 |
| localStorage 空間已滿時無法新增追蹤（@error-handling） | §6.1 #3 |
| 追蹤的商品已下架（@edge-case） | §6.1 #4 |
| 迷你趨勢歷史資料不足（@edge-case） | §6.1 #5 |
| 商品資料載入失敗時追蹤頁顯示錯誤狀態（@error-handling） | §6.1 #9 |
| 從列表勾選同類商品產出比較表並標示最便宜（@smoke @happy-path） | §2.6、§2.9 |
| 從不同入口加入比價（@happy-path） | §2.7 CompareToggle、§6.2 #21 |
| 比價選取少於 2 件無法開始（@edge-case） | §6.2 #12 |
| 比價選取超過 6 件上限（@edge-case） | §6.2 #13 |
| 比價僅限同分類商品（@business-rules） | §6.2 #14 |
| 多件同價商品並列標示最便宜（@business-rules） | §6.2 #15 |
| 比較表依分類顯示對應規格欄位（@business-rules） | §6.2 #16 |
| 從比價結果表加入追蹤（@happy-path） | §2.9 CompareView 內 WatchlistButton |
| 清除比價選取（@happy-path） | §6.2 #20 |
| 比價清單中的商品已下架（@edge-case） | §6.2 #17 |

---

## 7. CSS 關鍵樣式

> 採用 CSS 變數（`--color-*`）統一 token；下列為關鍵樣式骨架，class 命名與 §2.8/§2.9 skeleton 中的 binding 一致。完整樣式待 uiux-design-doc-generator 或實作時補齊。

```css
/* ── 追蹤清單卡片 ─────────────────────────────── */
.watchlist-card {
  display: grid;
  grid-template-columns: 1fr auto auto auto auto;  /* 名稱 | 現價 | 價差 | 迷你趨勢 | 動作 */
  gap: 12px; align-items: center;
  padding: 12px 16px; border: 1px solid var(--color-border);
  border-radius: 10px; background: var(--color-surface);
}
.watchlist-card.is-gone .item-name { color: var(--color-muted); text-decoration: line-through; }
.watchlist-card.is-gone .item-price { color: var(--color-muted); }   /* 顯示「—」 */
.price-up   { color: var(--color-up, #d33); }        /* 漲價（紅） */
.price-down { color: var(--color-down, #2a7d32); }  /* 跌價（綠） */
.price-flat { color: var(--color-muted, #888); }    /* 持平（灰） */
.drag-handle { cursor: grab; touch-action: none; }
.watchlist-card.dragging { opacity: .55; }
.watchlist-card.drop-target { outline: 2px dashed var(--color-accent); }

/* ── 比價表：sticky 表頭 + 首欄凍結 ───────────── */
.compare-scroll { overflow-x: auto; }               /* RWD 橫向捲動容器 */
.compare-table { border-collapse: separate; border-spacing: 0; min-width: 720px; }
.compare-table thead th {
  position: sticky; top: 0; z-index: 2;             /* 表頭滾動時固定 */
  background: var(--color-surface-2, #f6f7f9);
  border-bottom: 2px solid var(--color-border);
}
.compare-table th.row-label {
  position: sticky; left: 0; z-index: 3;            /* 首欄欄位名稱橫向凍結 */
  background: var(--color-surface-2, #f6f7f9);
  text-align: left; min-width: 120px;
}
.compare-table td, .compare-table th { padding: 10px 14px; border-bottom: 1px solid var(--color-border); }
.compare-table .cell-gone { color: var(--color-muted); }          /* 「已下架」欄 */
.compare-table .cell-price { font-weight: 600; font-variant-numeric: tabular-nums; }

/* ── 最便宜標示（含同價並列） ─────────────────── */
.cheapest-badge {
  display: inline-block; padding: 2px 8px; border-radius: 999px;
  background: var(--color-down, #2a7d32); color: #fff; font-size: 12px;
}

/* ── 浮動比價列（CompareBar） ─────────────────── */
.compare-bar {
  position: sticky; bottom: 0; z-index: 10;
  display: flex; gap: 12px; align-items: center; justify-content: center;
  padding: 10px 16px; background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  box-shadow: 0 -4px 12px rgb(0 0 0 / .06);
}
.compare-bar .start-btn:disabled { opacity: .5; cursor: not-allowed; }

/* ── Toast 提示 ───────────────────────────────── */
.toast { animation: toast-in .2s ease-out; }
@keyframes toast-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

/* ── RWD ──────────────────────────────────────── */
@media (max-width: 768px) {
  .watchlist-card {
    grid-template-columns: 1fr auto auto;           /* 名稱 | 價差+價格 | 動作；趨勢移至第二列 */
    grid-template-rows: auto auto;
  }
  /* 比較表維持並排（比較是核心價值，不降級為堆疊），以 .compare-scroll 橫向捲動 + 首欄凍結輔助 */
  .compare-table { min-width: 560px; }
  .compare-bar { flex-wrap: wrap; }
}
```

---

## 8. 開發順序（DAG）

```
            ┌──────────────┐
            │ ① 型別 +     │
            │   utils/storage│
            └──────┬───────┘
         ┌─────────┼─────────┐
         ▼         ▼         ▼
   ┌──────────┐ ┌────────┐ ┌────────┐
   │ ② utils/ │ │③ useWatch│ │④ useCompare│
   │ compare  │ │ list   │ │        │
   └────┬─────┘ └───┬────┘ └───┬────┘
        │      ┌────┴────┐     │
        │      ▼         ▼     │
        │  ⑤ 共用元件（WatchlistButton/CompareToggle/CompareBar/Sparkline）
        │      │         │     │
        ▼      ▼         ▼     ▼
   ┌────────┐ ┌────────────┐ ┌────────┐
   │⑥ Watch │ │ ⑦ Compare │
   │ listView│ │ View       │
   └────┬───┘ └─────┬──────┘
        └─────┬─────┘
              ▼
        ⑧ 路由 + 導覽列「我的追蹤」+ App 掛載 CompareBar
              │
              ▼
        ⑨ 003/004 整合（列表列按鈕/勾選、詳情頁按鈕）※ 外部依賴 003/004 檔案
              │
              ▼
        ⑩ E2E / 驗收測試（Playwright）
```

| 步驟 | 內容 | 依賴 | 驗收門檻 |
|------|------|------|----------|
| 1 | `types/watchlist.ts`（WatchlistItem／WatchlistStorageV1／CompareSelectionItem／StorageError／MIN/MAX）＋ `utils/storage.ts`（可用性探測、版本化讀寫、corrupt 備份） | - | Vitest：探測/讀寫/Quota 錯誤轉換通過 |
| 2 | `utils/compare.ts`（specColumnsFor／buildCompareRows／findCheapestIds）＋ 單元測試 | #1 | Vitest：同價並列、排除 gone、欄位依分類通過（對應 BDD #15/16/17） |
| 3 | `composables/useWatchlist.ts`（hydrate／add 去重／remove／reorder／updatePriceSnapshot／錯誤處理）＋ 測試（mock localStorage） | #1 | Vitest：重複加入、quota rollback、corrupt 自癒通過（BDD #1/2/3/7/11） |
| 4 | `composables/useCompare.ts`（sessionStorage／同分類檢查／2–6 上限）＋ 測試 | #1 | Vitest：跨分類拒絕、7 件拒絕、canStart 邏輯通過（BDD #12/13/14） |
| 5 | 共用元件：`Sparkline.vue`（7 日截取、資料不足）、`WatchlistButton.vue`、`CompareToggle.vue`、`CompareBar.vue`（N/6、開始比價停用、清除） | #3, #4 | 元件於 Storybook/臨時頁可操作；狀態切換正確 |
| 6 | `WatchlistView.vue`（合併列、價差樣式、迷你趨勢、拖曳排序、空狀態、載入失敗/重新載入、開頁更新快照） | #3, #5 | 手動驗證 BDD 追蹤清單全場景（§6.1） |
| 7 | `CompareView.vue`（比較表渲染、sticky 表頭、最便宜/同價並列/已下架標示、加入追蹤、清除返回、URL 直入防護） | #2, #4, #5 | 手動驗證 BDD 比價全場景（§6.2） |
| 8 | 路由 `/watchlist`、`/compare`；導覽列「我的追蹤」入口 + 追蹤數 badge；App 層掛載 `CompareBar` | #6, #7 | 兩頁面可經路由進入；跨路由比價選取保留 |
| 9 | 003/004 整合：列表列嵌入 WatchlistButton/CompareToggle、詳情頁按鈕、列表頁計數列（待 003/004 檔案就緒後接線；整合點契約見 §1.2） | #5, #8 | 003/004 的列表與詳情頁出現追蹤/比價操作且狀態即時同步 |
| 10 | E2E：Playwright 覆蓋 BDD 標註 @smoke 場景（列表加入追蹤、移除、比價結果與最便宜標示）+ 關鍵 edge case（localStorage 封鎖、7 件上限、跨分類） | #8, #9 | 全部 @smoke 場景綠 |

> 依賴為 DAG、無循環：後端/資料層不存在（純前端），故基礎順序為「型別 → 純函數/composable → 元件 → 頁面 → 路由 → 跨功能整合 → E2E」。步驟 9 需 003/004 檔案存在，屬外部排程依賴；若 003/004 尚未合併，005 以 §1.2 契約 + fixture 先行驗證，合併時僅接線。

---

## 9. 基礎架構設定

**不適用**：本功能為純前端靜態站改動（GitHub Pages 部署不變、無 Nginx/systemd/環境變數新增）。無新設定。
