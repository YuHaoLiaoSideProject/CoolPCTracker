# Dashboard — 快速加入追蹤清單 — 開發規格

> **技術棧**：Vue 3.5.13 · Vite 6.0.0 · TypeScript 5.6.3 · Vitest 3.2.4 · Playwright 1.62.1
> **Tech Decision**：`docs/tech-decisions/021-dashboard-watchlist.md`
> **操作流程**：`docs/interaction-flows/021-dashboard-watchlist.md`
> **BDD**：`docs/bdds/021-dashboard-watchlist.feature`
> **狀態**：✅ 已完成

---

## 概述

在 Dashboard 商品卡片（`DashboardCard.vue`）上整合已有的 `WatchlistButton` 元件，讓使用者一鍵加入/移除追蹤清單。核心包含：

1. **DashboardCard.vue 整合**：在 `.dc-top` 區域引入 `WatchlistButton`（button variant），與 🥇 標示並列；已下架商品隱藏按鈕
2. **事件冒泡隔離**：`@click.stop` 確保點擊追蹤按鈕不觸發卡片導航

> 本功能改動量極小（僅 1 個檔案 ~5 行 template + ~3 行 script import）。`WatchlistButton`、`useWatchlist`、`WatchlistItem` 均已完整實作，無需新增 composable 或型別。

---

## 1. 後端實作規格

**不適用**（純前端專案，無後端 API）

---

## 2. 前端實作規格

### 2.1 檔案改動總覽

```
web/src/
├── components/
│   ├── DashboardCard.vue           ← 修改：引入 WatchlistButton + @click.stop + 已下架隱藏
│   └── WatchlistButton.vue         ← 不變
├── composables/
│   └── useWatchlist.ts             ← 不變
└── types/
    └── watchlist.ts                ← 不變
```

### 2.2 DashboardCard.vue 改動

**改動範圍**：僅 `DashboardCard.vue`，涉及 3 處：

#### (a) `<script setup>` 新增 import

```typescript
// script 新增（在現有 import 區塊末尾）
import WatchlistButton from "./WatchlistButton.vue"
```

#### (b) `<template>` — `.dc-top` 區域重構

現有 `.dc-top` 結構（左：名稱，右：已下架/🥇）需改為嵌套 flex，加入 WatchlistButton：

```html
<div class="dc-top">
  <div class="dc-name">{{ item.name }}</div>
  <div class="dc-right">
    <div v-if="item.status === 'gone'" class="dc-gone">已下架</div>
    <template v-else>
      <span v-if="isLowest" class="dc-lowest" title="歷史新低" aria-label="歷史新低">🥇</span>
      <span @click.stop>
        <WatchlistButton :id="item.id" :name="item.name" :price="currentPrice" />
      </span>
    </template>
  </div>
</div>
```

**關鍵邏輯**：
- `v-if="item.status === 'gone'"`：已下架 → 僅顯示「已下架」標籤，不顯示 🥇 也不顯示追蹤按鈕
- `v-else`：非已下架 → 顯示 🥇（如有）+ WatchlistButton
- `@click.stop`：阻止點擊追蹤按鈕觸發 `<article>` 的 click 導航

#### (c) `<style scoped>` — 新增 `.dc-right` 樣式

```css
.dc-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}
```

### 2.3 不需改動的模組（已有完整實作）

| 模組 | 檔案 | 說明 |
|------|------|------|
| `WatchlistButton` | `components/WatchlistButton.vue` | props: `{id, name, price, variant?}`；內建 Star icon（空心/實心）、toast（2 秒自動消失）、錯誤處理 |
| `useWatchlist` | `composables/useWatchlist.ts` | singleton 模式；API: `isTracked(id)`, `add(id, name, price)`, `remove(id)`；localStorage 版本化儲存（key: `coolpc.watchlist`, version: 1） |
| `WatchlistItem` | `types/watchlist.ts` | `{id, name, addedAt, lastPriceSnapshot, priceSnapshotAt}` |

---

## 3. API 合約

**不適用**（無後端 API，追蹤清單資料儲存於 localStorage）

---

## 4. 資料流

本功能為純前端功能，資料流發生在前端內部組件之間：

```
DashboardCard.vue
  │
  ├─ props.item (Item)  ← 父元件傳入
  ├─ usePriceDelta(props.item) → currentPrice
  │
  └─ <WatchlistButton :id="item.id" :name="item.name" :price="currentPrice" />
       │
       ├─ useWatchlist().isTracked(id) → tracked (boolean)
       │    → 控制 Star icon（空心/實心）+ 文字（「加入追蹤」/「已追蹤」）
       │
       └─ handleClick()
            ├─ tracked === true → useWatchlist().remove(id)
            │    → 按鈕變為空心 Star + 「加入追蹤」
            │    → toast「已移除追蹤」
            │
            └─ tracked === false
                 ├─ price === null → toast「該商品目前無價格，無法追蹤」
                 └─ price !== null → useWatchlist().add(id, name, price)
                      ├─ 成功 → 按鈕變為實心 Star + 「已追蹤」
                      │         → toast「已加入追蹤」
                      │         → localStorage 寫入 {version:1, items:[...]}
                      ├─ already-tracked → toast「該商品已在追蹤清單」
                      ├─ storage-unavailable → toast「瀏覽器未開放本機儲存，無法使用追蹤功能」
                      └─ quota-exceeded → toast「儲存空間已滿，無法新增追蹤項目」
                           → optimistic update rollback（移除已加入的 item）
```

**儲存層**：
- localStorage key: `coolpc.watchlist`
- 格式: `{version: 1, items: WatchlistItem[]}`
- 讀寫透過 `@/utils/storage` 的 `readVersioned` / `writeVersioned`

---

## 5. 生命週期

不適用（無連線管理、session、或狀態機）

---

## 6. 邊界條件處理

| 情境 | 來源 | 處理方式 |
|------|------|---------|
| localStorage 不可用 | BDD `@error-handling` / IF §5 | `useWatchlist.add()` 回傳 `{ok:false, reason:'storage-unavailable'}`；WatchlistButton 顯示 toast「瀏覽器未開放本機儲存，無法使用追蹤功能」 |
| 儲存空間已滿（quota-exceeded） | BDD `@error-handling` / IF §5 | `useWatchlist.add()` 執行樂觀更新後 rollback；WatchlistButton 顯示 toast「儲存空間已滿，無法新增追蹤項目」 |
| 商品無價格（price === null） | BDD `@error-handling` / IF §5 | WatchlistButton 前置檢查 `price === null`，不呼叫 add()；顯示 toast「該商品目前無價格，無法追蹤」 |
| 商品已在追蹤清單（重複加入） | BDD `@error-handling` / IF §5 | `useWatchlist.add()` 回傳 `{ok:false, reason:'already-tracked'}`；WatchlistButton 顯示 toast「該商品已在追蹤清單」 |
| 已下架商品（status === 'gone'） | BDD `@edge-case` / IF §2.3 | DashboardCard 模板 `v-if="item.status === 'gone'"` 直接隱藏追蹤按鈕（與 🥇 標示共用 v-if/v-else） |
| `.dc-top` 空間擁擠 | Tech Decision §7 風險 | `.dc-top` 已有 `gap: 8px`；WatchlistButton 有 `white-space: nowrap`；`.dc-name` 有 `line-clamp: 2`；可微調 `flex-shrink` 確保按鈕不被壓縮 |
| `@click.stop` 未正確包裹 | Tech Decision §7 風險 | `@click.stop` 放在 WatchlistButton 外層 `<span>` 上（非元件內部）；E2E 測試驗證點擊追蹤按鈕不導航 |

---

## 7. CSS 關鍵樣式

| class / 選擇器 | 樣式重點 | 說明 |
|----------------|---------|------|
| `.dc-right` | `display: flex; align-items: center; gap: 8px; flex: 0 0 auto` | 新增 wrapper，將 🥇 與 WatchlistButton 水平排列 |
| `.watchlist-btn` | `display: inline-flex; gap: 0.35em; padding: 0.4em 0.85em; border-radius: 6px; white-space: nowrap` | 已有樣式（WatchlistButton.vue），button variant |
| `.watchlist-btn.tracked` | `background: var(--accent); color: #fff; border-color: var(--accent)` | 已追蹤高亮狀態 |
| `.watchlist-btn.is-icon` | `padding: 0.35em; border: none; background: transparent` | icon variant（本功能不使用，僅 DashboardCard 用 button） |
| `.watchlist-toast` | `position: absolute; bottom: calc(100% + 6px); left: 50%; transform: translateX(-50%)` | toast 浮動在按鈕上方 |
| `.dc-lowest` | `font-size: 1.2rem; flex: 0 0 auto` | 🥇 標示，與 WatchlistButton 並列 |

CSS class 名稱須與前端 code skeleton 的 class binding 一致。

---

## 8. 開發順序

| 步驟 | 內容 | 依賴 |
|------|------|------|
| T1 | **DashboardCard 整合 WatchlistButton**：修改 `DashboardCard.vue`（import + template `.dc-top` 重構 + `.dc-right` CSS） | — |
| T2 | **DashboardCard 單元測試更新**：新增測試場景（未追蹤/已追蹤按鈕狀態、已下架隱藏、@click.stop 不導航）；更新 snapshot | T1 |
| T3 | **E2E 測試**：Dashboard 卡片追蹤按鈕操作流程驗證（加入/移除/已下架隱藏/不導航） | T1 |

**Tech Decision 依賴對應**：
- T1 對應 Tech Decision T1（DashboardCard 整合 WatchlistButton）
- T2 對應 Tech Decision T2（單元測試更新）
- T3 對應 Tech Decision T3（E2E 測試）

T2、T3 可平行執行（均僅依賴 T1）。

---

## 9. 基礎架構設定

**不適用**（無 Nginx/systemd 設定，純前端功能）
