# Dashboard Groups — 開發規格

> **Tech Decision**：`docs/tech-decisions/018-dashboard-groups.md`
> **操作流程**：`docs/interaction-flows/018-dashboard-groups.md`
> **BDD**：`docs/bdds/018-dashboard-groups.feature`
> **狀態**：✅ 已完成

---

## 概述

在 Dashboard（017）基礎上增加「規格分組」維度，將同規格商品自動分組（如 DDR5 32GB、DDR4 16GB），讓使用者精確比較同規格商品的價格差異。核心包含：

1. **`useSpecGroups` composable**：純函數分組邏輯——接收商品列表 + 分類 ID，輸出分組選項 + 分組篩選後的商品列表
2. **`SpecGroupChips.vue` 元件**：分組 Chips UI，封裝折疊邏輯（>8 個 → 「更多 ▼」）
3. **`GROUP_STRATEGY` 配置**：per-category 分組策略（formatKey 純函數），易擴充新分類
4. **`DashboardView` 擴充**：整合 useSpecGroups + SpecGroupChips，分組模式下全量顯示（無 Top 10）

---

## 1. 後端實作規格

**不適用**。本功能為純前端，無後端改動。

---

## 2. 前端實作規格

### 2.1 檔案改動總覽

```
web/src/
├── types/
│   └── specGroup.ts                    ← 新增：GroupStrategy、GroupOption 型別 + GROUP_STRATEGY 配置
├── composables/
│   └── useSpecGroups.ts                ← 新增：分組邏輯 composable（items → groups + groupedItems）
├── components/
│   └── SpecGroupChips.vue              ← 新增：分組 Chips UI（折疊 >8 個）
└── views/
    └── DashboardView.vue               ← 修改：整合 useSpecGroups + SpecGroupChips + 分組篩選列表
```

### 2.2 `types/specGroup.ts` — 分組策略與型別

#### 2.2.1 型別定義

```typescript
// web/src/types/specGroup.ts — 規格分組型別 + 策略配置

import type { ItemSpec } from "@/types/item"

/** 單一分組選項（Chip 顯示用） */
export interface GroupOption {
  key: string     // 分組鍵，如 "DDR5 32GB"；空字串 "" 表示「全部」
  label: string   // 顯示文案，與 key 相同（或格式化後）
  count: number   // 該分組的商品數量
}

/** Per-category 分組策略 */
export interface GroupStrategy {
  /** 分組欄位鍵（多欄位依序組合；僅供文件參考，實際由 formatKey 決定） */
  fields: (keyof ItemSpec)[]
  /** 分組鍵格式化函式
   *  - 回傳 string：該商品歸入此分組
   *  - 回傳 null：該商品無有效規格，歸入「其他」
   */
  formatKey: (spec: ItemSpec) => string | null
}

/** 「全部」分組的特殊 key */
export const ALL_GROUP_KEY = ""

/** 「其他」分組的特殊 key（無規格商品歸入此組；不顯示在 Chips 中） */
export const OTHER_GROUP_KEY = "__other__"
```

#### 2.2.2 `GROUP_STRATEGY` 配置

```typescript
// web/src/types/specGroup.ts（續）

export const GROUP_STRATEGY: Record<string, GroupStrategy> = {
  記憶體: {
    fields: ["spec", "ram_gb"],
    formatKey: (s) => {
      const ddr = typeof s.spec === "string" ? s.spec : ""  // "DDR5" / "DDR4"
      const ram = s.ram_gb != null ? `${s.ram_gb}GB` : ""
      const key = `${ddr} ${ram}`.trim()
      return key || null
    },
  },
  顯示卡: {
    fields: ["vram_gb", "chip"],
    formatKey: (s) => {
      const vram = s.vram_gb != null ? `${s.vram_gb}GB` : ""
      const chip = s.chip ?? ""
      const key = `${vram} ${chip}`.trim()
      return key || null
    },
  },
  SSD: {
    fields: ["capacity_gb", "interface"],
    formatKey: (s) => {
      const cap = s.capacity_gb != null ? `${s.capacity_gb}GB` : ""
      const iface = s.interface ?? ""
      const key = `${cap} ${iface}`.trim()
      return key || null
    },
  },
  HDD: {
    fields: ["capacity_gb", "rpm"],
    formatKey: (s) => {
      const cap = s.capacity_gb != null ? `${s.capacity_gb}GB` : ""
      const rpm = s.rpm != null ? `${s.rpm}RPM` : ""
      const key = `${cap} ${rpm}`.trim()
      return key || null
    },
  },
  CPU: {
    fields: ["cores", "base_ghz"],
    formatKey: (s) => {
      const cores = s.cores != null ? `${s.cores}核` : ""
      const ghz = s.base_ghz != null ? `${s.base_ghz}GHz` : ""
      const key = `${cores} ${ghz}`.trim()
      return key || null
    },
  },
  主機板: {
    fields: ["socket", "chipset"],
    formatKey: (s) => {
      const socket = s.socket ?? ""
      const chipset = s.chipset ?? ""
      const key = `${socket} ${chipset}`.trim()
      return key || null
    },
  },
  電源: {
    fields: ["wattage_w"],
    formatKey: (s) => {
      return s.wattage_w != null ? `${s.wattage_w}W` : null
    },
  },
}
```

**擴充方式**：新增分類時，在 `GROUP_STRATEGY` 中加入對應 key（如 `RAM: { fields: [...], formatKey: ... }`），`useSpecGroups` 自動生效，無需改動核心邏輯。

### 2.3 `useSpecGroups.ts` — 分組邏輯 Composable

#### 2.3.1 職責

- 根據目前分類 ID 選擇 `GROUP_STRATEGY`
- 將商品列表按 `formatKey` 分組，收集唯一分組鍵
- 管理選取狀態（`selectedGroupKey`）
- 輸出分組篩選後的商品列表（`groupedItems`）
- 提供「全部」分組（`ALL_GROUP_KEY`）

#### 2.3.2 簽名與介面

```typescript
// web/src/composables/useSpecGroups.ts

import { ref, computed, toValue, type MaybeRefOrGetter, type Ref } from "vue"
import type { Item } from "@/types/item"
import {
  GROUP_STRATEGY,
  ALL_GROUP_KEY,
  OTHER_GROUP_KEY,
  type GroupOption,
} from "@/types/specGroup"

/**
 * 規格分組 composable
 * @param items - 目前分類的商品列表（Ref 或 getter）
 * @param categoryName - 目前分類名稱（如 "記憶體"、"顯示卡"），用於查詢 GROUP_STRATEGY
 *                       為 null 或無對應策略時，不分組（hasGroups = false）
 */
export function useSpecGroups(
  items: MaybeRefOrGetter<Item[]>,
  categoryName: MaybeRefOrGetter<string | null>,
) {
  const rawItems = computed(() => toValue(items))
  const category = computed(() => toValue(categoryName))

  /** 該分類的分組策略（null = 不支援分組） */
  const strategy = computed(() => {
    const cat = category.value
    return cat != null && cat in GROUP_STRATEGY ? GROUP_STRATEGY[cat] : null
  })

  /** 每件商品的分組鍵（key → groupKey 映射，快取避免重複計算） */
  const itemGroupKeyMap = computed(() => {
    const strat = strategy.value
    if (!strat) return new Map<string, string>()
    const map = new Map<string, string>()
    for (const item of rawItems.value) {
      const key = strat.formatKey(item.spec) ?? OTHER_GROUP_KEY
      map.set(item.id, key)
    }
    return map
  })

  /** 收集唯一分組鍵（排除「其他」+「全部」）→ 排序 */
  const uniqueKeys = computed(() => {
    const keys = new Set<string>()
    for (const gk of itemGroupKeyMap.value.values()) {
      if (gk !== OTHER_GROUP_KEY) keys.add(gk)
    }
    return [...keys].sort()
  })

  /** 分組選項列表（含「全部」；「其他」不顯示在 Chips 中） */
  const groups = computed<GroupOption[]>(() => {
    if (!strategy.value) return []

    const total = rawItems.value.length
    const otherCount = [...itemGroupKeyMap.value.values()].filter(
      (k) => k === OTHER_GROUP_KEY,
    ).length

    // 「全部」永遠排第一
    const allGroup: GroupOption = {
      key: ALL_GROUP_KEY,
      label: "全部",
      count: total,
    }

    // 每個分組計算 count
    const keyCounts = new Map<string, number>()
    for (const gk of itemGroupKeyMap.value.values()) {
      if (gk !== OTHER_GROUP_KEY) {
        keyCounts.set(gk, (keyCounts.get(gk) ?? 0) + 1)
      }
    }

    const specGroups: GroupOption[] = uniqueKeys.value.map((key) => ({
      key,
      label: key,
      count: keyCounts.get(key) ?? 0,
    }))

    return [allGroup, ...specGroups]
  })

  /** 是否支援分組（true → 顯示 Chips；false → 不顯示） */
  const hasGroups = computed(() => {
    // 至少 2 個分組（「全部」+ ≥1 個規格分組）才有顯示 Chips 的意義
    return strategy.value !== null && groups.value.length >= 2
  })

  /** 目前選取的分組 key（空字串 = 「全部」） */
  const selectedGroupKey = ref<string>(ALL_GROUP_KEY)

  /** 分組篩選後的商品列表（按價格由低到高排序） */
  const groupedItems = computed<Item[]>(() => {
    const strat = strategy.value
    const items = rawItems.value
    const selected = selectedGroupKey.value

    // 無策略或選取「全部」→ 返回全部商品
    if (!strat || selected === ALL_GROUP_KEY) {
      return [...items].sort((a, b) => {
        // 按最新歷史價格升冪
        const priceA = a.history.length > 0 ? a.history[a.history.length - 1].p : Infinity
        const priceB = b.history.length > 0 ? b.history[b.history.length - 1].p : Infinity
        return priceA - priceB
      })
    }

    // 選取特定分組 → 篩選 + 排序
    return items
      .filter((item) => {
        const gk = itemGroupKeyMap.value.get(item.id)
        return gk === selected
      })
      .sort((a, b) => {
        const priceA = a.history.length > 0 ? a.history[a.history.length - 1].p : Infinity
        const priceB = b.history.length > 0 ? b.history[b.history.length - 1].p : Infinity
        return priceA - priceB
      })
  })

  /** 切換分組 */
  function selectGroup(key: string): void {
    selectedGroupKey.value = key
  }

  /** 回到「全部」 */
  function resetGroup(): void {
    selectedGroupKey.value = ALL_GROUP_KEY
  }

  return {
    groups,
    hasGroups,
    selectedGroupKey,
    groupedItems,
    selectGroup,
    resetGroup,
  }
}
```

#### 2.3.3 關鍵設計說明

- **排序邏輯**：直接在 `groupedItems` 內按最新歷史價格升冪排序（與 BDD Scenario 一致），而非依賴 017 的 `useDashboard` Top 10 排序。分組模式下 Top 10 不適用（D6 決策）。
- **🥇 最便宜判定**：`groupedItems` 已按價格升冪排序，第一筆即為最便宜商品。DashboardView 可以 `index === 0` 判定是否顯示 🥇 標示。
- **「其他」分組**：格式化後 key 為 `OTHER_GROUP_KEY` 的商品不顯示在 Chips 中（D7 決策），但在「全部」分組中可見。

### 2.4 `SpecGroupChips.vue` — 分組 Chips 元件

#### 2.4.1 Props / Emits

```vue
<script setup lang="ts">
// web/src/components/SpecGroupChips.vue
import { ref, computed } from "vue"
import type { GroupOption } from "@/types/specGroup"

const COLLAPSE_THRESHOLD = 8  // 超過此數量時折疊（BDD @edge-case）

const props = defineProps<{
  groups: GroupOption[]
  selectedKey: string
}>()

const emit = defineEmits<{
  select: [key: string]
}>()

const isExpanded = ref(false)

/** 是否需要折疊（groups 數量 > COLLAPSE_THRESHOLD） */
const needsCollapse = computed(() => props.groups.length > COLLAPSE_THRESHOLD)

/** 顯示的 groups（折疊模式只顯示前 7 個 + 「更多」按鈕） */
const visibleGroups = computed(() => {
  if (!needsCollapse.value || isExpanded.value) return props.groups
  return props.groups.slice(0, COLLAPSE_THRESHOLD - 1) // 前 7 個（第 8 個位置留給「更多」按鈕）
})

/** 折疊按鈕文字 */
const collapseLabel = computed(() => {
  const hiddenCount = props.groups.length - (COLLAPSE_THRESHOLD - 1)
  return isExpanded.value ? `收起 ▲` : `更多 (${hiddenCount}) ▼`
})

function toggleExpand(): void {
  isExpanded.value = !isExpanded.value
}

function handleSelect(key: string): void {
  emit("select", key)
}
</script>
```

#### 2.4.2 Template 結構

```vue
<template>
  <div class="spec-group-chips">
    <button
      v-for="group in visibleGroups"
      :key="group.key"
      :class="['spec-group-chip', { 'spec-group-chip--active': selectedKey === group.key }]"
      @click="handleSelect(group.key)"
    >
      <span class="spec-group-chip__label">{{ group.label }}</span>
      <span class="spec-group-chip__count">{{ group.count }}</span>
    </button>

    <!-- 折疊/展開按鈕（groups > 8 時顯示） -->
    <button
      v-if="needsCollapse"
      class="spec-group-chip spec-group-chip--toggle"
      @click="toggleExpand"
    >
      {{ collapseLabel }}
    </button>
  </div>
</template>
```

#### 2.4.3 關鍵行為

| 行為 | 說明 |
|------|------|
| 折疊門檻 | `groups.length > 8` → 顯示前 7 個 + 「更多」按鈕（BDD @edge-case） |
| 展開 | 顯示全部 groups + 「收起」按鈕 |
| 選取高亮 | `selectedKey === group.key` 時加 `--active` modifier |
| 空狀態 | 不會發生（`hasGroups` 為 false 時 DashboardView 不渲染此元件） |

---

## 3. API 合約

**不適用**。純前端功能，無後端 API 改動。分組邏輯完全 client-side，資料來源為 001/002 已載入的 `useItems().items`。

---

## 4. 資料流

```
useItems().items (Ref<Item[]>)          ← 001/002 已載入的商品資料
        │
        ▼
useItems().activeCategory?.name         ← 目前選取的分類名稱（如 "記憶體"）
        │
        ▼
useSpecGroups(items, categoryName)
  ├── GROUP_STRATEGY[category]          ← 查詢 per-category 分組策略
  ├── itemGroupKeyMap                   ← 每件商品的分組鍵（Map<itemId, groupKey>）
  ├── groups: GroupOption[]             ← 唯一分組選項列表（含「全部」）
  ├── selectedGroupKey: ref<string>     ← 目前選取的分組（UI 互動）
  └── groupedItems: computed<Item[]>    ← 篩選 + 排序後的商品列表
        │
        ▼
DashboardView.vue
  ├── <SpecGroupChips>                  ← groups + selectedKey + @select
  └── <DashboardCard> × groupedItems   ← 🥇 index === 0 判定
```

**切換分組流程**：
```
使用者點擊 Chip → emit("select", key)
  → DashboardView: specGroups.selectGroup(key)
  → selectedGroupKey.value = key
  → groupedItems 自動重算（computed lazy reactivity）
  → DashboardView re-render（< 1ms for <1000 items）
  → 無 loading 動畫（BDD @happy-path Scenario 4）
```

---

## 5. 生命週期

**不適用**。無連線管理、session 或狀態機。Composable 為純 reactive 計算，無副作用。

---

## 6. 邊界條件處理

| 情境 | 來源 | 處理方式 |
|------|------|---------|
| 該分類無分組策略（`GROUP_STRATEGY` 無此 key） | Tech Decision D4 | `hasGroups = false` → 不顯示 Chips，直接顯示全部商品 |
| 所有商品均無 `spec.extra` 欄位 | BDD @edge-case Scenario 15 | `formatKey` 回傳 `null` → 全部歸入 `OTHER_GROUP_KEY` → 只有「全部」分組（`hasGroups = false`，因 groups.length = 1）→ 不顯示 Chips，商品列表直接顯示全部商品 |
| 分組 Chips 數量 > 8 | BDD @edge-case Scenario 7 | SpecGroupChips 折疊：顯示前 7 個 + 「更多 (N) ▼」按鈕 |
| 分組無商品（篩選後為空） | BDD @business-rules Scenario 5 | 顯示 `<EmptyState message="暫無此規格商品" />`，建議切換其他分組 |
| 商品為新上架（`history` 為空陣列） | — | `currentPrice = Infinity` → 排在最後；價格顯示為「—」（usePriceDelta 現有邏輯） |
| 快速切換分組（連續點擊） | BDD @edge-case Scenario 12 | computed 為 lazy reactivity，重算成本為 `items.filter()` + `.sort()`（< 1ms for < 1000 items） |
| 分組切換時間 > 300ms | BDD @edge-case Scenario 12 | 不可能發生（client-side 篩選無 I/O）；可加 Playwright performance assertion 驗證 |

---

## 7. CSS 關鍵樣式

| class | 樣式重點 |
|-------|---------|
| `.spec-group-chips` | `display: flex; flex-wrap: wrap; gap: 8px;` 水平排列 Chips，允許換行 |
| `.spec-group-chip` | `padding: 6px 14px; border-radius: 20px; border: 1px solid var(--color-border); background: var(--color-bg); cursor: pointer; transition: all 0.15s ease;` 基礎 chip 樣式 |
| `.spec-group-chip:hover` | `border-color: var(--color-primary); color: var(--color-primary);` 懸停效果 |
| `.spec-group-chip--active` | `background: var(--color-primary); color: white; border-color: var(--color-primary); font-weight: 600;` 選取高亮（與專案現有 primary color 一致） |
| `.spec-group-chip--toggle` | `background: none; border: none; color: var(--color-primary); font-size: 0.85rem;` 「更多/收起」按鈕樣式（無邊框） |
| `.spec-group-chip__label` | `margin-right: 4px;` 分組名稱文字 |
| `.spec-group-chip__count` | `opacity: 0.7; font-size: 0.8em;` 商品數量（弱化顯示） |

**響應式**：
- `@media (max-width: 768px)`：`.spec-group-chips` 改為 `overflow-x: auto; flex-wrap: nowrap;` 水平滾動（BDD 未明確要求 mobile dropdown，保持與 Tablet 一致的可滾動 Chips）

---

## 8. 開發順序

| 步驟 | 內容 | 依賴 |
|------|------|------|
| 1 | 新增 `types/specGroup.ts`：`GroupOption`、`GroupStrategy` 型別 + `ALL_GROUP_KEY`、`OTHER_GROUP_KEY` 常量 + `GROUP_STRATEGY` 配置（記憶體/顯示卡/SSD/HDD/CPU/主機板/電源） | — |
| 2 | 新增 `composables/useSpecGroups.ts`：接收 items + categoryName，輸出 groups / hasGroups / selectedGroupKey / groupedItems / selectGroup / resetGroup | #1 |
| 3 | 新增 `composables/__tests__/useSpecGroups.test.ts`：分組計算、排序、空分組、「其他」分組、hasGroups 邏輯 | #2 |
| 4 | 新增 `components/SpecGroupChips.vue`：Chips UI + 折疊邏輯（>8 個 → 「更多 ▼」） | #1 |
| 5 | 新增 `components/__tests__/SpecGroupChips.test.ts`：Chips 渲染、折疊/展開、選取高亮 | #4 |
| 6 | 修改 `views/DashboardView.vue`：import useSpecGroups；在 template 中加入 `<SpecGroupChips v-if="hasGroups">`；商品列表改為 `groupedItems`；🥇 判定 `index === 0` | #2, #4 |
| 7 | 新增 `views/__tests__/DashboardView.spec.ts`（或更新既有）：整合測試——分組 Chips 顯示/隱藏、切換分組後列表更新、🥇 標示 | #3, #5, #6 |
| 8 | E2E 測試（Playwright）：分組 Chips 正確顯示、切換分組後列表更新、折疊/展開「更多」、無規格商品歸入「其他」、分組切換 < 300ms | #7 |

---

## 9. 基礎架構設定

**不適用**。無 Nginx / systemd / 環境變數改動。本功能為純前端 client-side 邏輯，無新 API endpoint 或 WebSocket 連線。

---

## BDD Scenario 對照表

| BDD Scenario | 對應章節 | 實作位置 |
|--------------|---------|---------|
| `@happy-path` 系統自動依規格產生分組 Chips | §2.3 `groups` computed | `useSpecGroups.ts` → `groups` |
| `@happy-path` 預設顯示最便宜商品標示 🥇 | §2.3 `groupedItems` 排序 + §2.4 | `useSpecGroups.ts` → `groupedItems` + `DashboardView.vue` → `index === 0` |
| `@happy-path` 使用者切換分組後正確篩選商品 | §2.3 `selectGroup` + `groupedItems` | `useSpecGroups.ts` |
| `@happy-path` 分組切換為 client-side 篩選無 loading | §4 資料流 | computed lazy reactivity |
| `@business-rules` 規格分組邏輯正確（DDR 代數 × 容量組合） | §2.2 `GROUP_STRATEGY` 記憶體 | `types/specGroup.ts` |
| `@business-rules` 無規格商品歸入「其他」分組（不出現在 Chips 中） | §6 邊界條件 + §2.3 `OTHER_GROUP_KEY` | `useSpecGroups.ts` |
| `@business-rules` 「其他」分組內的商品亦按價格排序 | §2.3 `groupedItems` 排序 | `useSpecGroups.ts` |
| `@business-rules` 每次切換分組最便宜者重新標示 🥇 | §2.3 `groupedItems` + §6 | `useSpecGroups.ts` |
| `@business-rules` 分組無商品時顯示空狀態 | §6 邊界條件 | `DashboardView.vue` → `<EmptyState>` |
| `@edge-case` 分組 Chips 數量超過 8 個時折疊顯示 | §2.4 `COLLAPSE_THRESHOLD` | `SpecGroupChips.vue` |
| `@edge-case` 使用者點擊「更多 ▼」展開所有分組 Chips | §2.4 `toggleExpand` | `SpecGroupChips.vue` |
| `@edge-case` 使用者點擊「收起 ▲」重新折疊分組 Chips | §2.4 `toggleExpand` | `SpecGroupChips.vue` |
| `@edge-case` 所有分組 Chips 數量 ≤ 8 時不顯示折疊按鈕 | §2.4 `needsCollapse` | `SpecGroupChips.vue` |
| `@edge-case` 該分類僅有一種規格組合 | §2.3 `hasGroups`（length = 1 → false） | `useSpecGroups.ts` |
| `@edge-case` 該分類所有商品均無規格資料（hasGroups = false，不顯示 Chips） | §6 邊界條件 | `useSpecGroups.ts` → all `OTHER_GROUP_KEY` → groups.length = 1 |
| `@edge-case` 分組切換時間小於 300ms | §4 資料流 + §6 | client-side computed |
