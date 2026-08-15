# Parser 重寫報告：對齊真實 m-list.php 結構（issue #11，P0）

- **範圍**：`crawler/parser.py` 及其測試（`crawler/tests/test_parser.py`）；未動 fetcher/store/main/categories 簽名；未 commit/push
- **方法**：TDD 紅→綠→重構；以真實頁面 fixtures（`scripts/tests/fixtures/mobile/G{1,3,4,5,6,7,8,9,12}.html`，2026-08-15 spike #2 抓取存檔）為解析基準
- **驗收基準**：9 分類合計 ≈ 1,449（spike 報告統計）

## 1. 問題與根因

- 真實 m-list.php：`<span class=Q>` 內**每個子分類一個 table**（thead/tr/th = 子分類標題，無 `</th>` 收尾）；tbody/tr/td = 商品列，**td 內名稱與價格同格**（`名稱, $價格[↗|↘$異動價] <i>標記</i>`）；class=y（↪ 限量/加贈通知）、class=z（❤ 專業性產品說明）、disabled 皆為非商品列。
- 舊 parser 以 `tree.css_first("table")` 只取**第一個 table**（本頁為 logo 表頭）→ 實測每分類僅 3 筆錯誤項目、0 子分類（G=9 因子分類為空被過濾成 0 筆）；9 分類合計 24 筆（應 1,449）。
- 舊 crawler fixtures（`crawler/tests/fixtures/*.html`）為單 table、th=子分類、td 名稱/價格分格的**設計期結構**，與真實頁面不符 → 舊測試全綠但無法解析真實頁面。

## 2. 修改摘要

### `crawler/parser.py`（重寫解析主體，`parse_page(html, category) -> ParseResult` 介面不變）

- **真實結構優先**：`span.Q` 存在 → `_parse_span_q`——逐 table 取 th 為子分類、逐 td 商品列；`_product_cell_text` 過濾 disabled（tr/td class、td disabled attr）、class=y/z 通知列、❤/↪ 字首、空 cell。
- **td 名稱＋價格分離**：`_PRICE_SEGMENT_RE = ,\s*\$(\d[\d,]*)(?:[↗↘]\$(\d[\d,]*))?`——名稱 = 價格段前文字；價格 = 列表價 `, $N`（與 spike `extract_price_info` 一致；`↘$M` 為異動價，不影響價格欄）。
- **標記解析**：自**完整 cell** 偵測 Hot！/任搭↓N/↘/尾盤（`<i>Hot！</i>`、名稱內 `*尾盤`、價格段後 `任搭↓N`、價格段 `↘` 皆涵蓋）；標記文字自名稱剝離，不污染 ID 正規化。
- **G=9 子分類過濾**：僅保留子分類含 `subcategory_keyword`（"記憶卡"）的商品，邏輯不變。
- **舊單 table 結構保留為 fallback**（`_parse_legacy`，原邏輯原封不動）：既有 crawler fixtures 與 test_main 自訂頁面（`make_page`）走此路徑；真實頁面改版（無 span.Q）時降級解析避免全數漏品。
- 既有私有方法 `_parse_flags`/`_parse_price`/`_parse_cell`/`_parse_price_from_cells`/`_is_disabled_row` 全部保留（測試面不破壞）。

### `crawler/tests/test_parser.py`（新增 30 測試）

- `TestRealMobileStructure`：span.Q 多 table 全數擷取（G=4：10 子分類 / 48 筆）、td 名稱＋價格同格分離、特殊字元（↑）保留、`<i>Hot！</i>` 剝離、`$16150↘$15900` → price=16150 + price_drop 旗標。
- `TestRealMobileNoticeAndDisabledRows`：G=1 class=y/z 通知列過濾（157 筆，無 ❤/↪ 名稱）。
- `TestRealMobileG9Filter`：G=9 僅保留 4 段含「記憶卡」子分類（54 筆）。
- `TestRealMobileFlags`：G=12 任搭↓N（價格段後）、尾盤（名稱內）、↘（價格段）、Hot！四種標記真實案例。
- `TestRealMobileCategoryCounts`：9 分類逐項 = spike 統計（157/86/48/373/216/171/89/54/255）、合計 = 1,449。
- `TestCategoryFixtures.test_each_real_category_fixture_parses_without_exception`：9 真實頁面全數可解析。

### 既有 fixtures 處理（REFACTOR 註明）

- **未刪改** `crawler/tests/fixtures/*.html`：與真實結構矛盾（單 table 設計期樣式），但因 parser 保留 legacy fallback，它們轉為「fallback 路徑的相容性回歸測試」而非主解析基準；改寫它們會迫使 `crawler/tests/test_main.py` 的 `make_page`/`FIXTURE_COUNTS` 一併調整，超出本 issue 範圍且徒增風險。
- **主解析基準改為真實 fixtures**：`scripts/tests/fixtures/mobile/G*.html`（spike 存檔，2026-08-15 快照）──新增測試全部釘選此組；edge case 覆蓋不減反增（原有 38 個 parser 測試全數保留且轉為 legacy 路徑回歸）。

## 3. 測試結果（RED → GREEN）

| 階段 | 結果 |
|------|------|
| RED（新測試 vs 舊 parser） | **30 failed / 38 passed**——證明 bug：真實頁面每分類 3 筆、G=9 0 筆 |
| GREEN（重寫後） | `crawler/tests/test_parser.py`：**68 passed**（38 舊 + 30 新） |
| 全量回歸 | `.venv/bin/python -m pytest crawler/tests scripts/tests tests -v`：**252 passed**（既有 222 全數保持綠，新增 30） |

## 4. 實跑驗證（真實網路）

```
.venv/bin/python -m crawler.main --data-dir /tmp/coolpc-live-check
```

| 分類 | spike 統計 | 本版實跑 | 差異 |
|------|-----------:|--------:|------|
| 套裝/準系統 | 157 | 157 | 0 |
| 劈發價組合區 | 86 | 86 | 0 |
| CPU | 48 | 48 | 0 |
| 主機板 | 373 | 373 | 0 |
| 記憶體 | 216 | 216 | 0 |
| SSD | 171 | 171 | 0 |
| HDD | 89 | 89 | 0 |
| 記憶卡 | 54 | 54 | 0 |
| 顯示卡 | 255 | 255 | 0 |
| **合計** | **1,449** | **1,449** | **0** |

- meta：`status=ok`、`failed_categories=[]`、`changed=1447`。
- **items.json 收錄 1,447 筆**（< 1,449）：CPU 48→47、主機板 373→372 各 1 筆同分類**同名稱**（不同子分類）商品，經 `make_item_id(category, name)` 去重——與 spike 報告註記「47<48、372<373，差集仍為 0」完全一致；此為 store 既有去重語意，非 parser 漏品。

## 5. 結論（對照 spike）

- ✅ **驗收成立**：parser 重寫後，9 分類合計 1,449 筆與 spike 統計逐分類零差異（fixtures 離線與真實抓取雙重驗證）。
- ✅ 真實結構（span.Q 多 table、td 名稱＋價格同格、y/z 通知列）已完全覆蓋；1,449 筆中 4 種標記（Hot！/任搭↓N/↘/尾盤）均有真實案例入測。
- ✅ 既有 222 測試未破壞；edge case 覆蓋不減。

## 6. 殘留風險

1. **既有 crawler fixtures 仍為設計期結構**（legacy fallback 測試）：若日後移除 fallback，需一併改寫 `crawler/tests/fixtures/*.html` 與 `test_main.py::make_page`（超出本 issue 範圍）。
2. **fixture 釘選時點**：真實 fixtures 為 2026-08-15 快照，商品增減後 `REAL_COUNTS`/1,449 斷言需隨之更新（與 spike `test_mobile_1449_claim` 同原則）；建議排程上線後以「實跑總數 vs 前次基準」而非固定 1,449 做健康檢查（main.py 驟降保護已內建）。
3. **↘ 價格語意**：`$A↘$B` 取列表價 A（與 spike 一致）；若業務需要「目前售價 B」，需另開議題調整 RawItem 契約（價格欄語意會影響 store 歷史/驟降比較）。
4. **桌面版「酷幣」促銷**（`↓酷幣N↓`）仍未建模（spike §2.4 次要發現，非本 issue 範圍）。
5. **HTML 改版防禦**：無 span.Q 時自動降級 legacy 路徑，但 legacy 路徑對真實頁面無效——改版後需以驟降保護/人工檢視觸發新一輪對齊。
