# UI/UX 設計文件 — 005 Dashboard 頁面（dashboard-design）

> 文件類型：完整規格（綠地專案，無既有 UI，不做 BEFORE/AFTER 比較稿）
> 對應開發規格：`docs/development/017-dashboard-items.md`、`018-dashboard-groups.md`
> 對應 BDD：`docs/bdds/017-dashboard-items.feature`、`018-dashboard-groups.feature`
> 互動 mockup：`docs/uiux/023-dashboard-design.html`
> 共用 token：沿用 `web/src/styles/tokens.css`（與 003、004 一致，不可更動）

---

## 1. 現況審計

Dashboard 為綠地專案，設計依據來自：

- 017 §2.3 DashboardCard（精簡版卡片規格）
- 017 §2.4 DashboardSkeleton（骨架屏規格）
- 018 §2.4 SpecGroupChips（分組 Chips 元件）
- 現有 `tokens.css`（Design Token 唯一來源）
- 003 列表頁設計體系（RWD 行為表、狀態矩陣、無障礙基準）

| # | 現況事實／問題 | 嚴重度 | 位置 | 說明 |
|---|--------------|--------|------|------|
| 1 | DashboardView 不存在 | P1 | `web/src/views/` | 綠地設計，從零建立 |
| 2 | 共用 token 已完備 | P1 | `tokens.css` | Dashboard 直接沿用，不可自行新增變數 |
| 3 | SpecGroupChips 為新元件 | P1 | 無 precedent | 需定義完整設計（含折疊邏輯、選取態） |
| 4 | 側欄 → 頂部 Tab | P1 | 009 §4.1 | ListingView 用側欄，Dashboard 用頂部 Tab |
| 5 | 骨架屏需全頁設計 | P2 | 017 §2.4 | Tab 區域 + 列表區域佔位 |
| 6 | 無分組策略分類 | P2 | 018 §2.3 | GROUP_STRATEGY 未涵蓋 → 不顯示 Chips |
| 7 | 已下架商品處理 | P2 | 017 §2.3 | `status === 'gone'` → 隱藏價格、顯示標籤 |
| 8 | 歷史新低徽章 | P2 | 017 §2.2 | 🥇 徽章需定義視覺規格 |

---

## 2. 設計原則

1. **一致優先、沿用既有體系** — Dashboard 所有元件嚴格沿用 `tokens.css` 變數；卡片結構參考 ProductCard 但精簡化（無 Sparkline、無 WatchlistButton、無 CompareToggle）。
2. **Tab 導覽、快速切換** — 頂部 Tab 列表取代側欄，減少水平空間佔用；分組 Chips 為第二層篩選，兩層導覽分離。
3. **精簡資訊密度** — Dashboard 目標是「一目瞭然」，每張卡片只顯示：名稱、目前價格、歷史最低價、🥇 徽章、規格 Chips、已下架標籤。不含 Sparkline、漲跌 delta、追蹤/比較按鈕。
4. **漸進式揭露、狀態完整覆蓋** — 骨架屏 → 正常列表 → 空狀態 → 錯誤狀態四態完整覆蓋；分組 Chips 依資料自動顯示/隱藏（無策略 → 不顯示）。
5. **觸控與鍵盤優先** — 行動端觸控目標 44px（WCAG 2.5.5）；`focus-visible` 3px 光圈；卡片 `tabindex=0` + Enter/Space 可觸發詳情頁導航。

---

## 3. Design Token 表

共用 token（沿用 `tokens.css`，**不可更動**）。

### 3.1 核心 Token

| Token | Light | Dark | 用途 |
|-------|-------|------|------|
| `--brand` | `#1f6feb` | `#4c8dff` | Tab active、Chip active、連結 |
| `--brand-soft` | `#e8f0fe` | `#1d2f4d` | Tab active 底色、Chip active 底色 |
| `--price-up` | `#e02424` | `#f87171` | 漲（DashboardCard 不顯示 delta，僅供一致性） |
| `--price-down` | `#18933f` | `#4ade80` | 跌 |
| `--price-flat` | `#6b7280` | `#9ca3af` | 持平 |
| `--bg` | `#f7f8fa` | `#0f141a` | 頁面背景 |
| `--surface` | `#ffffff` | `#161c24` | 卡片、Tab 容器表面 |
| `--surface-2` | `#f1f3f5` | `#1e2733` | Skeleton 佔位、次要背景 |
| `--border` | `#e5e7eb` | `#2a3340` | 邊框 |
| `--text` | `#1f2937` | `#e5e7eb` | 主文字 |
| `--text-dim` | `#6b7280` | `#8b95a3` | 次要文字（計數、hint） |
| `--radius` | `10px` | `10px` | 卡片圓角 |
| `--radius-sm` | `6px` | `6px` | Tab、Chip、按鈕圓角 |
| `--shadow` | `0 1px 3px rgba(0,0,0,.08)` | `0 1px 3px rgba(0,0,0,.5)` | 卡片陰影 |
| `--shadow-hover` | `0 2px 8px rgba(31,111,235,.15)` | `0 2px 8px rgba(76,141,255,.25)` | 卡片 hover 陰影 |
| `--h` | `36px` | `36px` | 桌面控制高度（Tab、Chip） |
| `--h-mobile` | `44px` | `44px` | 行動控制高度（WCAG 2.5.5） |
| `--fs` | `0.875rem` | `0.875rem` | 基礎字級 |
| `--transition` | `0.2s ease` | `0.2s ease` | 過渡動畫 |
| `--fade` | `150ms` | `150ms` | 淡入動畫 |
| `--focus-ring` | `3px solid rgba(26,115,232,.14)` | `3px solid rgba(138,180,248,.22)` | 焦點光圈 |
| `--font-stack` | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans TC", "PingFang TC", "Microsoft JhengHei"` | 同左 | 字體 |
| `--font-mono` | `ui-monospace, SFMono-Regular, Menlo, Consolas` | 同左 | 等寬字體 |

### 3.2 Dashboard 專屬衍生樣式

| 項目 | 值 | CSS 對應 | 說明 |
|------|-----|---------|------|
| Tab 高度 | 36px / 44px | `var(--h)` / `var(--h-mobile)` | 與 SearchBar 一致 |
| Tab 間距 | 0px（底部 border 分隔） | `border-bottom` | 不用 gap，用視覺分隔 |
| Chip 高度 | 32px / 44px | 自訂（非 token） | 比 Tab 小一級（32px < `--h` 36px），表示第二層篩選；手機端 44px 沿用 `--h-mobile` |
| Chip 圓角 | 18px | `border-radius: 18px` | 橢圓 pill |
| 卡片名稱 | 0.95rem / 600 | `.dc-name` | 與 ProductCard 一致 |
| 目前價格 | 1.15rem / 700 | `.dc-current` | 大字強調 |
| 歷史最低價 | 0.78rem / 400 | `.dc-history-low` | 弱化顯示 |
| 🥇 徽章 | 1.2rem | `.dc-lowest` | 單一 emoji，不替代文字 |
| 規格 Chips | 0.72rem | `.chip` | 與 ProductCard 一致 |
| 已下架標籤 | 0.7rem / 600 | `.dc-gone` | pill 標籤 |
| Skeleton Tab | 80px × 32px | `.ds-tab` | 佔位方塊 |
| Skeleton 卡片 | auto × 120px | `.ds-card` | 佔位方塊 |

### 3.3 字級階層

| 層級 | 字級 | 字重 | 用途 |
|------|------|------|------|
| H2 | 1.05rem | 700 | 區塊標題 |
| 卡片名稱 | 0.95rem | 600 | DashboardCard 商品名 |
| 目前價格 | 1.15rem | 700 | 價格大字 |
| Tab 文字 | 0.88rem | 500/700 | Tab 按鈕 |
| Chip 文字 | 0.82rem | 600 | 分組 Chips |
| 歷史最低價 | 0.78rem | 400 | 弱化價格 |
| 計數 badge | 0.72rem | 700 | Tab/Chip 內計數 |
| 規格 Chips | 0.72rem | 400 | 規格標籤 |

---

## 4. 狀態矩陣

覆蓋 8 態：idle / hover / focus / active / disabled / loading / error / 空結果。

### 4.1 分類 Tab

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **idle** | 透明底、`text` 色、底部無 border | 可點擊切換分類 |
| **hover** | `brand-soft` 淡底 | 提示可操作 |
| **focus** | `:focus-visible` 3px accent 光圈 | 鍵盤 Enter/Space 觸發 |
| **active** | `brand` 字色、700 weight、底部 2px `brand` border | `aria-selected="true"` |
| **loading** | Tab 文字右側顯示 16px spinner（`--brand` 色、旋轉動畫）；`opacity: 0.7` | 等待載入完成（`aria-busy="true"`） |
| **disabled** | 不適用（Tab 始終可用） | — |

### 4.2 分組 Chips

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **idle** | `surface` 底、`border` 邊框、`text-dim` 色 | 可點擊切換分組 |
| **hover** | `border-color: brand`、`color: brand` | 提示可操作 |
| **focus** | `:focus-visible` 3px accent 光圈 | 鍵盤 Enter/Space 觸發 |
| **active** | `brand` 底、白色字、`border-color: brand`、600 weight | `aria-pressed="true"` |
| **disabled** | 不適用 | — |
| **折疊/展開** | 「更多 (N) ▼」/「收起 ▲」無邊框、`brand` 色 | 點擊展開/收起全部 Chips |

### 4.3 DashboardCard

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **idle** | `surface` 底、`border` 邊框、`shadow` 陰影 | 可點擊進入詳情 |
| **hover** | `border-color: brand` + `shadow-hover` | 提示可操作 |
| **focus** | `:focus-visible` 3px accent 光圈 | 鍵盤 Enter/Space 導航 |
| **active** | 按下瞬間 `surface-2` 底 | 點擊導航至詳情頁 |
| **disabled** | 不適用（Card 始終可點擊） | — |
| **error** | 價格區顯示「資料異常」`text-dim` 色（price 為 null 或資料損壞時） | 仍可點擊進入詳情 |
| **已下架** | 價格區顯示「已下架」文字、`text-dim` 色 | 仍可點擊進入詳情 |
| **歷史新低** | 🥇 徽章顯示於卡片右上角 | 資訊標示，無額外互動 |

### 4.4 骨架屏（DashboardSkeleton）

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **loading** | Tab 區 5 個 `surface-2` 方塊 + 列表區 10 個 `surface-2` 方塊、shimmer 動畫 | `aria-hidden="true"`（無互動） |

### 4.5 空狀態（EmptyState）

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **空分類** | SVG 圖示 +「此分類目前沒有商品」+「查看全部商品」按鈕 | 點擊清除回到全部 |
| **空分組** | SVG 圖示 +「暫無此規格商品」+「查看全部分組」按鈕 | 點擊回到全部分組 |
| **載入失敗** | SVG 圖示 +「資料載入失敗」+ [重試] 按鈕 | 點擊重試 |

---

## 5. RWD 斷點行為表

> **斷點定義**：與既有 codebase（CategorySidebar.vue、003 列表頁）一致，使用 1023/639 兩個斷點。

| 行為 | ≥1024（桌面） | 640–1023（平板） | ≤639（手機） |
|------|--------------|------------------|-------------|
| **整體佈局** | 單欄，`max-width: 1200px`、`padding: 16px` | 單欄、`padding: 14px` | 單欄、`padding: 10px` |
| **分類 Tab** | 水平排列、可見所有 Tab、底部 border 分隔 | 水平捲動（`overflow-x: auto`） | 水平捲動、Tab 高度 **44px** |
| **分組 Chips** | 水平排列、允許換行（`flex-wrap: wrap`） | 水平捲動（`overflow-x: auto; flex-wrap: nowrap`） | 水平捲動、Chips 高度 **44px** |
| **商品卡片** | `grid auto-fill minmax(300px, 1fr)` 多欄（1200px ≈ 3 欄） | 維持多欄（content 寬 ≥300px×2） | 單欄 |
| **控制元件** | 36px（`--h`） | 36px | **44px**（`--h-mobile`，WCAG 2.5.5） |
| **卡片間距** | grid gap 12px | grid gap 12px | grid gap 10px |
| **歷史最低價** | 單行顯示 | 單行顯示 | 可換行堆疊 |
| **骨架屏** | Tab 5 個 + 列表 10 個、3 欄 grid | Tab 5 個 + 列表 10 個、2 欄 grid | Tab 5 個 + 列表 10 個、單欄 |

---

## 6. 無障礙清單（WCAG）

| 準則 | 要求 | 對應設計 |
|------|------|----------|
| **1.4.1** 不以顏色單獨傳達 | 歷史新低資訊不得只靠 🥇 emoji | 🥇 為輔助標示，卡片名稱與價格已足夠理解商品；如需純文字替代，可在 `aria-label` 中加入「歷史新低」 |
| **2.5.5** 目標尺寸 | 觸控目標 ≥ 40×40px | 行動端 Tab/Chip/Card 按鈕一律 44px（`--h-mobile`） |
| **2.4.7** 焦點可見 | 所有可互動元素需可見 focus | `:focus-visible` 3px accent 光圈；卡片 `tabindex=0` |
| **2.4.1** 跳頁導覽 | 鍵盤使用者可跳過重複導覽區塊 | Tab 列表 + Chips + 商品列表同時存在時，在 Tab 區域前方放置 skip link（`.dashboard-skip`），於 Tab 鍵首次按下時顯示，目標為商品列表區 `#dashboard-list` |
| **4.1.2** 名稱／角色／狀態 | 動態元件需暴露狀態 | Tab `aria-selected`；Chip `aria-pressed`；Card `role="button"` + `aria-label`（含商品名與價格）；骨架屏 `aria-hidden`；空狀態 `role="status"`；錯誤 `role="alert"` |

**文字對比**（兩主題皆 ≥4.5:1）：

| 元素 | Light 對比 | Dark 對比 |
|------|-----------|----------|
| 主文字 on 背景 | `#1f2937/#f7f8fa` ≈ 13.8:1 | `#e5e7eb/#0f141a` ≈ 14.9:1 |
| 次要文字 on 背景 | `#6b7280/#f7f8fa` ≈ 5.7:1 | `#8b95a3/#0f141a` ≈ 5.2:1 |
| 品牌色 on 白底 | `#1f6feb/#ffffff` ≈ 4.6:1 | `#4c8dff/#161c24` ≈ 5.8:1 |
| Tab active 文字 on active 底色 | `#1f6feb/#e8f0fe` ≈ 4.06:1 | `#4c8dff/#1d2f4d` ≈ 3.8:1 |

> ⚠️ **已知問題**：Tab active 狀態（`--brand` on `--brand-soft`）對比度略低於 WCAG AA 4.5:1。此問題與既有 `CategorySidebar.vue` 的 `.is-active` 樣式一致，為專案級已知模式。若需改善，可考慮加深 `--brand-soft` 或改用 `--brand` 底 + 白色字（Chip active 已如此做）。

**HTML 語義結構**：

```html
<a class="dashboard-skip" href="#dashboard-list">跳至商品列表</a>  <!-- WCAG 2.4.1 skip link -->
<main class="dashboard-view">
  <nav aria-label="商品分類">          <!-- §7.1 Tabs -->
  <div role="group" aria-label="規格分組">  <!-- §7.2 Chips -->
  <div role="status" aria-live="polite" aria-busy="...">   <!-- §4.4 Skeleton -->
  <section id="dashboard-list" aria-label="商品列表">  <!-- §7.5 Grid -->
    <article class="dashboard-card" role="button" tabindex="0"> <!-- §7.3 -->
```

**動畫**：所有動畫於 `prefers-reduced-motion: reduce` 時關閉（`tokens.css` 已定義）。

---

## 7. 元件規格

### 7.1 分類 Tab（`.category-tabs`）

- **容器**：`display: flex; align-items: center; gap: 8px; padding: 12px 0; border-bottom: 1px solid var(--border);`
- **Tab 按鈕**：`height: var(--h); padding: 0 16px; border: none; background: transparent; color: var(--text-dim); font-size: 0.88rem; cursor: pointer; border-bottom: 2px solid transparent; transition: all var(--transition); white-space: nowrap;`
- **Tab active**：`color: var(--brand); font-weight: 700; border-bottom-color: var(--brand);`
- **Tab hover**：`background: var(--brand-soft);`
- **Tab loading**：`opacity: 0.7; cursor: wait;` + 右側 16px spinner（`--brand` 色、`border: 2px solid var(--text-dim); border-top-color: var(--brand); border-radius: 50%; animation: spin 0.6s linear infinite;`）
- **計數 badge**：`font-size: 0.72rem; color: var(--text-dim); margin-left: 4px;`
- **折疊按鈕（`.cat-tab--toggle`）**：`background: none; border: none; color: var(--brand); font-size: 0.85rem; padding: 8px 12px; cursor: pointer;`（與 §7.2 折疊按鈕樣式一致）
- **折疊邏輯**：`categories.length > 5` → 顯示前 5 個 Tab + 「更多 ▼」按鈕；點擊展開顯示全部 + 「收起 ▲」（Tech Decision D4、IF §5）
- **展開/收起動畫**：200ms ease（高度過渡，與 §7.2 Chips 折疊一致）
- **RWD**：`@media (max-width: 1023px)` → `overflow-x: auto; flex-wrap: nowrap; scrollbar-width: thin;`
- **RWD**：`@media (max-width: 639px)` → `height: var(--h-mobile);`

**Spinner 動畫**：

```css
@keyframes spin {
  to { transform: rotate(360deg); }
}
```

### 7.2 分組 Chips（`.spec-group-chips`）

- **容器**：`display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 0;`
- **Chip 按鈕**：`height: 32px; padding: 0 14px; border-radius: 18px; border: 1px solid var(--border); background: var(--surface); color: var(--text-dim); font-size: 0.82rem; cursor: pointer; transition: all var(--transition); white-space: nowrap;`
- **Chip active**：`background: var(--brand); border-color: var(--brand); color: #fff; font-weight: 600;`（`#fff` 為已知硬編碼，因 tokens.css 無 `--text-inverse` token）
- **Chip hover**：`border-color: var(--brand); color: var(--brand);`
- **計數**：`font-size: 0.72rem; opacity: 0.7; margin-left: 4px;`
- **折疊按鈕**：`background: none; border: none; color: var(--brand); font-size: 0.82rem; cursor: pointer;`
- **RWD**：`@media (max-width: 1023px)` → `overflow-x: auto; flex-wrap: nowrap; scrollbar-width: thin;`
- **RWD**：`@media (max-width: 639px)` → Chip 高度 44px

### 7.3 DashboardCard（`.dashboard-card`）

- **容器**：與 ProductCard 一致（`surface` 底、`border`、`radius`、`shadow`、`padding: 12px 14px`、`display: flex; flex-direction: column; gap: 8px;`）
- **頂部**：`display: flex; justify-content: space-between; align-items: flex-start;`
- **名稱**：`font-size: 0.95rem; font-weight: 600; line-height: 1.4;`（2 行截斷）
- **已下架標籤**：與 ProductCard `.pc-gone` 一致（pill、`0.7rem`、`text-dim`）
- **🥇 徽章**：`font-size: 1.2rem;`（emoji，`aria-label` 含「歷史新低」）
- **規格 Chips**：與 ProductCard `.pc-specs` 一致（`flex-wrap: wrap; gap: 4px;`）
- **價格區**：`display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;`
- **目前價格**：`font-size: 1.15rem; font-weight: 700; font-variant-numeric: tabular-nums;`
- **歷史最低價**：`font-size: 0.78rem; color: var(--text-dim);`
- **已下架文字**：`font-size: 1.15rem; color: var(--text-dim);`（替代價格位置）
- **hover**：`border-color: var(--brand); box-shadow: var(--shadow-hover);`
- **RWD**：`@media (max-width: 639px)` → `.dc-price { flex-wrap: wrap; }`

### 7.4 DashboardSkeleton（`.dashboard-skeleton`）

- **Tab 區域**：`display: flex; gap: 8px; padding: 12px 0; border-bottom: 1px solid var(--border);`
- **Tab 佔位**：`width: 80px; height: 32px; border-radius: var(--radius-sm); background: var(--surface-2);`
- **列表區域**：`display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px;`
- **卡片佔位**：`height: 120px; border-radius: var(--radius); background: var(--surface-2);`
- **shimmer 動畫**：`background: linear-gradient(90deg, var(--surface) 25%, var(--surface-2) 50%, var(--surface) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite;`
- **`@keyframes shimmer`**：`0% { background-position: 200% 0; } 100% { background-position: -200% 0; }`

### 7.5 頁面容器（`.dashboard-view`）

- **容器**：`max-width: 1200px; margin: 0 auto; padding: 16px; display: flex; flex-direction: column; gap: 16px;`
- **商品列表區**：`display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px;`
- **計數文字**：`font-size: 0.78rem; color: var(--text-dim);`（如「共 24 商品」）

---

## 8. 動畫規範

| 動畫 | 時間 | 觸發 | 說明 |
|------|------|------|------|
| Tab 切換 | 150ms fade | 點擊 Tab | 底部 border 滑動 + 列表淡入 |
| Chip 切換 | 150ms fade | 點擊 Chip | 列表內容淡入（無 loading，client-side 篩選） |
| 骨架屏 → 內容 | 200ms fade out | 資料載入完成 | 骨架屏 opacity 0 → 列表 opacity 1 |
| 卡片 hover | 150ms ease | 滑鼠進入 | border + shadow 過渡 |
| Chip 展開/收起 | 200ms ease | 點擊「更多/收起」 | 高度過渡 |
| shimmer | 1.5s infinite | 骨架屏顯示中 | 灰階漸層閃爍 |

**`prefers-reduced-motion`**：所有動畫於 `reduce` 時關閉（`tokens.css` 已定義 `animation-duration: 0.01ms !important; transition-duration: 0.01ms !important;`）。

---

## 9. 實作建議

1. **路由**：`/dashboard` → 懶載入 `DashboardView.vue`（chunk <10KB gzipped）。
2. **資料層**：沿用 `useItems` singleton（已有 index + categories + items 資料）；`useDashboard` 負責排序 + Top 10 + 歷史最低價；`useSpecGroups` 負責分組邏輯。
3. **元件化**：Tab 列表、Chips、Card、Skeleton 各為獨立元件；Tab 列表可考慮提取為共用元件（若 WatchlistView 也有類似需求）。
4. **Tab 預設選取**：`watch(categories)` 有值時自動選取第一分類（與 ListingView 一致）。
5. **分組 Chips 條件渲染**：`v-if="hasGroups"` — 無分組策略或僅一組時不顯示。
6. **🥇 判定**：分組模式下 `index === 0`；非分組模式下 `isLowest`（由 `useDashboard` 計算）。
7. **骨架屏淡出**：`<Transition name="fade">` 包裹骨架屏，資料載入完成後淡出。
8. **空狀態分流**：無商品 → `EmptyState kind="category"`；分組無商品 → `EmptyState kind="filter"`（自訂訊息）。

---

## 10. 驗收清單

### 10.1 功能（對應 BDD）

- [ ] 進入 Dashboard 顯示骨架屏 → 資料載入後淡出顯示 Tab + 列表
- [ ] 預設選取第一分類，顯示該分類 Top 10 最便宜商品
- [ ] Tab 切換正確載入不同分類
- [ ] 分組 Chips 正確顯示（記憶體：DDR5 32GB / DDR4 16GB 等）
- [ ] 分組 Chips 折疊（>8 個 → 「更多 ▼」）
- [ ] 分組切換正確篩選商品（client-side，無 loading）
- [ ] 🥇 徽章正確標示歷史新低商品
- [ ] 已下架商品顯示標籤、隱藏價格
- [ ] 歷史最低價正確顯示（與目前價格不同時）
- [ ] 點擊卡片導航至詳情頁

### 10.2 響應式

- [ ] Desktop（≥1024）：3 欄卡片、Tab 水平排列、Chips 換行
- [ ] Tablet（640–1023）：多欄卡片、Tab 水平捲動、Chips 水平捲動
- [ ] Mobile（≤639）：單欄卡片、Tab 44px、Chips 44px 水平捲動

### 10.3 狀態

- [ ] 骨架屏 shimmer 動畫正常
- [ ] 載入失敗 → ErrorState + 重試
- [ ] 空分類 → EmptyState
- [ ] 無分組策略 → 不顯示 Chips
- [ ] 分組無商品 → 空狀態提示

### 10.4 設計與無障礙

- [ ] 兩主題（light/dark）全元件可讀
- [ ] 行動端控制 44px、桌面 36px
- [ ] focus-visible 光圈、aria-selected / aria-pressed / role=button 到位
- [ ] 圖示全 inline SVG、`prefers-reduced-motion` 生效
- [ ] Tab 折疊（>5 → 「更多 ▼」）正確運作
- [ ] Tab loading spinner 顯示/隱藏正確
- [ ] Card error 狀態（price 為 null）正確顯示「資料異常」
- [ ] Skip navigation link 於 Tab 鍵首次按下時顯示
- [ ] 於 Chrome / Safari / Edge 最新版操作正常
