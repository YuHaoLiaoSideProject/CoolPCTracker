# 前端真資料驗收報告（frontend real-data acceptance）

> ⚠️ 歷史紀錄：本文撰寫於資料改為 api/ + 日期制命名之前，路徑（data/items.v{n}.json、meta.json version、__DATA_VERSION__、copyDataPlugin、web/public/data/ 等）已過時，現行架構見 README「資料/API 組織」。

- **日期**：2026-08-16
- **範圍**：002 §1.7 版本化命名契約驗證 ＋ 003/004 前端以真實爬蟲資料（1,447 筆）驗收
- **產物**：repo 根 `data/` 版本化檔（items.v2.json + meta.json）、前端相容修正、真資料 smoke（30 項）
- **未動**：crawler/、scripts/version_data.py（僅執行）；未 commit / push

## 1. 資料現況調查（與任務前提的差異）

| 項目 | 任務前提 | 實際 |
|------|---------|------|
| `data/items.json` | 「parser 重寫後實跑 1,447 筆」 | **舊 parser 的 24 筆壞資料**（多數空名稱、無價格；`version=0`，2026-08-15 15:40 由 ba39066 提交，早於 parser 重寫 commit 6fd564c） |
| `data/meta.json` | 正式 meta | 同批壞資料（total=24、counts 每分類 3 筆） |
| `data/items.v1.json` | 版本化快照 | 24 筆壞資料的快照（3,827 bytes） |
| 真資料所在 | — | 未 commit：parser-rewrite 報告（docs/spike/parser-rewrite-2026-08-16.md）記載實跑 `/tmp/coolpc-live-check` 已刪除；**可離線重現**：`scripts/tests/fixtures/mobile/G*.html`（2026-08-15 真實頁面快照，spike #2 存檔，9 頁齊全） |

**結論**：ba39066 提交的資料是 parser 重寫前的錯誤輸出，與 parser-rewrite 報告的「實跑 1,449 / 收錄 1,447」矛盾；真資料需由真實 fixtures 以重寫後 parser 離線重現（報告已驗證 fixtures 解析結果與實跑零差異）。

## 2. 契約對齊方式（002 §1.7）

1. **重現真資料**：以 `crawler.parser.Parser`（重寫後）解析 9 個真實 fixtures → `parse_spec` + `make_item_id` → `Store.diff/apply/save`（與 `crawler.main.run_crawler` 同管道、同 store 去重語意；暫存腳本於 /tmp，未進 repo）。產出 `data/items.json`（items 陣列 **1,447 筆**）＋ `data/meta.json`（status=ok、changed=1447、counts/total 為去重前 per-category 數，與 crawler 語意一致）。
2. **執行 `scripts/version_data.py`**（未修改）：items.v1.json（舊快照）與新 items.json 比對有異動 → 寫 `data/items.v2.json`（`{crawled_at, items}`，1,447 筆）＋ `meta.version=1→2`。版本鏈 v1（舊）→ v2（真資料）保留。
3. **vite.config copyDataPlugin**：無需修改——`../data/meta.json` 讀到 version=2 → `__DATA_VERSION__=2` 注入 → build 收尾複製 `items.v2.json` + `meta.json` 至 `dist/data/`（原本因「先前 items.v0.json 不存在」而略過複製的問題隨真資料就位自動消失）。
4. **dev 資料來源**：`cp data/items.v2.json web/public/data/items.v2.json`；dev 模式 `__DATA_VERSION__=2` 即抓取真資料。mock `items.v0.json`（43 筆）保留 + `web/public/data/README.md` 標記為離線測試用。

## 3. 真資料驗收結果（`vite preview` + playwright，期望值由 data/ 計算，不硬編碼）

**首頁 9 分類計數**（側欄逐項 = items 陣列計數，合計 1,447）：

| 分類 | 計數 | | 分類 | 計數 |
|------|-----:|---|---|-----:|
| 套裝/準系統 | 157 | | SSD | 171 |
| 劈發價組合區 | 86 | | HDD | 89 |
| CPU | 47 | | 記憶卡 | 54 |
| 主機板 | 372 | | 顯示卡 | 255 |
| 記憶體 | 216 | | **全部** | **1,447** |

- **點分類**：CPU → URL `?category=CPU` → 47 卡片；回全部 → 1,447
- **搜尋「RTX 5060」**：68 筆（含規格 chip 命中——`RTX5060` 無空格商品經 spec 平鋪後 `chip:"RTX 5060"` 命中，符合 search.ts「name + spec 值子字串」語意）；**VRAM≥12G 篩選**：88 筆
- **詳情頁**（真 GPU deep link，技嘉 RTX3060 WINDFORCE OC 12G / `756137f3d21174cb`）：標題＝真名稱、目前價 NT$、單筆歷史 → 「首日追蹤，尚無漲跌比較」、歷史最低＝目前價、規格表（品牌/晶片/VRAM(GB)）、ECharts canvas、目標價 markLine（套用/修改/abc 錯誤/清除）全流程
- **邊界**：無效 id → 找不到此商品＋返回列表；console/pageerror 無錯誤
- **效能**：首屏 1,447 卡片渲染 1.3s（無虛擬化，見殘留風險 4）

**smoke 結果：30/30 PASS**（`python3 web/scripts/smoke-004.py`，期望值動態讀取 `data/meta.json` version + `items.v{version}.json`）

## 4. 發現與修正清單

| # | 發現 | 修正 | 檔案 |
|---|------|------|------|
| 1 | **真資料 `spec` 為 `{brand, model, extra:{...}}` 巢狀**（spec_parser 產出），前端契約 `ItemSpec` 為平鋪欄位（`spec.vram_gb` 等）→ VRAM≥12G 篩選 0 命中、規格表會把 extra 整包當一列、卡片 chips 全空 | `parseItemsFile` 新增 `normalizeSpec`：extra 平鋪至頂層、null/undefined/空字串剔除、移除巢狀 `extra` 鍵（保留無 extra 舊形狀相容）；+1 單元測試（含 extra 含 `spec` 鍵衝突、null 最少欄位、篩選命中） | `web/src/composables/useItems.ts`、`__tests__/useItems.test.ts` |
| 2 | 記憶卡真資料產出 `capacity`（字串 "128GB"），前端 chips 只讀 `capacity_gb`（數字）→ 卡片無容量 chip | `specChipTexts` 記憶卡分支補 `spec.capacity` | `web/src/composables/usePriceDelta.ts` |
| 3 | smoke-004.py 錨定 mock 專用商品 ID（gone/空歷史/20 點/三日同低），真資料不存在 → 需資料驅動 | 重寫：期望值（總數/分類/搜尋/篩選/詳情商品）全部由 `data/items.v{version}.json` 計算；邊界改為「單筆歷史 首日追蹤」「無效 id」；修正 not-found 頁返回連結選擇器（`.back-link`）；BASE 改 localhost（preview 預設綁 ::1） | `web/scripts/smoke-004.py` |
| 4 | 舊壞資料 24 筆（空名稱無價）若保留會以 gone 混入真資料 | 全新開始重現（store 空基底），不保留壞資料 | `data/items.json` |
| 5 | `data/items.json` 權限 664→600（store 以 tempfile 寫入） | chmod 回 664（git 僅記 executable bit，無 diff） | `data/` |
| 6 | 任務搜尋範例「RTX 4070」於 2026-08-15 快照**不存在**（已是 RTX 50 世代：5060/5060Ti/5070/5080…） | 改用快照內存在之「RTX 5060」（68 筆）＋「VRAM≥12G」（88 筆）驗證 | — |

## 5. 驗證結果

| 項目 | 結果 |
|------|------|
| `cd web && npx vitest run` | **113 passed**（112 既有 + 1 新增平鋪測試；14 files） |
| `npm run build`（vue-tsc + vite build） | **零錯誤**；copyDataPlugin 複製 `items.v2.json` + `meta.json` → dist/data/（chunk 715KB 警告為既有 echarts 整包，非錯誤） |
| `vite preview` + playwright smoke | **30/30 PASS**（真資料 v2） |
| dev 模式 | `__DATA_VERSION__=2`，`/data/items.v2.json` 200（真資料） |

## 6. 殘留風險

1. **1,447 vs 1,449**：meta.counts/total 為去重前（CPU 48、主機板 373、total 1449）；items 陣列與前端側欄為去重後（CPU 47、主機板 372、合計 1,447）——store 既有「同分類同名稱（不同子分類）去重」語意，與 parser-rewrite 報告註記一致；前端顯示以 items 陣列為準（正確）。
2. **快照時點**：真資料為 2026-08-15 快照（crawled_at 沿用），首頁無過期橫幅（<7 天）；排程上線後版本會推進，smoke 期望值動態讀取版本號，不需改碼，但搜尋/篩選期望筆數會隨商品增減而變（smoke 亦動態計算，安全）。
3. **規格欄位缺口**（crawler 側，非本次範圍）：GPU 未解析 `tdp_w/wattage_w` → 「瓦數≥750W」篩選對真資料 0 命中（前端 specFilter 支援該欄位但 crawler 不產出）；記憶卡 `capacity`（字串）與篩選欄位 `capacity_gb`（數字）語意不一致 → 容量篩選不涵蓋記憶卡。chip 大小寫不一致（`RTX 5060Ti` vs `RTX 5060TI`）為 spec_parser 正規化缺口。
4. **列表渲染效能**：1,447 卡片一次渲染 1.3s（本機），無分頁/虛擬化；資料量再成長或低階行動裝置可能卡頓（ECharts 單商品圖表不受影響——每卡僅 SVG sparkline、詳情圖 1 序列）。
5. **dist/data 含 mock**：`web/public/data/items.v0.json` 隨 public/ 原樣進 dist（~25KB、不會被 fetch）；若未來本地無 meta.json（version 歸 0）時 build 會把 mock 當真資料複製——README 已標記，屬低風險 footgun。
6. **版本鏈 v1 為舊壞資料快照**：items.v1.json 保留在 repo（歷史事實），不含真資料；正式環境僅消費 v2 以後。

## 7. 變更清單（未 commit）

```
M data/items.json                舊 24 筆 → 真資料 1,447 筆（items 陣列）
M data/meta.json                 version 1→2、counts/total 真值
A data/items.v2.json             版本化快照（version_data.py 產出，{crawled_at, items}）
M web/src/composables/useItems.ts        spec.extra 平鋪（真資料形狀相容）
M web/src/composables/usePriceDelta.ts   記憶卡 capacity chip
M web/src/composables/__tests__/useItems.test.ts  +1 測試（113 total）
M web/scripts/smoke-004.py       真資料驅動重寫（30 項）
A web/public/data/items.v2.json  dev 真資料來源
A web/public/data/README.md      mock/真資料標記與更新方式
```
