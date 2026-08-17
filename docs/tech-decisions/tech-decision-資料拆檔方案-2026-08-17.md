# 開發方案決策文件：資料拆檔（data/items.json 每日資料分離）

> **⚠️ 契約 v2 演進（2026-08-17 定稿）**：本文件最初為 O4「三層拆檔」決策（契約 v1）。v2「**分類拆檔**」在 O4 基礎上再演進：`data/items.json` 單檔與 `api/latest.json` 均被**移除**，改為 `data/items/{g}.json` / `api/items/{g}.json` **每分類一檔**（g=分類 G 索引：1/3/4/5/6/7/8/9/12；頂層純 items 陣列、**無 meta、無 category 欄位**，meta 集中於 data/meta.json）；`api/index.json` 以 `categories[]`（id/name/file/count）取代 `latest_file`。下文 §2 起描述 O4（v1）決策歷程，**現行契約以本文決策摘要、§6.1/§7 的 v2 註記、`docs/development/*`、`docs/bdds/*`、README「資料/API 組織」為準**。
>
> **觸發**：2026-08-17 使用者指出 `data/items.json` 達 40k 行／~1MB，主張「應該拆檔，不要把每天資料放一起，依照日期切開」。
> **性質**：架構層資料組織評估（tech-assessment-generator 引導，非互動產出）
> **範圍**：`data/`（真相層）、`api/`（衍生對外層）、前端資料路徑、`crawler/`、`scripts/version_data.py`、測試與 BDD 文件
> **相關文件**：`docs/analysis/items-file-strategy.md`、`docs/development/001/002/004`、`docs/bdds/001/002/004`、`docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md`

---

## 📌 決策摘要

| 項目 | 內容 |
|------|------|
| **最終方案** | **方案 O4「三層拆檔」→ 契約 v2「分類拆檔」**：`data/items/{g}.json` / `api/items/{g}.json` **每分類一檔**（g=1/3/4/5/6/7/8/9/12；純 items 陣列、無 meta、無 category 欄位；每筆 history 僅 ≤2 點）、每日價格點拆至 `data/daily/YYYYMMDD.json`、對外趨勢拆至 `api/trends/{id}.json`；**`data/items.json` 單檔、`api/latest.json`、`latest_file` 均已移除**；對外層 = `api/items/{g}.json`（鏡像）＋ `api/daily/`（鏡像）＋ `api/trends/` ＋ `api/index.json`（categories[]（id/name/file/count）、daily_files[]、trends_prefix） |
| **決策日期** | 2026-08-17 |
| **決策前提** | ① 趨勢圖（004）與卡片 sparkline／漲跌徽章（003）需要跨日價格點，**歷史資料不可刪**；② 專案定位「認真長期維護」（原決策 §1）；③ 前端為純靜態 GitHub Pages，無後端可動態組裝 |
| **共識程度** | ✅ 2026-08-17 已確認：**D1 = 最小嵌入**（列表快照 history 僅最近 ≤2 點，卡片漲跌／sparkline 照常）、**D2 = `api/trends/{id}.json`**（詳情趨勢圖 1 request，useTrend 載入）、**D3 = O4**（data 層 items.json 最新狀態單檔，不拆每日狀態快照）；repo 年度 raw 成長 ~45MB |

---

## 1. 需求回顧

### 1.1 使用者的訴求（原始陳述）

> 「data/items.json 達 2 萬行，是因為原價屋資料太多？」
> 「應該拆檔，不要把每天資料放一起，依照日期切開」

**拆解**：
- 痛點 A：`data/items.json` 單檔累積（40k 行／1MB，且每天長大）
- 痛點 B：每日資料混在同一檔的 `history` 陣列中，沒有依日期分離
- 隱含前提：不願意接受「單檔無限成長」

### 1.2 需求假設（使用者取消問卷，以下為評估者推導，需在 §6.3 確認）

| 假設 | 內容 | 依據 |
|------|------|------|
| H1 | 歷史價格資料（趨勢圖用）**必須保留** | 004 規格／BDD：歷史趨勢圖、歷史最低價為 P0 功能 |
| H2 | 前端列表頁的漲跌徽章與 sparkline（003）**需要每商品最近價格點** | O4 定稿（最小嵌入）：`ProductCard`/`usePriceDelta` 取 `history` 末兩筆（≤2 點）；列表快照不再提供 30 點短歷史 |
| H3 | 拆檔後單檔大小應**有上限（不再隨時間成長）** | 使用者訴求核心 |
| H4 | 前端資料載入方式可接受調整（但以「單一入口 index.json → 最新快照」為不變契約） | 002 §1.7 runtime discovery |
| H5 | repo 體積成長需控制在可接受範圍（clone 不要數百 MB） | 「認真長期維護」定位 |

### 1.3 非需求

- ❌ 不是要減少爬蟲抓取範圍（1448 筆商品為正常量，非問題根源）
- ❌ 不是要把歷史資料丟掉
- ❌ 不是要引入資料庫／後端（維持全靜態 GitHub Pages 架構）

---

## 2. 現況量化診斷（2026-08-17 實測）

### 2.1 檔案組成

```
data/items.json         1,019,618 B（40,724 行，pretty-print indent=2）1448 筆商品
data/meta.json              423 B（crawled_at/counts/total/status）
api/items/20260815.json  632,930 B（compact，含完整 history）
api/items/20260816.json  662,983 B（compact，含完整 history）
api/latest.json          662,983 B（＝最新快照）
api/index.json               898 B
```

> **時序註記**：上述為 2026-08-17 決策當下（O4 落地前）實測數值；O4 定稿後 `api/items/` 已移除，
> 對外改為 latest / daily / trends / index 四類檔，`data/items.json` 序列化後每筆 history ≤2 點（固定大小）。

### 2.2 成長模型（關鍵數據）

| 量 | 數值 |
|---|---|
| 商品筆數 | 1448 |
| 快照（compact、不含 history） | **501 KB（固定）** |
| history 每商品每點成本 | **26.6 B**（compact `[d,p]`） |
| 每日 history 增量 | ~38 KB/天 |
| 前端下載（現況） | 現在 576 KB → **1 年後 13.9 MB/次** |
| repo api/ 年度 raw 成長（現況） | **~2.6 GB**（git delta 壓縮後估 400–700 MB） |
| data/items.json 年度成長 | ~14 MB（compact）／~26 MB（pretty） |

### 2.3 核心診斷

**問題不在資料量（1448 筆很正常），在儲存結構**：

1. **O(n²) 重複儲存**：每個 api 每日快照都把「到當天為止的完整 history」複製一份。
   第 N 天快照大小 = 501KB + N×38KB；repo 累積 = Σ(501 + k×38)KB ≈ **二次方成長**。
2. **前端下載隨時間惡化**：一年後每次載入 13.9MB，其中 96% 是重複歷史。
3. **行數問題是表象**：40k 行 = pretty-print（indent=2）造成，1448 筆 × 25 行；compact 後同一內容只有 1 行。

### 2.4 消費端盤點（誰需要 history）

| 消費端 | 需求 | 目前來源 |
|---|---|---|
| 列表卡片漲跌徽章 | 每商品**末 2 點** | 列表快照 `item.history`（O4 最小嵌入 ≤2 點） |
| 列表卡片 sparkline | 每商品**末 ≤2 點**（30 點方案未採） | 列表快照 history（ProductCard/Sparkline） |
| 詳情趨勢圖（004） | 單商品**完整 history** | `usePriceHistory` → `PriceTrendChart` |
| 歷史最低價（004） | 單商品完整 history | 同上 |

→ 列表需要「每商品最近少量點」（全部商品、但量少；O4 定稿 = ≤2 點）；詳情需要「單商品全部點」（單一商品、但量多）。兩者對資料組織的需求不同，是拆檔設計的核心。

---

## 3. 候選方案

### 方案 O1：維持現況（baseline）

單檔累積真相 + api 快照內嵌完整 history。零改動。

- 1 年後：前端下載 13.9MB/次；repo raw 2.6GB
- **結論：違反「長期維護」定位，不考慮**（僅作基準）

### 方案 O2：compact 壓縮（止痛）

`store.py` 寫入改 `separators=(",",":")`，`data/items.json` 40k 行 → 1 行。

- 改動 ~5 行；**成長問題完全沒解決**（1 年後照樣 13.9MB/次、repo 2.6GB）
- 結論：可作為立即止痛，非最終解

### 方案 O3：api 快照內嵌「截斷 history」（最近 N=90 天）

`version_data.py` 輸出差異：快照 items 的 history 只帶最近 90 天。

- 前端**零改動**；單檔大小固定上限 3.8MB
- repo raw 1.4GB/年（git delta 後估 100–200MB）——仍是 O(n²) 的滑動視窗變體
- 趨勢圖只顯示最近 90 天（004 BDD 未定義上限，可接受）
- 結論：改動最小但 repo 成長仍大；data/items.json 照樣累積

### 方案 O4：三層拆檔（**推薦**）

```
data/                        # 真相層（crawler 寫）
  items.json                 # 只留「最新狀態」+ 當日點（固定 ~500KB，不再累積歷史）
  meta.json                  # 中繼（不變，~423B）
  daily/YYYYMMDD.json        # 每日價格點 {id: price}（新增，~40KB/天；歷史序列 = 趨勢資料源）

api/                         # 對外層（version_data 組裝）
  items/YYYYMMDD.json        # 每日快照（不含 history，固定 ~500KB；維持 002 cache-busting）
  daily/YYYYMMDD.json        # 每日價格點（鏡像 data/daily）
  trends/{item_id}.json      # 逐商品完整歷史（詳情趨勢圖 1 request，~2.6KB/90 天）
  latest.json                # = 最新快照（穩定端點）
  index.json                 # latest_file + files[] + daily_files[] + trends 指標
```

> **O4 定稿修訂（2026-08-17）**：上樹中之 `api/items/YYYYMMDD.json` 已**移除**（不再產生）；對外層 = `api/latest.json`＋ `api/daily/`＋ `api/trends/`＋ `api/index.json`（latest_file="api/latest.json"、daily_files[]、trends_prefix），見 §6.1／§7 定稿結構。

- 前端：列表兩段式不變（fetch index → latest_file）；詳情圖改 fetch `api/trends/{id}.json`
- crawler：`store.py` 改動中等（save 不再寫 history、新增 daily 檔寫入）；`main.py` 幾乎不動
- repo 年度 raw ~207MB（git delta 後估 40–60MB）；前端下載固定 ~500KB + 10KB/商品
- **徹底消除 O(n²)**：所有對外檔皆固定大小，歷史以「每日價格點檔序列」存在

### 方案 O5：data 層也拆每日快照（完全依日期切開）

在 O4 基礎上，`data/items.json` 也改為 `data/items/YYYYMMDD.json` 每日快照（無內嵌 history）。

- crawler diff 基準改讀「昨日快照檔」（需處理跳日、失敗日）
- repo 年度 raw 再加 ~180MB（除非 api 直接 serve data/，不雙重 commit）
- 優點：真相層也是純檔案序列（可回放、可稽核）；缺點：crawler 重構成本最高、checkout 最大
- 評估：**對本專案（每日單次爬蟲、health check、單人維護）O4 的「最新狀態單檔」已足夠**——`items.json` 作為 diff 的工作記憶（prev state），歷史由 daily 序列承載，語意與現況一致

---

## 4. 權衡評估

### 4.1 權衡矩陣（1–5 分，5 最佳）

| 維度 | O1 現況 | O2 compact | O3 截斷 | **O4 三層拆檔** | O5 全面拆檔 |
|---|:---:|:---:|:---:|:---:|:---:|
| 🎯 需求符合度（拆檔訴求） | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| ⚡ 開發成本（改動範圍） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 🔧 維護成本（長期） | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 📈 成長性（O(n²)→O(n)） | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 📦 repo 體積（1 年後） | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 🖥️ 前端下載量（1 年後） | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 🔒 風險（回歸面） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **總分** | **19** | **21** | **25** | **33** | **30** |

### 4.2 關鍵取捨

**取捨 #1：crawler 改動 vs 真相層潔癖**
- O4 的 `data/items.json` 仍是最新狀態單檔（crawler diff 工作記憶，~500KB 固定）；O5 把它也拆成每日檔
- O4 節省：`store.py` 的 load（讀昨日檔＋跳日處理）不用重寫、health check 語意不變
- O5 的好處（真相＝檔案序列）在本專案場景下**沒有實際消費者**——趨勢圖消費的是 daily 價格點序列，不是狀態快照序列

**取捨 #2：列表 sparkline 資料來源（決策點 D1）**
- 拆檔後快照不含 history → 卡片 sparkline（末 30 點）與漲跌徽章（末 2 點）需要新來源：
  - **D1-a 快照內嵌「最近 N 點」**（最終定稿：**最小嵌入 N=2**）：列表快照每筆 history 僅 ≤2 點（~500KB 固定，前端漲跌徽章照常）；N=30 方案曾評估（快照 → 1.51MB、每檔多 ~1.1MB）但未採用
  - **D1-b 前端聚合 `api/daily/*.json`**：repo 最瘦；但列表頁多 request、前端邏輯複雜度上升
  - **決策（2026-08-17 確認）：D1-a 最小嵌入（≤2 點）**：單人專案以簡單穩定優先；卡片漲跌（末兩點）與 sparkline 由 ≤2 點歷史渲染，BDD 003 語意不變

**取捨 #3：詳情趨勢圖資料來源（決策點 D2）**
- **D2-a `api/trends/{item_id}.json`**（version_data 每日組裝）：詳情頁 1 request、~2.6KB；1448 檔 × 365 天 git delta 極小（每日只 +26.6B/檔）；**定稿（2026-08-17 確認）**
- **D2-b 前端聚合 daily 檔**：0 個額外靜態檔，但詳情頁需 fetch 全部 daily 檔（N 個 request）才湊出單商品歷史——浪費，不推薦

**取捨 #4：歷史每日價格點檔的保留策略**
- `data/daily/` 與 `api/daily/` 每年 +15MB raw（git delta 後 ~5MB）——**可全保留**（趨勢圖資料源）
- ~~`api/items/` 每日快照~~ — **O4 定稿已移除 `api/items/`**（無需清理 step）；對外歷史由 `api/daily/`（每日價格點，~40KB/天）與 `api/trends/`（逐商品全歷史，~10MB/年）承載，兩者皆可全保留

---

## 5. 決策理由

### 5.1 為什麼選 O4

1. **徹底消除 O(n²) 成長**：對外所有檔案固定大小；歷史以「每日價格點檔序列」線性累積（40KB/天）。前端下載從「1 年後 13.9MB」變「固定 ~500KB（列表）＋ ~2.6KB（單商品趨勢）」
2. **尊重使用者核心訴求**：「每天資料依日期切開」——每日價格點 `data/daily/YYYYMMDD.json` + `api/daily/YYYYMMDD.json` 即每日一檔；`data/items.json` 不再累積每日資料（只留最新狀態，固定大小）
3. **crawler 改動最小化**：`items.json` 仍是 diff 基準（prev state），`store.py` 只需改 save 邏輯與新增 daily 檔寫入；health check（007）語意完全不動
4. **對外契約維持 runtime discovery**（index.json → latest_file），前端列表頁資料載入路徑不變（003/004 共用單例結構保留）

### 5.2 為什麼放棄其他方案

| 方案 | 放棄理由 |
|---|---|
| **O1** | 1 年後前端 13.9MB/次、repo 2.6GB——O(n²) 違反長期維護定位 |
| **O2** | 只解決 40k 行表象，成長問題原封不動 |
| **O3** | 前端零改動很誘人，但 repo 仍 O(n²)（滑動視窗）、data/items.json 照樣累積、趨勢圖被截斷——治標 |
| **O5** | 真相層拆檔的收益（檔案序列可稽核）在本專案無實際消費者；crawler 重構成本最高、repo checkout 最大。**保留為使用者明確要求「連 data 狀態快照都拆」時的替代方案**（§6.3 決策點） |

### 5.3 分階段執行策略

| 階段 | 內容 | 工時 | 風險 |
|---|---|---|---|
| **Phase 0** | `data/items.json` 改 compact 寫入（立即止痛，40k 行 → 1 行） | ~0.5h | 極低 |
| **Phase 1** | O4 拆檔：store.py 改寫 + version_data 重組 + 前端趨勢資料路徑 + 測試/BDD/文件 | ~2d | 中（回歸面廣，但有測試鎖定） |

Phase 0 可先行上線（獨立、無依賴）；Phase 1 完成後 Phase 0 自然合併（compact 已是 O4 的一部分）。

---

## 6. 行動計畫

### 6.1 目標資料組織（O4 定稿 → 契約 v2 分類拆檔）

> **v2 演進（2026-08-17）**：下表 O4（v1）結構中的 `items.json` 單檔與 `api/latest.json` 已**取代**；現行契約如下：

```
data/
  items/{g}.json          # 每分類一檔（g=1/3/4/5/6/7/8/9/12；純 items 陣列、無 meta/category 欄位；每筆 history 僅最近 ≤2 點）
  meta.json               # meta 集中於此（items 檔不再內嵌 meta）
  daily/YYYYMMDD.json     # 每日價格點 {"<item_id>": <price>, ...} ~40KB/天（真相層歷史）
api/                        # 對外層（version_data 組裝；**無 api/latest.json、無 latest_file**）
  items/{g}.json          # 各分類鏡像（= data/items/{g}.json；每分類一檔）
  daily/YYYYMMDD.json     # 每日價格點（鏡像 data/daily）
  trends/{item_id}.json   # 逐商品完整歷史 {"id","history":[["d",p],...]}（詳情圖 1 request）
  index.json              # categories[]（id/name/file/count）、daily_files[]、trends_prefix、crawled_at/計數
```

> 下表為 O4（v1）歷史定稿結構（已非現行契約）：

```
data/
  items.json              # 最新狀態（每筆 history 僅最近 ≤2 點；固定 ~500KB）
  meta.json               # 不變
  daily/YYYYMMDD.json     # 每日價格點 {"<item_id>": <price>, ...} ~40KB/天（真相層歷史）
api/                        # 對外層（version_data 組裝；**不產生 api/items/**）
  latest.json             # 最新快照（items 同 data/items.json；覆寫語意）
  daily/YYYYMMDD.json     # 每日價格點（鏡像 data/daily）
  trends/{item_id}.json   # 逐商品完整歷史 {"id","history":[["d",p],...]}（詳情圖 1 request）
  index.json              # latest_file="api/latest.json"、daily_files[]、trends_prefix、crawled_at/計數
```

### 6.2 任務拆分

| # | 任務 | 檔案 | 依賴 |
|---|------|------|------|
| T1 | Phase 0：store.save compact 寫入 | `crawler/store.py`（`_write_json_atomic` separators） | — |
| T2 | store 拆分：save 只寫最新狀態；新增 `write_daily(date, prices)` | `crawler/store.py` | T1 |
| T3 | main 呼叫 write_daily（daily 檔名 = 台北日期） | `crawler/main.py` | T2 |
| T4 | version_data 重組：**移除 api/items/**；組裝 api/latest.json + api/daily + api/trends/{id} + index（latest_file="api/latest.json"、daily_files/trends_prefix 指標） | `scripts/version_data.py` | T3 |
| T5 | 前端列表：維持兩段式 fetch（index → latest_file = api/latest.json）；卡片漲跌來源（D1 定稿：快照內嵌 ≤2 點 → 讀末兩點即可） | `web/src/composables/useItems.ts`、`types/item.ts` | T4 |
| T6 | 前端詳情：`usePriceHistory` 改 fetch `api/trends/{id}.json` | `web/src/composables/usePriceHistory.ts`、`views/ProductDetailView.vue` | T4 |
| T7 | 測試更新：crawler tests（store/main ~5 檔）、version_data tests、前端 vitest、e2e oracle、smoke-004 | 各 tests/ | T2–T6 |
| T8 | BDD/文件同步：001（daily 檔語意）、002（api 組織）、004（trends 路徑）、README、PROJECT-REPORT | `docs/bdds/*.feature`、`docs/development/*`、`docs/interaction-flows/*`、`README.md` | T4 |
| T9 | workflow：commit 路徑含 `data/daily/ api/daily/ api/trends/`（api/items 已移除 → 無需「清理 90 天前快照」step） | `.github/workflows/crawl.yml`、`.gitignore`、`tests/test_gitignore.py` | T4 |

### 6.3 已確認的決策點（2026-08-17）

| 決策點 | 選項 | 2026-08-17 定稿 |
|---|---|---|
| **D1** 列表歷史資料來源 | a) 快照內嵌最近 N 點（N=30 曾評估 → **最小嵌入 N=2**；前端零改動、快照 ~500KB 固定）／ b) 前端聚合 daily 檔（repo 最瘦） | ✅ **最小嵌入（≤2 點）**：卡片漲跌（末兩點）與 sparkline 以 ≤2 點歷史渲染；快照維持固定大小 |
| **D2** 詳情趨勢圖來源 | a) `api/trends/{id}.json`（1 request，useTrend 載入）／ b) 前端聚合 daily 檔（多 request） | ✅ **`api/trends/{id}.json`**：1 request、~2.6KB/90 天；載入失敗僅趨勢區塊降級、不影響其餘頁面 |
| **D3** data 層是否連狀態快照都拆（O4 vs O5） | O4（items.json 最新狀態單檔）／ O5（data/items/ 每日檔） | ✅ **O4**（crawler 改動最小；data 層不拆狀態快照）→ **2026-08-17 v2 演進：O4＋分類拆檔**（`data/items.json` 單檔已被取代為 `data/items/{g}.json` 每分類一檔；類別由「date 維度」改為「分類維度」拆檔，純 items 陣列、無 meta/category 欄位、meta 移至 data/meta.json；`api/latest.json`／`latest_file` 同步移除，對外改為 `api/items/{g}.json` 鏡像＋`api/index.json` 的 `categories[]`） |

---

## 7. 風險登錄

| 風險 | 可能性 | 影響 | 緩解 |
|------|--------|------|------|
| 前端趨勢圖資料路徑改動造成 004 回歸 | 中 | 高 | 004 BDD + e2e 已鎖定；T6 先改資料層再改 UI，分步驗證 |
| version_data 組裝邏輯重寫出錯（trends 組裝 1448 檔） | 中 | 中 | 測試鎖定（T7）；組裝為純函數可單測 |
| repo 體積仍線性成長（~45MB/年） | 確定 | 低 | 可接受；T9 清理 step 控制 checkout |
| Phase 0 compact 後 git diff 可讀性下降 | 確定 | 低 | 僅真相檔；api 快照本就 compact |
| 若採 O5：crawler 跳日/失敗日基準邏輯出錯 | 中 | 高 | 已有 BDD #12/#21 失敗分類語意，需擴充測試 |

---

## 7. 檔案大小與用途明細（O4 歷史決策推算 → 契約 v2 分類拆檔）

> **v2 演進（2026-08-17）**：下表以 O4（v1）單檔推算（`items.json` ~501KB）；v2 分類拆檔後真相層改為 `data/items/{g}.json` 每分類一檔（各檔即該分類商品集合，總量不變、任一檔更小）、外層為 `api/items/{g}.json` 鏡像；`latest.json` 欄已移除。

### 真相層 data/（crawler 唯一寫入，v1 O4 單檔）

| 檔案 | 用途 | 現在大小 | 成長 |
|---|---|---|---|
| `items.json` | 最新商品狀態（crawler diff 基準、version_data 組裝來源；不再內嵌歷史） | **501 KB**（compact）／714 KB（pretty） | **固定，不再長大** |
| `meta.json` | 爬取中繼（crawled_at/counts/total/status，007 健康檢查） | 423 B | 固定 |
| `daily/YYYYMMDD.json` | 每日價格點 `{id: price}`（歷史真相，依日期切開） | **35 KB/天**（每商品每點 24.6 B） | 365 檔/年 ≈ 12.5 MB |

### 對外層 api/（version_data 組裝，前端消費）

> O4 定稿：**不再產生 `api/items/YYYYMMDD.json`**，下表為現行對外檔。

| 檔案 | 用途 | 現在大小 | 成長 |
|---|---|---|---|
| `daily/YYYYMMDD.json` | 每日價格點對外鏡像（歷史查詢／趨勢聚合備援） | 35 KB/天 | 365 檔/年 ≈ 12.5 MB |
| `trends/{item_id}.json` | 逐商品完整歷史（詳情趨勢圖 1 request） | 0.6 KB（30 天）／1.8 KB（90 天）／7.2 KB（365 天） | 1448 檔全保留 ≈ 10 MB/年 |
| `latest.json` | 最新快照穩定端點（items 同 data/items.json、每筆 history ≤2 點；覆寫語意） | 同最新 items（~501 KB） | 不累積 |
| `index.json` | 目錄入口（latest_file="api/latest.json" + daily_files[] + trends_prefix + 中繼） | ~26 KB | daily_files 清單緩慢成長（1 年後 ~50 KB） |

### 年度總帳

| 項目 | O4 預期 |
|---|---|
| repo raw 成長 | **~45 MB/年**（data/daily ~12.5MB + api/daily ~12.5MB + api/trends ~10MB + items/index 變化量；O4 定稿、api/items 移除後；git delta 後更小） |
| 前端列表下載 | 固定 ~500 KB（1 年後不變；現況將達 13.9 MB） |
| 前端詳情趨勢圖 | 1 request、~2–7 KB |
| 單檔最大 | 501 KB（D1-a 時 1.51 MB）——所有檔案皆有上限 |

---

## 📝 決策後續

- 本文件已存至 `docs/tech-decisions/tech-decision-資料拆檔方案-2026-08-17.md`，應納入版本控制
- **決策完成**：§6.3 三決策點（D1 最小嵌入 / D2 api/trends / D3 O4）已於 2026-08-17 確認；Phase 0（compact 寫入）與 Phase 1（拆檔 + 測試 + BDD/文件同步）依 002 BDD 流程展開中。
- **契約 v2 演進（2026-08-17 定稿）**：D3 由 O4 演進為「O4＋分類拆檔」——`data/items.json` 單檔與 `api/latest.json` 移除，改為 `data/items/{g}.json` / `api/items/{g}.json` 每分類一檔（純 items 陣列、無 meta/category 欄位，meta 集中於 data/meta.json）；`api/index.json` 以 `categories[]` 取代 `latest_file`；前端 useItems 依側欄 lazy 載入分類檔（`api/items/{g}.json?v={crawled_at}`），全站搜尋/詳情 deep link/追蹤用 loadAll 聚合。現行契約以 README「資料/API 組織」與 development/BDD 規格為準。
- 建議 1 個月後回顧：repo 成長率、前端下載量是否符合預期（~45MB/年、固定 500KB）
