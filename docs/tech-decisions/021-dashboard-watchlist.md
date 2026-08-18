# 開發方案決策文件：#021 Dashboard — 快速加入追蹤清單

> **性質**：前端功能層技術評估（tech-assessment-generator 引導，非互動模式產出）
> **對應**：GitHub Issue **#21** `feat(P1): Dashboard — 快速加入追蹤清單（US-05）`
> **範圍**：`web/src/components/DashboardCard.vue`（整合已有 WatchlistButton 元件）
> **上游文件**：`docs/interaction-flows/021-dashboard-watchlist.md`（主輸入）
> **決策方式**：基於上游文件 + 現有專案架構推導，**不提問**；所有決策點由評估者給定推薦結論，待實作前的 spec/review 階段正式確認

---

## 📌 決策摘要

| 項目 | 內容 |
|------|------|
| **最終方案** | **方案 A「DashboardCard 直接整合 WatchlistButton（button variant）」**：在 `DashboardCard.vue` 的 `.dc-top` 區域引入 `WatchlistButton`（variant `'button'`），與 🥇 標示並列；已下架商品隱藏按鈕；無需新增 composable 或型別（`useWatchlist` + `WatchlistButton` 已完整實作） |
| **決策日期** | 2026-08-17 |
| **決策前提** | ① `WatchlistButton.vue` 已完整實作（Star icon + toast + variant prop + 錯誤處理）；② `useWatchlist.ts` 已完整實作（singleton + localStorage + add/remove/isTracked + quota-exceeded rollback）；③ `ProductCard.vue` 已整合 WatchlistButton（可作為參考）；④ DashboardCard 目前無 WatchlistButton 整合（IF §8 差異 #1） |
| **核心效益** | 改動量極小（僅 1 個檔案、~5 行 template + ~3 行 script）；完全複用已有元件與 composable；與 ProductCard 行為一致 |
| **共識程度** | ✅ 非互動推導，共識待 spec/review 階段確認（§5.2） |

---

## 1. 需求回顧

### 1.1 使用者／Issue 訴求

> 「在 Dashboard 商品卡片上一鍵加入追蹤清單，讓使用者持續監控該商品價格變動。」

**拆解出的核心需求**：

| 需求項 | 說明 | 來源 |
|--------|------|------|
| DashboardCard 整合 WatchlistButton | 卡片內顯示追蹤按鈕 | IF §4 步驟 1–2 |
| 未追蹤狀態 | 空心 Star + 「加入追蹤」文字 | IF §2.3 |
| 已追蹤狀態 | 實心 Star + 「已追蹤」文字（按鈕高亮） | IF §2.3 |
| 已下架商品 | 不顯示追蹤按鈕 | IF §2.3 |
| Toast 通知 | 加入/移除/重複/無價格/儲存失敗 各有對應 toast | IF §3–5 |
| 追蹤上限 | 由 localStorage quota 決定（非硬編碼 100 項） | IF §6 |

### 1.2 需求假設（評估者由上游文件與現況推導）

| 假設 | 內容 | 依據 |
|------|------|------|
| H1 | `WatchlistButton` 與 `useWatchlist` 已完整實作，本功能僅需「整合」而非「實作」 | IF §8「已有可複用模組」；代碼審查確認 |
| H2 | DashboardCard 使用 `variant='button'`（完整按鈕），而非 `variant='icon'`（僅 icon） | IF §6「DashboardCard 用 button，ProductCard 用 icon」；ProductCard 實際為 button variant（與 IF 描述有出入，以 ProductCard 為準） |
| H3 | WatchlistButton 放置在 `.dc-top` 區域（卡片頂部），與 🥇 標示並列 | IF §8「建議在 `.dc-top` 區域，與 🥇 標示並列」 |
| H4 | 點擊卡片（導航到詳情頁）與點擊追蹤按鈕需互不干擾（stop propagation） | ProductCard 已有 `@click.stop` 在 actions 區域 |
| H5 | 已下架商品不顯示追蹤按鈕（`item.status === 'gone'`） | IF §2.3「已下架商品不顯示追蹤按鈕」 |

### 1.3 非需求

- ❌ 不需要新的 composable（`useWatchlist` 已完整）
- ❌ 不需要新的型別定義（`WatchlistItem` 已在 `types/watchlist.ts`）
- ❌ 不需要路由同步追蹤狀態（localStorage 已足夠）
- ❌ 不需要追蹤清單頁面的改動（本功能僅限 DashboardCard 整合）

---

## 2. 現況分析

### 2.1 現有模組狀態

| 模組 | 檔案 | 狀態 | 本功能需改動 |
|------|------|------|-------------|
| `WatchlistButton.vue` | `components/WatchlistButton.vue` | ✅ 已完整實作 | ❌ 不需改動 |
| `useWatchlist.ts` | `composables/useWatchlist.ts` | ✅ 已完整實作 | ❌ 不需改動 |
| `WatchlistItem` | `types/watchlist.ts` | ✅ 已定義 | ❌ 不需改動 |
| `DashboardCard.vue` | `components/DashboardCard.vue` | ⚠️ **未引入 WatchlistButton** | ✅ **需整合** |
| `ProductCard.vue` | `components/ProductCard.vue` | ✅ 已整合 WatchlistButton | ❌ 不需改動（參考用） |

### 2.2 WatchlistButton props & 行為

```typescript
// WatchlistButton.vue props
interface WatchlistButtonProps {
  id: string        // 商品 ID（必填）
  name: string      // 商品名稱（加入時快照用，必填）
  price: number | null  // 目前價格（null → 點擊時顯示「無價格」toast）
  variant?: 'button' | 'icon'  // 預設 'button'
}

// 內建行為
// - 自動呼叫 useWatchlist().isTracked(id) 判定狀態
// - 點擊 → add() 或 remove()
// - 內建 toast（已加入追蹤 / 已移除追蹤 / 錯誤訊息）
// - 2 秒自動消失
```

### 2.3 DashboardCard.vue 現有結構

```html
<article class="dashboard-card">
  <div class="dc-top">
    <div class="dc-name">{{ item.name }}</div>
    <div v-if="item.status === 'gone'" class="dc-gone">已下架</div>
    <span v-else-if="isLowest" class="dc-lowest">🥇</span>
    <!-- ← WatchlistButton 應放置於此處 -->
  </div>
  <div v-if="specChips.length" class="dc-specs">...</div>
  <div class="dc-price">...</div>
</article>
```

**關鍵觀察**：
- `.dc-top` 已使用 `display: flex; justify-content: space-between`（左：名稱，右：已下架/🥇）
- WatchlistButton 需放在 `.dc-top` 右側，與 🥇 並列
- 已下架時不顯示 🥇，也不顯示 WatchlistButton
- 需要 `@click.stop` 防止觸發卡片導航

### 2.4 ProductCard.vue 參考整合方式

```html
<!-- ProductCard.vue — 已有整合 -->
<div class="pc-actions" @click.stop>
  <WatchlistButton :id="item.id" :name="item.name" :price="currentPrice" />
  <CompareToggle :id="item.id" :category="categoryName ?? ''" variant="button" />
</div>
```

**差異**：
- ProductCard 的 actions 區域在卡片底部（`margin-top: auto`），作為獨立 row
- DashboardCard 需放在 `.dc-top` 區域（與 🥇 並列），因為 DashboardCard 無 actions 區域
- DashboardCard 只有 WatchlistButton，無 CompareToggle

---

## 3. 候選方案

### 方案 A（推薦）：DashboardCard 直接整合 WatchlistButton（button variant）

**架構**：
```
components/
  DashboardCard.vue          # 【改動】引入 WatchlistButton + 阻止事件冒泡
  WatchlistButton.vue        # 不變（已有完整實作）
composables/
  useWatchlist.ts            # 不變（已有完整實作）
```

**DashboardCard.vue 改動**：
```typescript
// script 新增 import
import WatchlistButton from "./WatchlistButton.vue"
```

```html
<!-- template: .dc-top 區域改動 -->
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

**資料流**：
```
DashboardCard.vue
  → props.item (Item)
  → usePriceDelta(props.item) → currentPrice
  → <WatchlistButton :id="item.id" :name="item.name" :price="currentPrice" />
    → WatchlistButton.vue
      → useWatchlist().isTracked(id) → tracked 狀態
      → Star icon（空心/實心）+ 文字（加入追蹤/已追蹤）
      → handleClick → add()/remove() → toast
```

### 方案 B（保守）：WatchlistButton 放在卡片底部（獨立 row）

將 WatchlistButton 放在 DashboardCard 底部，類似 ProductCard 的 `pc-actions` 區域。

- **優點**：與 ProductCard 佈局一致
- **缺點**：
  - DashboardCard 現有無底部 actions 區域，需新增 `.dc-actions` + `margin-top: auto`
  - DashboardCard 為精簡版卡片，底部加按鈕會增加卡片高度
  - 與 IF §8「建議在 `.dc-top` 區域」不符
- 結論：增加不必要改動，與 IF 建議不符

### 方案 C（激進）：DashboardCard 直接呼叫 useWatchlist API

不使用 WatchlistButton 元件，而是在 DashboardCard 內直接呼叫 `useWatchlist().add()/remove()` 並自行管理按鈕 UI。

- **優點**：可完全自訂按鈕樣式
- **缺點**：
  - 重複實作 WatchlistButton 已有的 toast + 狀態切換 + 錯誤處理邏輯
  - 違反 DRY 原則
  - 維護兩套追蹤按鈕邏輯，容易不一致
- 結論：完全不可取，重複造輪子

---

## 4. 權衡評估

### 4.1 權衡矩陣（1–5 分，5 最佳）

| 維度 | B 底部 actions row | **A .dc-top 整合** | C 直接呼叫 API |
|---|:---:|:---:|:---:|
| 🎯 需求符合度 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| ⚡ 開發速度 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 🔧 維護成本 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 🧩 模組化/可測試性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 🔄 複用性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 👥 團隊熟悉度 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 📦 效能 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **總分** | **27** | **34** | **22** |

### 4.2 關鍵取捨

**取捨 #1：WatchlistButton 放置位置**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）`.dc-top` 區域（與 🥇 並列） | IF §8 建議位置；緊湊佈局 | ✅ **選 A** |
| B）卡片底部（獨立 actions row） | ProductCard pattern；增加卡片高度 | ❌ DashboardCard 為精簡版，不需底部 actions |

**決策（D1）：放置在 `.dc-top`**
- IF §8 明確建議「在 `.dc-top` 區域，與 🥇 標示並列」
- DashboardCard 為精簡版卡片（無 CompareToggle），底部加 actions row 浪費空間
- `.dc-top` 已有 `display: flex; justify-content: space-between`，WatchlistButton 放在右側即可
- 已下架商品不顯示 🥇 也不顯示 WatchlistButton（v-if/v-else 統一控制）

**取捨 #2：阻止事件冒泡方式**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）`@click.stop` 包裹 WatchlistButton | 點擊按鈕不觸發卡片導航 | ✅ **選 A** |
| B）在卡片 click handler 中判斷 event.target | 判斷點擊來源再決定是否導航 | ❌ 不可靠且複雜 |

**決策（D2）：`@click.stop`**
- ProductCard 已有相同 pattern（`<div class="pc-actions" @click.stop>`）
- 簡潔可靠，一行解決
- 需包在 `<span>` 或 `<div>` 上（不能直接在 WatchlistButton 根元素加 `.stop`，因為 `.stop` 需在 Vue template 的事件修飾器上）

**取捨 #3：已下架商品的 WatchlistButton 顯示**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）不顯示（`v-if="item.status !== 'gone'"`） | 已下架商品無價格，追蹤無意義 | ✅ **選 A** |
| B）顯示但禁用（`disabled`） | 顯示按鈕但灰色不可點擊 | ❌ 無意義的 UI 元素 |

**決策（D3）：不顯示**
- IF §2.3 明確「已下架商品不顯示追蹤按鈕」
- 已下架商品無價格，`WatchlistButton` 的 `price=null` 會顯示「該商品目前無價格，無法追蹤」toast，但更好的做法是直接不顯示
- 與 🥇 標示共用 v-if/v-else 邏輯（已下架 → 顯示「已下架」標籤；非已下架 → 顯示 🥇 + WatchlistButton）

**取捨 #4：WatchlistButton variant**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）`variant='button'`（完整按鈕含文字） | 與 ProductCard 一致；文字明確 | ✅ **選 A** |
| B）`variant='icon'`（僅 Star icon） | 更緊湊；但可發現性低 | ❌ DashboardCard 空間充足，文字按鈕更直觀 |

**決策（D4）：`variant='button'`**
- IF §6「DashboardCard 用 button，ProductCard 用 icon」（但 ProductCard 實際用 button variant，以實作為準）
- DashboardCard 為精簡版卡片，空間充足（`.dc-top` 右側有足夠空間）
- 文字按鈕「加入追蹤」/「已追蹤」比純 icon 更直觀

---

## 5. 決策理由

### 5.1 為什麼選方案 A
1. **改動量極小**：僅 1 個檔案（`DashboardCard.vue`），~5 行 template + ~3 行 script import；無需新增 composable、型別、或元件
2. **完全複用已有實作**：`WatchlistButton`（Star icon + toast + 錯誤處理）和 `useWatchlist`（singleton + localStorage + quota rollback）已完整實作，無任何功能缺口
3. **符合 IF 需求**：IF §8 差異 #1「DashboardCard 未引入 WatchlistButton」是唯一需補齊的差異；差異 #2–#4（圖示/文案/上限）均以現有實作為準

### 5.2 為什麼放棄其他方案
| 方案 | 放棄理由 |
|---|---|
| **B 底部 actions row** | 增加不必要改動（需新增 `.dc-actions` + `margin-top: auto`）；DashboardCard 無 CompareToggle，底部 actions row 只有一個按鈕，浪費空間；與 IF §8 建議不符 |
| **C 直接呼叫 useWatchlist API** | 重複實作 WatchlistButton 已有的 toast + 狀態切換 + 錯誤處理；違反 DRY；維護兩套邏輯易不一致 |

### 5.3 與 IF §8 差異的對齊

| 差異 | IF 描述 | 現有實作 | 處理方式 |
|------|---------|---------|---------|
| DashboardCard 整合 WatchlistButton | 卡片內顯示追蹤按鈕 | 未引入 | ✅ **本功能核心改動** |
| 按鈕圖示 | 空心愛心或 + 號 / 實心愛心或 ✓ 號 | Star icon（空心/實心星星） | ⚠️ 以實作為準，不改動 |
| Toast 文案 | 「已加入追蹤清單」 | 「已加入追蹤」 | ⚠️ 以實作為準，不改動 |
| 追蹤清單上限 | 100 項硬編碼 | 無硬編碼上限，由 localStorage quota 決定 | ⚠️ 以實作為準，不改動 |

---

## 6. 行動計畫

### 6.1 目標架構

```
web/src/
  components/
    DashboardCard.vue          # 【改動】引入 WatchlistButton + @click.stop + 已下架隱藏
    WatchlistButton.vue        # 不變
  composables/
    useWatchlist.ts            # 不變
  types/
    watchlist.ts               # 不變
```

### 6.2 任務拆分

| # | 任務 | 檔案 | 改動說明 | 依賴 |
|---|------|------|---------|------|
| T1 | **DashboardCard 整合 WatchlistButton** | `components/DashboardCard.vue` | ① `script` 新增 `import WatchlistButton from "./WatchlistButton.vue"`；② `template` `.dc-top` 區域：已下架時不顯示 🥇 也不顯示按鈕；非已下架時顯示 🥇（如有）+ `<span @click.stop><WatchlistButton :id="item.id" :name="item.name" :price="currentPrice" /></span>`；③ 若需重構 `.dc-top` 為嵌套 flex（`.dc-right` wrapper），調整 CSS | — |
| T2 | **DashboardCard 單元測試更新** | `components/__tests__/DashboardCard.test.ts` | ① 新增 test：未追蹤商品顯示「加入追蹤」按鈕；② 新增 test：已追蹤商品顯示「已追蹤」按鈕；③ 新增 test：已下架商品不顯示追蹤按蹤按鈕；④ 新增 test：點擊追蹤按鈕不觸發卡片導航（`@click.stop`）；⑤ 更新 snapshot（若使用） | T1 |
| T3 | **E2E 測試** | `e2e/` 或 `playwright/` | ① Dashboard 卡片顯示追蹤按蹤按鈕；② 點擊「加入追蹤」→ 按鈕變為「已追蹤」+ toast；③ 點擊「已追蹤」→ 按鈕變為「加入追蹤」+ toast；④ 已下架商品不顯示追蹤按鈕；⑤ 點擊追蹤按鈕不導航至詳情頁 | T1 |

### 6.3 決策點（非互動推導，待 spec/review 正式確認）

| 決策點 | 選項 | 評估者結論（待確認） |
|---|---|---|
| **D1** 放置位置 | a) **`.dc-top` 區域**；b) 卡片底部 actions row | ✅ **a .dc-top**：IF §8 建議、DashboardCard 為精簡版無需底部 row |
| **D2** 阻止事件冒泡 | a) **`@click.stop`**；b) event.target 判斷 | ✅ **a @click.stop**：ProductCard 已有先例、簡潔可靠 |
| **D3** 已下架商品顯示 | a) **不顯示**；b) 顯示但禁用 | ✅ **a 不顯示**：IF §2.3 明確要求、已下架追蹤無意義 |
| **D4** WatchlistButton variant | a) **`'button'`**；b) `'icon'` | ✅ **a button**：文字更直觀、DashboardCard 空間充足 |

---

## 7. 風險登錄

| 風險 | 可能性 | 影響 | 緩解 |
|------|--------|------|------|
| `.dc-top` 右側放入 WatchlistButton 後空間擁擠（商品名過長 + 🥇 + 按鈕） | 中 | 低 | `.dc-top` 已有 `gap: 8px` + `flex-wrap`；WatchlistButton 有 `white-space: nowrap`；名稱已有 `line-clamp: 2` 限制；可微調 CSS `flex-shrink` 確保按鈕不被壓縮 |
| `@click.stop` 未正確包裹 → 點擊按鈕仍觸發導航 | 低 | 中 | 需確保 `@click.stop` 在 WatchlistButton 的外層 `<span>` 上（非 WatchlistButton 元件內部）；E2E 測試驗證 |
| DashboardCard 的 `currentPrice` 與 WatchlistButton 的 `price` prop 不同步 | 極低 | 極低 | 兩者皆由 `usePriceDelta(props.item).currentPrice` 計算，同源同值 |
| 單元測試 snapshot 因引入 WatchlistButton 而需更新 | 高 | 極低 | 更新 snapshot（`--update` flag）；無功能影響 |

---

## 📝 決策後續

- 本文件已存至 `docs/tech-decisions/021-dashboard-watchlist.md`，應納入版本控制。
- **決策待確認**：§6.3 四個決策點（D1–D4）為非互動推導結論，建議在 development-spec-generator／loop-review 階段正式確認後展開 T1–T3。
- 本功能改動量極小（1 個檔案 + 測試），核心工作為「整合」而非「實作」；`WatchlistButton` + `useWatchlist` 已完整實作，無功能缺口。
- 建議 1 個月後回顧：Dashboard 追蹤按鈕點擊率、使用者是否從 Dashboard 加入追蹤（vs 從 Listing 頁）、已下架商品追蹤需求（是否需保留已追蹤的已下架商品顯示）。
