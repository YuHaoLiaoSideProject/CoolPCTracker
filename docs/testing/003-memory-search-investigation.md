# 調查報告：E2E 是否涵蓋「記憶體」搜尋/篩選，與「搜尋 >1GB 無資料」根因

- 日期：2026-08-16（以倉庫內資料 `data/items.json` / `data/items.v2.json` 實際內容驗證）
- 範圍：唯讀調查，未修改任何 `web/src/` 業務程式碼或資料檔。
- 結論摘要：
  1. 現有 E2E **未涵蓋**「記憶體」分類的搜尋或規格篩選。
  2. 「搜尋 >1GB 無資料」是**預期行為**（搜尋是字面子字串比對，`>` 不是支援語法；`1GB` 亦無記憶體商品命中）。
  3. 但同時發現一個**真實前端 mapping bug**：規格篩選下拉的「記憶體」選項對應 `ram_gb` 欄位，而資料與爬蟲實際產出的是 `capacity_gb`，導致「記憶體 ≥ N」結構化篩選**永遠空結果**。

---

## 一、問題一：現有 E2E 是否涵蓋記憶體（RAM）搜尋/規格篩選？

### 答案：沒有。

`web/e2e/003-filtering.spec.ts` 是唯一一個列表篩選 E2E（`web/e2e/` 下僅此一支 + `helpers/oracle.ts`）。它所涵蓋的欄位與關鍵字如下：

### 規格篩選（`applyFilter` → 下拉 `規格欄位` + 數值）覆蓋

| 測試 | 欄位 key | 標籤 | 情境 |
|---|---|---|---|
| VRAM≥12G 結果正確 | `vram_gb` | VRAM | 單一篩選、集合相等 |
| 瓦數≥750W 空狀態 | `wattage_w` | 瓦數 | 資料缺口（無 wattage_w） |
| CPU核數≥8 結果正確 | `cores` | CPU核數 | 單一篩選 |
| VRAM≥12G 且 瓦數≥750W | `vram_gb` + `wattage_w` | — | 多條件 AND 空狀態 |
| CPU核數≥8 且 TDP≥120W | `cores` + `tdp_w` | — | 多條件 AND 交集 |
| VRAM≥24G 且 瓦數≥1200W | `vram_gb` + `wattage_w` | — | 空狀態 + 可清除 |
| vram 恰等於 12G 邊界 | `vram_gb` | VRAM | ≥ 邊界納入 |
| 無規格欄位靜默排除 | `vram_gb` | VRAM | 不報錯 |

### 搜尋關鍵字覆蓋

| 測試 | 關鍵字 | 情境 |
|---|---|---|
| 搜尋＋篩選並用 | `"RTX 5070"` | 名稱搜尋（顯示卡） |
| 清除全部條件 | `"RTX 5070"` | 名稱搜尋 + 清除 |

### 明確結論

- **記憶體（RAM，category label「記憶體」）完全沒有出現在任何 E2E 案例中。**
- 沒有用 `ram_gb`、`capacity_gb` 欄位做過規格篩選測試。
- 沒有對記憶體商品做過任何搜尋（`GB` / `8GB` / `16GB` / `32GB` / `DDR5` 等關鍵字皆未測）。
- `web/e2e/helpers/oracle.ts` 鏡像的 `matchesKeyword` / `flatSpec` / `applyConditions` 本身是通用的，但**沒有任何測試呼叫時傳入記憶體相關欄位或關鍵字**。
- 單元測試亦未補上此缺口：
  - `web/src/utils/__tests__/search.test.ts`：僅以顯示卡/主機板 fixture 測 `matchesKeyword`，無記憶體、無 `GB` 關鍵字。
  - `web/src/utils/__tests__/specFilter.test.ts`：只斷言 `SPEC_FIELD_LABELS.ram_gb.label === "記憶體"` 存在，**從未用真實記憶體資料跑過 `matchesCondition`**。
  - `web/src/composables/__tests__/useItems.test.ts`：有 parse 記憶體 fixture（`extra: { capacity_gb: 32, ... }`），只驗證 normalizeSpec 平鋪出 `capacity_gb`，未涉及搜尋/篩選命中。

---

## 二、問題二：搜尋與篩選的實際運作方式

### 2.1 搜尋（`web/src/utils/search.ts` → `matchesKeyword`）

```ts
export function matchesKeyword(it: Item, q: string): boolean {
  const needle = q.toLowerCase()
  if (it.name.toLowerCase().includes(needle)) return true
  const specText = Object.values(it.spec)
    .map(v => String(v ?? ""))
    .join(" ")
    .toLowerCase()
  return specText.includes(needle)
}
```

- 純**字面子字串比對**（`String.includes`），不區分大小寫。
- 比對範圍：`name` + 已正規化的 `spec` 欄位**值**（不是 key、不是 label）。
- **完全沒有單位正規化、沒有運算子（`>`、`<`、`≥`）解析、沒有數值比較**。`>`、`GB` 一律當作字面字元。

`useFilters.ts` 的過濾管線：`分類 → 搜尋 → 規格條件（AND）`，搜尋關鍵字只做 `trim + toLowerCase` 後傳給 `matchesKeyword`。

### 2.2 spec 正規化（`useItems.ts` → `normalizeSpec`）

- 將 `spec.extra` 平鋪到頂層（`capacity_gb` / `clock_mhz` / `spec` / `vram_gb`…），剔除 `null/undefined/空字串`。
- **值維持原樣**：`capacity_gb` 是**純數字**（如 `32`），`clock_mhz` 純數字，`spec` 是字串 `"DDR5"`，`model` 是字串（含 `32GB`）。
- 因此 spec 值本身**不含單位字串**（數字欄位沒有 `GB`），但 `model`（以及 `name`）字串裡含 `GB`。

### 2.3 規格篩選（`specFilter.ts`）

```ts
export const SPEC_FIELD_LABELS: Record<string, { label: string; unit: string }> = {
  vram_gb: { label: "VRAM", unit: "G" },
  cores: { label: "CPU核數", unit: "核" },
  wattage_w: { label: "瓦數", unit: "W" },
  capacity_gb: { label: "容量", unit: "GB" },
  ram_gb: { label: "記憶體", unit: "GB" },   // ← 記憶體選項對應 ram_gb
  tdp_w: { label: "TDP", unit: "W" },
}
```

- 篩選走**結構化數值比對**：`matchesCondition` 要求 `item.spec[field]` 為 `number` 且 `>= threshold`。
- 下拉「記憶體」→ `field = "ram_gb"`，比對 `item.spec.ram_gb`。

### 2.4 關鍵：真實記憶體資料用的是 `capacity_gb`，不是 `ram_gb`

`crawler/spec_parser.py` 的 `_parse_ram`（記憶體深度解析）產出：

```python
_DEEP_PARSERS = {
    "記憶體": _parse_ram,     # capacity_gb/spec/clock_mhz
    ...
}
# _parse_ram：cap = _ram_capacity_gb(rest); extra["capacity_gb"] = cap
```

實測 `data/items.json`（1,447 筆，記憶體 216 筆）：

- 記憶體 `capacity_gb` 出現：**210 / 216** 筆（6 筆 Biwin / Origin code 品牌未辨識 → `extra: {}` 無容量）。
- 記憶體 `ram_gb` 出現：**0 / 216** 筆。
- `capacity_gb` 值域：`8, 16, 32, 48, 64, 96, 128`（純整數）。
- 名稱樣本：`UMAX 單條32GB DDR5-4800/CL40`、`威剛 單條16GB DDR5-5600/CL46 …`、`金士頓 單條8GB DDR5-5600(CL36) FURY Beast …`。

→ 也就是說：**規格篩選下拉的「記憶體」選項（`ram_gb`）在資料中永遠不存在，套用「記憶體 ≥ 任意值」必定空結果**；而真正有值的「容量」（`capacity_gb`）是另一個下拉選項。

---

## 三、真實資料驗證：「>1GB」「1GB」「16GB」「32GB」命中情形

以 `matchesKeyword` 鏡像邏輯（與 `oracle.ts` 相同）在 1,447 筆上模擬：

| 關鍵字 | 全部命中 | 記憶體命中 | 說明 |
|---|---|---|---|
| `>1GB` | **0** | 0 | `>` 為字面字元，無任何 name/spec 值含 `>1GB` |
| `1GB` | 68 | **0** | 68 筆全為「主機板」名稱內的 `LAN 1Gb` / `Intel 1Gb`（大小寫不敏感）；記憶體最小容量 8GB，且 `1GB` 不是 `8GB/16GB/32GB/48GB/64GB/96GB/128GB` 的子字串 |
| `16GB` | 89 | 70 | 名稱含 `16GB` |
| `32GB` | 93 | 89 | 名稱含 `32GB` |
| `GB` | 477 | 184 | 名稱（及 model 字串）含 `GB` |
| `>` | 0 | 0 | 字面字元，無命中 |
| `>1` | 0 | 0 | 同上 |

結構化篩選 `matchesCondition` 對記憶體（216 筆）：

| 條件 | 命中 |
|---|---|
| `ram_gb >= 1` | **0**（欄位不存在） |
| `ram_gb >= 8/16/32` | **0** |
| `capacity_gb >= 1` | 210 |
| `capacity_gb >= 8` | 210 |
| `capacity_gb >= 16` | 191 |
| `capacity_gb >= 32` | 155 |

---

## 四、判定

### 「搜尋 >1GB 無資料」→ **(B) 預期行為**

- 搜尋框（`SearchBar` → `useFilters` → `matchesKeyword`）**本就不支援運算子語法**，是字面比對。`>`、`GB` 都當字面字元。
- `>1GB` 四個字元在資料中完全不存在 → 空結果，符合設計（見 `search.test.ts` 的「特殊字元字面比對不拋錯」案例，設計上就是 literal）。
- 即使輸入 `1GB`，記憶體分類也是 0 筆：**沒有 1GB 的記憶體商品**（最小 8GB），且 `1GB` 不是任何 `8GB/16GB/…` 的子字串。使用者想表達「容量大於 1GB」的意圖，應使用**規格篩選面板**（數值 ≥），而不是搜尋框。

### 同時發現的真實 bug（非使用者原始回報，但與「記憶體篩選」直接相關）→ **(前端 mapping bug / 資料契約不一致)**

- 規格篩選下拉「記憶體」選項綁定 `ram_gb`，但爬蟲 `spec_parser` 對記憶體產出的是 `capacity_gb`（`ram_gb` 從未被產出）。
- 結果：**結構化篩選「記憶體 ≥ N」永遠空結果**（等同現有 E2E 中 `wattage_w` 資料缺口的情境，但這是 mapping 錯誤而非純資料缺口——資料其實有值，只是存在 `capacity_gb`）。
- 佐證：`usePriceDelta.specChipTexts`、`SpecTable.SPEC_LABELS` 都把記憶體顯示為 `capacity_gb`；只有 `specFilter.SPEC_FIELD_LABELS` 多掛了一個 `ram_gb: "記憶體"`，與資料契約脫節。

---

## 五、修正建議（僅描述，不修改 `web/src/`）

1. **`web/src/utils/specFilter.ts`**：移除或改寫 `ram_gb` 選項。
   - 最簡：刪除 `SPEC_FIELD_LABELS.ram_gb` 與 `FILTERABLE_FIELDS` 中的 `"ram_gb"`，讓「容量（capacity_gb）」成為記憶體/SSD/HDD/記憶卡共用的容量篩選；或
   - 若要保留「記憶體」標籤，把 label「記憶體」改指 `capacity_gb`（但與現有「容量」label 衝突，需改 `parseCondition` 支援 label→field 一對多，或直接統一用「容量」）。
   - 同步 `web/src/types/filters.ts` 的 `SpecField` 聯合型別（移除 `"ram_gb"` 或保留註解標記棄用）。
2. **`web/src/types/item.ts`**：`ram_gb` 欄位標記為未使用/棄用（資料契約實際由 `capacity_gb` 承載），避免後續再誤用。
3. **補 E2E（建議，非 bug 修復）**：在 `web/e2e/003-filtering.spec.ts` 增加
   - 搜尋：`"16GB"` / `"GB"` / `"DDR5"`（驗證記憶體名稱+model 命中）、`">1GB"`（驗證 literal 空結果，寫死為預期行為防回歸）；
   - 篩選：`capacity_gb ≥ 16`（記憶體 191 筆）與 `capacity_gb ≥ 32`（155 筆）用真資料 oracle 斷言，取代/補足目前完全沒測到的「容量」欄位。
4. **影響範圍**：僅規格篩選下拉選項與型別宣告；移除 `ram_gb` 後「記憶體」分類的商品改由「容量」欄位篩選，搜尋行為不變。

---

## 附錄：證據樣本（data/items.json）

記憶體商品 spec 形狀（第一筆，`category === "記憶體"`）：

```json
{
  "id": "…",
  "category": "記憶體",
  "name": "UMAX 單條32GB DDR5-4800/CL40",
  "spec": {
    "brand": "UMAX",
    "model": "單條32GB DDR5-4800/CL40",
    "extra": { "capacity_gb": 32, "spec": "DDR5", "clock_mhz": 4800 }
  }
}
```

`normalizeSpec` 後（前端 `Item.spec`）：

```json
{ "brand": "UMAX", "model": "單條32GB DDR5-4800/CL40", "capacity_gb": 32, "spec": "DDR5", "clock_mhz": 4800 }
```

`matchesKeyword` 對該筆的 spec 值字串：

```text
UMAX 單條32GB DDR5-4800/CL40 32 DDR5 4800
```

- `GB` 命中（出現在 model）；`16GB` / `32GB` 命中（model）；`1GB` / `>1GB` 不命中。
- `capacity_gb` 的值是純數字 `32`，本身無 `GB` 字串；單位只在 name/model 字串中。
