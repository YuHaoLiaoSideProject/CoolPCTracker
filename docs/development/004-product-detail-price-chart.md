# 商品詳情與歷史趨勢圖（004-product-detail-price-chart）— 開發規格

> **對應計畫**：Tech Decision §4.1 行動計畫 P1「商品詳情 + ECharts 歷史趨勢圖」（1.5d）
> **技術決策**：`docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md`（§3.1 ECharts 5 on-demand / §3.4 資料模型 history `[d,p]`）
> **操作流程**：`docs/interaction-flows/004-product-detail-price-chart.md`
> **BDD**：`docs/bdds/004-product-detail-price-chart.feature`
> **測試計畫**：尚未產出（本規格完成後可經 test-plan-generator 補齊）
> **相關規格**：003 前端列表與搜尋篩選（入口來源）、005 追蹤清單與比價（詳情頁整合點）
> **狀態**：設計完成，待開發

---

## 概述

訪客從商品列表點入（或 URL deep link）任一商品詳情頁，檢視完整規格、目前價格、與前一筆的漲跌、歷史最低價，並在 ECharts 歷史趨勢圖上以 markLine 設定本次瀏覽有效的目標價線，一眼判斷目前價格是否值得下手。核心包含：

1. **`usePriceHistory` composable**：由商品 `history`（`[d,p]` delta 時間序列）計算目前價、漲跌（金額＋百分比）、歷史最低價（多日同價取最早日期）與圖表資料序列。
2. **`PriceTrendChart` 元件**：ECharts 5（on-demand import）折線趨勢圖，支援 tooltip 懸停查價、dataZoom 縮放、目標價 markLine、Y 軸擴展，並處理非等間距時間軸與單筆資料降級。
3. **`ProductDetailView` 詳情頁**：路由 `/product/:id` 載入、四態狀態機（loading / 載入失敗 / 找不到商品 / 就緒）、規格表（空值欄位隱藏）、價格摘要、目標價輸入驗證與最後更新時間顯示。
4. **`useItems` 共用資料載入**（003 契約）：`data/items.json` 載入、錯誤提示與重試機制，與 003 列表頁共用（同一份 fetch、同一組型別）。

> **整合點**：本功能純前端、無後端 API。進入來源為 003 列表頁（點擊商品列跳轉）；出口整合點預留 005 的「加入追蹤／加入比價」動作區。

---

## 2. 前端實作規格

### 2.1 檔案改動總覽

```
web/src/
├── main.ts                          ← 修改：註冊 router（hash history）、全域樣式
├── router/index.ts                  ← 修改：新增 /product/:id 路由（命名 route: 'product-detail'）
├── types/
│   └── item.ts                      ← 新增：ItemsFile / Item / Spec / PricePoint 型別（003/004/005 共用）
├── lib/
│   └── echarts.ts                   ← 新增：ECharts on-demand 註冊模組（全站共用）
├── composables/
│   ├── useItems.ts                  ← 003 契約：共用 items.json 載入（items/meta/loading/error/retry/isStale）
│   ├── usePriceHistory.ts           ← 新增：漲跌／歷史最低／格式化計算（004 核心）
│   └── useCrawledAt.ts              ← 新增：crawled_at → 台北時間顯示＋過期判斷（003/004 共用）
├── components/
│   ├── SpecTable.vue                ← 新增：規格表（欄位名：值，空值欄位不渲染）
│   ├── PriceTrendChart.vue          ← 新增：ECharts 歷史趨勢圖（tooltip／dataZoom／markLine／單點降級）
│   └── WatchActions.vue             ← 新增（005 預留）：加入追蹤／加入比價按鈕區，004 僅渲染佔位
└── views/
    └── ProductDetailView.vue        ← 新增：商品詳情頁（本功能主視圖）
```

> 註：`web/` 為綠地目錄，若 003 已先行建立 `useItems`、`types/item.ts`、`useCrawledAt`，則直接複用並回填本規格；否則 004 在此建立，作為 003 的共用基礎（見 §8 步驟依賴）。共用契約以 003 的 `useItems`（回傳 `items/meta/loading/error/retry/isStale`）為準。

### 2.2 資料來源契約（data/items.json，取代 API 合約）

純前端功能，無 HTTP API endpoint；唯一資料來源為同 origin 靜態檔 `data/items.json`（GitHub Pages 部署，crawler 每日 commit 更新）。

| 欄位 | 型別 | 約束 | 說明 |
|------|------|------|------|
| `meta.crawled_at` | string | ISO 8601 UTC | 最後爬取時間；顯示時轉台北時區 |
| `items[].id` | string | 唯一、跨日穩定 | `sha256(主分類 + 正規化名稱)` 取前 16 位 hex（001 產生，如 `3f9a1c2b8e4d5f6a`）；URL 直接帶入（hex 無特殊字元，仍以 encodeURIComponent 防呆） |
| `items[].spec` | object | 欄位可缺省 | 結構化規格；空值欄位詳情頁不顯示 |
| `items[].status` | `'in_stock' \| 'gone'` | - | gone＝已下架（不再出現於當日清單） |
| `items[].history` | `PricePoint[]` | 依 `d` 升冪、非等間距、僅異動時 append | delta 時間序列；原始 JSON 為 compact `[d, p]` 陣列（001 格式決策），由 `useItems` 載入層正規化為 `{d, p}`；`history[last]` 即目前價格 |

型別定義（`types/item.ts`）：

```typescript
/** 歷史價格點：d=日期(YYYY-MM-DD)，p=價格(NT$)。delta 策略 → 非等間距，僅價格異動時 append。
 *  ⚠️ items.json 原始格式為 compact 陣列 ["2026-08-15", 9990]（001 格式決策），
 *  由 useItems 載入層正規化為本物件型別。 */
export interface PricePoint {
  d: string
  p: number
}

/** 結構化規格；key 由 spec_parser 產出，任何欄位皆可缺省或為空 */
export interface Spec {
  brand?: string
  model?: string
  cores?: number
  threads?: number
  base_ghz?: number
  turbo_ghz?: number
  tdp_w?: number
  socket?: string
  [key: string]: string | number | boolean | undefined
}

export type ItemStatus = 'in_stock' | 'gone'

export interface Item {
  id: string
  category: string
  subcategory?: string  // 子分類標題（如「Intel 第14代」；G=9 過濾後收錄；與 003 §2.2 共用型別一致）
  name: string
  spec: Spec
  flags?: { hot?: boolean; promo?: string; price_drop?: boolean; clearance?: boolean }
  status: ItemStatus
  first_seen: string
  last_seen: string
  history: PricePoint[]
}

export interface ItemsMeta {
  crawled_at: string
  source: string
}

export interface ItemsFile {
  meta: ItemsMeta
  items: Item[]
}
```

### 2.3 `useItems` — 共用資料載入（003 契約，錯誤／重試）

**職責**：fetch 同 origin `data/items.json`，解析驗證後提供 `items`／`meta`；暴露載入失敗與重試。**本節即 003 §2.4 `useItems` 的契約**（同一 composable、同一 fetch、單例共享 module-level cache），004 詳情頁與 003 列表頁共用同一份資料，避免重複請求。GitHub Pages 快取風險由 002 的 cache-busting 策略（`items.v{n}.json` + `__DATA_VERSION__`）處理，本層以相對路徑 `data/items.json` 為準（002 §1.7 契約就緒後換用版本化檔名）。

```typescript
import { ref, computed, type Ref } from 'vue'
import type { ItemsFile, Item } from '@/types/item'

export type LoadError = 'fetch' | 'parse' | null   // 與 003 同一錯誤分類（fetch=載入失敗 / parse=格式錯誤）

/** 共享 items.json 載入狀態；單例建立，003/004 共用（003 §2.4 同一實作） */
export function useItems() {
  const items = ref<Item[]>([]) as Ref<Item[]>
  const meta = ref<ItemsFile['meta'] | null>(null)
  const loading = ref(true)
  const error = ref<LoadError>(null)

  /** 載入（首次自動呼叫；錯誤後由 retry 重叫）。HTTP 失敗→'fetch'；JSON.parse/shape 失敗→'parse' */
  async function load(): Promise<void> { /* 同 003 §2.4：fetch(data/items.json) → parseItemsFile（含 compact [d,p]→PricePoint 正規化） */ }

  /** 錯誤畫面「重新載入」按鈕的處理；載入成功後 error 清空、loading=false */
  function retry(): void { void load() }

  load()
  return { items, meta, loading, error, retry, isStale }
  // isStale：crawled_at > 7 天 → true（與 007 新鮮度規則共用，見 §2.6 useCrawledAt）
}
```

### 2.4 `usePriceHistory` — 漲跌／歷史最低計算

**職責**：輸入 `history`（依日期升冪），輸出價格摘要（current／previous／diff／diffPercent／trend／low／lowDate）與圖表資料序列。純函數計算邏輯抽離為可單元測試的 util（Vitest 覆蓋 BDD 三組漲跌範例與多日最低範例）。

**漲跌計算規則**（BDD `@edge-case @business-rule` 三組範例）：
- `previous = history[len-2]`、`current = history[len-1]`；`diff = current - previous`。
- `diff < 0` → 標籤 `降價 NT$510（-4.9%）`（金額取絕對值、千分位；百分比帶負號、1 位小數），綠色 ▼。
- `diff > 0` → `漲價 NT$100（+5.3%）`，紅色 ▲。
- `diff === 0` → `持平`，灰色 —（不顯示金額／百分比）。
- 僅一筆時 `previous = null` → 不計算漲跌，顯示「首日追蹤，尚無漲跌比較」。

**歷史最低規則**：`min = min(history.p)`；`lowDate` 取**最早**達成日（history 依日期升冪，取第一個 `p === min` 的點即可）——BDD 連續三日同為最低價時顯示 `2026-08-10`。

```typescript
import { computed, type Ref } from 'vue'
import type { PricePoint } from '@/types/item'

export type Trend = 'up' | 'down' | 'flat' | null

export interface PriceStats {
  current: number | null          // history 最後一筆 p；空 history 為 null
  currentDate: string | null
  previous: number | null         // 前一筆；僅一筆／空時為 null
  diff: number | null             // current - previous
  diffPercent: number | null      // diff / previous * 100（1 位小數）
  trend: Trend
  low: number | null              // 歷史最低價
  lowDate: string | null          // 最早達成日
  empty: boolean                  // history 長度 0
  single: boolean                 // history 長度 1 → 首日追蹤
}

/** 以 history [d,p] 計算價格摘要（history 需依 d 升冪；PricePoint 由 useItems 自 compact [d,p] 正規化） */
export function usePriceHistory(history: Ref<PricePoint[]>) {
  const stats = computed<PriceStats>(() => {
    const h = history.value
    if (h.length === 0) return /* empty: 全 null、empty=true */
    const current = h[h.length - 1].p
    const previous = h.length >= 2 ? h[h.length - 2].p : null
    // diff / diffPercent / trend：previous 為 null 時全為 null
    // low = min(...p)；lowDate = 第一個 p===low 的 d（最早達成日）
    // TODO: 依上述規則填值
  })

  /** 圖表資料序列（日期字串陣列、價格陣列） */
  const chartSeries = computed(() => ({
    dates: history.value.map((h) => h.d),
    prices: history.value.map((h) => h.p),
  }))

  return { stats, chartSeries }
}

// ---- 格式化 util（可獨立 export 供 003 sparkline 與卡片漲跌複用） ----

/** NT$9,990 千分位格式 */
export function formatPrice(n: number): string {
  return n.toLocaleString('zh-TW')
}

/** 漲跌金額標籤：diff<0 → 「降價 NT$510」；diff>0 → 「漲價 NT$100」 */
export function formatDiffAmount(diff: number): string

/** 漲跌百分比標籤：帶符號 1 位小數，「-4.9%」／「+5.3%」 */
export function formatDiffPercent(diff: number, previous: number): string

/** 完整漲跌標籤（view 直接使用）：降價 NT$510（-4.9%）／漲價 NT$100（+5.3%）／持平 */
export function formatTrendLabel(diff: number, previous: number): string
```

### 2.5 `PriceTrendChart` — ECharts 趨勢圖元件

**職責**：將 `history` 渲染為折線圖，負責 ECharts 全部圖表層互動；不持有可能跨元件共享的狀態（純 props → option 渲染）。

**Props / Emits**：

```typescript
export interface Props {
  history: PricePoint[]      // 依 d 升冪；長度 ≥1（空歷史由 view 降級，不渲染本元件）
  targetPrice?: number | null  // 目標價；null/undefined = 不顯示 markLine
  yMin?: number                // Y 軸下限（view 依含目標價的範圍計算後傳入，見 §2.6）
  yMax?: number
}
// 無 emits；超出區間提示由 view 計算（見 §2.6）
```

**ECharts on-demand 整合**（`lib/echarts.ts`）：

```typescript
// lib/echarts.ts — 全站共用，避免重複註冊與 bundle 膨脹
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, DataZoomComponent,
  MarkLineComponent, LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart, GridComponent, TooltipComponent,
  DataZoomComponent, MarkLineComponent, LegendComponent, CanvasRenderer,
])

export default echarts
```

**Option 重點規格**：

| 項目 | 規格 |
|------|------|
| **非等間距 X 軸** | `xAxis.type = 'time'`：資料點依實際日期定位，長間隔如實留白、**不補點**（delta 序列僅異動時有值，如實呈現）。`axisLabel.formatter` 顯示 `MM-DD`；`tooltip` 用 formatter 顯示完整 `YYYY-MM-DD` 與價格。⚠️ 實測若資料點極稀疏造成過度留白（如 3 個月僅 2 點），可評估切換 `type:'category'` 以日期為類別，需於 code review 記錄決策 |
| **Y 軸** | `yAxis.type='value'`；`min/max` 由 view 傳入（含目標價擴展）；`axisLabel.formatter` → `NT$9,990` |
| **tooltip** | `trigger:'axis'`、`axisPointer:{type:'cross'}`；formatter 顯示「日期／價格」，若設有目標價一併顯示「目標價 NT$…」 |
| **dataZoom** | `[{type:'inside'}]`（滾輪／觸控拖曳縮放）；`[{type:'slider'}]` 僅在點數 ≥15 時 `show:true`，點數少時隱藏 |
| **markLine 目標價** | `series.markLine.data=[{yAxis: targetPrice}]`；`silent:true`、`symbol:'none'`、`lineStyle:{type:'dashed', color:'#f59e0b', width:1.5}`；label formatter → `目標價 NT$9,500`（見 §7 配色） |
| **單筆資料降級** | `history.length === 1`：仍渲染折線圖（單點），`symbolSize` 放大、開啟 `label` 顯示價格；停用 dataZoom；X 軸範圍以該日為中心。Y 軸正常含該價 |
| **resize** | 容器以 `ResizeObserver` 監聽，`chart.resize()`；`onUnmounted` 時 `chart.dispose()` |

```vue
<!-- PriceTrendChart.vue — <script setup> 骨架 -->
<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { ECharts } from 'echarts/core'
import echarts from '@/lib/echarts'
import type { PricePoint } from '@/types/item'

const props = defineProps<{
  history: PricePoint[]
  targetPrice?: number | null
  yMin?: number
  yMax?: number
}>()

const el = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null
let observer: ResizeObserver | null = null

function buildOption() {
  // xAxis: type 'time'；series: LineChart data = history.map(h => [h.d, h.p])
  // dataZoom: inside + (點數≥15 → slider)
  // markLine: props.targetPrice 存在時加入（label formatter: 目標價 NT${formatPrice(v)}）
  // yAxis min/max = props.yMin/yMax；tooltip formatter 顯示 YYYY-MM-DD 與價格
  // history.length===1 → 單點降級（symbolSize、label 顯示價格、無 dataZoom）
  // TODO: 組裝 EChartsOption
}

onMounted(() => {
  chart = echarts.init(el.value!)
  chart.setOption(buildOption())
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(el.value!)
})

watch(() => [props.history, props.targetPrice, props.yMin, props.yMax],
  () => chart?.setOption(buildOption(), { notMerge: true }))

onUnmounted(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>

<template>
  <div ref="el" class="price-trend-chart" :aria-label="'歷史價格趨勢圖'" role="img" />
</template>
```

### 2.6 `ProductDetailView` — 詳情頁整合

**路由**：`router/index.ts` 新增 `{ path: '/product/:id', name: 'product-detail', component: ProductDetailView }`（hash history，GitHub Pages 免 server rewrite）。id 含 `|`，003 跳轉時 `encodeURIComponent(item.id)`；讀取 `route.params.id` 後 `decodeURIComponent` 還原（vue-router 一般已解碼，防呆處理特殊字元）。

**四態狀態機**：

```
status(idle/loading) ──load──▶ error(network/parse) ──retry──▶ loading
        │                                    ▲
        └──────────── ready ─────────────────┘
                        ├─ items 找不到該 id → not-found（「找不到此商品」＋返回列表）
                        ├─ item.history 空     → 降級（規格＋目前價「—」＋「尚無歷史資料」）
                        ├─ item.history 1 筆   → 降級（首日追蹤＋單點圖）
                        └─ 正常                → 完整資訊＋趨勢圖＋目標價輸入
```

**頁面區塊**（由頂至底）：麵包屑／返回（保留 003 分類 context）→ 標題＋狀態 badge（gone 顯示「此商品已下架」）→ 價格摘要卡（目前價、漲跌、歷史最低＋日期、最後更新時間）→ 規格表 → 趨勢圖＋目標價輸入區 → 005 預留動作區（`WatchActions` 佔位）。

**規格表空值處理**：`Object.entries(spec)` 過濾掉 `value == null || value === ''`（含 `undefined`）；key 經 `SPEC_LABELS` 對照顯示中文（未知 key 顯示原始 key）。欄位順序維持物件鍵序（spec_parser 產出順序）。

```typescript
const SPEC_LABELS: Record<string, string> = {
  brand: '品牌', model: '型號', cores: '核心數', threads: '執行緒',
  base_ghz: '基礎時脈(GHz)', turbo_ghz: '超頻時脈(GHz)',
  tdp_w: '功耗 TDP(W)', socket: '腳位',
}
// 渲染：entries.filter(([,v]) => v != null && v !== '') → key 標籤化
```

**目標價互動（session 級，不寫入任何儲存）**：BDD「目標價僅本次瀏覽有效」——`targetPrice` 為 view 內 `ref`，離開路由即銷毀，重進需重輸。

```vue
<!-- ProductDetailView.vue — <script setup> 骨架 -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import SpecTable from '@/components/SpecTable.vue'
import PriceTrendChart from '@/components/PriceTrendChart.vue'
import WatchActions from '@/components/WatchActions.vue'
import { useItems } from '@/composables/useItems'
import { usePriceHistory } from '@/composables/usePriceHistory'
import { useCrawledAt } from '@/composables/useCrawledAt'
import { formatPrice } from '@/utils/format'      // 003 共用格式化（utils/format.ts）

const route = useRoute()
const { items, meta, loading, error, retry } = useItems()   // 003 契約：共用載入（含錯誤/重試）

const itemId = computed(() => decodeURIComponent(String(route.params.id)))
const item = computed(() => items.value.find((i) => i.id === itemId.value))
const notFound = computed(() => !loading.value && !error.value && !item.value)

// ---- 價格摘要（§2.4） ----
const history = computed(() => item.value?.history ?? [])
const { stats } = usePriceHistory(history)

// ---- 最後更新時間（台北時區）與過期判斷（與 003 共用 useCrawledAt） ----
const { updatedLabel, isStale } = useCrawledAt(() => data.value?.meta.crawled_at)

// ---- 目標價（session 級） ----
const targetInput = ref('')
const targetPrice = ref<number | null>(null)
const targetError = ref('')              // 驗證訊息；非空 → 輸入框紅框
const targetOutOfRange = ref(false)      // 超出歷史區間提示

const histMin = computed(() => stats.value.low)
const histMax = computed(() => (history.value.length ? Math.max(...history.value.map((h) => h.p)) : null))

// Y 軸範圍：納入目標價後自動擴展（BDD @edge-case：9,000 超出 9,990~11,500 仍套用且軸擴展）
const yMin = computed(() => Math.min(histMin.value ?? 0, targetPrice.value ?? Infinity) * 0.98)
const yMax = computed(() => Math.max(histMax.value ?? 0, targetPrice.value ?? 0) * 1.02)

/** 驗證與套用目標價（BDD @edge-case 四組範例）：
 *  空白 → 「請輸入目標價」；非數字(abc) → 「請輸入有效數字」；
 *  0 / -100 → 「請輸入大於 0 的有效數字」；通過 → targetPrice 套用、targetError 清空 */
function applyTarget(): void {
  const raw = targetInput.value.trim()
  if (raw === '') { targetError.value = '請輸入目標價'; return }
  const v = Number(raw)
  if (!Number.isFinite(v)) { targetError.value = '請輸入有效數字'; return }
  if (v <= 0) { targetError.value = '請輸入大於 0 的有效數字'; return }
  targetPrice.value = v
  targetError.value = ''
  targetOutOfRange.value = v < (histMin.value ?? v) || v > (histMax.value ?? v)
}

function clearTarget(): void { targetPrice.value = null; targetInput.value = ''; targetOutOfRange.value = false }
</script>

<template>
  <!-- loading → skeleton；error → 「資料載入失敗」＋「重新載入」(retry) -->
  <!-- notFound → 「找不到此商品」＋返回列表連結 -->
  <!-- stats.empty → 規格＋目前價「—」＋「尚無歷史資料」 -->
  <!-- 正常 → 完整版面：breadcrumb／title(＋下架 badge)／價格摘要／SpecTable／PriceTrendChart＋目標價輸入／WatchActions -->
</template>
```

**最後更新時間**（`useCrawledAt`）：`meta.crawled_at`（UTC ISO）轉台北時區顯示 `2026-08-15 14:00（台北時間）`；距今 > 7 天顯示「資料可能已過期」提示（與 003 `isStale`／007 `useDataFreshness` 共用同一過期規則，見 007 §6.4）。

---

## 6. 邊界條件處理

來源：BDD `@error-handling` / `@edge-case` / `@business-rule` + Tech Decision 取捨。降級原則：**任何資料不足都不產生白畫面與未捕捉例外**。

| # | 情境（BDD 來源） | 行為 | 對應規格 |
|---|------------------|------|----------|
| E1 | items.json 載入失敗（網路／伺服器）`@error-handling @p0 @e2e` | 全頁顯示「資料載入失敗」＋「重新載入」按鈕；點擊後重新 fetch，成功即恢復詳情頁；失敗停留錯誤畫面並可返回列表 | §2.3 `useItems.retry` |
| E2 | items.json JSON 解析失敗（截斷）`@error-handling`（與 003 同源） | 顯示「資料格式錯誤」，不白畫面；與 003 列表頁共用同一 error 呈現 | §2.3 `error='parse'` |
| E3 | 無效商品 id 直接進入（deep link／id 格式錯誤）`@error-handling @p0` | 顯示「找不到此商品」＋「返回列表」連結 | §2.6 `notFound` |
| E4 | history 為空 `@error-handling @p1` | 顯示規格＋目前價格顯示「—」（目前價取自最後一筆，空則無值可顯示）；不顯示趨勢圖與漲跌；顯示「尚無歷史資料」 | §2.4 `stats.empty`、§2.6 |
| E5 | history 僅一筆（首日追蹤）`@edge-case @p1` | 顯示「首日追蹤，尚無漲跌比較」；歷史最低＝目前價（日期即該日）；趨勢圖單點顯示 | §2.4 `stats.single`、§2.5 單點降級 |
| E6 | 目標價輸入驗證（0／-100／abc／空白）`@edge-case @p1` | 不套用 markLine；輸入框紅框＋對應提示：`請輸入大於 0 的有效數字`／`請輸入有效數字`／`請輸入目標價` | §2.6 `applyTarget` |
| E7 | 目標價超出歷史區間 `@edge-case @p2` | 仍套用 markLine；`yMin/yMax` 擴展納入目標價；顯示提示「目標價超出歷史區間」 | §2.6 `targetOutOfRange`、`yMin/yMax` |
| E8 | 漲跌計算三態 `@edge-case @business-rule @p1` | 降價 綠 ▼ `降價 NT$510（-4.9%）`／漲價 紅 ▲ `漲價 NT$100（+5.3%）`／持平 灰 — `持平`；百分比 1 位小數 | §2.4 |
| E9 | 歷史最低多日相同 `@edge-case @p2` | 取最早達成日（升冪第一個 min 點） | §2.4 `lowDate` |
| E10 | 規格空值欄位 `@business-rule @p1` | 空值（null/undefined/''）欄位整列不渲染，其餘正常顯示 | §2.6 SPEC_LABELS filter |
| E11 | 最後更新時間 `@business-rule @p2` | `crawled_at` → `2026-08-15 14:00（台北時間）`；> 7 天加過期提示（與 007 共用規則） | §2.6 `useCrawledAt` |
| E12 | 目標價僅本次瀏覽有效 `@business-rule @p2` | session 級 `ref`，路由離開即銷毀；重進需重輸，不做任何持久化（005 整合前） | §2.6 `targetPrice` |
| E13 | 商品已下架（status=gone）`@edge-case @business-rule @p2` | 顯示「此商品已下架」badge；既有歷史趨勢圖與價格資訊照常顯示 | §2.6 badge |
| E14 | 非等間距歷史（delta 長間隔） | time 軸如實呈現不補點；tooltip 顯示實際日期；極稀疏時依 §2.5 評估 category 軸 | §2.5 |
| E15 | id 含特殊字元（`\|`）deep link | 跳轉 encode、讀取 decode；找不到走 E3 | §2.6 |
| E16 | 圖表容器 0 寬（頁面未渲染完成／窄螢幕） | `init` 前確認容器尺寸；ResizeObserver 觸發 resize；避免 init 時 0 尺寸 | §2.5 |

---

## 7. CSS 關鍵樣式

樣式採 scoped SFC（`<style scoped>`）+ 少數全域 class；設計 token 與 003 一致（間距 4px 基數、圓角 8px、卡片陰影）。

```css
/* ProductDetailView.vue scoped — 詳情頁布局 */
.detail-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px 16px 64px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.detail-breadcrumb {
  font-size: 13px;
  color: var(--color-text-muted);          /* 返回列表：保留 003 分類 context（query 回帶） */
}
.detail-title {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.4;
  display: flex;
  align-items: center;
  gap: 12px;
}
.badge-gone {
  background: #fef2f2; color: #b91c1c;      /* 下架 badge：淺紅底深紅字 */
  border: 1px solid #fecaca;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
}

/* 價格摘要卡 */
.price-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); /* RWD 自動折欄 */
  gap: 16px;
  background: var(--color-surface);          /* 白卡 */
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px;
}
.price-current { font-size: 28px; font-weight: 800; }
.price-change--down { color: #16a34a; }      /* 降價：綠 ▼ */
.price-change--up   { color: #dc2626; }      /* 漲價：紅 ▲ */
.price-change--flat { color: #6b7280; }      /* 持平：灰 — */
.price-low { font-size: 14px; color: var(--color-text-muted); }

/* 規格表：兩欄 grid、空值欄位不渲染 */
.spec-table {
  display: grid;
  grid-template-columns: 140px 1fr;          /* 欄位名：值 */
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}
.spec-key {
  background: var(--color-surface-muted);    /* 欄位名淺底 */
  padding: 8px 14px; font-size: 13px;
  color: var(--color-text-muted);
  border-bottom: 1px solid var(--color-border);
}
.spec-value {
  padding: 8px 14px; font-size: 14px;
  border-bottom: 1px solid var(--color-border);
}

/* 目標價輸入：錯誤紅框 */
.target-form { display: flex; gap: 8px; align-items: center; }
.target-input { width: 160px; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; }
.target-input.is-error { border-color: #dc2626; box-shadow: 0 0 0 2px rgba(220, 38, 38, .15); }
.target-error { color: #dc2626; font-size: 13px; }
.hint-out-of-range { color: #d97706; font-size: 13px; }   /* 目標價超出歷史區間 */

/* 錯誤／空狀態（與 003 共用樣式語義） */
.state-error, .state-empty { text-align: center; padding: 48px 16px; color: var(--color-text-muted); }
.retry-btn { /* 「重新載入」按鈕：主按鈕樣式，與 003 一致 */ }

/* 趨勢圖容器 */
.price-trend-chart { width: 100%; height: 360px; }
```

**markLine 目標價樣式**：目標價線為 ECharts 圖表內繪製（option `lineStyle`，非 CSS）：`dashed #f59e0b` 琥珀色橫線＋標籤「目標價 NT$9,500」（底色白字琥珀、12px、圓角）；與降價綠／漲價紅區別（目標價是「期望線」，非漲跌語意）。若需覆寫 ECharts 標籤文字外觀，以 `:deep(.echarts-mark-line-label)` 精準覆蓋，不影響其他 series。

---

## 8. 開發順序（DAG）

| 步驟 | 任務 | 依賴 | 產出／驗收 |
|------|------|------|-----------|
| 1 | 前端骨架：Vite 6 + Vue 3.5 + TS + vue-router（hash history）+ 安裝 `echarts`；`data/items.json` fixture 放置於 `web/public/data/` | - | `npm run dev` 可跑、路由可切換 |
| 2 | `types/item.ts` 型別 + `lib/echarts.ts` on-demand 註冊 + `useItems` 載入（network/parse 錯誤、retry；003 契約） | #1 | fixture 載入；斷網情境顯示錯誤可重試 |
| 3 | `usePriceHistory` composable（漲跌三態／歷史最低取最早／格式化）+ Vitest 單元測試（BDD E8、E9、E5 範例資料） | #2 | 測試全綠 |
| 4 | `PriceTrendChart` 元件：time 軸、tooltip、dataZoom、markLine、單點降級、resize | #2, #3 | 手動驗證縮放／懸停／單點 |
| 5 | `ProductDetailView`：路由 `/product/:id`、四態狀態機、`SpecTable`（空值隱藏）、價格摘要、`useCrawledAt` 更新時間 | #2, #3 | BDD happy path 主流程可用 |
| 6 | 目標價互動：`applyTarget` 驗證（4 組訊息）、markLine 套用／修改／清除、Y 軸擴展、超出區間提示 | #4, #5 | BDD 目標價三場景＋驗證範例 |
| 7 | 降級與錯誤畫面收尾：history 空／單筆、下架 badge、找不到商品、載入失敗畫面 | #5 | BDD E1–E5、E13 |
| 8 | 003 整合：列表卡片點擊 → `router.push`（encode id）、返回列表帶回分類 context、過期提示共用 | #5（含 003 列表） | 列表⇄詳情來回正確 |
| 9 | 005 整合點預留：`WatchActions` 佔位、傳遞 `item.id`（不實作追蹤功能） | #5 | 佔位渲染不報錯 |
| 10 | E2E（Playwright）覆蓋 `@e2e` 場景（列表點入檢視、目標價線、載入失敗重試）＋ RWD／樣式收尾 | #6–#9 | E2E 全綠 |

> DAG 驗證：依賴方向全部向前（2→3→4→5→6→7→8→9→10 主鏈），無後向依賴、無環。後端資料（001 crawler 產出 items.json）為部署期依賴，非本功能程式依賴。

---

## 附錄 A：BDD Scenario 覆蓋對照表

| BDD Scenario（tags） | 規格對應 |
|----------------------|----------|
| 從列表點入詳情頁並檢視完整資訊 `@happy-path @smoke @p0 @e2e` | §2.6 整合、§2.4 漲跌/最低、§2.5 圖表 |
| 設定目標價格線 `@happy-path @smoke @p1 @e2e` | §2.6 applyTarget、§2.5 markLine |
| 修改與清除目標價線 `@happy-path @p1` | §2.6（watch targetPrice → setOption notMerge）、clearTarget |
| items.json 載入失敗時顯示錯誤並可重試 `@error-handling @p0 @e2e` | §6 E1、§2.3 |
| 以無效商品 id 直接進入詳情頁 `@error-handling @p0` | §6 E3 |
| 商品尚無歷史資料 `@error-handling @p1` | §6 E4 |
| 目標價輸入驗證（4 組 Examples）`@edge-case @p1` | §6 E6、§2.6 applyTarget |
| 目標價超出歷史價格區間 `@edge-case @p2` | §6 E7 |
| 漲跌計算與呈現（3 組 Examples）`@edge-case @business-rule @p1` | §6 E8、§2.4 |
| 只有一筆歷史價格時的功能降級 `@edge-case @p1` | §6 E5、§2.5 單點 |
| 歷史最低價於多日相同時取最早日期 `@edge-case @p2` | §6 E9、§2.4 lowDate |
| 規格空值欄位不顯示 `@business-rule @p1` | §6 E10、§2.6 |
| 顯示資料最後更新時間 `@business-rule @p2` | §6 E11、§2.6 useCrawledAt |
| 目標價僅本次瀏覽有效 `@business-rule @p2` | §6 E12 |
| 商品已下架仍可檢視歷史 `@edge-case @business-rule @p2` | §6 E13 |

## 附錄 B：與相鄰功能整合點

| 相鄰功能 | 整合點 | 預留方式 |
|----------|--------|----------|
| 003 前端列表與搜尋篩選 | ①列表商品列點擊 → `/product/:id` 跳轉（整列可點）②返回列表保留分類 context ③共用 `useItems`／`useCrawledAt`／`types/item.ts` ④卡片漲跌顯示可複用 `formatTrendLabel` | §2.1／§2.3／§8 step 8 |
| 005 追蹤清單與比價 | 詳情頁「加入追蹤」「加入比價」按鈕區（005 BDD 以詳情頁為入口之一）；本功能僅提供 `WatchActions` 佔位與 `item.id` 傳遞，不實作追蹤邏輯 | §2.1 WatchActions／§8 step 9 |
