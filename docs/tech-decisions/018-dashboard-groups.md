# 開發方案決策文件：#018 Dashboard — 依規格分組比較商品

> **性質**：前端功能層技術評估（tech-assessment-generator 引導，非互動模式產出）
> **對應**：GitHub Issue **#18** `feat(P1): Dashboard — 依規格分組比較商品`
> **範圍**：`web/src/`（前端新增 useSpecGroups composable、SpecGroupChips 元件，擴充 DashboardView）
> **上游文件**：`docs/interaction-flows/018-dashboard-groups.md`（主輸入）、`docs/tech-decisions/017-dashboard-items.md`（同功能群參考）
> **決策方式**：基於上游文件 + 現有專案架構推導，**不提問**；所有決策點由評估者給定推薦結論，待實作前的 spec/review 階段正式確認

---

## 📌 決策摘要

| 項目 | 內容 |
|------|------|
| **最終方案** | **方案 D「獨立 useSpecGroups composable + SpecGroupChips 元件 + 策略配置」**：新增 `useSpecGroups.ts` composable（純函數分組邏輯）、`SpecGroupChips.vue` 元件（折疊 Chips UI）、`GROUP_STRATEGY` 配置（per-category 分組欄位定義）；複用 `useItems` singleton 的 `items` + `activeCategoryId`；分組狀態為 composable 內 ref（不路由同步）；最便宜者 🥇 由 `usePriceDelta.currentPrice` 計算 |
| **決策日期** | 2026-08-17 |
| **決策前提** | ① Dashboard 為 017 已建立的獨立頁面（`/dashboard`）；② 017 已有 `useDashboard` composable（排序 + Top 10 + 歷史最低價）；③ 本功能在 017 基礎上增加「規格分組」維度；④ 無後端，client-side 篩選 <300ms；⑤ 分組 Chips > 8 個時折疊為「更多 ▼」 |
| **核心效益** | 獨立 composable 符合專案 pattern；策略配置易擴充新分類；SpecGroupChips 可跨頁複用；client-side 過濾零延遲 |
| **共識程度** | ✅ 非互動推導，共識待 spec/review 階段確認（§6.3） |

---

## 1. 需求回顧

### 1.1 使用者／Issue 訴求

> 「將同規格商品自動分組（如 DDR5 32GB、DDR4 16GB），讓使用者精確比較同規格商品的價格差異。」

**拆解出的核心需求**：

| 需求項 | 說明 | 來源 |
|--------|------|------|
| 自動分組 | 解析 spec 欄位產生規格分組（如 DDR5 32GB × 品牌） | IF §4 步驟 1 |
| 分組 Chips UI | 顯示所有分組，選取後 client-side 篩選 | IF §4 步驟 1–3 |
| 最便宜者標示 🥇 | 每個分組內最便宜者標示金牌 | IF §4 步驟 2 |
| 無規格商品歸入「其他」 | 無結構化 spec 的商品不遺漏 | IF §5 異常處理 |
| Chips > 8 折疊 | 超過 8 個分組時折疊為「更多 ▼」 | IF §6 邊界限制 |
| 切換 < 300ms | client-side 篩選，無 loading | IF §6 邊界限制 |

### 1.2 需求假設（評估者由上游文件與現況推導）

| 假設 | 內容 | 依據 |
|------|------|------|
| H1 | 分組邏輯與 017 `useDashboard`（排序 + Top 10）為不同關注點，應分離 | 職責分離：排序/Top 10 vs 分組/篩選 |
| H2 | 分組 Chips 為 DashboardView 專用 UI，但抽取為獨立元件以便未來複用（如 ListingView） | IF §2.2 入口為「選取特定分類後自動觸發」 |
| H3 | 分組狀態不需要路由同步（不需 URL 可分享的分組狀態） | IF 未提及深連結需求；Dashboard 為瀏覽型頁面 |
| H4 | 分組鍵由 per-category 策略配置決定（不同分類用不同 spec 欄位組合） | IF §3 步驟 1「解析規格欄位」；`specChipTexts` 已有 per-category 邏輯 |
| H5 | 🥇 最便宜判定基於目前價格（`usePriceDelta.currentPrice`），非歷史最低價 | IF §4 步驟 2「按價格低→高排序，最便宜者標示 🥇」；017 已有 `currentPrice` |
| H6 | 本功能建立在 017 的 `DashboardView` + `useDashboard` 基礎上，而非獨立頁面 | 018 為 017 的延伸功能（US-02 依賴 US-01） |

### 1.3 非需求

- ❌ 不需要路由參數同步分組狀態（URL 不含 group query param）
- ❌ 不需要跨分類分組（分組只在單一分類內）
- ❌ 不需要拖曳排序分組順序
- ❌ 不需要自訂分組規則（規則由策略配置預定義）

---

## 2. 現況分析

### 2.1 可複用的現有模組

| 模組 | 檔案 | 可複用性 | 備註 |
|------|------|---------|------|
| `useItems` | `composables/useItems.ts` | ✅ **直接複用** | `items`（已載入商品）、`activeCategoryId`（目前分類）、`itemToCategory`（對照 map） |
| `useDashboard` | `composables/useDashboard.ts`（017 新增） | ⚠️ **需理解介面** | 017 產出 `dashboardItems`（排序 + Top 10），本功能在此基礎上增加分組維度 |
| `usePriceDelta` | `composables/usePriceDelta.ts` | ✅ **直接複用** | `currentPrice`（目前價格）、`specChipTexts`（規格 chips 顯示） |
| `useFilters` | `composables/useFilters.ts` | ⚠️ **不整合** | 已有搜尋+規格篩選（`>=` 條件），分組邏輯不同（分組是 grouping，不是 filtering） |
| `EmptyState` | `components/EmptyState.vue` | ✅ **直接複用** | 分組無商品時顯示 |
| `formatPrice` | `utils/format.ts` | ✅ **直接複用** | 價格千分位格式化 |

### 2.2 ItemSpec 可用分組欄位

| 分類 | 分組欄位建議 | 範例分組鍵 |
|------|-------------|-----------|
| 記憶體 | `ram_gb` + `spec.spec`（如有，含 DDR type） | `DDR5 32GB`、`DDR4 16GB` |
| 顯示卡 | `vram_gb` + `chip` | `12GB RTX 4070`、`8GB RTX 4060` |
| SSD | `capacity_gb` + `interface` | `1TB NVMe`、`500GB SATA` |
| HDD | `capacity_gb` + `rpm` | `2TB 7200RPM`、`1TB 5400RPM` |
| CPU | `cores` + `base_ghz`（或 `socket`） | `8核 3.8GHz`、`16核 LGA1700` |
| 主機板 | `socket` + `chipset` | `AM5 B650`、`LGA1700 B760` |
| 電源 | `wattage_w` | `750W`、`850W` |
| 其他 | `brand`（fallback） | `ASUS`、`MSI` |

### 2.3 與 017 `useDashboard` 的關係

017 的 `useDashboard` 負責：
- 排序（按 `currentPrice` 升冪）
- 取 Top 10（`slice(0, 10)`）
- 歷史最低價計算（`categoryLowest` Map）

018 的分組邏輯是**另一個維度**：
- 先分組（spec → groupKey）
- 再在每個分組內排序 + 取 Top N

**關鍵問題**：分組後的 Top N 應如何處理？

| 方案 | 說明 | 結論 |
|------|------|------|
| A）分組後每組 Top N | 每個分組顯示前 N 名（N 可為 10 或較小值） | ⚠️ 分組多時總卡片數爆炸（10 組 × 10 = 100） |
| B）分組後全量顯示 | 每個分組顯示所有商品（無 Top N 限制） | ✅ **推薦**：分組本身就是篩選，每組商品數有限（同規格通常 <20），全量顯示更合理 |
| C）分組 + 全站 Top 10 混合 | 不分組，Top 10 中標示所屬分組 | ❌ 違反需求（使用者要「同規格比較」） |

**決策（D-RELATION）：取 B（分組後全量顯示）**
- 分組的目的是「同規格比較」，每組商品數有限（同規格 <20 商品），不需要 Top N 限制
- 若某分組商品過多（>50），可在後續版本加入分組內 Top N，但初版不需要
- 017 的 `useDashboard`（排序 + Top 10）在分組模式下**不適用**——分組後全量顯示，無 Top 10

---

## 3. 候選方案

### 方案 D（推薦）：獨立 useSpecGroups composable + SpecGroupChips 元件

**架構**：
```
composables/
  useSpecGroups.ts           # 【新增】分組邏輯（純函數：items → groups + selectedGroup → filteredItems）
  useDashboard.ts            # （017 已有）排序 + 歷史最低價（分組模式下不使用 Top 10 邏輯）
components/
  SpecGroupChips.vue         # 【新增】分組 Chips UI（折疊 >8 個）
  DashboardCard.vue          # （017 已有）商品卡片
views/
  DashboardView.vue          # （017 已有）整合分組 Chips + 分組篩選列表
types/
  specGroup.ts               # 【新增】分組策略 + 分組結果型別
```

**useSpecGroups composable 介面**：
```typescript
function useSpecGroups(
  items: Ref<Item[]>,              // 目前分類的商品列表
  activeCategoryId: Ref<string | null>, // 目前分類 ID（用於選擇分組策略）
) {
  // —— 分組計算 ——
  const groups: computed<GroupOption[]>    // 所有分組選項 [{key, label, count}]
  const selectedGroupKey: ref<string>     // 目前選取的分組鍵（null = "全部"）
  const filteredItems: computed<Item[]>   // 分組篩選後的商品列表
  const hasGroups: computed<boolean>      // 該分類是否支援分組（false → 不顯示 Chips）

  // —— 操作 ——
  function selectGroup(key: string): void // 切換分組
  function resetGroup(): void             // 回到「全部」
  return { groups, selectedGroupKey, filteredItems, hasGroups, selectGroup, resetGroup }
}
```

**GROUP_STRATEGY 配置**：
```typescript
// types/specGroup.ts
interface GroupStrategy {
  /** 分組欄位鍵（多欄位依序組合） */
  fields: (keyof ItemSpec)[]
  /** 分組鍵格式化函式（null → "其他"） */
  formatKey: (spec: ItemSpec) => string | null
}

const GROUP_STRATEGY: Record<string, GroupStrategy> = {
  記憶體: {
    fields: ["ram_gb", "spec"],
    formatKey: (s) => {
      const ddr = typeof s.spec === "string" ? s.spec : ""  // "DDR5" / "DDR4"
      const ram = s.ram_gb != null ? `${s.ram_gb}GB` : null
      if (!ddr && !ram) return null
      return ddr && ram ? `${ddr} ${ram}` : ddr || ram || null
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
  // ... 其他分類
}
```

**資料流**：
```
useItems().items (Ref<Item[]>)
  → useSpecGroups(items, activeCategoryId)
    → parseGroupKey(item) → groupKey (string | null)
    → collect unique groupKeys → groups (GroupOption[])
    → selectedGroupKey (ref) → filteredItems (computed: items.filter by groupKey)
  → DashboardView
    → SpecGroupChips (groups, selectedGroupKey, @select)
    → DashboardCard × filteredItems.length
```

### 方案 L（保守）：整合進 useFilters

將分組邏輯直接加到 `useFilters` composable 中（新增 `groupKey` 狀態 + `groupedItems` computed）。

- **優點**：不新增 composable、所有篩選邏輯集中
- **缺點**：
  - `useFilters` 職責膨脹（搜尋 + 規格條件 + 分組 = 三種收斂維度）
  - `useFilters` 已有 `filteredItems`（搜尋+規格），再加 `groupedItems`（分組）會有兩個 filtered 列表，呼叫端需決定用哪個
  - `useFilters` 的 `categoryId` 參數與分組策略耦合（分組策略需知道 categoryId 來選 GROUP_STRATEGY）
  - 測試複雜度增加（useFilters 已有 keyword/conditions/categoryId 三個狀態）
- 結論：違反 SRP，增加現有模組複雜度，不可取

### 方案 P（激進）：路由同步 + 全站分組

將分組狀態同步到 URL query param（`?group=DDR5+32GB`），並支援跨分類分組。

- **優點**：可分享連結、瀏覽器後退恢復分組狀態
- **缺點**：
  - IF 未提及深連結需求（H3）
  - 跨分類分組無意義（不同分類的規格欄位不同，混在一起分組無比較價值）
  - 路由同步增加複雜度（watch route query → update selectedGroupKey → 反向 sync）
  - 初版不需要此複雜度
- 結論：過度設計，違反 YAGNI

---

## 4. 權衡評估

### 4.1 權衡矩陣（1–5 分，5 最佳）

| 維度 | L 整合 useFilters | **D 獨立 composable** | P 路由同步 |
|---|:---:|:---:|:---:|
| 🎯 需求符合度 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| ⚡ 開發速度 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| 🔧 維護成本 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 🧩 模組化/可測試性 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 🔄 複用性（跨頁面） | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 👥 團隊熟悉度 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 📦 效能（<300ms） | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **總分** | **20** | **33** | **23** |

### 4.2 關鍵取捨

**取捨 #1：分組邏輯的位置**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）新 composable `useSpecGroups` | 獨立模組，接收 items + categoryId，回傳 groups + filteredItems | ✅ **選 A** |
| B）整合 `useFilters` | 在現有 useFilters 中新增 groupKey 狀態 | ❌ SRP 違反 |

**決策（D1）：新 composable `useSpecGroups`**
- 與 `useFilters` 職責分離：`useFilters` = 搜尋 + 規格條件（`>=` 篩選）；`useSpecGroups` = 分組（grouping）
- 兩者可獨立測試、獨立演進
- `useSpecGroups` 可在 `useFilters` 之前或之後執行（分組是獨立維度）
- 符合專案 composable 分離 pattern（每個 view 有獨立 composable）

**取捨 #2：分組 Chips 為獨立元件 vs 內聯**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）獨立 `SpecGroupChips.vue` | 可複用元件，props: groups + selectedKey，emit: select | ✅ **選 A** |
| B）內聯在 `DashboardView.vue` | Chips template 直接寫在 DashboardView 的 `<template>` 中 | ❌ 元件臃腫 |

**決策（D2）：獨立 `SpecGroupChips.vue`**
- 折疊邏輯（>8 個 → 「更多 ▼」）封裝在元件內部，DashboardView 不需處理
- 未來 ListingView 或其他頁面可用同一元件
- DashboardView 保持清晰（只負責整合，不負責 Chips 渲染細節）

**取捨 #3：分組狀態管理**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）composable 內 `ref` | `selectedGroupKey` 在 useSpecGroups 內部管理 | ✅ **選 A** |
| B）路由參數同步 | URL `?group=DDR5+32GB`，watch route query | ❌ 過度設計 |

**決策（D3）：composable 內 ref**
- IF 未提及深連結需求（H3）
- Dashboard 為瀏覽型頁面，瀏覽器後退恢復分組狀態非必要
- 降低初版複雜度；若未來需 URL 同步，可在 useSpecGroups 內加入 `watch(selectedGroupKey, ...)` 同步到 route query
- 分組切換 <300ms 由 composable 內 ref 保證（無路由開銷）

**取捨 #4：分組鍵的格式化**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）`GROUP_STRATEGY` 配置 + `formatKey` 函式 | 每個分類定義 formatKey（spec → string） | ✅ **選 A** |
| B）硬編碼 switch/case | 在 useSpecGroups 內用 `if (category === '記憶體') ...` | ❌ 難以維護 |

**決策（D4）：策略配置**
- 與 `specChipTexts`（usePriceDelta.ts）的 per-category 邏輯對齊
- `formatKey` 可返回 `null`（無規格 → 歸入「其他」分組）
- 擴充新分類只需新增 `GROUP_STRATEGY` 項目，不改 useSpecGroups 核心邏輯
- 可獨立單測（formatKey 為純函數）

**取捨 #5：「全部」分組是否顯示**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）顯示「全部」Chip（預設選取，顯示所有商品） | 使用者可回到不分組視圖 | ✅ **選 A** |
| B）不顯示「全部」，預設選第一個分組 | 強制分組 | ❌ 靈活性低 |

**決策（D5）：顯示「全部」Chip**
- 使用者可能不想分組，只想看所有商品
- 「全部」作為預設選取（`selectedGroupKey` 初始值為 `""` 或特殊常量 `ALL`）
- 點擊「全部」→ `selectedGroupKey = null` → 不過濾，顯示全部商品
- 與 IF §4 步驟 2「預設選取第一組」有衝突？→ **修正**：IF 的「第一組」指「全部」（第一個 Chip），若不顯示「全部」則指第一個分組鍵。此處取「全部」方案，預設選取「全部」。

**取捨 #6：分組後的 Top N 限制**

| 選項 | 說明 | 結論 |
|------|------|------|
| A）分組後全量顯示（無 Top N） | 每組顯示所有商品 | ✅ **選 A** |
| B）分組後每組 Top 10 | 與 017 一致 | ❌ 分組多時卡片數爆炸 |

**決策（D6）：全量顯示**
- 分組本身已是篩選（同規格商品通常 <20）
- 017 的 Top 10 是「各分類最便宜」的概覽邏輯；018 的分組是「同規格精確比較」，目標不同
- 若某分組商品 >50，可在後續版本加 Top N，但初版不需要

---

## 5. 決策理由

### 5.1 為什麼選方案 D
1. **符合專案既有 pattern**：useItems、useFilters、useWatchlist、useCompare 為獨立 composable；useSpecGroups 遵循此 pattern，每個 composable 負責一個關注點
2. **職責分離清晰**：`useFilters`（搜尋+規格條件）vs `useSpecGroups`（分組）為不同維度的收斂，分離後各自可獨立演進、獨立測試
3. **策略配置易擴充**：`GROUP_STRATEGY` 配置新增分類只需新增一行，不改核心邏輯；`specChipTexts` 已有 per-category pattern 可參考

### 5.2 為什麼放棄其他方案
| 方案 | 放棄理由 |
|---|---|
| **L 整合 useFilters** | SRP 違反：useFilters 已有 keyword + conditions + categoryId 三種狀態，再加 groupKey 會有四種狀態、兩個 filtered 列表（filteredItems vs groupedItems），呼叫端需決定用哪個；測試複雜度倍增 |
| **P 路由同步** | 過度設計：IF 未提及深連結需求；跨分類分組無意義；路由同步增加 watch/watchEffect + route query 讀寫邏輯，初版不需要 |

### 5.3 分階段執行策略

| 階段 | 內容 | 依賴 |
|---|---|---|
| **Phase 1** | `types/specGroup.ts`（GROUP_STRATEGY 配置 + GroupOption 型別）+ `useSpecGroups.ts` composable（分組邏輯 + 單測） | — |
| **Phase 2** | `SpecGroupChips.vue` 元件（Chips UI + 折疊 >8 + 單測） | Phase 1（型別） |
| **Phase 3** | 擴充 `DashboardView.vue`（整合 useSpecGroups + SpecGroupChips + 分組篩選列表）+ 路由不變 | Phase 1–2 |
| **Phase 4** | E2E 測試（分組正確、Chips 切換、折疊、無規格歸入「其他」、<300ms） | Phase 3 |

---

## 6. 行動計畫

### 6.1 目標架構

```
web/src/
  types/
    specGroup.ts                   # 【新增】GroupStrategy、GroupOption 型別 + GROUP_STRATEGY 配置
  composables/
    useSpecGroups.ts               # 【新增】分組邏輯（pure function：items → groups + filteredItems）
    useDashboard.ts                # （017 已有）不變（分組模式下不使用 Top 10 邏輯）
  components/
    SpecGroupChips.vue             # 【新增】分組 Chips UI（折疊 >8）
    DashboardCard.vue              # （017 已有）不變
  views/
    DashboardView.vue              # （017 已有）擴充：加入 SpecGroupChips + 分組篩選
```

### 6.2 任務拆分

| # | 任務 | 檔案 | 依賴 |
|---|------|------|------|
| T1 | `types/specGroup.ts`：定義 `GroupStrategy`（fields + formatKey）、`GroupOption`（key + label + count）、`GROUP_STRATEGY` 配置（記憶體/顯示卡/SSD/HDD/CPU/主機板/電源/其他）；formatKey 為純函數，null → 「其他」 | `types/specGroup.ts`、`types/__tests__/specGroup.test.ts` | — |
| T2 | `useSpecGroups.ts`：接收 `items: Ref<Item[]>` + `activeCategoryId: Ref<string | null>`；計算 `groups: computed<GroupOption[]>`（收集唯一 groupKey → 排序 → 加入「全部」+「其他」）；`selectedGroupKey: ref<string>`（初始 `""` 表示全部）；`filteredItems: computed<Item[]>`（selectedGroupKey 為空 → 全部，否則 filter by groupKey）；`hasGroups: computed<boolean>`（groups.length > 1 才顯示 Chips） | `composables/useSpecGroups.ts`、`composables/__tests__/useSpecGroups.test.ts` | T1 |
| T3 | `SpecGroupChips.vue`：接收 `groups: GroupOption[]` + `selectedKey: string`；emit `select(key: string)`；折疊邏輯：groups.length > 8 → 顯示前 7 個 + 「更多 ▼」button；展開後顯示全部 + 「收起 ▲」；active chip 以 CSS class 高亮 | `components/SpecGroupChips.vue`、`components/__tests__/SpecGroupChips.test.ts` | T1 |
| T4 | 擴充 `DashboardView.vue`：import `useSpecGroups`；在 `useItems().items` 載入後呼叫 `useSpecGroups(items, activeCategoryId)`；在 template 中加入 `<SpecGroupChips>` （`v-if="hasGroups"`）；商品列表改為 `filteredItems`（分組篩選後）而非直接用 `items`；切換分組時呼叫 `selectGroup(key)` | `views/DashboardView.vue`、`views/__tests__/DashboardView.test.ts`（更新） | T2、T3 |
| T5 | E2E 測試：分組 Chips 正確顯示、切換分組後列表更新、折疊/展開「更多」、無規格商品歸入「其他」、分組切換 <300ms（Playwright performance assertion） | `e2e/` 或 `playwright/` | T4 |

### 6.3 決策點（非互動推導，待 spec/review 正式確認）

| 決策點 | 選項 | 評估者結論（待確認） |
|---|---|---|
| **D1** 分組邏輯位置 | a) 整合 useFilters；b) **獨立 useSpecGroups composable** | ✅ **b 獨立**：SRP 分離、可獨立測試、符合專案 pattern |
| **D2** SpecGroupChips | a) 獨立元件 `SpecGroupChips.vue`；b) 內聯在 DashboardView | ✅ **a 獨立元件**：折疊邏輯封裝、可跨頁複用 |
| **D3** 分組狀態管理 | a) **composable 內 ref**；b) 路由參數同步 | ✅ **a ref**：IF 無深連結需求、降低複雜度 |
| **D4** 分組鍵格式化 | a) **GROUP_STRATEGY 配置 + formatKey**；b) 硬編碼 switch/case | ✅ **a 策略配置**：易擴充、可單測、與 specChipTexts pattern 對齊 |
| **D5** 是否顯示「全部」Chip | a) **顯示（預設選取）**；b) 不顯示（預設第一分組） | ✅ **a 顯示**：靈活性高、使用者可回到不分組視圖 |
| **D6** 分組後 Top N | a) **全量顯示**；b) 每組 Top 10 | ✅ **a 全量**：分組已是篩選、同規格 <20 商品、避免卡片數爆炸 |
| **D7** 「其他」分組位置 | a) 排在最後；b) 排在最前；c) **不顯示（無規格商品不出現在分組 Chips 中）** | ✅ **c 不顯示**：IF §5 說「歸入其他分組」但未要求顯示「其他」Chip；無規格商品在「全部」中可見即可；避免使用者困惑（「其他」含義不清） |

---

## 7. 風險登錄

| 風險 | 可能性 | 影響 | 緩解 |
|------|--------|------|------|
| `spec.spec` 欄位（DDR type）不是所有記憶體商品都有 → 分組鍵不完整（只有 "32GB" 無 "DDR5"） | 中 | 低 | formatKey 設計為「有 DDR 顯示 DDR + 容量，無 DDR 則只顯示容量」；「32GB」本身已是有效分組鍵 |
| 分組 Chips > 8 個時折疊 UI 使用者可能忽略「更多 ▼」 | 低 | 低 | 折疊按鈕以明顯樣式（如藍色文字 + icon）提示；可選：顯示折疊數量（「更多 (5) ▼」） |
| `useSpecGroups` 的 `filteredItems` 與 `useFilters` 的 `filteredItems` 同名衝突 | 低 | 中 | useSpecGroups 回傳 `groupedItems`（非 `filteredItems`）；或在 DashboardView 解構時改名（`const { filteredItems: groupFiltered }`） |
| 快速切換分組（連續點擊多個 Chip）導致 computed 重算 | 極低 | 極低 | computed 為 lazy reactivity（Vue 3 優化）；重算成本為 `items.filter()`（<1ms for <1000 items） |
| GROUP_STRATEGY 配置的 formatKey 與 `specChipTexts`（usePriceDelta）顯示不一致 | 低 | 低 | formatKey 與 specChipTexts 為不同用途（分組鍵 vs 顯示 chips）；格式不同是正常的；可加 equivalence test 確保分組鍵涵蓋 specChipTexts 顯示的欄位 |

---

## 📝 決策後續

- 本文件已存至 `docs/tech-decisions/018-dashboard-groups.md`，應納入版本控制。
- **決策待確認**：§6.3 七個決策點（D1–D7）為非互動推導結論，建議在 development-spec-generator／loop-review 階段正式確認後展開 Phase 1–4。
- 本功能建立在 017 的 `DashboardView` + `useDashboard` 基礎上；分組模式下不使用 017 的 Top 10 邏輯（分組後全量顯示）。
- `GROUP_STRATEGY` 配置的 formatKey 需基於真實資料驗證（確認 `spec.spec` 欄位確實含有 DDR type 資訊）；若不含，需調整分組策略（如改用 ram_gb + clock_mhz）。
- 建議 1 個月後回顧：分組 Chips 使用率、折疊 UI 點擊率、是否需加入「全部」以外的跨分類分組。
