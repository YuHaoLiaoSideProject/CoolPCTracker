# frontend-listing-search — 開發規格

> **對應 Roadmap**：Phase 1（P1 前端骨架、搜尋與篩選）— 對應 `docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md` §4.1 行動計畫 P1「前端骨架：Vue + Vite + 資料載入 + 分類頁 + 商品列表」與「搜尋與篩選（全文 + spec 篩選，如 VRAM≥12G）」
> **技術決策**：`docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md`
> **操作流程**：`docs/interaction-flows/003-frontend-listing-search.md`
> **BDD**：`docs/bdds/003-frontend-listing-search.feature`
> **測試計畫**：（尚未產出，可由 test-plan-generator 追溯產生）
> **狀態**：設計完成，待開發

---

## 概述

提供公開訪客以「9 大分類瀏覽、全文搜尋、結構化規格篩選」三種方式收斂 1,449 筆追蹤商品，並以商品卡片一眼掌握目前價格、昨日漲跌與迷你趨勢。**本功能為純前端**（無後端 API、無 WebSocket），唯一外部依賴為同 origin 的資料 API（契約 v2 分類拆檔：`api/index.json`（categories[]）＋ `api/items/{g}.json` 每分類一檔靜態檔案，crawler 產出 `data/items/{g}.json` 後由 002 鏡像組裝；分類檔每筆 history 僅 ≤2 點）。核心包含：

1. **`useItems`（資料載入 composable）**：runtime 讀 `api/index.json`（categories[]＋crawled_at）→依側欄 lazy 載入對應分類檔 `api/items/{g}.json?v={crawled_at}`；`loadAll` 聚合全部分類供全站搜尋／詳情 deep link／追蹤；解析驗證、錯誤分類（載入失敗／格式錯誤）、重試、資料過期判定。
2. **`useFilters`（篩選狀態 composable）**：搜尋關鍵字、規格條件（AND 組合）、目前分類三態狀態機與過濾運算（純函數、可測試）。
3. **`CategorySidebar`**：固定 9 大分類側欄（含深層連結 `?category=<key>` 雙向同步）。
4. **`ProductList` / `ProductCard`**：商品卡片（名稱、規格 chips、目前價、昨日漲跌、sparkline），並預留 004 詳情頁／005 追蹤／005 比價之 props 與事件入口。
5. **`SpecFilterPanel` + `specFilter` 工具**：規格門檻解析（`VRAM≥12G` → 結構化條件）、「≥ 大於等於」語意、AND 交集比對、規格 key 對照。
6. **`EmptyState` / `ErrorState` / `Sparkline`**：空狀態分流（搜尋／篩選／空分類）、載入錯誤與重試、SVG 迷你趨勢。

**整合點**：卡片「開啟詳情」事件對接 004（router 導航）；「加入追蹤」按鈕與「比價勾選」以 props/事件預留，005 實作時僅接線 store 即可，本功能不改列表元件。

---

## 2. 前端實作規格

### 2.1 檔案改動總覽

綠地專案，全部為**新增**檔案（`data/` 目錄由爬蟲 001 產出、002 部署，本功能不負責寫入）：

```
web/
├── vite.config.ts                       ← 新增：base 依 repo name（GitHub Pages）
├── src/
│   ├── main.ts                          ← 新增：createApp + router 掛載
│   ├── App.vue                          ← 新增：全站外框（頂部 header + <router-view>）
│   ├── router/index.ts                  ← 新增：`/` → ListingView；建議 createWebHashHistory
│   ├── types/
│   │   ├── item.ts                      ← 新增：Item / ItemSpec / PricePoint / CategoryFile / IndexFile 型別（契約 v2）
│   │   └── filters.ts                   ← 新增：SpecField / SpecCondition / FilterState
│   ├── data/
│   │   └── categories.ts                ← 新增：9 大分類定義（key、label、gIndex）
│   ├── composables/
│   │   ├── useItems.ts                  ← 新增：資料載入（fetch/解析/錯誤/重試/過期判定）
│   │   ├── useFilters.ts                ← 新增：搜尋+篩選+分類狀態與過濾運算
│   │   └── usePriceDelta.ts             ← 新增：漲跌計算（今日 vs 昨日）與顯示分類
│   ├── utils/
│   │   ├── search.ts                    ← 新增：全文比對（name + spec 欄位、不區分大小寫）
│   │   ├── specFilter.ts                ← 新增：篩選條件解析、「≥」語意比對、key 對照
│   │   └── format.ts                    ← 新增：價格/日期格式化（NT$、台北時間）
│   ├── components/
│   │   ├── CategorySidebar.vue          ← 新增：分類側欄（含「全部」）
│   │   ├── SearchBar.vue                ← 新增：搜尋框（300ms debounce）
│   │   ├── SpecFilterPanel.vue          ← 新增：規格篩選面板（可移除條件 chips）
│   │   ├── ProductList.vue              ← 新增：列表容器（標題+筆數、空狀態分流、清除全部）
│   │   ├── ProductCard.vue              ← 新增：商品卡片（004/005 整合點在此）
│   │   ├── Sparkline.vue                ← 新增：SVG 迷你趨勢圖
│   │   ├── EmptyState.vue               ← 新增：空狀態（search/filter/category 三種）
│   │   └── ErrorState.vue               ← 新增：錯誤狀態（fetch/parse 兩類 + 重試）
│   └── views/
│       └── ListingView.vue              ← 新增：首頁/列表頁（組合以上全部）
```

### 2.2 型別定義（`types/item.ts`）

`data/items/{g}.json` 為爬蟲 001 產出、`data/` 目錄由 002 部署提交；此處型別即該檔案（**契約 v2 分類拆檔：每分類一檔、純 items 陣列、無 meta、無 category 欄位**）的**前端契約**（欄位以 `optional` 容忍爬蟲尚未解析的欄位）：

```typescript
// web/src/types/item.ts
/** 歷史價格點：d = 日期（UTC），p = 台幣整數。
 *  ⚠️ 分類檔原始格式為 compact 陣列 ["2026-08-15", 9990]（001 格式決策），
 *  由 useItems.parseCategoryFile 於載入層正規化為本物件型別；元件一律使用正規化後型別。 */
export interface PricePoint {
  d: string  // "2026-08-15"
  p: number  // 9990
}

/** 結構化規格：spec_parser（001）產出；未解析到的欄位為 undefined */
export interface ItemSpec {
  brand?: string
  model?: string
  cores?: number        // CPU 核數（篩選條件：CPU核數≥8）
  threads?: number      // 執行緒
  base_ghz?: number     // 基礎時脈
  turbo_ghz?: number    // 超頻時脈
  tdp_w?: number        // TDP（瓦）
  socket?: string       // 腳位，如 LGA1700
  vram_gb?: number      // 顯示卡 VRAM（G）（篩選條件：VRAM≥12G）
  wattage_w?: number    // 電源瓦數（篩選條件：瓦數≥750W）
  capacity_gb?: number  // 容量（SSD/HDD/記憶卡）
  ram_gb?: number       // 記憶體容量（P2 篩選可擴充）
  [key: string]: string | number | undefined  // 保留擴充欄位
}

export type ItemStatus = 'in_stock' | 'gone'

export interface Item {
  id: string            // hash(主分類 + 正規化名稱)，跨日穩定（001 為 sha256 hex[:16]）
  // ⚠️ 契約 v2：Item **無 category 欄位**（分類為外部狀態——item 屬哪一檔即屬哪一分類）
  subcategory?: string  // 子分類標題（如「Intel 第14代」；G=9 過濾後收錄）
  name: string
  spec: ItemSpec        // 可能為空物件 {}（無結構化規格）
  flags?: { hot?: boolean; promo?: string; price_drop?: boolean; clearance?: boolean }
  // 對應 001 四種標記：Hot！→ hot、任搭↓N → promo、↘ → price_drop、尾盤 → clearance
  status: ItemStatus
  first_seen: string
  last_seen: string
  history: PricePoint[] // 契約 v2：分類檔每筆僅最近 ≤2 點（完整歷史由 api/trends/{id}.json 提供）；可能為空陣列或僅 1 筆（首次出現）
}

/** api/items/{g}.json 分類檔契約（契約 v2）：頂層即 Item 陣列 */
export type CategoryFile = Item[]

/** api/index.json 契約（契約 v2）：categories[] 為分類索引（前端 lazy 載入入口），取代 v1 的 latest_file */
export interface IndexFile {
  crawled_at: string    // UTC ISO 字串，供過期判定（>7 天，與 007 新鮮度規則共用）與 cache-busting（?v=）
  categories: { id: string; name: string; file: string; count: number }[]
  daily_files: { file: string; url: string; records: number }[]
  trends_prefix: string
  total?: number
  status?: string
}
```

### 2.3 分類定義（`data/categories.ts`）

分類為**固定常數**（與爬蟲 `categories.py` 同步），側欄只渲染此表 → 天然滿足 BDD「側欄不顯示追蹤範圍外的分類」：

```typescript
// web/src/data/categories.ts
export type CategoryKey =
  | 'CPU' | 'MB' | 'RAM' | 'GPU' | 'SSD'
  | 'HDD' | 'DESKTOP' | 'BUNDLE' | 'CARD'

export interface CategoryDef {
  key: CategoryKey   // URL 參數值，如 ?category=GPU
  label: string      // 顯示名（契約 v2：分類為外部狀態，item 無 category 欄位；label 僅用於顯示/過濾比對）
  gIndex: number     // 爬蟲手機版頁 G 索引（契約 v2：同時是分類檔名 data/items/{g}.json / api/items/{g}.json 的 {g}）
}

export const CATEGORIES: CategoryDef[] = [
  { key: 'CPU',     label: 'CPU',           gIndex: 4  },
  { key: 'MB',      label: '主機板',         gIndex: 5  },
  { key: 'RAM',     label: '記憶體',         gIndex: 6  },
  { key: 'GPU',     label: '顯示卡',         gIndex: 12 },
  { key: 'SSD',     label: 'SSD',           gIndex: 7  },
  { key: 'HDD',     label: 'HDD',           gIndex: 8  },
  { key: 'DESKTOP', label: '套裝/準系統',     gIndex: 1  },
  { key: 'BUNDLE',  label: '劈發價組合區',    gIndex: 3  },
  { key: 'CARD',    label: '記憶卡',         gIndex: 9  },
]

export const CATEGORY_KEYS: readonly string[] = CATEGORIES.map(c => c.key)
export function isCategoryKey(v: unknown): v is CategoryKey {
  return typeof v === 'string' && CATEGORY_KEYS.includes(v)
}
export function labelOf(key: CategoryKey): string {
  return CATEGORIES.find(c => c.key === key)!.label
}
```

### 2.4 `useItems` — 資料載入 composable（契約 v2：lazy 分類載入 + loadAll 聚合）

職責：runtime 讀 `api/index.json`（categories[]＋crawled_at）→ 依側欄「當前分類」**lazy 載入** `api/items/{g}.json?v={crawled_at}`（每分類一檔、純 items 陣列）；`loadAll()` 以 Promise.all 聚合全部分類檔供全站搜尋／詳情 deep link／追蹤使用。解析與 shape 驗證、錯誤分類、重試、過期判定。**錯誤分類決定 ErrorState 顯示文案**；任何失敗都不能影響側欄／搜尋框渲染（錯誤只在列表區域呈現）。

```typescript
// web/src/composables/useItems.ts
import { ref, computed, type Ref } from 'vue'
import type { IndexFile, CategoryFile, Item } from '@/types/item'

export type LoadError = 'fetch' | 'parse' | null
// 'fetch'：HTTP 失敗 / 網路中斷 → 「資料載入失敗」
// 'parse'：JSON 解析或 shape 驗證失敗 → 「資料格式錯誤」

export class ParseError extends TypeError {}  // 供 error 分類判別

const INDEX_URL = `${import.meta.env.BASE_URL}api/index.json`
// runtime 發現（002 §1.7 合約，契約 v2）：index.json 是唯一入口（categories[]＋crawled_at，無 latest_file），
// 分類檔以 `?v={crawled_at}` 做 cache-busting（crawled_at 更新 → 強制取新，取代 v1 latest.json 的無 busting 語意），
// 卡片漲跌/目前價讀分類檔 items[].history（每筆 ≤2 點）；完整歷史由 api/trends/{id}.json 提供（004 useTrend）。

export function useItems() {
  const items = ref<Item[]>([]) as Ref<Item[]>          // 目前分類已載入的 items（lazy）
  const allItems = ref<Item[]>([]) as Ref<Item[]>       // loadAll 聚合的全站 items（搜尋/deep link/追蹤用）
  const meta = ref<IndexFile['crawled_at'] | null>(null) // crawled_at（過期判定與 ?v=）
  const index = ref<IndexFile | null>(null)             // categories[] 索引
  const loading = ref(true)
  const error = ref<LoadError>(null)

  async function loadIndex(): Promise<IndexFile> {
    const indexRes = await fetch(INDEX_URL)              // 1. 取入口（categories[]）
    if (!indexRes.ok) throw new Error(`HTTP ${indexRes.status}`)
    const idx: unknown = await indexRes.json()
    return parseIndex(idx)                               // shape 驗證 categories[]/crawled_at（無 latest_file）
  }

  /** lazy：依分類 G（gIndex → file）載入單一分類檔；可用於側欄切換 */
  async function loadCategory(g: number): Promise<void> {
    try {
      const idx = index.value ?? (index.value = await loadIndex())
      const cat = idx.categories.find(c => Number(c.id) === g)
      if (!cat) throw new ParseError('categories[] 缺該分類')
      const res = await fetch(`${import.meta.env.BASE_URL}${cat.file}?v=${encodeURIComponent(idx.crawled_at)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const raw: unknown = await res.json()              // 壞 JSON → SyntaxError
      items.value = parseCategoryFile(raw)               // 頂層即 Item[]；shape 驗證失敗 → ParseError
      meta.value = idx.crawled_at
    } catch (e) {
      error.value = e instanceof ParseError || e instanceof SyntaxError ? 'parse' : 'fetch'
    } finally { loading.value = false }
  }

  /** loadAll：併發載入全部分類檔聚合為全站 items（全站搜尋/詳情 deep link/追蹤頁使用） */
  async function loadAll(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const idx = index.value ?? (index.value = await loadIndex())
      const files = idx.categories.map(c => c.file)
      const results = await Promise.all(
        files.map(f => fetch(`${import.meta.env.BASE_URL}${f}?v=${encodeURIComponent(idx.crawled_at)}`)),
      )
      if (results.some(r => !r.ok)) throw new Error('HTTP 部分分類載入失敗')
      const raws = await Promise.all(results.map(r => r.json()))
      allItems.value = raws.flatMap(r => parseCategoryFile(r))
      items.value = allItems.value                      // 預設以全站列表呈現（「全部」）
      meta.value = idx.crawled_at
    } catch (e) {
      error.value = e instanceof ParseError || e instanceof SyntaxError ? 'parse' : 'fetch'
      // items/allItems 保持上次成功資料（若有）或空陣列；絕不 throw 至元件層
    } finally {
      loading.value = false
    }
  }

  /** 過期判定：meta.crawled_at（UTC）距今 > 7 天（超過 7 天）→ 顯示過期橫幅（資料仍顯示）。
   *  與 007 新鮮度規則共用（今日/昨日/N 天前；>7 天警告），詳見 007 §1.7/§6.4 */
  const isStale = computed(() => {
    if (!meta.value) return false
    const days = Math.floor((Date.now() - new Date(meta.value.crawled_at).getTime()) / 86_400_000)
    return days > 7
  })

  // 初始進入首頁：直接 loadAll 聚合（全站列表；側欄切分類後可改走 loadCategory lazy 路徑）
  loadAll()
  return { items, allItems, index, meta, loading, error, retry: loadAll, loadCategory, isStale }
}

/** shape 驗證（契約 v2）：頂層即 Item 陣列且每筆具 id/name/subcategory/history；不符即拋 ParseError。
 *  正規化：原始 history 為 compact [d,p] 陣列（001 格式），此處 map 為 { d, p }（PricePoint）。 */
function parseCategoryFile(raw: unknown): CategoryFile {
  // TODO: 最小驗證（Array.isArray、欄位存在性）
  // 缺 history 的舊資料 → 補 []，避免下游 undefined 崩潰
  // history: rawItems[i].history.map(([d, p]) => ({ d, p })) ← compact → PricePoint 正規化
  // 驗證失敗 → throw new ParseError('分類檔 shape 不符')
  return raw as CategoryFile
}

/** shape 驗證（契約 v2）：categories[]（id/name/file/count）＋ crawled_at；無 latest_file 欄位。 */
function parseIndex(raw: unknown): IndexFile {
  // TODO: 最小驗證（crawled_at 為 ISO 字串、categories 為非空陣列、每項具 file/count）
  // v1 的 latest_file 已移除：前端一律經 categories[].file 動態發現分類檔
  // 驗證失敗 → throw new ParseError('index.json shape 不符')
  return raw as IndexFile
}
```

**單元測試方向（Vitest，mock global.fetch）**：成功載入（loadAll 1,449 筆）／lazy 單一分類載入（loadCategory）／HTTP 404→`error='fetch'`／壞 JSON→`error='parse'`／index categories[] 缺欄位→`error='parse'`／compact history 正規化為 PricePoint／`crawled_at` 8 天前→`isStale=true`（7 天內 false）／retry 成功後 error 清空／`?v={crawled_at}` 帶入 fetch URL。

### 2.5 `useFilters` — 搜尋＋篩選＋分類狀態

職責：管理三種收斂維度（分類／關鍵字／規格條件）並計算 `filteredItems`。**過濾運算全為純函數**（`matchesKeyword`／`matchesCondition`），composable 只做狀態組合，單元測試可直接測純函數。**契約 v2：分類為外部狀態**——傳入的 `items` 已是「目前分類」的載入結果（lazy 載入分類檔）或「全部」的 loadAll 聚合，故過濾管線**不再依 `item.category` 欄位做分類比對**（Item 無 category 欄位）。

```typescript
// web/src/composables/useFilters.ts
import { ref, computed, type Ref } from 'vue'
import type { Item } from '@/types/item'
import type { SpecCondition } from '@/types/filters'
import { matchesKeyword } from '@/utils/search'
import { matchesCondition } from '@/utils/specFilter'

export function useFilters(items: Ref<Item[]>) {
  const keyword = ref('')                       // 原始輸入；比對前 trim + lowercase
  const conditions = ref<SpecCondition[]>([])   // 多條件一律 AND
  const categoryKey = ref<string | null>(null)  // null = 全部（分類切換由 useItems loadCategory 載入對應檔）

  /** 過濾管線：搜尋 → 規格條件（AND 依序收斂）；分類由外部載入層決定（v2） */
  const filteredItems = computed<Item[]>(() => {
    const q = keyword.value.trim().toLowerCase()
    return items.value.filter(it => {
      if (q && !matchesKeyword(it, q)) return false
      return conditions.value.every(c => matchesCondition(it, c))
    })
  })

  const hasActiveFilter = computed(
    () => keyword.value.trim() !== '' || conditions.value.length > 0,
  )

  function setKeyword(v: string) { keyword.value = v }
  function addCondition(c: SpecCondition) {
    // 同欄位重複套用 → 取代（保留較新值），避免混淆；其餘保留
    conditions.value = [...conditions.value.filter(x => x.field !== c.field), c]
  }
  function removeCondition(id: string) { conditions.value = conditions.value.filter(c => c.id !== id) }
  function clearSearch() { keyword.value = '' }
  function clearFilters() { conditions.value = [] }
  /** 清除全部條件：僅清搜尋+篩選，**保留目前分類**（BDD：回到目前分類的完整集合） */
  function clearAll() { keyword.value = ''; conditions.value = [] }
  function setCategory(key: string | null) { categoryKey.value = key }

  return {
    keyword, conditions, categoryKey, filteredItems, hasActiveFilter,
    setKeyword, addCondition, removeCondition,
    clearSearch, clearFilters, clearAll, setCategory,
  }
}
```

```typescript
// web/src/types/filters.ts
export type SpecField =
  | 'vram' | 'cores' | 'wattage'   // P1 三條件（BDD 需求）
  | 'capacity' | 'ram' | 'tdp_w'   // P2 可擴充（須與 spec_parser 產出對齊）
  | (string & {})                  // 保留擴充

export interface SpecCondition {
  id: string        // `${field}-${value}`，供 chip 移除
  label: string     // 顯示文案，如「VRAM≥12G」
  field: SpecField  // 對應 item.spec 欄位
  op: '>='          // 本功能僅支援「大於等於」（tech decision 語意）
  value: number
  unit: string      // 顯示用單位：G / W / 核 …
}

export interface FilterState {
  keyword: string
  conditions: SpecCondition[]
  categoryKey: string | null
}
```

### 2.6 規格篩選語意（`utils/specFilter.ts`）

核心規則（對應 BDD @business-rules / @edge-case）：

- **條件解析**：`VRAM≥12G` → `{ field:'vram', op:'>=', value:12, unit:'G' }`；僅支援 `≥`（`>=`／`＞` 於 UI 上統一轉為 `≥` 亦可，P2）。
- **比對語意**：`value >= threshold`，**邊界值納入**（12G 命中 12G）。
- **缺欄位商品**：`item.spec[field]` 非 number → **不命中、靜默排除、不報錯**。

```typescript
// web/src/utils/specFilter.ts
import type { Item } from '@/types/item'
import type { SpecCondition, SpecField } from '@/types/filters'

/** 顯示標籤 ↔ item.spec 欄位 key 對照（擴充時同步更新此表） */
export const SPEC_FIELD_LABELS: Record<string, { label: string; unit: string }> = {
  vram:    { label: 'VRAM',     unit: 'G'  },
  cores:   { label: 'CPU核數',  unit: '核' },
  wattage: { label: '瓦數',     unit: 'W'  },
  capacity:{ label: '容量',     unit: 'GB' },
  ram:     { label: '記憶體',   unit: 'GB' },
  tdp_w:   { label: 'TDP',      unit: 'W'  },
}

/** 「VRAM≥12G」→ SpecCondition；格式不符或欄位未知 → null（UI 顯示提示不套用） */
export function parseCondition(input: string): SpecCondition | null {
  // 正規式：標籤 + 可選空白 + ≥ + 數值 + 可選單位
  const m = input.trim().match(/^(.+?)\s*[≥>=]\s*(\d+(?:\.\d+)?)\s*([A-Za-z\u6838GW]*)$/)
  if (!m) return null
  const field = Object.keys(SPEC_FIELD_LABELS).find(
    k => SPEC_FIELD_LABELS[k].label === m[1].trim(),
  )
  if (!field) return null
  const value = Number(m[2])
  return { id: `${field}-${m[2]}`, label: input.trim(), field, op: '>=', value, unit: m[3] || '' }
}

/** ≥ 語意比對：缺欄位 → false（靜默排除）；邊界值（等於門檻）→ true */
export function matchesCondition(it: Item, c: SpecCondition): boolean {
  const v = it.spec[c.field]
  if (typeof v !== 'number') return false
  return v >= c.value
}
```

```typescript
// web/src/utils/search.ts
/** 全文搜尋：僅比對 name + spec 欄位值（不區分大小寫、子字串字面比對）。
 *  不含 flags / status / history（BDD：搜尋「9999」不得命中歷史價 9999 的商品）。 */
export function matchesKeyword(it: Item, q: string): boolean {
  if (it.name.toLowerCase().includes(q)) return true
  // spec 可能為空物件 → join 後為 ''，不命中（無規格欄位商品仍可被名稱搜尋命中）
  const specText = Object.values(it.spec).map(v => String(v ?? '')).join(' ').toLowerCase()
  return specText.includes(q)
}
```

### 2.7 `CategorySidebar.vue`

職責：渲染 9 大分類（含「全部」）、高亮目前分類、顯示各分類商品數。**不**直接操作 URL——透過 `select` 事件交給 ListingView 統一同步 router。

```vue
<script setup lang="ts">
import { CATEGORIES, type CategoryKey } from '@/data/categories'

defineProps<{
  active: CategoryKey | null       // 目前分類；null = 全部
  counts?: Record<string, number>  // 分類 → 商品數（由 ListingView 計算傳入）
}>()
const emit = defineEmits<{
  (e: 'select', key: CategoryKey | null): void  // null = 全部
}>()
// template: <button class="cat" :class="{ 'is-active': active === c.key }"
//            v-for="c in CATEGORIES" @click="emit('select', c.key)">
</script>
```

### 2.8 `SearchBar.vue`

職責：受控輸入 + 300ms debounce（避免每鍵全量過濾）。空白字元輸入在過濾層自然為 no-op（見 §6.3）。

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const input = ref(props.modelValue)
let timer: ReturnType<typeof setTimeout> | undefined
watch(input, v => {
  clearTimeout(timer)
  timer = setTimeout(() => emit('update:modelValue', v), 300)  // debounce
})
watch(() => props.modelValue, v => { if (v !== input.value) input.value = v })  // 外部清空同步
// template: <input type="search" v-model="input" placeholder="搜尋商品名稱或規格…" />
</script>
```

### 2.9 `SpecFilterPanel.vue`

職責：提供數值門檻表單（欄位下拉 + ≥ + 數值 + 單位）、已套用條件 chips（可單獨移除）。每個欄位一次只能有一個條件（重複套用 → 取代，見 `useFilters.addCondition`）。

```vue
<script setup lang="ts">
import { ref } from 'vue'
import type { SpecCondition } from '@/types/filters'
import { SPEC_FIELD_LABELS, parseCondition } from '@/utils/specFilter'

const props = defineProps<{ conditions: SpecCondition[] }>()
const emit = defineEmits<{
  (e: 'add', c: SpecCondition): void
  (e: 'remove', id: string): void
}>()

const field = ref<keyof typeof SPEC_FIELD_LABELS>('vram')
const value = ref<number | null>(null)
const error = ref('')

function apply() {
  const c = parseCondition(`${SPEC_FIELD_LABELS[field.value].label}≥${value.value}`)
  if (!c || value.value == null) { error.value = '請輸入有效數值門檻（≥）'; return }
  error.value = ''
  emit('add', c)
}
// template: 欄位 select + ≥ + number input + 套用按鈕；下方 render 條件 chips（含 ✕）
</script>
```

### 2.10 `ProductList` / `ProductCard` — 列表與卡片（含 004/005 整合點）

`ProductList` 職責：標題＋命中筆數、空狀態分流、清除全部按鈕、渲染卡片。`ProductCard` 職責：卡片資訊與**整合點事件出口**。

```vue
<script setup lang="ts">
// components/ProductList.vue
import { computed } from 'vue'
import ProductCard from './ProductCard.vue'
import EmptyState from './EmptyState.vue'
import type { Item } from '@/types/item'
import type { SpecCondition } from '@/types/filters'

const props = defineProps<{
  items: Item[]
  total: number                    // 未過濾前總筆數（標題顯示「x / total」）
  keyword: string
  conditions: SpecCondition[]
}>()
const emit = defineEmits<{
  (e: 'clear-all'): void
  (e: 'open', item: Item): void            // 轉接 004 詳情入口
  (e: 'toggle-watch', item: Item): void    // 轉接 005
  (e: 'toggle-compare', item: Item): void  // 轉接 005
}>()

/** 空狀態分流：優先搜尋無結果 → 篩選無結果 → 空分類（見 §6.2） */
const emptyKind = computed<'search' | 'filter' | 'category'>(() => {
  if (props.keyword.trim()) return 'search'
  if (props.conditions.length) return 'filter'
  return 'category'
})
// template: header（標題+命中筆數+「清除全部條件」v-if="hasActiveFilter"）
//           items.length ? 卡片 grid : <EmptyState :kind="emptyKind" … />
</script>
```

```vue
<script setup lang="ts">
// components/ProductCard.vue —— 004/005 整合點集中於此元件
import { computed } from 'vue'
import type { Item } from '@/types/item'
import { usePriceDelta } from '@/composables/usePriceDelta'
import Sparkline from './Sparkline.vue'
import { formatPrice } from '@/utils/format'

const props = defineProps<{
  item: Item
  watched?: boolean          // 005：已追蹤狀態（005 實作前預設 false，不渲染按鈕亦可）
  compareSelected?: boolean  // 005：比價已勾選
}>()
const emit = defineEmits<{
  (e: 'open', item: Item): void            // 004：點名稱/卡片 → 詳情頁（004 改為 router-link）
  (e: 'toggle-watch', item: Item): void    // 005：追蹤按鈕切換
  (e: 'toggle-compare', item: Item): void  // 005：比價勾選切換
}>()

const { currentPrice, deltaClass, deltaText } = usePriceDelta(props.item)
const sparkPoints = computed(() => props.item.history.slice(-30))  // 卡片取最近 N 點；O4：列表快照 history 僅 ≤2 點，sparkline 以可取得之短歷史繪製（<2 點不畫線）
const specChips = computed(() => chipTexts(props.item.spec))       // 如 ['14核','20緒','125W']
// template: 見 §7 對應 class：pc-name / pc-specs / pc-price / pc-delta / pc-compare
</script>
```

```typescript
// web/src/lib/priceChange.ts（共用事實來源：003 卡片 badge / 004 詳情頁摘要）
// 語意：current = history 最後一點；previous = 倒數第二點 = 「上一筆有紀錄的日期」
// （非連續日如 08-10 → 08-15 仍以最後兩點比較，不補中間日、不以日曆昨日猜測）。
// 僅 1 筆 / 空 → previous/diff/trend 全 null（上游優雅降級）。
export function computePriceChange(history: PricePoint[]): PriceChange

// web/src/composables/usePriceDelta.ts（卡片呈現；規格 chips 白名單 specChipTexts 亦於此檔）
export function usePriceDelta(item: Item) {
  const change = computed(() => computePriceChange(item.history))
  // 漲紅 price-up / 跌綠 price-down / 持平灰 price-flat / 首日「新」price-new / 空「—」
  return {
    currentPrice: computed(() => change.value.current),
    deltaClass: computed(() => priceChangeBadgeClass(change.value)),
    deltaText: computed(() => priceChangeBadgeText(change.value)),
  }
}
```

**Sparkline**（`components/Sparkline.vue`）：SVG `viewBox="0 0 100 28"` polyline，將 history 縮放至該座標系；**少於 2 筆不畫線**，顯示「—」（與 005 追蹤頁「資料不足」語意一致）：

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { PricePoint } from '@/types/item'

const props = defineProps<{ points: PricePoint[] }>()
const poly = computed(() => sparklinePoints(props.points))  // "x1,y1 x2,y2 …"
// template:
//   <svg v-if="props.points.length >= 2" class="sparkline" viewBox="0 0 100 28" preserveAspectRatio="none">
//     <polyline :points="poly" />
//   </svg>
//   <span v-else class="sparkline--empty">—</span>
</script>
```

### 2.11 `EmptyState` / `ErrorState`

```vue
<script setup lang="ts">
// components/EmptyState.vue
defineProps<{
  kind: 'search' | 'filter' | 'category'
  keyword?: string          // kind='search'：顯示「沒有符合『{keyword}』的商品」
  conditions?: string[]     // kind='filter'：列出已套用條件
}>()
const emit = defineEmits<{ (e: 'clear'): void }>()
// kind 對應文案：
//   search   → 「沒有符合『xx』的商品」+「清除搜尋」
//   filter   → 「沒有符合條件的商品」+ 條件列表 +「清除篩選」
//   category → 「此分類目前沒有商品」+「清除篩選」（若無篩選則純說明，不顯示錯誤）
</script>
```

```vue
<script setup lang="ts">
// components/ErrorState.vue
defineProps<{ kind: 'fetch' | 'parse' }>()
const emit = defineEmits<{ (e: 'retry'): void }>()
// kind='fetch' → 圖示 +「資料載入失敗」+「重試」
// kind='parse' → 圖示 +「資料格式錯誤」+「重試」（文案依 §6.1）
</script>
```

### 2.12 `ListingView.vue` — 列表頁組合與 deep link

職責：組合全部元件；**URL 分類參數為分類狀態的唯一真相來源**（雙向同步）；掛載時依 `?category=<key>` 初始化（deep link）。

```vue
<script setup lang="ts">
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useItems } from '@/composables/useItems'
import { useFilters } from '@/composables/useFilters'
import { isCategoryKey, type CategoryKey } from '@/data/categories'
import CategorySidebar from '@/components/CategorySidebar.vue'
import SearchBar from '@/components/SearchBar.vue'
import SpecFilterPanel from '@/components/SpecFilterPanel.vue'
import ProductList from '@/components/ProductList.vue'
import ErrorState from '@/components/ErrorState.vue'

const route = useRoute()
const router = useRouter()
const { items, allItems, index, meta, loading, error, retry, loadCategory, isStale } = useItems()
const filters = useFilters(items)

// —— deep link：初次進入即依 ?category=<key> 呈現（BDD：直接以分類頁網址進入）——
//    分類為外部狀態（v2）：切分類 = 載入對應分類檔 api/items/{g}.json（lazy），列表 items 即該分類
const initial = route.query.category
if (isCategoryKey(initial)) {
  filters.setCategory(initial as CategoryKey)
  void loadCategory(gIndexOf(initial as CategoryKey))   // lazy 載入該分類檔（?v={crawled_at}）
}

// —— URL 與狀態雙向同步：點側欄 → router.replace 更新 URL；URL 變（含前進/後退）→ 更新狀態 ——
function selectCategory(key: CategoryKey | null) {
  router.replace(key ? { query: { category: key } } : { query: {} })
}
watch(() => route.query.category, v => {
  if (isCategoryKey(v)) {
    filters.setCategory(v as CategoryKey)
    void loadCategory(gIndexOf(v as CategoryKey))        // v2：切分類 lazy 載入
  } else {
    filters.setCategory(null)
    void loadAll()                                        // 「全部」→ 聚合全部分類
  }
})

// 各分類商品數（側欄顯示）：v2 直接取 api/index.json 的 categories[].count（item 無 category 欄位）
const counts = computed(() => {
  const map: Record<string, number> = {}
  for (const c of index.value?.categories ?? []) map[c.name] = c.count
  return map
})

// 004/005 事件轉接：本功能僅 emit 至父層預留；005 實作時改接 watchlist/compare store
function onOpen(item: Item) { router.push(`/product/${encodeURIComponent(item.id)}`) }  // 004
function onToggleWatch(item: Item) { /* TODO(005): store.toggle(item.id) */ }
function onToggleCompare(item: Item) { /* TODO(005): store.toggle(item.id) */ }
</script>

<template>
  <div class="listing">
    <Transition name="fade">
      <div v-if="isStale" class="stale-banner" role="alert">
        資料可能已過期（最後更新：{{ formatDateTime(meta?.crawled_at) }}）
      </div>
    </Transition>

    <aside class="listing-sidebar">
      <CategorySidebar :active="filters.categoryKey" :counts="counts" @select="selectCategory" />
    </aside>

    <main class="listing-main">
      <SearchBar v-model="filters.keyword" />
      <SpecFilterPanel :conditions="filters.conditions"
        @add="filters.addCondition" @remove="filters.removeCondition" />

      <!-- 載入中：skeleton（側欄/搜尋框仍可見，不白屏） -->
      <div v-if="loading" class="skeleton-list" aria-busy="true">…</div>

      <!-- 錯誤：僅列表區域顯示 ErrorState + 重試 -->
      <ErrorState v-else-if="error" :kind="error" @retry="retry" />

      <ProductList v-else
        :items="filters.filteredItems" :total="items.length"
        :keyword="filters.keyword" :conditions="filters.conditions"
        @clear-all="filters.clearAll" @open="onOpen"
        @toggle-watch="onToggleWatch" @toggle-compare="onToggleCompare" />
    </main>
  </div>
</template>
```

**Router 設定**（`router/index.ts`）：GitHub Pages SPA 建議 `createWebHashHistory()`（重新整理不 404，deep link 相容）；路由表僅 `{ path: '/', component: ListingView }`，004 再加入 `/product/:id`。

**Vite 設定**（`vite.config.ts`）：`base` 依 repo name（如 `'/CoolPCTracker/'`，部署時以 env 注入）；`assetsDir`、`resolve.alias '@' → src`。

---

## 6. 邊界條件處理

### 6.1 載入失敗與格式錯誤

| # | 情境 | 觸發 | 處理 |
|---|------|------|------|
| E1 | **載入失敗**（BDD @error-handling @smoke @p0） | 網路中斷／`api/index.json` 或任一 `api/items/{g}.json`（categories[].file 指向）回應 404 | `error='fetch'` → 列表區域 `ErrorState` 顯示「資料載入失敗」＋「重試」；側欄、搜尋框、篩選面板**照常渲染**，不白屏 |
| E2 | **JSON 格式錯誤**（@error-handling @p1） | 檔案被截斷、`res.json()` 拋 SyntaxError 或 shape 驗證失敗 | `error='parse'` → 「資料格式錯誤」＋「重試」；若先前載入過成功資料，保留舊資料可顯示（以 `items` 非空為準），否則空列表＋錯誤狀態 |
| E3 | **資料過期**（@error-handling @p2） | `meta.crawled_at` 距今 > 7 天（超過 7 天，與 007 §6.4 共用） | 頂部黃色橫幅「資料可能已過期（最後更新：X，台北時間）」；**資料仍正常顯示** |

### 6.2 空結果與空狀態分流

| # | 情境 | 觸發 | 處理 |
|---|------|------|------|
| E4 | **搜尋無結果**（@error-handling @p0） | 關鍵字無任何 name/spec 命中 | `emptyKind='search'` → 「沒有符合『量子電腦』的商品」＋「清除搜尋」按鈕（點擊 → `clearSearch()`） |
| E5 | **篩選組合無結果**（@error-handling @p1） | 條件過嚴（如 VRAM≥24G 且瓦數≥1200W） | `emptyKind='filter'` → 「沒有符合條件的商品」＋**列出已套用條件 chips**＋「清除篩選」 |
| E6 | **空分類**（@edge-case @p2） | 某分類當日 0 筆商品 | `emptyKind='category'` → 空狀態說明，**不顯示錯誤、不觸發重試** |
| E7 | **僅空白字元搜尋**（@edge-case @p2） | 輸入「   」 | `keyword.trim()===''` → 過濾管線跳過搜尋步驟，列表維持目前完整集合（含「清除全部」按鈕不顯示，因 `hasActiveFilter` 為 false） |

### 6.3 資料缺漏降級

| # | 情境 | 觸發 | 處理 |
|---|------|------|------|
| E8 | **缺昨日價**（@edge-case @p1） | `history` 僅 1 筆或為空 | `delta=null` → 僅 1 筆（有價）漲跌欄顯示「新」（中性色 `price-new`）；空 history 顯示「—」；名稱、價格、sparkline 照常 |
| E9 | **無規格欄位商品**（@edge-case @p1，@business-rules @p1） | `spec` 為空物件（如「XC-5500 隨機贈品主機」） | 名稱搜尋仍命中（`matchesKeyword` 只看 name）；結構化篩選**靜默排除**（`matchesCondition` 回 false）、頁面不報錯 |
| E10 | **sparkline 資料不足** | history < 2 筆 | 不畫線，顯示「—」；與 005 追蹤頁「資料不足」語意一致 |
| E11 | **搜尋範圍限制**（@business-rules @p1） | 關鍵字「9999」僅存在於 history | `matchesKeyword` 只比對 name+spec → 不命中，列表為空狀態 |

### 6.4 篩選與搜尋語意

| # | 情境 | 觸發 | 處理 |
|---|------|------|------|
| E12 | **邊界值納入**（@edge-case @business-rules @p1） | 商品規格恰等於門檻：VRAM 12G / CPU 8 核 / 750W | `>=` 語意：`v >= c.value`，**12G 命中 VRAM≥12G**、8 核命中 CPU核數≥8、750W 命中瓦數≥750W |
| E13 | **多條件 AND**（@happy-path @p1，@business-rules） | 同時套用 VRAM≥12G 且瓦數≥750W | `conditions.every(matchesCondition)` 交集；本功能**不支援 OR 群組**（P2） |
| E14 | **特殊字元字面比對**（@edge-case @p2） | 輸入「RTX+4070 & 12G≥」 | 使用 `String.prototype.includes` 字面子字串比對（非 regex），`+`、`&`、`≥` 無需跳脫、不拋錯 |
| E15 | **僅 9 大分類**（@business-rules @p2） | 側欄渲染 | 側欄資料源為 `CATEGORIES` 常數（與爬蟲 categories.py 同步），**不含**電源、機殼、螢幕等範圍外分類 |
| E16 | **深層連結無效分類參數**（深層連結的防禦） | `?category=FOO` | `isCategoryKey` 驗證失敗 → 視同「全部」；側欄無高亮，列表顯示全部 |

### 6.5 BDD 覆蓋矩陣（24 Scenario 全數對應）

| # | BDD Scenario（標籤） | 對應章節 |
|---|----------------------|---------|
| 1 | 進入首頁並瀏覽全部商品（@happy-path @smoke @p0） | §2.3、§2.12、§7（側欄＋列表全量 1,449 筆） |
| 2 | 點擊分類瀏覽該分類商品（@happy-path @p0） | §2.5、§2.7、§2.12（URL 同步＋高亮） |
| 3 | 全文搜尋命中目標商品（@happy-path @smoke @p0） | §2.6 search.ts、§2.8 |
| 4 | 套用單一結構化規格篩選（@happy-path @p0） | §2.6 specFilter.ts、§2.9 |
| 5 | 同時套用多個篩選條件（AND）（@happy-path @p1） | §2.5（`every`）、§6.4 E13 |
| 6 | 搜尋與篩選同時作用（@happy-path @p1） | §2.5 過濾管線（分類→搜尋→篩選） |
| 7 | 瀏覽商品卡片資訊（@happy-path @p0） | §2.10、§2.4 usePriceDelta、§7 |
| 8 | 清除全部搜尋與篩選條件（@happy-path @p1） | §2.5 `clearAll()`（保留目前分類） |
| 9 | 直接以分類頁網址進入（deep link）（@happy-path @p1） | §2.12（initial + watch route.query） |
| 10 | 資料 API 載入失敗（@error-handling @smoke @p0） | §6.1 E1、§2.4 |
| 11 | 資料格式錯誤（@error-handling @p1） | §6.1 E2、§2.4 |
| 12 | 搜尋無結果（@error-handling @p0） | §6.2 E4、§2.11 |
| 13 | 篩選組合無結果（@error-handling @p1） | §6.2 E5、§2.11 |
| 14 | 資料過期提示（@error-handling @p2） | §6.1 E3、§2.4 `isStale`（>7 天，與 007 新鮮度規則一致） |
| 15 | 搜尋框僅輸入空白字元（@edge-case @p2） | §6.2 E7、§2.5（trim） |
| 16 | 搜尋含特殊字元（@edge-case @p2） | §6.4 E14、§2.6 search.ts |
| 17 | 無規格欄位商品仍可被名稱搜尋命中（@edge-case @p1） | §6.3 E9、§2.6 search.ts |
| 18 | 商品缺少昨日價時漲跌顯示「—」（@edge-case @p1） | §6.3 E8、§2.4 usePriceDelta |
| 19 | 分類下無任何商品（@edge-case @p2） | §6.2 E6、§2.11 |
| 20 | 篩選門檻為「≥」，邊界值納入（@edge-case @business-rules @p1） | §6.4 E12、§2.6 |
| 21 | 昨日漲跌依今日與昨日價格計算（@business-rules @p1） | §2.4 usePriceDelta（漲紅/跌綠/持平灰） |
| 22 | 分類側欄僅顯示 9 大分類（@business-rules @p2） | §6.4 E15、§2.3 |
| 23 | 搜尋範圍僅涵蓋名稱與規格欄位（@business-rules @p1） | §6.3 E11、§2.6 |
| 24 | 結構化篩選僅對有對應欄位生效（@business-rules @p1） | §6.3 E9、§2.6 matchesCondition |

---

## 7. CSS 關鍵樣式

### 7.1 設計 token

```css
:root {
  /* 漲跌顏色：漲紅 / 跌綠 / 持平灰（BDD 指定語意） */
  --price-up:   #e02424;  /* 漲 → 紅 */
  --price-down: #18933f;  /* 跌 → 綠 */
  --price-flat: #6b7280;  /* 持平 → 灰 */

  --brand: #1f6feb; --brand-soft: #e8f0fe;
  --bg: #f7f8fa; --surface: #ffffff; --border: #e5e7eb;
  --text: #1f2937; --text-dim: #6b7280;
  --warn-bg: #fff7e6; --warn-border: #f5c518; --warn-text: #8a6d00;
  --radius: 10px; --shadow: 0 1px 3px rgba(0, 0, 0, .08);
}
```

### 7.2 列表卡片（`.product-card`）

```css
.product-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 12px 14px; display: flex; flex-direction: column; gap: 8px;
  cursor: pointer;                       /* 004：點卡片進詳情 */
  transition: border-color .15s, box-shadow .15s;
}
.product-card:hover { border-color: var(--brand); box-shadow: 0 2px 8px rgba(31,111,235,.15); }
.pc-name { font-size: .95rem; font-weight: 600; line-height: 1.4;
           display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.pc-price { display: flex; align-items: baseline; gap: 8px; }
.pc-current { font-size: 1.15rem; font-weight: 700; color: var(--text); }
.pc-delta { font-size: .85rem; font-weight: 600; }
```

### 7.3 規格 chips（`.pc-specs` / `.chip`）

```css
.pc-specs { display: flex; flex-wrap: wrap; gap: 4px; }
.chip {
  font-size: .72rem; color: var(--text-dim);
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 999px; padding: 2px 8px;
}
```

### 7.4 漲跌顏色（對應 `usePriceDelta.deltaClass`）

```css
.price-up   { color: var(--price-up); }   /* 漲 500（紅） */
.price-down { color: var(--price-down); } /* 跌 500（綠） */
.price-flat { color: var(--price-flat); } /* 持平（灰） */
.price-new  { color: var(--text-dim);     /* 首日追蹤（僅 1 筆）：中性色 badge */
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 999px; padding: 1px 8px; font-size: .72rem; }
```

### 7.5 sparkline

```css
.sparkline { width: 100%; height: 28px; display: block; }
.sparkline polyline {
  fill: none; stroke: var(--brand); stroke-width: 1.5;
  stroke-linejoin: round; stroke-linecap: round;
}
.sparkline--empty { color: var(--text-dim); font-size: .8rem; }
```

### 7.6 佈局與 RWD 斷點

```css
/* 桌面 ≥1024px：側欄 240px + 主區兩欄 */
.listing { display: grid; grid-template-columns: 240px 1fr; gap: 20px;
           max-width: 1200px; margin: 0 auto; padding: 16px; }
.listing-sidebar { position: sticky; top: 72px; align-self: start; }
.cat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }

/* 平板 640–1023px：側欄收合為頂部水平捲動 chips */
@media (max-width: 1023px) {
  .listing { grid-template-columns: 1fr; }
  .listing-sidebar { position: static; }
  .sidebar-list { display: flex; overflow-x: auto; gap: 8px; }  /* 水平捲軸分類列 */
  .cat { flex: 0 0 auto; }
}

/* 手機 <640px：卡片單欄、chips 換行、價格縱向堆疊 */
@media (max-width: 639px) {
  .listing { padding: 10px; gap: 12px; }
  .cat-grid { grid-template-columns: 1fr; }
  .pc-price { flex-wrap: wrap; }
}
```

### 7.7 載入／錯誤／空狀態／過期橫幅

```css
/* skeleton 載入態：灰階漸層閃爍 */
.skeleton-list .sk { height: 120px; border-radius: var(--radius);
  background: linear-gradient(90deg, #eee 25%, #f5f5f5 50%, #eee 75%);
  background-size: 200% 100%; animation: shimmer 1.2s infinite; }
@keyframes shimmer { to { background-position: -200% 0; } }

.stale-banner {  /* 頂部過期提示 */
  background: var(--warn-bg); border: 1px solid var(--warn-border);
  color: var(--warn-text); padding: 8px 14px; border-radius: 8px;
  font-size: .85rem; text-align: center;
}
.error-state, .empty-state { text-align: center; padding: 48px 16px; color: var(--text-dim); }
.error-state .retry-btn { margin-top: 12px; }  /* 主色按鈕 */
.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
```

---

## 8. 開發順序

DAG（無循環）：資料層 → 列表 → 搜尋 → 篩選 → RWD／整合。

| 步驟 | 內容 | 依賴 |
|------|------|------|
| 1 | **專案初始化**：Vite + Vue 3.5 + TS + Vitest 設定；`vite.config.ts` base（repo name）；router（hash history）；`types/item.ts`、`types/filters.ts`、`data/categories.ts`、`utils/format.ts` | - |
| 2 | **資料載入層**：`useItems`（index categories[] 發現／lazy loadCategory／loadAll 聚合／parse 驗證／錯誤分類／retry／isStale）＋ Vitest（mock fetch：成功、404、壞 JSON、過期） | #1 |
| 3 | **App shell 與佈局**：`App.vue`、`ListingView.vue` 兩欄框架（側欄＋主區）、skeleton 載入態 | #1 |
| 4 | **分類側欄＋deep link**：`CategorySidebar`（9 分類、高亮、counts）＋ URL `?category=<key>` 雙向同步（初始讀取＋select 更新＋watch 回寫） | #2, #3 |
| 5 | **商品列表與卡片**：`ProductList`、`ProductCard`（名稱／價格／規格 chips／漲跌／sparkline）、`Sparkline`、`EmptyState`、`ErrorState` | #2, #3 |
| 6 | **全文搜尋**：`SearchBar`（300ms debounce）＋ `utils/search.ts`（name+spec 字面比對） | #5 |
| 7 | **規格篩選**：`utils/specFilter.ts`（`VRAM≥12G` 解析、≥ 語意、key 對照）＋ `SpecFilterPanel`（表單＋條件 chips） | #5 |
| 8 | **交集整合**：搜尋×篩選×分類過濾管線、`clearAll`（保留分類）、空狀態分流（search/filter/category）、空白與特殊字元防禦 | #4, #6, #7 |
| 9 | **RWD＋整合點預留**：斷點樣式（1024/640）、過期橫幅；`ProductCard` 接 `open`（004）/`toggle-watch`、`toggle-compare`（005）事件出口 | #5, #8 |
| 10 | **測試補齊＋驗收**：Vitest 覆蓋（specFilter 邊界值、漲跌計算、空分類、缺昨日價、僅空白搜尋、搜尋範圍限制）；以 Playwright（可選）或手動依 BDD smoke 清單驗證 | #6–#9 |

**注意**：步驟 4 與步驟 8 需特別驗證「深層連結」與「清除全部條件」兩條 BDD 場景（屬跨步驟整合行為）；004/005 實作時**不得改動**步驟 5–8 的元件介面，僅在 ListingView 的事件處理器接線（`onOpen` → 004 router、`onToggleWatch/onToggleCompare` → 005 store）。
