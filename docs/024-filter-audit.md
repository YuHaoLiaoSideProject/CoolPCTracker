# 篩選條件審計

> 審計日期：2026-08-18
> 資料來源：api/index.json (crawled_at: 2026-08-18)、api/items/*.json
> 範圍：CoolPCTracker 9 大分類，所有 spec 篩選能力

---

## 1. 現有支援的篩選條件

### 1.1 SpecFilterPanel（數值門檻 ≥ 篩選）

用途：全域規格篩選面板（不限分類），所有條件為 AND 交集。

| 條件名 | 欄位 (`spec.*`) | 類型 | 單位 | 作用分類 | 備註 |
|--------|----------------|------|------|----------|------|
| VRAM | `vram_gb` | number | G | 顯示卡 | 資料覆蓋率 68% |
| CPU核數 | `cores` | number | 核 | CPU | 資料覆蓋率 68% |
| 瓦數 | `wattage_w` | number | W | **（無）** | ⚠️ 資料中無此欄位，永遠不命中 |
| 記憶體 | `ram_gb` | number | GB | 記憶體 | 資料覆蓋率 100% |
| TDP | `tdp_w` | number | W | CPU | 資料覆蓋率 63% |

> 定義於 `web/src/utils/specFilter.ts` → `SPEC_FIELD_LABELS` + `FILTERABLE_FIELDS`

### 1.2 Dashboard 篩選器（useDashboardFilters）

用途：Dashboard 分類頁的多面向篩選。

| 篩選器 | 欄位 | 類型 | 作用分類 | 備註 |
|--------|------|------|----------|------|
| 價格範圍 | `history[].p` | number | 全部 | Min / Max |
| 品牌 | `spec.brand` | string | 全部 | Chip 多選（聯集） |
| 容量 | `spec.capacity` | string | SSD/HDD | Chip 多選（如 "1TB"） |
| 轉速 | `spec.rpm` | number→string | HDD | Chip 多選（如 "7200RPM"） |
| 記憶體容量 | `spec.ram_gb` | number→string | 記憶體 | Chip 多選（如 "16GB"） |
| DDR 類型 | `spec.spec` | string | 記憶體 | Chip 多選（如 "DDR5"） |
| 介面 | `spec.interface` | string | SSD | Chip 多選（如 "NVMe"） |

> 定義於 `web/src/composables/useDashboardFilters.ts`

---

## 2. 所有分類的 spec 欄位（extra 平鋪後）

以下為 `api/items/*.json` 中，經 `normalizeSpec()` 平鋪後實際出現在 `item.spec` 的欄位。

| 分類 | ID | 商品數 | 有 extra | 可用 extra 欄位（覆蓋率） |
|------|----|--------|----------|--------------------------|
| 套裝/準系統 | g1 | 156 | 0 | （無結構化欄位） |
| 劈發價組合區 | g3 | 83 | 83 | `summary`: 100%（純文字摘要） |
| CPU | g4 | 47 | 41 | `cores`: 68%, `threads`: 68%, `base_ghz`: 87%, `turbo_ghz`: 87%, `tdp_w`: 63% |
| 主機板 | g5 | 372 | 339 | `chipset`: 89%, `form_factor`: 90% |
| 記憶體 | g6 | 217 | 217 | `ram_gb`: 100%, `spec` (DDR類型): 58%, `clock_mhz`: 56% |
| SSD | g7 | 171 | 92 | `capacity_gb`: 45%, `format`: 33%, `interface`: 4% |
| HDD | g8 | 89 | 89 | `capacity_gb`: 100%, `rpm`: 100% |
| 記憶卡 | g9 | 54 | 35 | `spec` (SDXC等): 62%, `capacity`: 16% |
| 顯示卡 | g12 | 251 | 226 | `chip`: 79%, `vram_gb`: 68% |

> 所有分類共通：`brand` (string)、`model` (string) 始終存在（部分為 null）

---

## 3. 缺少的篩選條件（應補齊）

### 3.1 SpecFilterPanel 缺少（數值 ≥ 門檻）

| 條件名 | 欄位 | 類型 | 影響分類 | 優先級 | 說明 |
|--------|------|------|----------|--------|------|
| ~~瓦數~~ | `wattage_w` | number | **無** | — | 已註冊但資料中無此欄位，屬無效條件，建議移除 |
| 基礎時脈 | `base_ghz` | number | CPU | P2 | 覆蓋率 87%，可用 ≥ 篩選 |
| 超頻時脈 | `turbo_ghz` | number | CPU | P2 | 覆蓋率 87%，可用 ≥ 篩選 |
| 記憶體時脈 | `clock_mhz` | number | 記憶體 | P2 | 覆蓋率 56%，可用 ≥ 篩選 |
| 容量(GB) | `capacity_gb` | number | SSD / HDD | P1 | SSD 覆蓋 45%、HDD 覆蓋 100%，數值型可 ≥ |
| 轉速 | `rpm` | number | HDD | P2 | 覆蓋率 100%，可用 ≥ 篩選 |

### 3.2 Dashboard 缺少（分類 Chip / 多選篩選）

| 條件名 | 欄位 | 類型 | 影響分類 | 優先級 | 說明 |
|--------|------|------|----------|--------|------|
| 顯示卡晶片 | `chip` | string | 顯示卡 | P1 | 覆蓋率 79%，如 RTX 4070 / RX 7800 XT |
| 主機板晶片組 | `chipset` | string | 主機板 | P2 | 覆蓋率 89%，如 B650 / Z790 |
| 主機板版型 | `form_factor` | string | 主機板 | P2 | 覆蓋率 90%，如 ATX / M-ATX / ITX |
| DDR 類型 | `spec` | string | 記憶卡 | P3 | 覆蓋率 62%，如 SDXC / microSD |
| SSD 格式 | `format` | string | SSD | P3 | 覆蓋率 33%，如 2.5" / M.2 |
| SSD 介面 | `interface` | string | SSD | P3 | 覆蓋率極低 4%，效益有限 |
| CPU 型號摘要 | `spec` | string | CPU | P3 | 部分商品有分類摘要（如 "Intel" / "AMD"），可用於快速篩選 |

### 3.3 完全無法篩選的分類

| 分類 | 狀態 | 建議 |
|------|------|------|
| 套裝/準系統 (g1) | 無結構化 spec | 僅能靠品牌或關鍵字搜尋，短期無需額外篩選 |
| 劈發價組合區 (g3) | 僅有 `summary` 純文字 | 不適合結構化篩選，維持關鍵字搜尋即可 |

---

## 4. 篩選覆蓋率矩陣

以 ✅ = 已支援、⚠️ = 有資料但未支援、❌ = 無資料 表示：

| 分類 | brand | vram_gb | cores | tdp_w | ram_gb | wattage_w | base_ghz | turbo_ghz | clock_mhz | capacity_gb | rpm | chip | chipset | form_factor | spec(DDR) | interface |
|------|-------|---------|-------|-------|--------|-----------|----------|-----------|-----------|-------------|-----|------|---------|-------------|-----------|-----------|
| 套裝/準系統 | ✅搜尋 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 劈發價組合區 | ✅搜尋 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| CPU | ✅搜尋 | ❌ | ✅ | ✅* | ❌ | ❌ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 主機板 | ✅搜尋 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ⚠️ | ❌ | ❌ |
| 記憶體 | ✅搜尋 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️** | ❌ |
| SSD | ✅搜尋 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️*** | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ |
| HDD | ✅搜尋 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅**** | ✅**** | ❌ | ❌ | ❌ | ❌ | ❌ |
| 記憶卡 | ✅搜尋 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ❌ |
| 顯示卡 | ✅搜尋 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ |

> \* tdp_w 僅 CPU 有資料（63%），其他分類無此欄位
> \** 記憶體的 `spec` 在 Dashboard 以 DDR 類型 Chip 篩選（58%），但未在 SpecFilterPanel
> \*** SSD `capacity_gb` 在 Dashboard 以 `capacity` (string) 篩選（45%），但 SpecFilterPanel 無數值版
> \**** HDD `capacity_gb` + `rpm` 在 Dashboard 已支援（各 100%），但 SpecFilterPanel 無數值版

---

## 5. 重點發現與建議

### 優先修正
1. **移除 `wattage_w`**：`SPEC_FIELD_LABELS` 與 `FILTERABLE_FIELDS` 已註冊但無資料對應，造成使用者誤用（永遠不命中任何商品）
2. **新增 `capacity_gb`**：SSD + HDD 合計 260 商品有此欄位，數值型可直接加 ≥ 篩選
3. **新增 `chip` 篩選器（顯示卡）**：200/251 商品有晶片型號，是顯示卡最核心的篩選維度

### 中期擴充
4. 新增 `base_ghz` / `turbo_ghz`：CPU 87% 覆蓋率
5. 新增 `chipset` / `form_factor`：主機板 89-90% 覆蓋率
6. 新增 `clock_mhz`：記憶體 56% 覆蓋率

### 低優先
7. SSD `format`（33%）與 `interface`（4%）覆蓋率偏低，可觀望
8. 記憶卡 `spec` / `capacity` 覆蓋率中等，視使用量決定
