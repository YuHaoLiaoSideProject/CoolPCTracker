# 開發方案決策文件：#020 Dashboard — Sparkline 整合與擴充

> **性質**：前端功能層技術評估（tech-assessment-generator 引導，非互動模式產出）
> **對應**：GitHub Issue **#20** `feat(P1): Dashboard — 查看價格走勢（sparkline）`
> **範圍**：`web/src/`（擴充 Sparkline.vue 趨勢著色 + tooltip、DashboardCard.vue 整合 Sparkline）
> **上游文件**：`docs/interaction-flows/020-dashboard-sparkline.md`（主輸入）、`docs/tech-decisions/018-dashboard-groups.md`（同功能群參考）
> **決策方式**：基於上游文件 + 現有專案架構推導，**不提問**；所有決策點由評估者給定推薦結論，待實作前的 spec/review 階段正式確認

---

## 📌 決策摘要

| 項目 | 內容 |
|------|------|
| **最終方案** | **方案 A「擴充 Sparkline.vue + Tooltip 子元件 + DashboardCard 整合」**：Sparkline.vue 新增 `trend` prop（趨勢著色）、`enableTooltip` prop（hover tooltip）；新增 `SparklineTooltip.vue` 純展示子元件；DashboardCard.vue 引入 Sparkline（`slice(-30)` 截斷 + `computePriceChange` trend 傳入）；ProductCard.vue 同步擴充 trend prop |
| **決策日期** | 2026-08-17 |
| **決策前提** | ① Sparkline.vue 已存在（SVG polyline，viewBox 100×28）；② DashboardCard.vue 已存在（017 建立）；③ ProductCard.vue 已整合 Sparkline 但無 trend prop；④ `computePriceChange()` 已實作 trend 判定；⑤ CSS tokens 已定義 `--price-up`（紅）、`--price-down`（綠）、`--price-flat`（灰） |
| **核心效益** | 最小改動量（擴充現有元件而非重寫）；Sparkline 趨勢著色 + tooltip 可跨 DashboardCard / ProductCard 複用；tooltip 為純展示子元件，易測試 |
| **共識程度** | ✅ 非互動推導，共識待 spec/review 階段確認（§6.3） |

---

## 1. 需求回顧

### 1.1 使用者／Issue 訴求

> 「在商品卡片上顯示價格走勢 mini sparkline，讓使用者快速判斷價格趨勢（漲/跌/持平）。」

**拆解出的核心需求**：

| 需求項 | 說明 | 來源 |
|--------|------|------|
| Sparkline 整合至 DashboardCard | 卡片內顯示 sparkline | IF §4 步驟 1–2 |
| 趨勢顏色 | 綠色（下跌）/ 紅色（上漲）/ 灰色（持平） | IF §3 步驟 TrendType |
| Hover tooltip | 顯示日期 + 價格（精確到該數據點） | IF §4 步驟 3 |
| 30 天資料截斷 | 僅顯示最近 30 天資料 | IF §6 邊界限制 |
| 資料不足處理 | <2 筆顯示「資料不足」文字 | IF §5 異常處理 |
| 已下架商品 | 不顯示 sparkline | IF §2.3 顯示條件 |

### 1.2 需求假設（評估者由上游文件與現況推導）

| 假設 | 內容 | 依據 |
|------|------|------|
| H1 | Sparkline 擴充 trend prop 後，ProductCard.vue 可同步受益（目前 ProductCard 已引入 Sparkline 但無 trend） | IF §8 ProductCard 參考 |
| H2 | Tooltip 為純展示子元件，狀態由 Sparkline 管理（hover index → tooltip position） | IF §4 步驟 3「顯示 tooltip，包含日期 + 價格」 |
| H3 | 30 天截斷在呼叫端（DashboardCard / ProductCard）處理，不在 Sparkline 內部處理 | IF §8「Sparkline 本身無，需 call site 處理」；與 ProductCard L24 `slice(-30)` 一致 |
| H4 | Trend 計算直接複用 `computePriceChange()`，不需要新的 composable | IF §8 已有可複用模組 |
| H5 | Tooltip 不需要錨點追蹤（不追蹤最近數據點），而是在 hover 時顯示所有點的日期 + 價格 | IF §4 步驟 3「顯示 tooltip，包含日期 + 價格」 |
| H6 | 已下架商品不顯示 sparkline 由 DashboardCard 控制（`v-if="item.status !== 'gone'"`），Sparkline 不需處理此邏輯 | IF §2.3 顯示條件 |

### 1.3 非需求

- ❌ 不需要 sparkline 動畫（ polyline 無需 transition）
- ❌ 不需要 sparkline 點擊事件（tooltip 為 hover-only）
- ❌ 不需要可配置的 30 天範圍（硬編碼 30 天即可）
- ❌ 不需要 tooltip 自訂格式（固定日期 + 價格）
- ❌ 不需要 sparkline 面積填充（ polyline 無 fill）

---

## 2. 現況分析

### 2.1 現有 Sparkline.vue 狀態

| 項目 | 現狀 | 需改動 |
|------|------|--------|
| 輸入 | `points: PricePoint[]` | 不變 |
| 趨勢著色 | `stroke: var(--brand)` 統一色 | → 新增 `trend` prop，依 trend 動態著色 |
| Tooltip | 無 | → 新增 hover handler + `SparklineTooltip` 子元件 |
| 資料截斷 | 無（直接畫所有 points） | → 不變（由呼叫端 `slice(-30)` 處理） |
| 尺寸 | `viewBox 0 0 100 28`，width 100% | 不變 |
| 空資料 | `v-else` 顯示「資料不足」文字 | 不變 |

### 2.2 現有 DashboardCard.vue 狀態

| 項目 | 現狀 | 需改動 |
|------|------|--------|
| Sparkline 引入 | ❌ 未引入 | → 引入 Sparkline + 計算 sparkPoints + trend |
| 價格顯示 | `dc-current` + `dc-history-low` | → 在價格旁加入 Sparkline（與 ProductCard 佈局對齊） |
| 已下架處理 | `v-if="item.status === 'gone'"` 隱藏價格 | → 已下架不顯示 Sparkline（IF §2.3） |
| 30 天截斷 | 無 | → `item.history.slice(-30)` |

### 2.3 現有 ProductCard.vue 狀態

| 項目 | 現狀 | 需改動 |
|------|------|--------|
| Sparkline 引入 | ✅ 已引入（`<Sparkline :points="sparkPoints" />`） | → 加入 `:trend` prop |
| 30 天截斷 | ✅ 已實作（`item.history.slice(-30)`） | 不變 |
| 趨勢著色 | ❌ Sparkline 無 trend prop | → Sparkline 擴充後同步受益 |

### 2.4 已有可複用模組

| 模組 | 檔案 | 可用於 |
|------|------|--------|
| `computePriceChange()` | `lib/priceChange.ts` | Trend 判定（`trend: "up" | "down" | "flat" | null`） |
| `priceChangeBadgeClass()` | `lib/priceChange.ts` | 趨勢 CSS class 對應（`price-up` / `price-down` / `price-flat`） |
| `usePriceDelta()` | `composables/usePriceDelta.ts` | 卡片漲跌狀態（已有 `deltaClass` / `deltaText`） |
| `PriceTrend` type | `lib/priceChange.ts` | `"up" | "down" | "flat" | null` — 可直接作為 Sparkline 的 trend prop 型別 |
| `PricePoint` type | `types/item.ts` | `d: string, p: number` — tooltip 資料來源 |
| CSS tokens | `styles/tokens.css` | `--price-up`（紅）、`--price-down`（綠）、`--price-flat`（灰） |

---

## 3. 候選方案

### 方案 A（推薦）：擴充 Sparkline.vue + Tooltip 子元件 + DashboardCard 整合

**架構**：
```
components/
  Sparkline.vue              # 【擴充】新增 trend prop（著色）+ hover handler + SparklineTooltip 引入
  SparklineTooltip.vue       # 【新增】純展示 tooltip 子元件（日期 + 價格，absolute 定位）
  DashboardCard.vue          # 【擴充】引入 Sparkline + computePriceChange + slice(-30)
  ProductCard.vue            # 【微調】Sparkline 加入 :trend prop（同步受益）
```

**Sparkline.vue 擴充介面**：
```typescript
// 新增 props
interface SparklineProps {
  points: PricePoint[]              // 不變
  trend?: PriceTrend | null         // 【新增】趨勢 → 動態著色
  enableTooltip?: boolean           // 【新增】啟用 hover tooltip（預設 false）
}

// 新增 emit（可選，若 tooltip 需向外通知）
// 無需 emit（tooltip 為純展示）

// hover handler
const hoveredIndex = ref<number | null>(null)
function onMouseMove(e: MouseEvent) { /* 計算 hover 對應的 data point index */ }
function onMouseLeave() { hoveredIndex.value = null }
```

**SparklineTooltip.vue**：
```typescript
// 純展示子元件
interface TooltipProps {
  point: PricePoint       // 資料點
  x: number               // SVG 座標 x（% 或 px）
}

// template: absolute 定位的 tooltip div，顯示 `${point.d}  NT$${formatPrice(point.p)}`
```

**DashboardCard 整合**：
```typescript
// 新增 import
import Sparkline from "./Sparkline.vue"
import { computePriceChange } from "@/lib/priceChange"

// 新增 computed
const sparkPoints = computed(() => props.item.history.slice(-30))
const sparkTrend = computed(() => computePriceChange(props.item.history).trend)
```

**template 佈局**（在 `.dc-price` 區域）：
```html
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

**資料流**：
```
DashboardCard.vue
  → props.item.history (PricePoint[])
  → slice(-30) → sparkPoints (PricePoint[])
  → computePriceChange(history) → trend (PriceTrend)
  → <Sparkline :points="sparkPoints" :trend="trend" :enable-tooltip="true" />
    → Sparkline.vue
      → trend prop → stroke CSS class (price-up / price-down / price-flat)
      → enableTooltip → hover handler → hoveredIndex → <SparklineTooltip>
```

### 方案 B（保守）：仅整合 Sparkline，不擴充 tooltip

僅在 DashboardCard 引入 Sparkline（傳入 trend prop），不新增 tooltip 功能。

- **優點**：改動量最小；tooltip 為 Nice-to-have（IF §4 步驟 3 稱「選用」）
- **缺點**：
  - 未滿足 IF §4 步驟 3 的 tooltip 需求
  - Sparkline 擴充 trend prop 後，若後續加 tooltip 需再次改動 Sparkline
  - ProductCard 同樣無 tooltip（功能不一致）
- 結論：功能不完整，不推薦

### 方案 C（激進）：Sparkline 內建 30 天截斷 + trend 計算

將 `slice(-30)` 和 `computePriceChange()` 邏輯全部移入 Sparkline.vue，Sparkline 自行負責截斷和趨勢計算。

- **優點**：呼叫端更簡單（只需傳 `item.history`，不需自行截斷和計算 trend）
- **缺點**：
  - Sparkline 需要 `history` 全量資料（而非截斷後的 points）來計算 trend
  - 與 ProductCard 現有 pattern 衝突（ProductCard 已在外部 `slice(-30)`）
  - Sparkline 職責膨脹（SVG 渲染 + 資料截斷 + 趨勢計算）
  - Sparkline 無法得知「30 天」這個業務規則（與 SF 違反）
- 結論：SRP 違反，違反 IF §8「截斷未實作（Sparkline 本身無，需 call site 處理）」

---

## 4. 權衡評估

### 4.1 權衡矩陣（1–5 分，5 最佳）

| 維度 | B 仅整合無 tooltip | **A 擴充+tooltip** | C Sparkline 內建截斷 |
|---|:---:|:---:|:---:|
| 🎯 需求符合度 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| ⚡ 開發速度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 🔧 維護成本 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 🧩 模組化/可測試性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 🔄 複用性（跨元件） | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 👥 團隊熟悉度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 📦 效能 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **總分** | **27** | **33** | **22** |

### 4.2 關鍵取捨

**取捨 #1：Tooltip 是否實作**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）實作 tooltip（hover 顯示日期 + 價格） | 完整滿足 IF §4 步驟 3 | ✅ **選 A** |
| B）不實作 tooltip | 省工時，但功能不完整 | ❌ 不推薦 |

**決策（D1）：實作 tooltip**
- IF §4 步驟 3 明確描述「hover sparkline 顯示 tooltip（日期 + 價格）」
- Tooltip 為純展示子元件（`SparklineTooltip.vue`），實作成本低（~50 行）
- 與 ProductCard 保持功能一致性（兩種卡片都有 tooltip）

**取捨 #2：Sparkline 擴充方式**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）擴充現有 Sparkline.vue（新增 trend + tooltip） | 向後相容（新 prop 皆 optional） | ✅ **選 A** |
| B）新建 SparklineV2.vue | 不改動舊元件，但增加重複代碼 | ❌ 不推薦 |

**決策（D2）：擴充現有 Sparkline.vue**
- 新增的 `trend` 和 `enableTooltip` prop 皆為 optional（預設值保持現有行為）
- ProductCard 現有 `<Sparkline :points="sparkPoints" />` 不需改動即可繼續運作
- 只有一個 Sparkline 元件，避免「哪個版本？」的混淆

**取捨 #3：Tooltip 資料來源**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）Sparkline 內部管理 hover state + tooltip | hoveredIndex 由 Sparkline 內 ref 管理 | ✅ **選 A** |
| B）外部管理 hover state（emit mouseover event） | DashboardCard / ProductCard 管理 tooltip 狀態 | ❌ 過度耦合 |

**決策（D3）：Sparkline 內部管理**
- Tooltip 為 Sparkline 的展示細節，不應洩漏到外部
- hoveredIndex 為 Sparkline 內部 ref，外部無需知曉
- 與 Sparkline 的 SVG 座標計算緊耦合（hover 位置 → data point index）

**取捨 #4：Tooltip 位置策略**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）absolute 定位於 SVG 容器內，跟隨 hovered data point x 座標 | 精確對齊數據點 | ✅ **選 A** |
| B）fixed 定位於 viewport（tooltip 跟隨滑鼠） | 不需計算 SVG 座標 | ❌ tooltip 與數據點脫節 |

**決策（D4）：absolute 定位於 SVG 容器內**
- Tooltip 精確對齊 hovered data point 的 x 座標
- SVG 容器需 `position: relative`（或由 `sparkline` class 控制）
- tooltip 在卡片邊界內自動限制（避免溢出）

**取捨 #5：30 天截斷位置**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）呼叫端（DashboardCard / ProductCard）`slice(-30)` | 與 ProductCard 現有 pattern 一致 | ✅ **選 A** |
| B）Sparkline 內部截斷 | 呼叫端更簡單，但 Sparkline 職責膨脹 | ❌ SRP 違反 |

**決策（D5）：呼叫端截斷**
- 與 ProductCard L24 `item.history.slice(-30)` 完全一致
- Sparkline 保持「純渲染」職責（接收 points → 畫 SVG）
- 「30 天」為業務規則，不應嵌入通用元件

**取捨 #6：Trend 計算位置**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）呼叫端計算 trend，傳入 Sparkline | Sparkline 為純展示（接收 trend → 着色） | ✅ **選 A** |
| B）Sparkline 內部計算 trend（需全量 history） | Sparkline 需多一個 `allHistory` prop | ❌ 與 C 方案相同問題 |

**決策（D6）：呼叫端計算 trend**
- `computePriceChange()` 已有，呼叫端直接呼叫即可
- Sparkline 只接收 `trend: PriceTrend`，不需知道 history 全量
- 與 IF §8「Trend 計算來源：基於最後兩筆；`priceChange.ts` 已實作 `computePriceChange()`」一致

---

## 5. 決策理由

### 5.1 為什麼選方案 A
1. **最小改動量，最大複用性**：擴充現有 Sparkline.vue（新增 optional props），DashboardCard / ProductCard 同步受益；tooltip 為純展示子元件，~50 行代碼
2. **完全滿足 IF 需求**：趨勢顏色（D2/D6）+ hover tooltip（D1/D3/D4）+ 30 天截斷（D5）+ 資料不足處理（Sparkline 現有 `v-else`）
3. **符合專案既有 pattern**：Sparkline 為純展示元件（接收 props → 渲染 SVG）；trend 計算由 `computePriceChange()` 處理；30 天截斷由呼叫端 `slice(-30)` 處理（ProductCard L24 已有先例）

### 5.2 為什麼放棄其他方案
| 方案 | 放棄理由 |
|---|---|
| **B 仅整合無 tooltip** | 功能不完整：IF §4 步驟 3 明確要求 tooltip；tooltip 為純展示子元件，實作成本低，不值得省略 |
| **C Sparkline 內建截斷** | SRP 違反：Sparkline 為通用 SVG 渲染元件，不應嵌入「30 天」業務規則；與 ProductCard 現有 pattern 衝突（ProductCard 已在外部 `slice(-30)`） |

---

## 6. 行動計畫

### 6.1 目標架構

```
web/src/
  components/
    Sparkline.vue              # 【擴充】新增 trend prop（著色）+ enableTooltip prop + hover handler
    SparklineTooltip.vue       # 【新增】純展示 tooltip 子元件（日期 + 價格，absolute 定位）
    DashboardCard.vue          # 【擴充】引入 Sparkline + computePriceChange + slice(-30)
    ProductCard.vue            # 【微調】Sparkline 加入 :trend prop
  lib/
    priceChange.ts             # 不變（computePriceChange 已有 trend 判定）
  composables/
    usePriceDelta.ts           # 不變
  types/
    item.ts                    # 不變（PriceTrend 已在 priceChange.ts）
```

### 6.2 任務拆分

| # | 任務 | 檔案 | 依賴 |
|---|------|------|------|
| T1 | **Sparkline.vue 擴充 — trend 著色**：新增 `trend?: PriceTrend \| null` prop；依 trend 動態設定 stroke color：`"up"` → `var(--price-up)`、`"down"` → `var(--price-down)`、`"flat"` → `var(--price-flat)`、`null` → `var(--brand)`（fallback）；新增 CSS class `sparkline--up` / `sparkline--down` / `sparkline--flat`；**向後相容**：trend 為 optional，不傳時保持 `var(--brand)` | `components/Sparkline.vue`、`components/__tests__/Sparkline.test.ts` | — |
| T2 | **SparklineTooltip.vue 新增**：純展示子元件；props: `point: PricePoint` + `x: number`（SVG 座標 x，0–100）；template: `position: absolute` 的 div，顯示 `${point.d}  NT$${formatPrice(point.p)}`；定位：`left: ${x}%` + `transform: translateX(-50%)` + `bottom: 100%`（向上彈出）；樣式：`background: var(--surface)` + `border: 1px solid var(--border)` + `border-radius: var(--radius)` + `padding: 4px 8px` + `font-size: 0.72rem` + `white-space: nowrap` + `pointer-events: none` + `z-index: 10` | `components/SparklineTooltip.vue`、`components/__tests__/SparklineTooltip.test.ts` | — |
| T3 | **Sparkline.vue 擴充 — hover tooltip**：新增 `enableTooltip?: boolean` prop（預設 `false`）；新增 `hoveredIndex: ref<number \| null>(null)`；新增 `onMouseMove(e: MouseEvent)` handler：計算滑鼠相對 SVG 容器的 x 位置 → 對應 data point index（`Math.round((xPercent / 100) * (points.length - 1))`）→ 設定 `hoveredIndex`；新增 `onMouseLeave()` handler：`hoveredIndex.value = null`；template：SVG 外包一層 `<div class="sparkline-container" style="position: relative">`，hover 時渲染 `<SparklineTooltip :point="points[hoveredIndex]" :x="hoverX" />`；SVG 加入 `@mousemove="onMouseMove"` + `@mouseleave="onMouseLeave"`；SVG 設定 `pointer-events: all`（hover 可觸發） | `components/Sparkline.vue`、`components/__tests__/Sparkline.test.ts` | T2 |
| T4 | **DashboardCard.vue 整合 Sparkline**：import `Sparkline` + `computePriceChange`；新增 computed `sparkPoints = computed(() => props.item.history.slice(-30))`；新增 computed `sparkTrend = computed(() => computePriceChange(props.item.history).trend)`；template：在 `.dc-price` 區域、`dc-current` 之後加入 `<Sparkline :points="sparkPoints" :trend="sparkTrend" :enable-tooltip="true" />`；已下架商品不顯示 Sparkline（已在 `<template v-else>` 內，自然不顯示）；`.dc-price` 加入 `align-items: center`（與 Sparkline 垂直對齊） | `components/DashboardCard.vue`、`components/__tests__/DashboardCard.test.ts` | T1、T3 |
| T5 | **ProductCard.vue 同步加入 trend prop**：Sparkline 加入 `:trend="sparkTrend"`；新增 computed `sparkTrend = computed(() => computePriceChange(props.item.history).trend)`；`enableTooltip` 不加（ProductCard 現有無 tooltip 行為，保持向後相容；後續可按需加入） | `components/ProductCard.vue`、`components/__tests__/ProductCard.test.ts` | T1 |
| T6 | **E2E 測試**：≥2 筆歷史資料的商品卡片顯示 sparkline；<2 筆顯示「資料不足」；已下架商品不顯示 sparkline；價格下跌顯示綠色線條；價格上漲顯示紅色線條；價格持平顯示灰色線條；Hover sparkline 顯示 tooltip（日期 + 價格）；移開 cursor 隱藏 tooltip；歷史資料跨多月時僅顯示最近 30 天（`slice(-30)` 驗證）；Sparkline 響應式縮放（隨卡片寬度） | `e2e/` 或 `playwright/` | T4 |

### 6.3 決策點（非互動推導，待 spec/review 正式確認）

| 決策點 | 選項 | 評估者結論（待確認） |
|---|---|---|
| **D1** Tooltip 是否實作 | a) 實作 tooltip；b) **不實作 tooltip** | ✅ **a 實作**：IF §4 步驟 3 明確要求；純展示子元件成本低 |
| **D2** Sparkline 擴充方式 | a) **擴充現有 Sparkline.vue**；b) 新建 SparklineV2.vue | ✅ **a 擴充**：新 prop 皆 optional，向後相容；避免多版本混淆 |
| **D3** Tooltip 狀態管理 | a) **Sparkline 內部管理**；b) 外部管理 | ✅ **a 內部**：tooltip 為 Sparkline 展示細節，hoveredIndex 為內部 ref |
| **D4** Tooltip 位置策略 | a) **absolute 定位於 SVG 容器內**；b) fixed 定位於 viewport | ✅ **a absolute**：精確對齊數據點 x 座標 |
| **D5** 30 天截斷位置 | a) **呼叫端 `slice(-30)`**；b) Sparkline 內部截斷 | ✅ **a 呼叫端**：與 ProductCard L24 一致；Sparkline 保持純渲染 |
| **D6** Trend 計算位置 | a) **呼叫端計算**；b) Sparkline 內部計算 | ✅ **a 呼叫端**：`computePriceChange()` 已有；Sparkline 只接收 trend prop |

---

## 7. 風險登錄

| 風險 | 可能性 | 影響 | 緩解 |
|------|--------|------|------|
| hover 在小螢幕（手機）無法觸發 → tooltip 永遠不顯示 | 中 | 低 | tooltip 為 Nice-to-have；手機用戶可透過卡片詳情頁查看完整歷史（IF §2.2 入口為桌面 dashboard）；可選：`@touchstart` 支援觸控 tooltip（後續版本） |
| Sparkline tooltip 在卡片邊界溢出（第一個/最後一個數據點的 tooltip 被截斷） | 中 | 低 | tooltip 加入 `max-width` + `overflow: hidden`；或邊界點改為向內偏移（`transform: translateX(0)` vs `translateX(-100%)`）；可在 T3 中處理 |
| `hoveredIndex` 在快速滑動時 flicker（tooltip 閃爍） | 低 | 低 | SVG 的 `@mousemove` 事件已足夠穩定（Vue 3 的事件委派）；若 flicker 可加 `requestAnimationFrame` throttle |
| ProductCard 同步 trend prop 後，現有 snapshot 測試需更新 | 高 | 低 | 更新 ProductCard snapshot（`--update` flag）；無功能影響 |
| Sparkline tooltip 的 `formatPrice` 導入與 DashboardCard 重複 | 低 | 極低 | 共用 `@/utils/format`，無重複問題 |

---

## 📝 決策後續

- 本文件已存至 `docs/tech-decisions/020-dashboard-sparkline.md`，應納入版本控制。
- **決策待確認**：§6.3 六個決策點（D1–D6）為非互動推導結論，建議在 development-spec-generator／loop-review 階段正式確認後展開 T1–T6。
- Sparkline.vue 擴充 trend prop 後，ProductCard 可在 T5 同步受益（目前 ProductCard 已引入 Sparkline 但無 trend）。
- `enableTooltip` 預設為 `false`，ProductCard 可按需在後續版本加入 tooltip（T5 決定不加，保持向後相容）。
- 建議 1 個月後回顧：tooltip 使用率（hover 事件追蹤）、小螢幕 tooltip 需求（觸控支援）。
