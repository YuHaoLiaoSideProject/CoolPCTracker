# dashboard-sparkline — 開發規格

> **技術棧**：Vue 3.5.13 · Vite 6.0.0 · TypeScript 5.6.3 · Vitest 3.2.4 · Playwright 1.62.1
> **Tech Decision**：`docs/tech-decisions/020-dashboard-sparkline.md`
> **操作流程**：`docs/interaction-flows/020-dashboard-sparkline.md`
> **BDD**：`docs/bdds/020-dashboard-sparkline.feature`
> **狀態**：✅ 已完成

---

## 概述

在商品卡片上顯示價格走勢 mini sparkline，讓使用者快速判斷價格趨勢（漲/跌/持平）。核心包含：

1. **Sparkline.vue 擴充**：新增 `trend` prop（趨勢動態著色）+ `enableTooltip` prop（hover tooltip）
2. **SparklineTooltip.vue 新增**：純展示 tooltip 子元件（日期 + 價格，absolute 定位）
3. **DashboardCard.vue 整合**：引入 Sparkline + `computePriceChange()` + `slice(-30)` 截斷
4. **ProductCard.vue 同步**：Sparkline 加入 `:trend` prop（同步受益）
5. **priceChange.ts**：已有 `computePriceChange()` 共用純函數，不需改動

---

## 1. 後端實作規格

**不適用**（純前端專案，無後端）

---

## 2. 前端實作規格

### 2.1 檔案改動總覽

```
web/src/
├── components/
│   ├── Sparkline.vue              ← 修改：新增 trend prop（著色）+ enableTooltip prop + hover handler
│   ├── SparklineTooltip.vue       ← 新增：純展示 tooltip 子元件（日期 + 價格，absolute 定位）
│   ├── DashboardCard.vue          ← 修改：引入 Sparkline + computePriceChange + slice(-30)
│   └── ProductCard.vue            ← 修改：Sparkline 加入 :trend prop
├── components/__tests__/
│   ├── Sparkline.test.ts          ← 修改：trend 著色 + tooltip 互動測試
│   ├── SparklineTooltip.test.ts   ← 新增：tooltip 渲染測試
│   ├── DashboardCard.test.ts      ← 修改：整合 sparkline 後的渲染測試
│   └── ProductCard.test.ts        ← 修改：trend prop 渲染測試
├── lib/
│   └── priceChange.ts             ← 不變（computePriceChange 已有 trend 判定）
├── composables/
│   └── usePriceDelta.ts           ← 不變
└── types/
    └── item.ts                    ← 不變（PriceTrend 已在 priceChange.ts）
```

### 2.2 Sparkline.vue — 擴充 trend 著色

**職責**：SVG 迷你趨勢圖渲染，支援趨勢動態著色（`trend` prop）與 hover tooltip（`enableTooltip` prop）。

```typescript
// props 與型別
interface SparklineProps {
  points: PricePoint[]              // 不變
  trend?: PriceTrend | null         // 【新增】趨勢 → 動態著色；null 時 fallback 為 var(--brand)
  enableTooltip?: boolean           // 【新增】啟用 hover tooltip（預設 false）
}
```

```typescript
// script setup 關鍵邏輯
const props = withDefaults(defineProps<SparklineProps>(), {
  trend: null,
  enableTooltip: false,
})

const hoveredIndex = ref<number | null>(null)
const hoveredX = ref<number>(0)  // tooltip 的 x 座標（%）

function onMouseMove(e: MouseEvent) {
  // 計算滑鼠相對 SVG 容器的 x 位置 → 對應 data point index
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const xPercent = ((e.clientX - rect.left) / rect.width) * 100
  hoveredX.value = xPercent
  hoveredIndex.value = Math.round((xPercent / 100) * (props.points.length - 1))
}

function onMouseLeave() {
  hoveredIndex.value = null
}

// 趨勢 → CSS class 對應
const trendClass = computed(() => {
  switch (props.trend) {
    case 'up': return 'sparkline--up'
    case 'down': return 'sparkline--down'
    case 'flat': return 'sparkline--flat'
    default: return ''  // fallback: var(--brand)
  }
})
```

```vue
<template>
  <div class="sparkline-container">
    <svg
      :class="['sparkline', trendClass]"
      viewBox="0 0 100 28"
      preserveAspectRatio="none"
      @mousemove="enableTooltip ? onMouseMove($event) : undefined"
      @mouseleave="enableTooltip ? onMouseLeave() : undefined"
    >
      <polyline
        v-if="points.length >= 2"
        :points="polylinePoints"
        fill="none"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
    <SparklineTooltip
      v-if="enableTooltip && hoveredIndex !== null && points[hoveredIndex]"
      :point="points[hoveredIndex]"
      :x="hoveredX"
    />
  </div>
</template>
```

> **向後相容**：`trend` 為 optional，不傳時保持 `var(--brand)` 原有行為。ProductCard 現有 `<Sparkline :points="sparkPoints" />` 不需改動即可繼續運作。

### 2.3 SparklineTooltip.vue — 純展示 tooltip 子元件

**職責**：在 hover 時顯示單一數據點的日期與價格。

```typescript
interface TooltipProps {
  point: PricePoint       // 資料點（d: string, p: number）
  x: number               // SVG 座標 x（%，0–100）
}
```

```vue
<template>
  <div
    class="sparkline-tooltip"
    :style="{ left: `${x}%`, transform: 'translateX(-50%)' }"
  >
    <span class="sparkline-tooltip__date">{{ point.d }}</span>
    <span class="sparkline-tooltip__price">NT${{ formatPrice(point.p) }}</span>
  </div>
</template>
```

樣式要點（詳見 §7 CSS 關鍵樣式）：
- `position: absolute`、`bottom: 100%`（向上彈出）
- `pointer-events: none`（不攔截 mouse 事件）
- `white-space: nowrap`、`z-index: 10`

### 2.4 DashboardCard.vue — 整合 Sparkline

**職責**：商品卡片，整合 Sparkline 顯示。

```typescript
// 新增 import
import Sparkline from "./Sparkline.vue"
import { computePriceChange } from "@/lib/priceChange"

// 新增 computed（在現有 computed 之後）
const sparkPoints = computed(() => props.item.history.slice(-30))
const sparkTrend = computed(() => computePriceChange(props.item.history).trend)
```

```html
<!-- template：在 .dc-price 區域，dc-current 之後加入 Sparkline -->
<div class="dc-price">
  <template v-if="item.status === 'gone'">
    <span class="dc-current dc-gone-text">已下架</span>
  </template>
  <template v-else>
    <span class="dc-current">{{ currentPrice != null ? formatPrice(currentPrice) : '—' }}</span>
    <Sparkline :points="sparkPoints" :trend="sparkTrend" :enable-tooltip="true" />
    <span v-if="lowestPrice != null && lowestPrice !== currentPrice" class="dc-history-low">
      歷史最低 {{ formatPrice(lowestPrice) }}
    </span>
  </template>
</div>
```

**資料處理**：
- `sparkPoints`：`item.history.slice(-30)` — 僅顯示最近 30 天資料（30 天截斷在呼叫端處理）
- `sparkTrend`：`computePriceChange(item.history).trend` — 基於最後兩筆計算趨勢
- 已下架商品（`item.status === 'gone'`）自然不顯示 Sparkline（在 `<template v-else>` 內）

### 2.5 ProductCard.vue — 同步 trend prop

**職責**：listing 頁商品卡片，同步受益於 Sparkline trend 著色。

```typescript
// 新增 import（在現有 import 之後）
import { computePriceChange } from "@/lib/priceChange"

// 新增 computed
const sparkTrend = computed(() => computePriceChange(props.item.history).trend)
```

```html
<!-- 修改 Sparkline 引入，加入 :trend prop -->
<Sparkline :points="sparkPoints" :trend="sparkTrend" />
```

> **不加 `enableTooltip`**：ProductCard 現有無 tooltip 行為，保持向後相容。後續可按需加入。

---

## 3. API 合約

**不適用**（無後端 API，純前端功能）

---

## 4. 資料流

前端內部資料流（Sparkline ← DashboardCard ← item.history）：

```
DashboardCard.vue
  │
  ├─ props.item.history (PricePoint[])
  │     │
  │     ├─ slice(-30) ──→ sparkPoints (PricePoint[])
  │     │                   │
  │     │                   └─→ <Sparkline :points="sparkPoints" />
  │     │
  │     └─ computePriceChange(history)
  │           │
  │           └─→ trend: PriceTrend ("up" | "down" | "flat" | null)
  │                   │
  │                   └─→ <Sparkline :trend="sparkTrend" />
  │
  └─ Sparkline.vue
        │
        ├─ trend prop → stroke CSS class (sparkline--up / sparkline--down / sparkline--flat)
        │
        └─ enableTooltip prop → hover handler → hoveredIndex (ref<number | null>)
              │
              └─→ <SparklineTooltip :point="points[hoveredIndex]" :x="hoveredX" />
```

**資料轉換步驟**：

| 步驟 | 觸發者 | 資料 | 性質 |
|------|--------|------|------|
| 1 | DashboardCard 載入 | `item.history`（全量 PricePoint[]） | 同步（props 傳入） |
| 2 | DashboardCard computed | `sparkPoints = history.slice(-30)` | 同步（computed） |
| 3 | DashboardCard computed | `sparkTrend = computePriceChange(history).trend` | 同步（computed） |
| 4 | Sparkline render | `polylinePoints`（由 points 轉 SVG座標） | 同步（computed） |
| 5 | Sparkline hover | `hoveredIndex`（滑鼠位置 → data point index） | 同步（DOM event） |
| 6 | SparklineTooltip render | `points[hoveredIndex]`（日期 + 價格） | 同步（computed） |

---

## 5. 生命週期

不適用（無連線管理、session 或狀態機；sparkline 為純展示元件，無獨立生命週期）

---

## 6. 邊界條件處理

| 情境 | 來源 | 處理方式 |
|------|------|---------|
| 商品無歷史資料（0 筆） | BDD @error-handling / IF §5 | Sparkline `v-else` 顯示「資料不足」文字 |
| 商品僅 1 點歷史資料 | BDD @error-handling / IF §5 | Sparkline `v-else`（`points.length < 2`）顯示「資料不足」文字 |
| 已下架商品 | BDD @error-handling / IF §2.3 | DashboardCard `v-if="item.status === 'gone'"` 不顯示 Sparkline，顯示「已下架」標籤 |
| 歷史資料跨多月（>30 天） | BDD @error-handling / IF §6 | 呼叫端 `slice(-30)` 截斷，僅顯示最近 30 天 |
| 恰好 2 筆歷史資料 | BDD @edge-case / IF §6 | `points.length >= 2` 成立，正常顯示 sparkline |
| 歷史資料全部相同價格 | BDD @edge-case / IF §6 | `computePriceChange()` 返回 `trend = "flat"`，sparkline 為灰色水平線 |
| 歷史資料恰好 31 天 | BDD @edge-case / IF §6 | `slice(-30)` 截斷第 1 天，僅顯示最近 30 天 |
| 價格從高到低再回升（V 型） | BDD @edge-case / IF §6 | sparkline polyline 直接反映實際座標變化，走勢呈現「下降→回升」 |
| Hover 在小螢幕（手機）無法觸發 | Tech Decision §7 風險 | tooltip 為 Nice-to-have；手機用戶可透過卡片詳情頁查看完整歷史；後續可選 `@touchstart` 支援 |
| Tooltip 在卡片邊界溢出 | Tech Decision §7 風險 | tooltip 加入 `max-width` + `overflow: hidden`；邊界點改為向內偏移 |

---

## 7. CSS 關鍵樣式

### 7.1 Sparkline 趨勢著色

| class | 樣式重點 |
|-------|---------|
| `.sparkline` | `width: 100%`、`height: auto`、`display: block`；stroke 預設 `var(--brand)` |
| `.sparkline--up` | `stroke: var(--price-up)`（紅色，價格上漲） |
| `.sparkline--down` | `stroke: var(--price-down)`（綠色，價格下跌） |
| `.sparkline--flat` | `stroke: var(--price-flat)`（灰色，價格持平） |
| `.sparkline-container` | `position: relative`、`display: inline-block`、`width: 100%`（tooltip 定位參考） |

### 7.2 Tooltip 樣式

| class | 樣式重點 |
|-------|---------|
| `.sparkline-tooltip` | `position: absolute`、`bottom: 100%`、`left: {x}%`、`transform: translateX(-50%)` |
| `.sparkline-tooltip` | `background: var(--surface)`、`border: 1px solid var(--border)`、`border-radius: var(--radius)` |
| `.sparkline-tooltip` | `padding: 4px 8px`、`font-size: 0.72rem`、`white-space: nowrap`、`pointer-events: none`、`z-index: 10` |
| `.sparkline-tooltip__date` | `color: var(--text-secondary)`、`margin-right: 4px` |
| `.sparkline-tooltip__price` | `color: var(--text-primary)`、`font-weight: 500` |

### 7.3 CSS Token 對照

| Token | 值（推斷） | 用途 |
|-------|-----------|------|
| `--price-up` | 紅色系 | 價格上漲 sparkline stroke |
| `--price-down` | 綠色系 | 價格下跌 sparkline stroke |
| `--price-flat` | 灰色系 | 價格持平 sparkline stroke |
| `--brand` | 品牌主色 | trend 為 null 時 fallback |
| `--surface` | 卡片背景色 | tooltip 背景 |
| `--border` | 邊框色 | tooltip 邊框 |
| `--radius` | 圓角值 | tooltip 圓角 |

### 7.4 CSS class 與 code skeleton 對應

code skeleton 中的 class binding 與上方 CSS class 一致：
- `<svg :class="['sparkline', trendClass]">` → `.sparkline` + `.sparkline--up/down/flat`
- `<div class="sparkline-container">` → `.sparkline-container`
- `<div class="sparkline-tooltip">` → `.sparkline-tooltip`

---

## 8. 開發順序

| 步驟 | 內容 | 檔案 | 依賴 |
|------|------|------|------|
| 1 | **Sparkline.vue 擴充 — trend 著色**：新增 `trend?: PriceTrend \| null` prop；依 trend 動態設定 stroke color（`up` → `var(--price-up)`、`down` → `var(--price-down)`、`flat` → `var(--price-flat)`、`null` → `var(--brand)` fallback）；新增 CSS class `sparkline--up` / `sparkline--down` / `sparkline--flat` | `components/Sparkline.vue`、`components/__tests__/Sparkline.test.ts` | — |
| 2 | **SparklineTooltip.vue 新增**：純展示子元件；props: `point: PricePoint` + `x: number`；template: `position: absolute` 的 div，顯示 `${point.d}  NT$${formatPrice(point.p)}`；定位：`left: ${x}%` + `transform: translateX(-50%)` + `bottom: 100%` | `components/SparklineTooltip.vue`、`components/__tests__/SparklineTooltip.test.ts` | — |
| 3 | **Sparkline.vue 擴充 — hover tooltip**：新增 `enableTooltip?: boolean` prop（預設 `false`）；新增 `hoveredIndex: ref<number \| null>(null)`；新增 `onMouseMove(e)` handler（計算滑鼠相對 SVG 容器的 x 位置 → 對應 data point index）；新增 `onMouseLeave()` handler；template：SVG 外包一層 `<div class="sparkline-container">`，hover 時渲染 `<SparklineTooltip>`；SVG 加入 `@mousemove` + `@mouseleave` | `components/Sparkline.vue`、`components/__tests__/Sparkline.test.ts` | #2 |
| 4 | **DashboardCard.vue 整合 Sparkline**：import `Sparkline` + `computePriceChange`；新增 computed `sparkPoints = item.history.slice(-30)`；新增 computed `sparkTrend = computePriceChange(item.history).trend`；template：在 `.dc-price` 區域加入 `<Sparkline :points="sparkPoints" :trend="sparkTrend" :enable-tooltip="true" />`；已下架商品自然不顯示 Sparkline（在 `<template v-else>` 內） | `components/DashboardCard.vue`、`components/__tests__/DashboardCard.test.ts` | #1, #3 |
| 5 | **ProductCard.vue 同步加入 trend prop**：Sparkline 加入 `:trend="sparkTrend"`；新增 computed `sparkTrend = computePriceChange(props.item.history).trend`；不加 `enableTooltip`（保持向後相容） | `components/ProductCard.vue`、`components/__tests__/ProductCard.test.ts` | #1 |
| 6 | **E2E 測試**：≥2 筆歷史資料的商品卡片顯示 sparkline；<2 筆顯示「資料不足」；已下架商品不顯示 sparkline；價格下跌顯示綠色線條；價格上漲顯示紅色線條；價格持平顯示灰色線條；Hover sparkline 顯示 tooltip（日期 + 價格）；移開 cursor 隱藏 tooltip；歷史資料跨多月時僅顯示最近 30 天；Sparkline 響應式縮放（隨卡片寬度） | `e2e/` 或 `playwright/` | #4 |

**DAG 依賴圖**：

```
#1 (Sparkline trend)  ──┬──→ #3 (Sparkline tooltip) ──→ #4 (DashboardCard 整合) ──→ #6 (E2E)
                        │
#2 (SparklineTooltip) ──┘
                        │
#1 (Sparkline trend) ──┼──→ #5 (ProductCard 同步)
```

**BDD Scenario 對照表**：

| BDD Scenario | 對應步驟 |
|-------------|---------|
| 有充足歷史資料的商品顯示 sparkline | #1, #4 |
| 價格下跌時 sparkline 顯示綠色線條 | #1 (trend="down" → sparkline--down) |
| 價格上漲時 sparkline 顯示紅色線條 | #1 (trend="up" → sparkline--up) |
| 價格持平时 sparkline 顯示灰色線條 | #1 (trend="flat" → sparkline--flat) |
| Hover sparkline 顯示 tooltip | #3, #4 |
| 移開 cursor 後 tooltip 隱藏 | #3 (onMouseLeave) |
| 商品無歷史資料顯示「資料不足」 | #1 (points.length < 2 → v-else) |
| 商品僅 1 點歷史資料顯示「資料不足」 | #1 (points.length < 2 → v-else) |
| 已下架商品不顯示 sparkline | #4 (v-if="item.status === 'gone'") |
| 歷史資料跨多月時僅顯示最近 30 天 | #4 (slice(-30)) |
| 恰好 2 筆歷史資料時顯示 sparkline | #1 (points.length >= 2) |
| 歷史資料全部相同價格時為灰色水平線 | #1 (trend="flat") |
| 歷史資料恰好 31 天時第 1 天被截斷 | #4 (slice(-30)) |
| 價格從高到低再回升的走勢正確 | #1 (polyline 直接反映座標) |
| 趨勢顏色與 trend 型別對應（Scenario Outline） | #1 |
| 資料筆數決定 sparkline 顯示模式（Scenario Outline） | #1, #4 |
| 已下架商品不顯示 sparkline 且顯示「已下架」標籤 | #4 |
| Sparkline 響應式縮放隨卡片寬度 | #1 (viewBox 100×28, width 100%) |
| 價格資料僅繪製最近 30 天 | #4 (slice(-30)) |

---

## 9. 基礎架構設定

**不適用**（純前端專案，無 Nginx/systemd 設定需求）
