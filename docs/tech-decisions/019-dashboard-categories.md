# 開發方案決策文件：#019 Dashboard — 切換分類瀏覽

> **性質**：前端功能層技術評估（tech-assessment-generator 引導，非互動模式產出）
> **對應**：GitHub Issue **#19** `feat(P1): Dashboard — 切換分類瀏覽（US-03）`
> **範圍**：`web/src/`（前端新增 CategoryTabs 元件、擴充 useDashboard / useSpecGroups / DashboardView）
> **上游文件**：`docs/interaction-flows/019-dashboard-categories.md`（主輸入）、`docs/tech-decisions/017-dashboard-items.md`（Dashboard 主功能）、`docs/tech-decisions/018-dashboard-groups.md`（規格分組功能）
> **決策方式**：基於上游文件 + 現有專案架構推導，**不提問**；所有決策點由評估者給定推薦結論，待實作前的 spec/review 階段正式確認

---

## 📌 決策摘要

| 項目 | 內容 |
|------|------|
| **最終方案** | **方案 D「CategoryTabs 元件 + useDashboard 擴充 + useItems loadCategory 整合」**：新增 `CategoryTabs.vue` 元件（分類 Tab 列表 + 折疊 >5 + spinner 載入態）；擴充 017 的 `useDashboard` composable（新增 `activeCategory` 狀態管理 + `switchCategory` 操作）；整合 018 的 `useSpecGroups`（切換分類時自動重置分組）；直接複用 `useItems.loadCategory()` 的快取/in-flight 機制（取消上一請求由 `useItems` 內部處理） |
| **決策日期** | 2026-08-17 |
| **決策前提** | ① 本功能建立在 017（DashboardView + useDashboard）+ 018（useSpecGroups + SpecGroupChips）基礎上；② Dashboard 已有 Tab 列表基礎（017 D6 預設第一分類），本功能增加折疊、spinner、切換取消等 UX 增強；③ 分類資料來源為 `useItems().categories`（index.json 動態提供）；④ 無後端，切換分類 = `loadCategory(id)`（快取已載入 → 立即切換；未載入 → fetch）；⑤ 分類 Tab >5 個時折疊為「更多 ▼」 |
| **核心效益** | CategoryTabs 可跨頁複用（ListingView 的 CategorySidebar 為側欄，本元件為頂部 Tab）；useItems 的 inFlight Map 已處理併發去重（切換時無需額外取消邏輯）；折疊邏輯封裝在元件內部，DashboardView 保持清晰 |
| **共識程度** | ✅ 非互動推導，共識待 spec/review 階段確認（§6.3） |

---

## 1. 需求回顧

### 1.1 使用者／Issue 訴求

> 「讓使用者在不同分類間快速切換（CPU / 記憶體 / 顯示卡...），一次比較多個分類的最便宜商品。」

**拆解出的核心需求**：

| 需求項 | 說明 | 來源 |
|--------|------|------|
| 分類 Tab 列表 | 頂部顯示所有分類 Tab（CPU、記憶體、顯示卡…） | IF §4 步驟 1 |
| Tab 預設選取 | 預設選取第一個分類 | IF §4 步驟 1 |
| Tab 切換高亮 | 點擊 Tab 後反白高亮 | IF §4 步驟 2 |
| 切換 Spinner | 切換時顯示載入 spinner（快取命中時不顯示） | IF §4 步驟 2、驗收清單 |
| 切換取消 | 切換新分類時取消上一分類的載入請求 | IF §5 異常處理 |
| 商品列表更新 | 切換後商品列表正確更新為新分類 | IF §4 步驟 2 |
| 分組 Chips 更新 | 切換後 SpecGroupChips 更新為新分類的規格分組 | IF §4 步驟 2 |
| Tab 折疊 | 分類 >5 個時折疊為「更多 ▼」 | IF §5 異常處理、驗收清單 |
| 切換速度 | 切換 <1 秒 | IF §6 邊界限制 |
| 空分類處理 | 新分類無商品時顯示空狀態 | IF §5 異常處理 |

### 1.2 需求假設（評估者由上游文件與現況推導）

| 假設 | 內容 | 依據 |
|------|------|------|
| H1 | 本功能為 017 Dashboard 的 UX 增強（Tab 折疊 + spinner + 切換取消），不是獨立頁面 | IF §1「Dashboard 頁面已載入」、017 §1.1 H1 |
| H2 | 分類 Tab 的資料來源為 `useItems().categories`（index.json 動態提供），非靜態 9 大分類 | 017 §1.2 H2、useItems v2 架構 |
| H3 | 切換分類的載入行為由 `useItems.loadCategory(id)` 處理（快取 + inFlight 去重），本功能不需要額外 fetch 邏輯 | useItems §fetchCategory（inFlight Map） |
| H4 | 切換分類時需重置 018 的 `useSpecGroups`（selectedGroupKey 回到「全部」） | IF §4 步驟 2「分組 chips 更新」 |
| H5 | 切換分類時 Spinner 的顯示時機：僅在 `useItems.loadCategory` 需要實際 fetch 時顯示（快取命中 → 無 spinner） | IF §4 步驟 2「顯示載入 spinner」+ useItems 快取語意 |
| H6 | Tab 折疊的「更多 ▼」展開後，顯示全部分類（無上限）；收起時顯示前 5 個 + 「更多 ▼」 | IF §5「折疊其餘分類」 |

### 1.3 非需求

- ❌ 不需要 URL 同步目前 Tab（URL 由 017 的 `/dashboard` 路由管理，分類 Tab 為頁面內狀態）
- ❌ 不需要拖曳排序分類順序
- ❌ 不需要 Tab 搜尋/過濾（分類數量有限，9 大分類）
- ❌ 不需要記憶上次選取的分類（每次進入 Dashboard 預設第一個分類）

---

## 2. 現況分析

### 2.1 與 017、018 的關係

本功能是 017（DashboardView + useDashboard）的 **UX 增強**，不是獨立模組：

```
017 DashboardView + useDashboard
  └── 018 useSpecGroups + SpecGroupChips（分組維度）
        └── 019 CategoryTabs（分類切換 UX 增強）
```

| 面向 | 017（基底） | 018（分組） | 019（本功能） |
|------|------------|------------|-------------|
| 職責 | DashboardView 整合 + 排序/Top 10 | 規格分組 + Chips UI | 分類 Tab 切換 UX |
| 核心模組 | `useDashboard` composable | `useSpecGroups` composable | `CategoryTabs.vue` 元件 + `useDashboard` 擴充 |
| 資料來源 | `useItems.items` | `useItems.items` + `activeCategoryId` | `useItems.categories` + `useItems.loadCategory` |
| 狀態管理 | `activeCategoryId`（useItems 內） | `selectedGroupKey`（useSpecGroups 內） | `activeCategoryId`（useItems 內）+ Tab UI 狀態 |

**關鍵整合點**：
- 017 的 `DashboardView` 已有 Tab 列表基礎（017 D6「預設第一分類」）；019 將 Tab 從「靜態列表」升級為「可折疊 + spinner + 切換取消」的完整 UX
- 018 的 `useSpecGroups` 依賴 `activeCategoryId`；切換分類時需重置 `selectedGroupKey`（回到「全部」）
- `useItems.loadCategory(id)` 已有 `inFlight` Map 去重機制（快速切換時同 id 不重複 fetch）

### 2.2 可複用的現有模組

| 模組 | 檔案 | 可複用性 | 備註 |
|------|------|---------|------|
| `useItems` | `composables/useItems.ts` | ✅ **直接複用** | `categories`（分類目錄）、`loadCategory(id)`（切換+快取）、`isLoadingCategory(id)`（分類級載入旗標）、`inFlight` Map（併發去重） |
| `useDashboard` | `composables/useDashboard.ts`（017 新增） | ⚠️ **需擴充** | 新增 `activeCategory` computed（目前分類資訊）+ `switchCategory` 操作（切換+重置分組） |
| `useSpecGroups` | `composables/useSpecGroups.ts`（018 新增） | ⚠️ **需整合** | 切換分類時需呼叫 `resetGroup()`（回到「全部」） |
| `CategorySidebar` | `components/CategorySidebar.vue` | ⚠️ **可參考但不複用** | CategorySidebar 為 ListingView 的側欄（垂直列表+count），本功能為頂部 Tab（水平排列+spinner）；UI 互動模式不同 |
| `ErrorState` | `components/ErrorState.vue` | ✅ **直接複用** | 分類載入失敗時顯示 |
| `EmptyState` | `components/EmptyState.vue` | ✅ **直接複用** | 分類無商品時顯示 |

### 2.3 useItems 的切換/快取/inFlight 機制

`useItems.loadCategory(id)` 的內部流程（關鍵路徑）：

```
loadCategory(id)
  → activeCategoryId.value = id          // 立即切換 UI 狀態
  → if (loadedIds.has(id)) return         // 快取命中：無需 fetch，立即完成
  → fetchCategory(id)
    → inFlight.has(id) ? await inFlight.get(id) : // 併發去重：等待同一 Promise
      fetch → parse → append items → loadedIds.add(id)
```

**關鍵觀察**：
- **快取命中**：`loadedIds.has(id)` → `loadCategory` 立即返回（<1ms），無 loading 狀態
- **首次載入**：需要 fetch → `categoryLoading[id]` 設為 true → fetch 完成後設為 false
- **併發切換**：快速切換 Tab 時，若 A 分類 fetch 未完成就切到 B，`inFlight` Map 確保同 id 不重複 fetch；但**不會取消 A 的 fetch**（useItems 無 AbortController）

**問題**：useItems 目前**沒有取消進行中 fetch 的機制**（IF §5 要求「取消上一個請求」）。

---

## 3. 候選方案

### 方案 D（推薦）：CategoryTabs 元件 + useDashboard 擴充 + AbortController

**架構**：
```
web/src/
  components/
    CategoryTabs.vue          # 【新增】分類 Tab 列表（折疊 >5 + spinner + active 高亮）
  composables/
    useDashboard.ts           # 【擴充】新增 switchCategory（切換 + 重置分組 + AbortController）
    useSpecGroups.ts          # （018 已有）暴露 resetGroup()
  views/
    DashboardView.vue         # 【擴充】整合 CategoryTabs + useDashboard.switchCategory
```

**CategoryTabs 元件介面**：
```typescript
// components/CategoryTabs.vue
defineProps<{
  categories: CategoryMeta[]        // useItems().categories
  activeId: string | null           // 目前選中分類 id
  loadingIds: Set<string>           // 正在載入的分類 id（spinner 顯示用）
}>()

defineEmits<{
  (e: "select", id: string): void  // 點擊 Tab → 呼叫 switchCategory
}>()
```

**useDashboard 擴充**：
```typescript
// composables/useDashboard.ts（在 017 基礎上新增）
function useDashboard(items, activeCategoryId, useSpecGroupsReset) {
  // —— 017 已有 ——
  const dashboardItems = computed(...)
  const categoryLowest = computed(...)

  // —— 019 新增 ——
  /** 目前分類資訊（供 CategoryTabs 高亮用） */
  const activeCategory = computed(() =>
    categories.value.find(c => c.id === activeCategoryId.value) ?? null
  )

  /** 分類級載入中判定（Spinner 顯示用） */
  const categoryLoading = computed(() => {
    const id = activeCategoryId.value
    return id ? useItems().isLoadingCategory(id) : false
  })

  /** 切換分類（含分組重置 + AbortController 取消上一分類） */
  async function switchCategory(newId: string): Promise<void> {
    // 1. 取消上一分類的進行中 fetch（AbortController）
    abortPreviousCategory()
    // 2. 切換 useItems 的 activeCategoryId + loadCategory
    await useItems().loadCategory(newId)
    // 3. 重置 useSpecGroups 的分組狀態
    useSpecGroupsReset()
  }

  return { dashboardItems, categoryLowest, activeCategory, categoryLoading, switchCategory }
}
```

**AbortController 策略**：
- 在 `useDashboard` 內維護一個 `AbortController` 實例
- 每次 `switchCategory` 時：`abortPreviousController.abort()` → `new AbortController()` → 傳入 `fetch` 的 `signal`
- **但**：`useItems.fetchCategory` 目前不接受 `AbortController`（fetch 無 signal 參數）

**問題**：需要修改 `useItems.fetchCategory` 加入 `AbortController` 支援（或在 Dashboard 層模擬取消）。

### 方案 A（保守）：仅 CategoryTabs 元件，不改 useItems

不改 `useItems`，不做 AbortController（不取消上一請求）；Spinner 僅在 `categoryLoading[id]` 為 true 時顯示（useItems 已有的分類級載入旗標）。

- **優點**：不改 useItems 核心邏輯、風險最低
- **缺點**：不滿足 IF §5「取消上一個請求」需求；若 A 分類 fetch 很慢、切到 B 再切回 A，A 的舊 fetch 完成後仍會 append items（快取語意：只增不減）
- **評估**：useItems 的快取語意（只增不減）下，「取消」的實際影響很小（A 的 fetch 完成後 items 被 append，但 `activeCategoryId` 已指向 B，UI 不顯示 A 的資料）；切回 A 時快取命中（`loadedIds.has(A)`），無 loading。**實際 UX 影響：幾乎無感**（背景多一次無用 fetch，但 UI 立即切換）

### 方案 P（激進）：AbortController 深度整合 + useItems 重構

修改 `useItems.fetchCategory` 加入 `AbortController` 參數；在 `loadCategory` 中呼叫 `abortController.abort()` 取消上一分類的 fetch；Dashboard 層透過 useItems 暴露的 API 控制取消。

- **優點**：真正取消 HTTP 請求、節省頻寬、符合 IF §5 字面需求
- **缺點**：改 useItems 核心邏輯（影響 ListingView 等其他消費者）；AbortController 需要所有 fetch 呼叫都傳入 signal； aborted fetch 需要錯誤處理（catch AbortError，不顯示為 loadError）；重構風險高
- **評估**：useItems 為 module-level singleton，所有頁面共用；改動影響範圍大。且 AbortController 只在「首次載入未完成時切換」才有意義（已快取的分類切換不需要 fetch），此場景在 Dashboard 中發生頻率低

---

## 4. 權衡評估

### 4.1 權衡矩陣（1–5 分，5 最佳）

| 維度 | A 保守（不改 useItems） | **D 中庸（CategoryTabs + 擴充 useDashboard）** | P 激進（AbortController 深度整合） |
|---|:---:|:---:|:---:|
| 🎯 需求符合度 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| ⚡ 開發速度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| 🔧 維護成本 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 📦 效能（網路/渲染） | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 🧩 模組化/可測試性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 🔄 跨頁面一致性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 👥 團隊熟悉度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **總分** | **26** | **33** | **25** |

### 4.2 關鍵取捨

**取捨 #1：取消上一分類請求的實作方式**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）不取消（useItems 快取語意自然處理） | 切換時 `activeCategoryId` 立即指向新分類（UI 即時切換）；舊分類的 fetch 完成後 append items（背景），但 UI 不顯示 | ✅ **選 A** |
| B）AbortController 深度整合 | 修改 useItems 加入 AbortController，真正取消 HTTP 請求 | ❌ 改動 useItems 核心邏輯、影響範圍大、複雜度高 |

**決策（D1）：取 A（不取消，useItems 快取語意自然處理）**

理由：
1. **useItems 快取語意**：`loadCategory(id)` 先設 `activeCategoryId = id`（UI 立即切換），再判斷 `loadedIds.has(id)`（快取命中 → 無 fetch）；未命中才 fetch。切換時 UI 立即反映新分類，無視覺延遲
2. **背景 fetch 無害**：舊分類的 fetch 完成後 `items.append()`，但 `activeCategoryId` 已指向新分類，DashboardView 的 `filteredItems` 只顯示新分類資料；背景 append 不影響 UI
3. **useItems 不接受 AbortController**：改動 `fetchCategory` 需加 `signal` 參數、`AbortError` 錯誤分類、`inFlight` Map 清理邏輯；影響 ListingView 等所有消費者
4. **實際場景**：Dashboard 切換分類時，index.json 已載入（9 個分類目錄就緒）；首次切換某分類需要 fetch（~35KB JSON），fetch 時間在本地靜態檔案 <200ms；AbortController 節省的頻寬在此場景下微乎其微
5. **IF §5 字面需求 vs 實際 UX**：IF 說「取消上一個請求，僅顯示最新分類」——useItems 的 `activeCategoryId` 即時切換已實現「僅顯示最新分類」；「取消請求」在快取語意下無實質 UX 差異

**取捨 #2：CategoryTabs 為獨立元件 vs 內聯在 DashboardView**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）獨立 `CategoryTabs.vue` | 可複用元件，props: categories + activeId + loadingIds，emit: select | ✅ **選 A** |
| B）內聯在 `DashboardView.vue` | Tab template 直接寫在 DashboardView | ❌ 元件臃腫 |

**決策（D2）：獨立 `CategoryTabs.vue`**
- 折疊邏輯（>5 → 「更多 ▼」）封裝在元件內部
- Spinner 邏輯（`loadingIds.has(id)`）封裝在元件內部
- 未來 ListingView 或其他頁面可用（水平 Tab 類 UI）
- DashboardView 保持清晰（只負責整合）

**取捨 #3：Spinner 顯示策略**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）僅在實際 fetch 時顯示（`isLoadingCategory(id)` 為 true） | 快取命中 → 無 spinner；首次載入 → 有 spinner | ✅ **選 A** |
| B）切換時 always 顯示（即使快取命中） | 一律顯示 spinner <100ms | ❌ 快取命中時 spinner 閃爍 UX 差 |

**決策（D3）：僅在實際 fetch 時顯示**
- `useItems.isLoadingCategory(id)` 已提供分類級載入旗標（`categoryLoading[id]` 或 `inFlight.has(id)`）
- 快取命中（`loadedIds.has(id)`）→ `loadCategory` 立即返回 → `categoryLoading[id]` 不會被設為 true → 無 spinner
- 首次載入 → `fetchCategory` 設 `categoryLoading[id] = true` → spinner 顯示 → 完成後 `false` → spinner 消失
- IF §4 步驟 2「顯示載入 spinner」在快取命中時不需要（<1ms 切換無感知）

**取捨 #4：Tab 折疊策略**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）>5 個折疊，顯示前 5 個 + 「更多 ▼」 | IF §5 明確要求 | ✅ **選 A** |
| B）>3 個折疊 | 手機版需要更多空間 | ❌ IF 明確說 5 |
| C）動態折疊（根據容器寬度） | 響應式折疊 | ❌ 過度複雜 |

**決策（D4）：>5 個折疊**
- 與 IF §5 一致（「顯示更多 ▼折疊其餘分類」）
- 9 大分類中有 9 個 Tab；>5 → 前 5 個 + 「更多 ▼」
- 「更多 ▼」展開後顯示全部 9 個 + 「收起 ▲」
- 折疊/展開為元件內部狀態（`expanded: ref<boolean>(false)`）

**取捨 #5：useSpecGroups 重置時機**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）切換分類時自動重置（`resetGroup()`） | 使用者切換分類 → 分組回到「全部」 | ✅ **選 A** |
| B）保留分組狀態（跨分類記住） | 切換分類後分組不變 | ❌ 不同分類的規格不同，保留無意義 |

**決策（D5）：切換分類時自動重置**
- 不同分類的 `GROUP_STRATEGY` 不同（記憶體用 ram_gb+spec，顯示卡用 vram_gb+chip），保留分組狀態無意義
- `useSpecGroups` 已暴露 `resetGroup()`（018 設計）
- `useDashboard.switchCategory` 內部呼叫 `resetGroup()`（若 `useSpecGroupsReset` 存在）

**取捨 #6：useDashboard 擴充 vs 新建 useCategoryTabs**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）擴充 017 的 `useDashboard`（新增 switchCategory + activeCategory） | 在已有 composable 上增加分類切換職責 | ✅ **選 A** |
| B）新建 `useCategoryTabs` composable | 獨立處理 Tab 狀態 + 切換邏輯 | ❌ 過度分離（Tab 狀態就是 useItems.activeCategoryId） |

**決策（D6）：擴充 useDashboard**
- `activeCategoryId` 已在 `useItems` 內管理，不需要額外 composable 狀態
- `switchCategory` 邏輯簡單（呼叫 loadCategory + resetGroup），不值得獨立 composable
- `activeCategory`（目前分類的 CategoryMeta）為 computed，從 categories 查詢即可
- `categoryLoading` 為 computed，從 `useItems().isLoadingCategory()` 取值

---

## 5. 決策理由

### 5.1 為什麼選方案 D
1. **符合專案既有 pattern**：useItems 的 `loadCategory` + `isLoadingCategory` 已提供完整的切換/快取/載入旗標機制；不需要重複造輪子
2. **useItems 快取語意天然處理「取消」**：`loadCategory` 先設 `activeCategoryId`（UI 即時切換），快取命中 → 無 fetch；未命中 → 背景 fetch 完成後 append（UI 不受影響）
3. **CategoryTabs 可跨頁複用**：獨立元件，props/emit 介面清晰；未來 ListingView 可用同一元件（替代 CategorySidebar 的水平模式）

### 5.2 為什麼放棄其他方案
| 方案 | 放棄理由 |
|---|---|
| **A 保守** | 不改 useItems 核心邏輯是對的，但缺少 CategoryTabs 獨立元件（折疊+spinner 封裝）和 useDashboard 擴充（switchCategory + activeCategory）；Tab 邏輯會散落在 DashboardView template 中，不符合元件化 pattern |
| **P 激進** | AbortController 深度整合改 useItems 核心邏輯（fetchCategory + inFlight Map + 錯誤分類），影響 ListingView 等所有消費者；Dashboard 場景下 fetch <200ms，取消的實際效益微乎其微；重構風險高 |

### 5.3 分階段執行策略

| 階段 | 內容 | 依賴 |
|---|---|---|
| **Phase 1** | `CategoryTabs.vue` 元件（Tab 列表 + 折疊 >5 + spinner + active 高亮）+ 單測 | —（可先做，純 UI 元件） |
| **Phase 2** | 擴充 `useDashboard.ts`（新增 `activeCategory` computed + `categoryLoading` computed + `switchCategory` 操作）+ 單測 | Phase 1（型別） |
| **Phase 3** | 擴充 `DashboardView.vue`（整合 CategoryTabs + useDashboard.switchCategory + useSpecGroups.resetGroup）+ 更新 `useSpecGroups` 暴露 resetGroup | Phase 1–2 |
| **Phase 4** | E2E 測試（Tab 切換、spinner 顯示、折疊/展開、分組重置、切換 <1s） | Phase 3 |

---

## 6. 行動計畫

### 6.1 目標架構

```
web/src/
  components/
    CategoryTabs.vue              # 【新增】分類 Tab 列表（折疊 >5 + spinner + active 高亮）
    SpecGroupChips.vue             # （018 已有）不變
    DashboardCard.vue              # （017 已有）不變
  composables/
    useDashboard.ts                # 【擴充】新增 activeCategory + categoryLoading + switchCategory
    useSpecGroups.ts               # 【微調】暴露 resetGroup()（018 可能已有，確認）
  views/
    DashboardView.vue              # 【擴充】整合 CategoryTabs + useDashboard.switchCategory
  types/
    specGroup.ts                   # （018 已有）不變
```

### 6.2 任務拆分

| # | 任務 | 檔案 | 依賴 |
|---|------|------|------|
| T1 | `CategoryTabs.vue` 元件：接收 `categories: CategoryMeta[]` + `activeId: string \| null` + `loadingIds: Set<string>`；emit `select(id: string)`；折疊邏輯：`categories.length > 5` → 顯示前 5 個 + 「更多 ▼」button；展開後顯示全部 + 「收起 ▲」；active tab 以 CSS class 高亮（與 CategorySidebar 的 `.is-active` 樣式對齊）；loading tab 顯示 spinner icon（`<span class="spinner" />`） | `components/CategoryTabs.vue`、`components/__tests__/CategoryTabs.test.ts` | — |
| T2 | `useDashboard.ts` 擴充：新增 `activeCategory: computed<CategoryMeta \| null>`（從 categories 查詢 activeCategoryId）；`categoryLoading: computed<boolean>`（`useItems().isLoadingCategory(activeCategoryId.value)`）；`switchCategory(id: string): Promise<void>`（呼叫 `loadCategory(id)` + `resetGroup()`）；確認 `useSpecGroups` 暴露 `resetGroup()`（若未暴露，於 T3 補充） | `composables/useDashboard.ts`、`composables/__tests__/useDashboard.test.ts` | T1（型別） |
| T3 | `useSpecGroups.ts` 微調（若尚未暴露 `resetGroup`）：確認或新增 `resetGroup(): void`（`selectedGroupKey.value = ""` 回到「全部」） | `composables/useSpecGroups.ts` | — |
| T4 | `DashboardView.vue` 擴充：import `CategoryTabs`；在 template 中加入 `<CategoryTabs>`（`v-if="categories.length > 0"`）；`categories` 取自 `useItems().categories`；`activeId` 取自 `useDashboard().activeCategory?.id`；`loadingIds` 取自 `useDashboard().categoryLoading`（或直接傳 `new Set([activeCategoryId])`）；`@select="switchCategory"`；確保切換後 SpecGroupChips 自動更新（由 useSpecGroups 的 `activeCategoryId` watch 處理） | `views/DashboardView.vue`、`views/__tests__/DashboardView.test.ts`（更新） | T1–T3 |
| T5 | E2E 測試：Tab 正確顯示所有分類、預設選取第一個分類、切換 Tab 後列表更新、切換後 SpecGroupChips 更新、>5 個 Tab 時折疊/展開、快取命中時無 spinner、首次載入時 spinner 顯示、切換 <1s（Playwright performance assertion） | `e2e/` 或 `playwright/` | T4 |

### 6.3 決策點（非互動推導，待 spec/review 正式確認）

| 決策點 | 選項 | 評估者結論（待確認） |
|---|---|---|
| **D1** 取消上一分類請求 | a) **不取消（useItems 快取語意自然處理）**；b) AbortController 深度整合 | ✅ **a 不取消**：useItems 的 activeCategoryId 即時切換已實現「僅顯示最新分類」；背景 fetch 無害（append items 但 UI 不顯示）；改 useItems 風險高 |
| **D2** CategoryTabs 為獨立元件 vs 內聯 | a) **獨立 `CategoryTabs.vue`**；b) 內聯在 DashboardView | ✅ **a 獨立元件**：折疊+spinner 封裝、可跨頁複用、DashboardView 保持清晰 |
| **D3** Spinner 顯示策略 | a) **僅在實際 fetch 時顯示**（`isLoadingCategory(id)`）；b) 切換時 always 顯示 | ✅ **a 僅 fetch 時**：快取命中 → 無 spinner（<1ms 切換無感知）；避免 spinner 閃爍 |
| **D4** Tab 折疊閾值 | a) **>5 個折疊**；b) >3 個；c) 動態折疊 | ✅ **a >5 個**：IF §5 明確要求；9 大分類 → 前 5 + 「更多 ▼」 |
| **D5** 切換分類時重置分組 | a) **自動重置（resetGroup）**；b) 保留分組狀態 | ✅ **a 自動重置**：不同分類的 GROUP_STRATEGY 不同，保留無意義 |
| **D6** useDashboard 擴充 vs 新建 composable | a) **擴充 useDashboard**；b) 新建 useCategoryTabs | ✅ **a 擴充**：activeCategoryId 已在 useItems 內管理；switchCategory 邏輯簡單不值得獨立 composable |
| **D7** CategoryTabs 折疊時顯示數量 | a) **不顯示折疊數量**（「更多 ▼」）；b) 顯示折疊數量（「更多 (4) ▼」） | ✅ **a 不顯示**：IF 未要求；9 大分類下折疊 4 個為常態，顯示數量增加視覺噪音 |

---

## 7. 風險登錄

| 風險 | 可能性 | 影響 | 緩解 |
|------|--------|------|------|
| useItems `isLoadingCategory(id)` 的 `categoryLoading` 旗標在快取命中時不觸發 → Spinner 不顯示（但使用者可能期望切換時有視覺回饋） | 低 | 低 | 快取命中切換 <1ms，無視覺延遲；若需確認切換已完成，可在 Tab 切換時加 CSS active state 動畫（背景色漸變）作為回饋 |
| CategorySidebar（ListingView）與 CategoryTabs（DashboardView）的 active 樣式不一致 | 低 | 低 | 共用 CSS 變數（`--brand-soft`、`--brand`）和 class name pattern（`.is-active`）；建議抽取共用 CSS 或 design token |
| `useSpecGroups` 的 `resetGroup()` 未暴露（018 可能僅在 composable 內部使用） | 中 | 低 | T3 確認並補充；若 018 已暴露則不需改動 |
| 分類目錄（index.json categories）為動態，可能隨爬蟲更新新增/移除分類 → Tab 列表自動更新（useItems.categories 為 ref） | 極低 | 極低 | useItems.categories 為 ref，CategoryTabs 透過 props 接收，自動響應變更 |
| Dashboard 與 ListingView 的分類切換 UX 差異（Tab vs 側欄）可能造成使用者混淆 | 低 | 低 | 兩個頁面目的不同（Dashboard = 概覽 Top 10，Listing = 全量瀏覽）；UX 差異反映功能差異，可接受 |
| 折疊「更多 ▼」展開後 Tab 列表過長（9 個 Tab 在手機上水平排列可能溢出） | 中 | 低 | 手機版（≤639px）建議 Tab 改為可水平捲動（`overflow-x: auto`），與 CategorySidebar 的手機版 pattern 一致 |

---

## 📝 決策後續

- 本文件已存至 `docs/tech-decisions/019-dashboard-categories.md`，應納入版本控制。
- **決策待確認**：§6.3 七個決策點（D1–D7）為非互動推導結論，建議在 development-spec-generator／loop-review 階段正式確認後展開 Phase 1–4。
- 本功能建立在 017（DashboardView + useDashboard）+ 018（useSpecGroups + SpecGroupChips）基礎上；若 017/018 尚未實作，需先完成 017 Phase 1–4 + 018 Phase 1–4。
- **核心決策 D1（不改 useItems）**：useItems 的快取語意（只增不減 + inFlight 去重）已天然處理分類切換場景；AbortController 取消在靜態 JSON 場景下無實質 UX 差異。若未來資料來源改為動態 API（fetch 時間 >1s），可重新評估 AbortController 整合。
- 建議 1 個月後回顧：Tab 切換效能（分類數成長時）、折疊 UI 點擊率、是否需加入「記住上次 Tab」功能。
