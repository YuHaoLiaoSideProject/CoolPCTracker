# 024 RWD 審計

**審計時間**：2026-03-29  
**審計範圍**：`HomeView.vue`、`CategoryTabs.vue`、`ProductCard.vue`、`ProductList.vue`

---

## 審計結果

| 規格項目 | 桌面 ≥1024 | 平板 640–1023 | 手機 ≤639 | 狀態 |
|---------|-----------|--------------|----------|------|
| 整體佈局 max-width 1200px | ✅ `.home-view { max-width: 1200px }` | ✅ 繼承 | ✅ 繼承 | ✅ PASS |
| CategoryTabs 水平排列 | ✅ `display: flex` | ✅ `overflow-x: auto` | ✅ `overflow-x: auto` | ✅ PASS |
| CategoryTabs 水平捲動（平板） | — | ⚠️ 斷點為 768px 而非 1023px（640–767px 區間未套用捲動） | — | ⚠️ MINOR |
| CategoryTabs 44px 高度 | — | ✅ `var(--h-mobile)` = 44px（768px 以下） | ✅ `var(--h-mobile)` = 44px | ⚠️ 斷點偏嚴 |
| 工具列垂直堆疊 | ✅ 水平排列 | ❌ **無平板斷點**，仍為水平 | ✅ `flex-direction: column` | ❌ FAIL |
| 進階篩選預設折疊 | ✅ `isExpanded = ref(window.innerWidth >= 1024)` → 展開 | ✅ ≤1023 初始 false → 折疊 | ✅ 同左 | ✅ PASS |
| 商品卡片 grid auto-fill minmax(300px,1fr) | ✅ `.cat-grid` 同規格 | ✅ 維持多欄 | ✅ `grid-template-columns: 1fr` 單欄 | ✅ PASS |
| 控制元件 36px | ✅ `--h: 36px` | ✅ `--h: 36px` | — | ✅ PASS |
| 控制元件 44px（手機） | — | — | ✅ `--h-mobile: 44px` | ✅ PASS |
| ProductCard price wrap（手機） | ✅ 基礎已有 `flex-wrap: wrap` | ✅ 同左 | ✅ `.pc-history-low { flex-basis: 100% }` | ✅ PASS |
| ProductCard actions 44px（手機） | ✅ `height: 30px`（.pc-btn） | ✅ 同左 | ✅ `var(--h-mobile)` = 44px | ✅ PASS |
| 骨架屏 grid 同規格 | ✅ `repeat(auto-fill, minmax(300px, 1fr))` | ✅ 同左 | ✅ 同左 | ✅ PASS |

---

## 缺失項目（需補齊）

| # | 項目 | 說明 | 建議修改 |
|---|------|------|----------|
| 1 | **工具列平板垂直堆疊** | 024 §5 規定 640–1023px 工具列應「垂直堆疊」，但 `HomeView.vue` 僅有 `@media (max-width: 639px)` 手機斷點，**缺少 `@media (max-width: 1023px)` 斷點**來讓工具列在平板也垂直堆疊。 | 在 `HomeView.vue` 的 `<style>` 中新增：`@media (max-width: 1023px) { .toolbar-row--primary { flex-direction: column; align-items: stretch; } }` |
| 2 | **CategoryTabs 捲動斷點偏嚴** | `CategoryTabs.vue` 使用 `@media (max-width: 768px)` 啟用水平捲動，但規格要求 ≥640px（平板）就應捲動。640–767px 區間的平板裝置可能無法水平捲動溢出的 tabs。 | 將 `@media (max-width: 768px)` 改為 `@media (max-width: 1023px)`，與規格一致。 |
| 3 | **CategoryTabs 44px 斷點偏嚴** | 同上，44px 高度的斷點在 768px 才生效，640–767px 區間維持 `--h` (36px)。 | 合併至 #2 的斷點修正即可。 |

---

## 補充說明

- **CSS 變數**：`tokens.css` 定義 `--h: 36px` / `--h-mobile: 44px`，各元件透過 `var(--h)` / `var(--h-mobile)` 引用，手機端控制元件高度符合規格。
- **進階篩選折疊邏輯**：`HomeView.vue` 中 `isExpanded` 初始值為 `window.innerWidth >= 1024`，桌面預設展開、平板/手機預設折疊，完全符合 §5 規定。
- **卡片 grid 手機單欄**：`ProductList.vue` 在 `@media (max-width: 639px)` 設定 `grid-template-columns: 1fr`，手機端確實為單欄。
