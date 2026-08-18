# Dashboard — 快速加入追蹤清單（US-05）— 互動流程

> **Issue**：#21
> **User Story**：US-05
> **Parent**：#16 Dashboard
> **依賴**：#17 (US-01)
> **整合**：#15 (005-watchlist-and-compare)
> **關聯 Tech Decision**：`docs/tech-decisions/021-dashboard-watchlist.md`（待產出）
> **關聯 BDD**：`docs/bdds/021-dashboard-watchlist.feature`（待產出）

---

## 1. 功能概述

**一句話**：在商品卡片上一鍵加入追蹤清單，讓使用者持續監控該商品價格變動。

核心交互元件：
1. **WatchlistButton.vue**：追蹤按鈕元件（star icon + toast 通知）
2. **useWatchlist.ts**：追蹤清單 composable（localStorage 單例，add/remove/reorder）
3. **DashboardCard.vue**：商品卡片，需整合 WatchlistButton

---

## 2. 使用者與場景

### 2.1 使用者角色

| 角色 | 目標 |
|------|------|
| **追蹤用戶** | 監控特定商品價格變動 |
| **裝機玩家** | 追蹤多個商品等待降價 |

### 2.2 觸發入口

| 入口 | 說明 |
|------|------|
| 商品卡片上的 [加入追蹤] 按鈕 | 主要入口（Star icon + 文字） |

### 2.3 顯示條件

- 未追蹤商品：顯示空心 Star icon + 「加入追蹤」文字
- 已追蹤商品：顯示實心 Star icon + 「已追蹤」文字（按鈕高亮）
- 已下架商品（`status === 'gone'`）：不顯示追蹤按鈕
- 無價格商品（`currentPrice === null`）：點擊時顯示錯誤 toast

---

## 3. 操作流程圖

```mermaid
flowchart TD
    Start([商品卡片載入])
    
    Start --> CheckTracked{商品已在追蹤清單?}
    
    CheckTracked -->|否| ShowAddBtn[顯示 [加入追蹤] 按鈕]
    CheckTracked -->|是| ShowRemoveBtn[顯示 [已追蹤] 按鈕]
    
    ShowAddBtn --> UserClick{使用者點擊}
    ShowRemoveBtn --> UserClick
    
    UserClick -->|點擊 [加入追蹤]| CheckPrice{商品有價格?}
    UserClick -->|點擊 [已追蹤]| RemoveFromWatchlist[移除追蹤清單]
    
    CheckPrice -->|否| ShowNoPrice[Toast: 該商品目前無價格，無法追蹤]
    CheckPrice -->|是| CheckStorage{localStorage 可用?}
    
    CheckStorage -->|是| SaveSuccess[儲存成功]
    CheckStorage -->|否| ShowStorageError[Toast: 瀏覽器未開放本機儲存]
    
    SaveSuccess --> ToggleBtn[按鈕變為 [已追蹤]]
    ToggleBtn --> ShowToast[Toast: 已加入追蹤]
    
    RemoveFromWatchlist --> RemoveSuccess[移除成功]
    RemoveSuccess --> ToggleBtn2[按鈕變為 [加入追蹤]]
    ToggleBtn2 --> ShowToast2[Toast: 已移除追蹤]
    
    style ShowNoPrice fill:#fff8e1,stroke:#f0a000
    style ShowStorageError fill:#fff0f0,stroke:#e00
```

---

## 4. 逐步互動說明

### 步驟 1：檢視追蹤按鈕狀態

| | 描述 |
|---|------|
| **觸發** | 商品卡片載入完成 |
| **操作前** | 商品列表已顯示 |
| **系統回應** | 檢查商品是否已在追蹤清單（`useWatchlist().isTracked(id)`），顯示對應按鈕狀態 |
| **操作後** | 未追蹤：空心 Star + 「加入追蹤」；已追蹤：實心 Star + 「已追蹤」（按鈕高亮） |
| **下一步** | 步驟 2：點擊追蹤按鈕 |

### 步驟 2：加入追蹤清單

| | 描述 |
|---|------|
| **觸發** | 使用者點擊 [加入追蹤] 按鈕 |
| **操作前** | 按鈕顯示為空心 Star + 「加入追蹤」 |
| **系統回應** | ① 檢查商品是否有價格（`price === null` → 顯示錯誤 toast）；② 呼叫 `useWatchlist().add(id, name, price)`；③ 成功：按鈕變為實心 Star + 「已追蹤」，顯示 toast「已加入追蹤」 |
| **操作後** | 商品已加入追蹤清單（localStorage） |
| **下一步** | 繼續瀏覽或前往追蹤清單頁面 |

### 步驟 3：移除追蹤清單

| | 描述 |
|---|------|
| **觸發** | 使用者點擊 [已追蹤] 按鈕 |
| **操作前** | 按鈕顯示為實心 Star + 「已追蹤」 |
| **系統回應** | 呼叫 `useWatchlist().remove(id)`；按鈕變為空心 Star + 「加入追蹤」，顯示 toast「已移除追蹤」 |
| **操作後** | 商品已從追蹤清單移除 |
| **下一步** | 繼續瀏覽 |

---

## 5. 異常處理

| 情境 | 使用者看到 | 恢復路徑 |
|------|-----------|---------|
| localStorage 不可用 | Toast: 「瀏覽器未開放本機儲存，無法使用追蹤功能」 | 清除瀏覽器資料或使用其他瀏覽器 |
| 儲存空間已滿（quota-exceeded） | Toast: 「儲存空間已滿，無法新增追蹤項目」 | 前往追蹤清單頁面移除商品 |
| 商品已在追蹤清單（重複加入） | Toast: 「該商品已在追蹤清單」 | 無（正常行為） |
| 商品無價格（`price === null`） | Toast: 「該商品目前無價格，無法追蹤」 | 等待爬蟲更新價格 |

---

## 6. 邊界與限制

| 項目 | 限制 | 說明 |
|------|------|------|
| 儲存方式 | localStorage（版本化儲存） | `coolpc.watchlist` key，version 1 |
| 追蹤清單上限 | 由 localStorage quota 決定 | 無硬編碼上限；`quota-exceeded` 時回報錯誤 |
| 價格快照 | 加入時記錄 `lastPriceSnapshot` + `priceSnapshotAt` | 供追蹤清單頁顯示加入時價格 |
| Toast 持續時間 | 2 秒自動消失 | `setTimeout(() => toast = '', 2000)` |
| 按鈕 variant | `'button'`（預設）或 `'icon'`（僅 icon） | DashboardCard 用 button，ProductCard 用 icon |

---

## 7. 驗收檢查清單

- [ ] 未追蹤商品顯示空心 Star + 「加入追蹤」按鈕
- [ ] 已追蹤商品顯示實心 Star + 「已追蹤」按鈕（高亮）
- [ ] 點擊 [加入追蹤] 後按鈕變為 [已追蹤]
- [ ] 點擊 [已追蹤] 後按鈕變為 [加入追蹤]
- [ ] 加入追蹤後顯示 toast「已加入追蹤」
- [ ] 移除追蹤後顯示 toast「已移除追蹤」
- [ ] localStorage 不可用時顯示錯誤 toast
- [ ] 儲存空間已滿時顯示錯誤 toast
- [ ] 商品已在追蹤清單時顯示提示 toast
- [ ] 商品無價格時顯示錯誤 toast
- [ ] 已下架商品不顯示追蹤按鈕

---

## 8. 與現有實作的差異（⚠️ 待補齊）

> 以下為本互動流程描述的功能與目前程式碼實作的差異，需在開發規格中規劃補齊。

| 功能點 | 互動流程描述 | 目前實作 | 狀態 |
|--------|-------------|---------|------|
| DashboardCard 整合 WatchlistButton | 卡片內顯示追蹤按鈕 | `DashboardCard.vue` **未引入** WatchlistButton | ❌ 未整合 |
| 按鈕圖示 | 空心愛心或 + 號 / 實心愛心或 ✓ 號 | Star icon（空心/實心星星） | ⚠️ 圖示不同（以實作為準） |
| Toast 文案 | 「已加入追蹤清單」 | 「已加入追蹤」 | ⚠️ 文案不同（以實作為準） |
| 追蹤清單上限 | 100 項硬編碼 | 無硬編碼上限，由 localStorage quota 決定 | ⚠️ 限制不同（以實作為準） |
| 價格檢查 | 未提及 | `price === null` 時顯示「該商品目前無價格，無法追蹤」 | ❌ 遺漏（已補入 §5） |
| variant prop | 未提及 | 支援 `variant: 'button' | 'icon'` | ❌ 遺漏（已補入 §6） |

### 已有可複用模組

| 模組 | 檔案 | 可用於 |
|------|------|--------|
| `useWatchlist()` | `composables/useWatchlist.ts` | 追蹤清單狀態管理（singleton，add/remove/isTracked） |
| `WatchlistButton.vue` | `components/WatchlistButton.vue` | 追蹤按鈕元件（含 toast，支援 variant） |
| `ProductCard.vue` | `components/ProductCard.vue` | 已整合 WatchlistButton（可作為 DashboardCard 整合參考） |

### 參考：ProductCard 的 WatchlistButton 整合方式

`ProductCard.vue`（ listing 頁卡片）已整合 WatchlistButton，可作為 DashboardCard 整合的參考：

```html
<!-- ProductCard.vue template -->
<div class="pc-actions" @click.stop>
  <WatchlistButton :id="item.id" :name="item.name" :price="currentPrice" />
  <CompareToggle :id="item.id" :category="categoryName ?? ''" variant="button" />
</div>
```

**差異**：ProductCard 的 actions 區域在卡片底部（`margin-top: auto`），DashboardCard 需決定放置位置（建議在 `.dc-top` 區域，與 🥇 標示並列）。
