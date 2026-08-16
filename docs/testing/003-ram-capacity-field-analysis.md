# 調查報告：「記憶體」篩選欄位與 `capacity_gb` 語意（RAM vs 儲存）分析

- 日期：2026-08-16（以 `crawler/spec_parser.py` 原始碼 + `data/items.json` 1,447 筆實際內容驗證）
- 範圍：**唯讀調查**，未修改任何 `web/src/`、`crawler/`、`data/`。
- 目的：回答使用者顧慮——「若把『記憶體』篩選改指 `capacity_gb`，套裝電腦（DESKTOP/劈發價組合區 BUNDLE）是否無法分辨 RAM 容量 vs SSD/HDD 儲存容量？」並給出修正建議。

---

## 一、結論摘要（TL;DR）

1. **`ram_gb` 在全部資料中出現 0 次**（`items.json`、`items.v2.json` 皆為 0；`items.v1.json` 亦為 0）。爬蟲 `spec_parser.py` **從未產出 `ram_gb`**。
2. **`capacity_gb` 確實被「RAM」與「儲存裝置」兩種語意共用（overloaded）**：
   - `_parse_ram`（記憶體）→ `extra["capacity_gb"]` = **RAM 容量**；
   - `_parse_ssd` / `_parse_hdd`（SSD/HDD）→ `extra["capacity_gb"]` = **儲存容量**。
   三者寫入**同一個 key**，單看欄位值無法分辨語意，必須靠 `item.category` 區分。
3. **直接回答使用者顧慮**：把「記憶體」篩選改指 `capacity_gb`，**套裝電腦（套裝/準系統）與劈發價組合區「不會」發生 RAM/儲存混淆**——因為這兩個分類的 parser **根本不產出 `capacity_gb`**（它們是輕量解析，只產出 `brand/model/usage/summary`），會被篩選靜默排除，和現在一樣。
4. **但「改指 `capacity_gb`」整體仍是錯的**：真正的混淆在 **SSD / HDD**——它們的 `capacity_gb` 是儲存容量，會被「記憶體 ≥ 16」誤命中（SSD 77 筆、HDD 89 筆）。因此**不能**採用「移除 `ram_gb`、記憶體改由 `capacity_gb` 承載」的簡化修法。
5. **建議修正**：保留「記憶體」獨立欄位 `ram_gb`，由**資料層 `crawler/spec_parser.py` 的 `_parse_ram` 改產出 `ram_gb`**（消除 overload），前端 `SPEC_FIELD_LABELS` 的 `ram_gb → 記憶體` 已是正確對照、**無需改 label**；僅需同步收斂 `capacity_gb` 的語意與型別註解。

---

## 二、Parser 分析（`crawler/spec_parser.py`）

### 2.1 誰寫 `capacity_gb`、誰寫 `ram_gb`

| Parser 函式 | 分類 | 產出欄位 | 語意 |
|---|---|---|---|
| `_parse_ram` | 記憶體 | `extra["capacity_gb"]`（另有 `spec`/`clock_mhz`） | **RAM 容量**（整數 GB） |
| `_parse_ssd` | SSD | `extra["capacity_gb"]`（另有 `interface`/`format`） | **儲存容量**（整數 GB，1TB=1024） |
| `_parse_hdd` | HDD | `extra["capacity_gb"]`（另有 `rpm`/`interface`） | **儲存容量**（整數 GB） |
| `_parse_memory_card` | 記憶卡 | `extra["capacity"]`（**字串 token**，如 `"128GB"`，非 `capacity_gb`） | 儲存容量（輕量、刻意保留原始字串） |
| `_parse_prebuilt` | 套裝/準系統 | 僅 `brand/model/usage`（`usage` 常為空） | **無任何容量欄位** |
| `_parse_bundle` | 劈發價組合區 | 僅 `brand/model/summary` | **無任何容量欄位** |
| 其餘（CPU/GPU/主機板） | — | `cores/threads/…`、`vram_gb/…`、`chipset/…` | 與容量無關 |

- **`ram_gb`：全文 0 次出現**。`spec_parser.py` 沒有任何地方寫入 `ram_gb`。
- **`capacity_gb`：overloaded 確認**。`_parse_ram` 用自己的 `_ram_capacity_gb()` 計算 RAM 容量，但寫入的 key 仍是 `capacity_gb`，與 `_parse_ssd`/`_parse_hdd`（共用 `_capacity_gb()`）**同 key 不同語意**。

### 2.2 `_DEEP_PARSERS` / `_LIGHT_PARSERS` 對照表（原始碼註冊表）

```python
_DEEP_PARSERS = {
    "CPU": _parse_cpu,     # cores/threads/base_ghz/turbo_ghz/tdp_w/socket
    "顯示卡": _parse_gpu,  # chip/vram_gb/interface/length_mm
    "記憶體": _parse_ram,  # capacity_gb/spec/clock_mhz   ← 應改為 ram_gb
    "SSD": _parse_ssd,     # capacity_gb/interface/format  ← 儲存容量
    "HDD": _parse_hdd,     # capacity_gb/rpm/interface     ← 儲存容量
    "主機板": _parse_mobo, # chipset/socket/form_factor
}
_LIGHT_PARSERS = {
    "記憶卡": _parse_memory_card,   # brand/capacity/spec（capacity 為字串 token）
    "套裝/準系統": _parse_prebuilt, # brand/model/usage（無容量）
    "劈發價組合區": _parse_bundle,  # model/summary（無容量）
}
```

### 2.3 各分類規格解析邏輯重點

- **記憶體 `_parse_ram`**：`_ram_capacity_gb(rest)` 取乘式（`8GB*2→16`）＞ `N GB`＞ `N G`；`_RE_RAM_SPEC` 抓 `DDR[0-9]`；`_RE_RAM_CLOCK` 抓時脈。容量寫入 `capacity_gb`。
- **SSD `_parse_ssd`**：共用 `_capacity_gb(rest)`（取首個 TB/GB，1TB=1024），寫入 `capacity_gb`；`_ssd_interface`（M.2/U.2/mSATA/SATA）與 `_ssd_format`（NVMe/SATA）。
- **HDD `_parse_hdd`**：共用 `_capacity_gb(rest)`，寫入 `capacity_gb`；`_RE_RPM` 抓轉速。
- **記憶卡 `_parse_memory_card`**：`_RE_CARD_CAPACITY` 抓 `\d+(TB|GB|MB)`，寫入 `extra["capacity"]`（**字串**，刻意與深度分類 `capacity_gb` 型別不同）。
- **套裝/準系統 `_parse_prebuilt`**：只做品牌剝離 + 用途關鍵字（`_PREBUILT_USAGE`）→ `usage`。**完全不解析容量**。
- **劈發價組合區 `_parse_bundle`**：剝離開頭標籤 `【…】`，寫 `summary`。**完全不解析容量**。

> 結論：`capacity_gb` 的 overload **只在「記憶體 vs SSD/HDD」之間**；記憶卡走的是另一把 `capacity`（字串）；套裝/準系統、劈發價組合區**根本不產出容量欄位**。

---

## 三、資料統計（`data/items.json`，1,447 筆）

> 統計時將 `spec.extra` 平鋪至頂層（鏡像前端 `useItems.normalizeSpec` 的行為），與前端 `item.spec` 實際可讀取的形狀一致。

### 3.1 逐分類欄位出現次數

| 分類 | 筆數 | `capacity_gb` | `ram_gb` | 其他關鍵欄位 |
|---|---|---|---|---|
| CPU | 47 | 0 | 0 | `cores/threads` 32、`base_ghz/turbo_ghz` 41、`tdp_w` 30 |
| 顯示卡 | 255 | 0 | 0 | `vram_gb` 173、`chip` 201 |
| **記憶體** | **216** | **210** | **0** | `clock_mhz` 116、`spec` 122 |
| **SSD** | **171** | **77** | 0 | `format` 58、`interface` 7 |
| **HDD** | **89** | **89** | 0 | `rpm` 89 |
| **記憶卡** | **54** | **0** | 0 | `spec` 34、`capacity`(字串) 9 |
| **套裝/準系統** | **157** | **0** | 0 | `usage` 0（全無） |
| **劈發價組合區** | **86** | **0** | 0 | `summary` 86 |
| 主機板 | 372 | 0 | 0 | `chipset` 332、`form_factor` 337 |

- 全資料 `ram_gb`：**0 次**（不分分類皆 0）。
- 全資料 `capacity_gb`：**376 次** = 記憶體 210 + SSD 77 + HDD 89。
- `capacity_gb` 值域：記憶體 `8~128`；SSD `500~8192`；HDD `1024~32768`。

### 3.2 「記憶體 ≥ 16」若改指 `capacity_gb`（全域、無分類範圍）會命中什麼

| 分類 | `capacity_gb >= 16` 命中筆數 | 語意是否正確 |
|---|---|---|
| 記憶體 | **191** | ✅ RAM 容量 |
| SSD | **77** | ❌ 儲存容量（誤命中） |
| HDD | **89** | ❌ 儲存容量（誤命中） |
| 套裝/準系統 | 0（無欄位） | —（被排除） |
| 劈發價組合區 | 0（無欄位） | —（被排除） |

→ 直接證明：**「記憶體 ≥ 16 改指 `capacity_gb`」會把 77 顆 SSD + 89 顆 HDD 的儲存容量誤當成 RAM**；而套裝/劈發價反而因無欄位而不受影響。

### 3.3 樣本

**記憶體（`capacity_gb` = RAM 容量）**

```json
{"name":"UMAX 單條32GB DDR5-4800/CL40","spec":{"brand":"UMAX","model":"單條32GB DDR5-4800/CL40","capacity_gb":32,"spec":"DDR5","clock_mhz":4800}}
{"name":"威剛 單條8GB DDR5-5600/CL46 (AD5U56008G-S)","spec":{"brand":"威剛","model":"單條8GB DDR5-5600/CL46 (AD5U56008G-S)","capacity_gb":8,"spec":"DDR5","clock_mhz":5600}}
{"name":"UMAX 單條16GB DDR5-5600/CL46","spec":{"capacity_gb":16,"spec":"DDR5","clock_mhz":5600}}
```

**SSD（`capacity_gb` = 儲存容量）**

```json
{"name":"威剛 Ultimate SU800 1TB/2.5吋/…【五年】","spec":{"capacity_gb":1024}}
{"name":"威剛 Ultimate SU650 480G/2.5吋/…【三年保】","spec":{"capacity_gb":480}}
```

**HDD（`capacity_gb` = 儲存容量）**

```json
{"name":"Toshiba 2TB (128M/5400轉/3年保) (DT02ABA200)…","spec":{"capacity_gb":2048,"rpm":5400}}
{"name":"Toshiba 4TB【P300系列】(128M/5400轉/3年保)…","spec":{"capacity_gb":4096,"rpm":5400}}
```

**記憶卡（`capacity` 為字串 token，非 `capacity_gb`）**

```json
{"name":"金士頓 Canvas Select+ 64G micro SDXC / R:100 / 終保 / 附轉卡 (SDCS3/64GB)","spec":{"capacity":"64GB","spec":"SDXC"}}
{"name":"三星 2024 EVO Plus 512G micro SDXC / …","spec":{"spec":"SDXC"}}   // 無 capacity（"512G" 無 GB 字尾，未被 _RE_CARD_CAPACITY 抓取）
```

**套裝/準系統（名稱含 RAM+儲存，但 spec 無任何容量欄位）**

```json
{"name":"ASUS Ascent GX10 GB10 / 128G / Gen4 1TB SSD【現貨】","spec":{"brand":"ASUS","model":"Ascent GX10 GB10 / 128G / Gen4 1TB SSD【現貨】"}}
{"name":"ASUS ROG【GM700TZ-R9800X149W】R7 9800X3D / 16G / 1T / 850W電供 / 水冷","spec":{"brand":"ASUS","model":"… 16G / 1T …"}}
{"name":"MSI Infinite S3 14NTA5【3208TW】i5-14400F / 16G / 1T / WIN11 / RTX 3050","spec":{"brand":"MSI","model":"… 16G / 1T …"}}
```

> 注意：這些套裝名稱明明同時含 `128G`（RAM）與 `1TB SSD`（儲存），但 `_parse_prebuilt` **兩者都不解析**，因此套裝在目前資料中對 RAM 容量與儲存容量**皆無結構化欄位**。

**劈發價組合區（僅 summary）**

```json
{"name":"【套裝搭購優惠】羅技 G512 機械式鍵盤","spec":{"summary":"羅技 G512 機械式鍵盤"}}
{"name":"微星 戰略組合包(GK20鍵盤+Versa 300無線滑鼠+…耳機)原價5109","spec":{"summary":"微星 戰略組合包(…)"}}
```

---

## 四、回答使用者顧慮

**問**：若把「記憶體」篩選統一改指 `capacity_gb`，套裝電腦（DESKTOP / 劈發價組合區 BUNDLE）是否無法分辨 RAM 容量 vs SSD/HDD 儲存容量？

**答：No——就「套裝/準系統」與「劈發價組合區」而言不會混淆，因為這兩個分類完全不產出 `capacity_gb`（輕量 parser 只給 `brand/model/usage/summary`），篩選時會被靜默排除，與現況相同。**

**但這不代表「改指 `capacity_gb`」是安全的**：真正的混淆發生在 **SSD（77 筆有 `capacity_gb`）與 HDD（89 筆有 `capacity_gb`）**。因為 `capacity_gb` 是 overloaded key（記憶體=RAM、SSD/HDD=儲存共用同一把 key），若在**未選分類（全部）**或前端無分類範圍時套用「記憶體 ≥ 16 → `capacity_gb >= 16`」，會把 SSD/HDD 的儲存容量誤當成 RAM 命中。

**區分責任：主要在資料層（crawler `spec_parser.py`），其次才是前端**：

- **資料層**：`_parse_ram` 把 RAM 容量寫進與 SSD/HDD 共用的 `capacity_gb`，產出語意不清（overloaded），需「001 修正」——讓記憶體改用獨立 `ram_gb`。
- **前端**：`specFilter.ts` 的 `SPEC_FIELD_LABELS` 多掛了一個資料永遠不存在的 `ram_gb → 記憶體`；但即使把「記憶體」改指 `capacity_gb`，也只是把 overload 從「空結果」變成「誤命中 SSD/HDD」，**根因仍在資料層**。

---

## 五、修正建議（供前端修 bug 用，本報告不執行）

### 首選方案：保留獨立「記憶體」欄位，資料層先產出 `ram_gb`

1. **資料層（必要，根因修正）— `crawler/spec_parser.py`**
   - `_parse_ram()`：把 `extra["capacity_gb"] = cap` 改為 `extra["ram_gb"] = cap`。
   - 同步更新函式 docstring 與 `_DEEP_PARSERS` 註解：`"記憶體": _parse_ram  # ram_gb/spec/clock_mhz`。
   - 重新執行爬蟲 + `scripts/version_data.py` 產出新的 `data/items.json` 與 `items.v*.json`（前端讀取的是版本化快照）。
   - 效果：RAM 容量有自己的 key，`capacity_gb` 剩 SSD/HDD 專用，overload 消失。

2. **前端 `web/src/utils/specFilter.ts`**
   - `ram_gb: { label: "記憶體", unit: "GB" }` **保留不動**（資料層產出 `ram_gb` 後即正確，`FILTERABLE_FIELDS` 的 `"ram_gb"` 也保留）。
   - `capacity_gb: { label: "容量", unit: "GB" }` 建議收斂語意：改 label 為「儲存容量」（或從 `FILTERABLE_FIELDS` 移除，避免與「記憶體」再度混用）；並在註解標明僅適用 SSD/HDD。

3. **前端 `web/src/types/filters.ts`**
   - `SpecField` 保留 `"ram_gb"`；把 `"capacity_gb"` 的 P2 註解改為「儲存容量（SSD/HDD）」。
   - `SpecCondition` 視需要可加選用 `category?: string` 作為防禦（非必要，若資料層已修正則不必）。

4. **前端 `web/src/types/item.ts`（契約註解）**
   - `capacity_gb` 註解由「容量（SSD/HDD/記憶卡/記憶體）」改為「儲存容量（SSD/HDD）」。
   - `ram_gb` 註解維持「記憶體容量」（現已正確，僅待資料層產出）。

### 替代方案（僅前端、不重爬，不建議）

- 加 `category` 範圍限制到 `SpecCondition`/`matchesCondition`/`useFilters`：讓「記憶體」條件只在 `category === "記憶體"` 生效、「儲存容量」只在 `SSD/HDD` 生效。
- 缺點：改動較多（型別 + 3 個檔 + E2E oracle），且資料仍維持 overloaded 語意，未來容易再踩坑。

### 補 E2E（使用者已決定要補）

- `web/e2e/003-filtering.spec.ts`：
  - `記憶體（ram_gb）≥ 16` → 記憶體 191 筆、`≥ 32` → 155 筆（用真資料 oracle）。
  - 新增**防回歸斷言**：「記憶體篩選不得命中 SSD/HDD」（資料層修正後，SSD/HDD 無 `ram_gb`，應為 0）。
  - 保留/補強 `capacity_gb`（儲存容量）篩選案例，驗證只命中 SSD/HDD。

---

## 附錄：關鍵數字速查

| 項目 | 值 |
|---|---|
| 全資料 `ram_gb` 出現次數 | **0**（items.json / items.v2.json 皆 0） |
| 全資料 `capacity_gb` 出現次數 | **376** |
| 記憶體 `capacity_gb` | 210 / 216（值域 8~128） |
| SSD `capacity_gb` | 77 / 171（值域 500~8192） |
| HDD `capacity_gb` | 89 / 89（值域 1024~32768） |
| 記憶卡 `capacity`（字串） | 9 / 54 |
| 套裝/準系統 `capacity_gb` / `ram_gb` | 0 / 0 |
| 劈發價組合區 `capacity_gb` / `ram_gb` | 0 / 0 |
| 「記憶體≥16」改指 capacity_gb 的誤命中 | SSD 77 + HDD 89 |
