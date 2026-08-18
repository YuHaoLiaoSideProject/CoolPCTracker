# UI/UX Review #23 — Dashboard 響應式佈局與視覺規範

> **審查對象**：`docs/uiux/023-dashboard-design.md`
> **對應互動流程**：`docs/interaction-flows/019-dashboard-categories.md`
> **對應技術決策**：`docs/tech-decisions/019-dashboard-categories.md`
> **共用 Token**：`web/src/styles/tokens.css`
> **參考元件**：`web/src/components/CategorySidebar.vue`
> **審查日期**：2026-08-17
> **審查者**：UI/UX Review Agent

---

## 審查結果總覽

| # | 審查項目 | 結果 | 說明 |
|---|---------|------|------|
| 1 | 完整性（元件覆蓋） | ⚠️ 建議 | 4 個主要元件已涵蓋，但 Tab 折疊行為與 Spinner 視覺規格缺失 |
| 2 | RWD 斷點 | ❌ 缺失 | §5 行為表與 §7 CSS 斷點不一致（767 vs 639） |
| 3 | Design Token 一致性 | ✅ 通過 | 所有引用值與 tokens.css 完全一致 |
| 4 | 無障礙 WCAG | ⚠️ 建議 | 基礎合規，但缺少語義結構、跳頁導覽、active 狀態對比度不足 |
| 5 | 狀態覆蓋（8 態） | ⚠️ 建議 | 大部分覆蓋，但 CategoryTabs 缺 loading/error 態、Card 缺 error 態 |
| 6 | 動畫規範 | ✅ 通過 | 核心動畫已定義，prefers-reduced-motion 正確處理 |
| 7 | 與互動流程對齊 | ❌ 缺失 | Tab 折疊行為（IF §5）未在設計中體現 |
| 8 | 與技術決策對齊 | ⚠️ 建議 | D1-D3/D5-D6 已體現，D4（Tab 折疊）缺失，D3（Spinner）無視覺規格 |

---

## 1. 完整性 — 元件覆蓋

### ✅ 主要元件已涵蓋

| 元件 | 規格位置 | 狀態矩陣 | 備註 |
|------|---------|---------|------|
| CategoryTabs | §7.1 | §4.1 | ✅ |
| SpecGroupChips | §7.2 | §4.2 | ✅ |
| DashboardCard | §7.3 | §4.3 | ✅ |
| DashboardSkeleton | §7.4 | §4.4 | ✅ |
| DashboardView 容器 | §7.5 | — | ✅ |

### ❌ Tab 折疊行為缺失

IF §4 步驟 1 與 §5 明確要求：「分類 Tab >5 個時，顯示「更多 ▼」折疊其餘分類」。Tech Decision D4 也選定「>5 個折疊」。然而 **§7.1 CategoryTabs 完全沒有折疊/展開的 CSS 規格或行為描述**。

SpecGroupChips（§7.2）有折疊按鈕規格，但 CategoryTabs 沒有。這是上游文件明確要求的功能，在設計文件中遺漏。

**影響**：實作者無法從本文件得知 Tab 折疊的視覺行為（折疊阈值、按鈕樣式、展開動畫）。

### ⚠️ Spinner 視覺規格缺失

Interaction Flow §4 步驟 2 要求切換分類時「顯示載入 spinner」。Tech Decision D3 決定「僅在實際 fetch 時顯示」。然而 **§4.1 狀態矩陣與 §7.1 元件規格中均未定義 Spinner 的視覺樣式**（大小、顏色、動畫）。

建議至少補充：Spinner 為小圓圈（16px）+ `--brand` 色 + 旋轉動畫，顯示於 Tab 文字右側。

### ⚠️ Chip 高度缺少 Token 引用

§3.2 記錄 Chip 高度為 `32px / 44px`，但 CSS 對應欄寫「自訂」，未使用既有 token。tokens.css 中 `--h: 36px` 是 Tab/按鈕高度，Chip 用 32px 是刻意小一級（§2 設計原則 #2：「第二層篩選」），但建議明確註記為何不沿用 `--h`，或新增 `--h-chip: 32px` token 以保持一致性。

---

## 2. RWD 斷點 — ❌ 缺失

### 斷點數值不一致

| 位置 | Tablet 範圍 | Mobile 範圍 |
|------|-----------|------------|
| §5 行為表 | 768–1023 | ≤767 |
| §7.1 CSS | `max-width: 1023px` | `max-width: 639px` |
| §7.2 CSS | `max-width: 1023px` | `max-width: 639px` |
| CategorySidebar.vue | `max-width: 1023px` | `max-width: 639px` |

**問題**：§5 行為表定義 mobile 為 ≤767px，但所有 CSS 實作使用 ≤639px。兩者之間 640–767px 的裝置在行為表中被歸為「手機」，但在 CSS 中被歸為「平板」。

**建議**：統一斷點。既然現有 codebase（CategorySidebar.vue）已使用 1023/639，建議將 §5 行為表修正為：

| 行為 | ≥1024（桌面） | 640–1023（平板） | ≤639（手機） |
|------|-------------|-----------------|-------------|

---

## 3. Design Token 一致性 — ✅ 通過

### Token 值比對

所有 §3.1 列出的 token 與 `tokens.css` 逐項比對：

| Token | Design Doc | tokens.css | 結果 |
|-------|-----------|-----------|------|
| `--brand` | `#1f6feb` / `#4c8dff` | ✅ 一致 | |
| `--brand-soft` | `#e8f0fe` / `#1d2f4d` | ✅ 一致 | |
| `--price-up/down/flat` | 三色 | ✅ 一致 | |
| `--bg/surface/surface-2` | 三色 | ✅ 一致 | |
| `--border` | `#e5e7eb` / `#2a3340` | ✅ 一致 | |
| `--text/text-dim` | 二色 | ✅ 一致 | |
| `--radius/radius-sm` | `10px / 6px` | ✅ 一致 | |
| `--shadow/shadow-hover` | 兩組值 | ✅ 一致 | |
| `--h/--h-mobile` | `36px / 44px` | ✅ 一致 | |
| `--fs` | `0.875rem` | ✅ 一致 | |
| `--transition/--fade` | `0.2s ease / 150ms` | ✅ 一致 | |
| `--focus-ring` | `3px solid rgba(...)` | ✅ 一致 | |
| `--font-stack/--font-mono` | 字體清單 | ✅ 一致 | |

### ⚠️ tokens.css 中有但設計文件未列出的 token

`--warn-bg/border/text`、`--accent`、`--success`、`--danger`、`--warning` 未出現在 §3.1 表格中。這些 token 不直接用於 Dashboard 元件，但若 ErrorState / EmptyState 共用元件使用它們，建議至少加註腳說明「沿用 tokens.css 中的 warning/danger 色彩」。

### ⚠️ Chip active 白色硬編碼

§7.2 Chip active 狀態 `color: #fff` 為硬編碼。tokens.css 無 `--text-inverse` 或 `--color-white` token。建議新增 `--text-inverse: #fff` 或至少在 §3.2 註記此為已知例外。

---

## 4. 無障礙 WCAG — ⚠️ 建議

### ✅ 已合規

| WCAG 準則 | 設計對應 | 結果 |
|-----------|---------|------|
| 1.4.1 不以顏色單獨傳達 | §6：🥇 為輔助標示 | ✅ |
| 2.5.5 目標尺寸 | §5：行動端 44px | ✅ |
| 2.4.7 焦點可見 | §6：`:focus-visible` 3px 光圈 | ✅ |
| 4.1.2 名稱/角色/狀態 | §6：aria-selected/pressed/role=button | ✅ |

### ⚠️ Active 狀態對比度不足

§6 文字對比表覆蓋了「主文字 on 背景」和「次要文字 on 背景」，但**未驗證 Active 狀態的對比度**：

| 組合 | 值 | 計算對比度 | WCAG AA (≥4.5:1) |
|------|-----|----------|-----------------|
| Tab active 文字 on active 底色 | `--brand` on `--brand-soft`（Light） | ≈4.06:1 | ❌ 不足 |
| Tab active 文字 on active 底色 | `--brand` on `--brand-soft`（Dark） | 需驗證 | — |

`#1f6feb` on `#e8f0fe` ≈ 4.06:1，低於 WCAG AA 的 4.5:1 要求（正常文字）。

**注意**：此問題同樣存在於既有 `CategorySidebar.vue` 的 `.is-active` 樣式，為專案級已知模式。建議：
1. 在 §6 補充 active 狀態對比度驗證
2. 考慮加深 `--brand-soft` 或改用 `--brand` 底 + 白色字（Chip active 已如此做）

### ⚠️ 缺少語義結構規範（WCAG 1.3.1）

設計文件未規定頁面的 HTML 語義結構。建議補充：

```
<main class="dashboard-view">
  <nav aria-label="商品分類">          <!-- §7.1 Tabs -->
  <div role="group" aria-label="規格分組">  <!-- §7.2 Chips -->
  <div role="status" aria-live="polite">   <!-- §4.4 Skeleton -->
  <section aria-label="商品列表">          <!-- §7.5 Grid -->
    <article class="dashboard-card" role="button" tabindex="0"> <!-- §7.3 -->
```

### ⚠️ 缺少跳頁導覽（WCAG 2.4.1）

當分類 Tab + 組 Chips + 商品列表同時存在時，鍵盤使用者需多次 Tab 鍵才能到達商品列表。建議在 §6 補充 skip link 規格：「跳至商品列表」連結（`.dashboard-skip`），於 Tab 鍵首次按下時顯示。

### ⚠️ 骨架屏 aria-live 策略

§4.4 記錄骨架屏 `aria-hidden="true"`，但未說明資料載入完成後的 `aria-live` 通知。建議：列表區域使用 `aria-live="polite"` + `aria-busy` 動態切換，讓螢幕閱讀器使用者感知載入完成。

---

## 5. 狀態覆蓋（8 態）— ⚠️ 建議

### 狀態覆蓋矩陣

| 元件 | idle | hover | focus | active | disabled | loading | error | 空結果 |
|------|------|-------|-------|--------|----------|---------|-------|--------|
| CategoryTabs | ✅ | ✅ | ✅ | ✅ | ✅ N/A | ❌ **缺失** | ❌ **缺失** | — |
| SpecGroupChips | ✅ | ✅ | ✅ | ✅ | ✅ N/A | ✅ N/A | ✅ N/A | ✅ |
| DashboardCard | ✅ | ✅ | ✅ | ✅ | ✅ N/A | ✅ N/A | ❌ **缺失** | — |
| DashboardSkeleton | — | — | — | — | — | ✅ | — | — |
| EmptyState | — | — | — | — | — | — | ✅ | ✅ |

### ❌ CategoryTabs 缺 loading 狀態

§4.1 狀態矩陣未包含 loading 態。Tech Decision D3 明確要求「僅在實際 fetch 時顯示 spinner」，但設計文件未定義 loading Tab 的視覺表現。

建議補充 §4.1：

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **loading** | Tab 文字右側顯示 16px spinner（`--brand` 色、旋轉動畫）| 等待載入完成 |

### ❌ CategoryTabs 缺 error 狀態

若某分類載入失敗，Tab 本身應有何視覺回饋？建議補充：

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **error** | Tab 文字右側顯示 ⚠️ 圖示、`--danger` 色 | 點擊重試 |

或統一由全域 ErrorState 處理（§4.5 已有），但需明確說明 Tab 本身不顯示 error 態。

### ❌ DashboardCard 缺 error 狀態

當卡片資料異常（price 為 null、資料損壞）時的處理未定義。建議補充：

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **error** | 價格區顯示「資料異常」`text-dim` 色 | 仍可點擊進入詳情 |

### ✅ 其餘狀態覆蓋完整

SpecGroupChips 的折疊/展開、DashboardCard 的已下架/歷史新低、EmptyState 的三種空狀態分流均有定義。

---

## 6. 動畫規範 — ✅ 通過

### 動畫清單比對

| 動畫 | §8 規格 | 實作位置 | 結果 |
|------|---------|---------|------|
| Tab 切換 | 150ms fade | §7.1 `transition: all var(--transition)` | ✅ |
| Chip 切換 | 150ms fade | §7.2 `transition: all var(--transition)` | ✅ |
| 骨架屏→內容 | 200ms fade out | §9.7 `<Transition name="fade">` | ✅ |
| 卡片 hover | 150ms ease | §7.3 hover 樣式 | ✅ |
| Chip 展開/收起 | 200ms ease | §7.2 折疊按鈕 | ✅ |
| shimmer | 1.5s infinite | §7.4 `@keyframes shimmer` | ✅ |
| prefers-reduced-motion | 關閉所有動畫 | tokens.css 已定義 | ✅ |

### ⚠️ 建議補充

1. **Card active（按下）動畫**：§4.3 定義 active 為 `surface-2` 底色，但 §8 未列為動畫項目。建議補充「100ms ease」過渡。
2. **EmptyState / ErrorState 入場動畫**：未定義。建議補充 200ms fade-in 入場。
3. **Tab 折疊/展開動畫**：§7.2 提及 200ms ease，但 §8 未列入 Tab 層級的折疊動畫（待 §7.1 補充 Tab 折疊後一併定義）。

---

## 7. 與互動流程對齊 — ❌ 缺失

### IF §4 逐步對應

| IF 步驟 | 設計文件對應 | 結果 |
|---------|------------|------|
| §4 步驟 1：檢視分類 Tab 列表 | §7.1 Tab 容器 + 按鈕規格 | ✅ |
| §4 步驟 1：預設選取第一分類 | §9.4 實作建議 | ✅ |
| §4 步驟 2：切換分類 | §4.1 active 狀態 + §8 Tab 切換動畫 | ✅ |
| §4 步驟 2：Tab 反白高亮 | §4.1 active 視覺 | ✅ |
| §4 步驟 2：**顯示載入 spinner** | **❌ 未定義 Spinner 視覺** | ❌ |
| §4 步驟 2：分組 Chips 更新 | §4.2 + §9.5 條件渲染 | ✅ |
| §4 步驟 3：瀏覽新分類商品 | §7.3 Card + §7.5 Grid | ✅ |

### IF §5 異常處理對應

| IF 異常 | 設計文件對應 | 結果 |
|---------|------------|------|
| Tab >5 個折疊 | **❌ §7.1 未定義 Tab 折疊** | ❌ |
| 切換時上一個仍在載入 | Tech D1：不取消（快取語意處理） | ✅（非 UI 設計範疇） |
| 新分類無商品 | §4.5 空分類 EmptyState | ✅ |

### 關鍵缺失：Tab 折疊

IF §5 明確要求「分類 Tab 超過 5 個 → 顯示「更多 ▼」折疊其餘分類」。此功能在 §7.2 SpecGroupChips 有完整定義（折疊按鈕、展開/收起），但 §7.1 CategoryTabs 完全未提及。這是上游互動流程的明確需求，在設計文件中遺漏。

---

## 8. 與技術決策對齊 — ⚠️ 建議

### 決策點逐項比對

| 決策 | Tech Decision 結論 | 設計文件體現 | 結果 |
|------|-------------------|------------|------|
| **D1** 不取消上一分類請求 | 不改 useItems，快取語意處理 | 非 UI 層面，不需在設計中體現 | ✅ |
| **D2** CategoryTabs 為獨立元件 | 獨立 `CategoryTabs.vue` | §7.1 獨立元件規格 | ✅ |
| **D3** Spinner 僅在 fetch 時顯示 | `isLoadingCategory(id)` 控制 | **❌ 未定義 Spinner 視覺規格** | ❌ |
| **D4** Tab >5 個折疊 | >5 → 前 5 + 「更多 ▼」 | **❌ §7.1 未定義 Tab 折疊** | ❌ |
| **D5** 切換分類時重置分組 | `resetGroup()` 回到「全部」 | §9.5 條件渲染 + §4.2 Chips 更新 | ✅ |
| **D6** useDashboard 擴充 | 新增 switchCategory | §9.2 資料層建議 | ✅ |
| **D7** 折疊不顯示數量 | 「更多 ▼」無數字 | 未提及（因 Tab 折疊整體缺失） | — |

### D4 缺失影響分析

D4 是本功能的核心 UX 特性之一（9 大分類 → 前 5 + 折疊），但設計文件的 §7.1 完全未涵蓋。實作者將無法從本文件得知：
- 折疊閾值（>5）
- 「更多 ▼」按鈕的視覺樣式
- 展開後的佈局變化
- 展開/收起動畫

建議在 §7.1 補充完整的折疊/展開規格（可參考 §7.2 SpecGroupChips 的折疊按鈕模式）。

---

## 整體評價

### ❌ NEEDS_REVISION

**原因**：存在2個缺失（missing）問題需修正後方可通過：

1. **❌ Tab 折疊行為完全缺失**（§7.1）— 上游互動流程 IF §5 與 Tech Decision D4 明確要求的功能，設計文件未涵蓋。這是本功能的核心 UX 特性，影響 9 大分類的導覽體驗。

2. **❌ RWD 斷點數值不一致**（§5 vs §7）— 行為表定義 mobile ≤767px，但所有 CSS 使用 ≤639px，差距 128px。需統一。

### 關鍵建議（修正優先序）

| 優先序 | 項目 | 說明 |
|--------|------|------|
| **P0** | 補充 §7.1 Tab 折疊規格 | 參考 §7.2 SpecGroupChips 折疊模式，補充阈值（>5）、按鈕樣式、展開動畫 |
| **P0** | 統一 RWD 斷點 | 將 §5 行為表修正為 1023/639 與 CSS 一致 |
| **P1** | 補充 §4.1 Tab loading 狀態 | 定義 Spinner 視覺（16px、brand 色、旋轉動畫） |
| **P1** | 補充 §6 Active 對比度驗證 | `--brand` on `--brand-soft` ≈ 4.06:1，建議備註或調整色值 |
| **P2** | 補充語義結構規範 | §6 增加 HTML 語義（nav/main/article/role）|
| **P2** | 補充 Card error 狀態 | §4.3 增加資料異常的 fallback 視覺 |
| **P3** | 補充 Chip `--text-inverse` token | 將 `#fff` 硬編碼替換為 token 引用 |

### 通過項目

- ✅ Design Token 與 tokens.css 完全一致
- ✅ 4 個主要元件 + 容器規格完整
- ✅ 核心動畫含 `prefers-reduced-motion` 處理
- ✅ 基礎無障礙（focus-visible、aria、target size）
- ✅ 字級階層清晰
- ✅ 與 003/004 列表頁設計體系一致
