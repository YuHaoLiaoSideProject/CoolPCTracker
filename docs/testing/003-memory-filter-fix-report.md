# 003 記憶體篩選修正報告（ram_gb vs capacity_gb）

> ⚠️ 歷史紀錄：本文撰寫於資料改為 api/ + 日期制命名之前，路徑（data/items.v{n}.json、web/public/data/、copyDataPlugin 等）已過時，現行架構見 README「資料/API 組織」。

日期：2026-08-16
狀態：完成（全部測試通過）

## 摘要

端到端修正「記憶體篩選永遠空結果」：
- 根因：`crawler/spec_parser.py::_parse_ram()` 把記憶體容量寫入 `extra["capacity_gb"]`，
  與 SSD/HDD 的儲存容量共用同一 key；前端下拉「記憶體」綁定 `ram_gb` → 資料中 0 筆 → 空結果。
- 修正：parser 改寫 `ram_gb`、既有資料做確定性遷移（capacity_gb → ram_gb，僅記憶體分類）、
  前端語意收斂（記憶體=ram_gb、儲存=capacity_gb）、補 E2E 回歸。

## 改動檔案清單

### 資料層（根因）
- `crawler/spec_parser.py`：`_parse_ram()` 寫入 `extra["ram_gb"]`（原 `capacity_gb`）、
  更新模組 docstring 與 `_DEEP_PARSERS` 註解（`記憶體: # ram_gb/spec/clock_mhz`）。

### parser 測試
- `crawler/tests/test_spec_parser.py`：記憶體斷言 `capacity_gb` → `ram_gb`、
  `TestExtraScope` 記憶體 allowed 集合改 `{ram_gb, spec, clock_mhz}`、
  新增 `test_ram_writes_ram_gb_not_capacity_gb`。

### 資料遷移（確定性、可重跑）
- 新增 `scripts/migrate_ram_gb.py`（冪等，可 `--check`；僅 category==="記憶體" 的
  `capacity_gb` → `ram_gb`，SSD/HDD 的 `capacity_gb`、記憶卡的 `capacity` 字串不動）。
- 已遷移檔案：
  - `data/items.json`（210 筆）
  - `data/items.v2.json`（210 筆）
  - `web/public/data/items.v2.json`（210 筆，dev server 讀取檔）
  - `web/dist/data/items.v2.json`（210 筆，build 產物同步；此目錄 gitignored）
  - `data/items.v1.json`（記憶體 0 筆，no-op，一併涵蓋）

### 前端語意收斂
- `web/src/utils/specFilter.ts`：`capacity_gb.label`「容量」→「儲存容量」（註明僅 SSD/HDD）；
  `ram_gb.label`「記憶體」保留；`FILTERABLE_FIELDS` 已含 `ram_gb`。
- `web/src/types/filters.ts`：`SpecField` 註解分離 `capacity_gb`（儲存容量）／`ram_gb`（記憶體容量）。
- `web/src/types/item.ts`：`capacity_gb` 註解「儲存容量（SSD/HDD）」；`ram_gb`「記憶體容量」。
- `web/src/components/SpecTable.vue`：`SPEC_LABELS.capacity_gb`「容量(GB)」→「儲存容量(GB)」。
- `web/src/composables/usePriceDelta.ts`：記憶體規格 chips 改讀 `spec.ram_gb`（原 `capacity_gb`）；
  SSD/HDD 維持讀 `capacity_gb`。

### 前端測試
- `web/src/utils/__tests__/specFilter.test.ts`：`capacity_gb.label` 斷言改「儲存容量」。
- `web/src/composables/__tests__/useItems.test.ts`：記憶體 fixture `extra.capacity_gb` → `ram_gb`。
- `web/src/composables/__tests__/usePriceDelta.test.ts`：新增記憶體讀 `ram_gb`（防回歸）、
  SSD/HDD 讀 `capacity_gb` 的 chips 測試。

### E2E
- `web/e2e/003-filtering.spec.ts`：新增 4 個回歸測試（搜尋記憶體名稱命中 + 「>1GB」literal 空結果；
  `ram_gb≥16`、`ram_gb≥32` 動態 oracle；`capacity_gb≥500` 僅 SSD/HDD）。
- `web/e2e/helpers/oracle.ts`：未改動（動態讀 `flatSpec(it.spec)[field]`，遷移後自動讀 `ram_gb`）。

## 遷移前後欄位統計

| 欄位 | 遷移前 | 遷移後 |
|------|--------|--------|
| 記憶體 `ram_gb` | 0 | **210** |
| 記憶體 `capacity_gb` | **210** | 0 |
| SSD `capacity_gb` | 77 | 77（不變） |
| HDD `capacity_gb` | 89 | 89（不變） |
| `meta.json` total / counts | 1449 / 記憶體 216、SSD 171、HDD 89 | 不變 |

記憶體 `ram_gb` 值域：8 / 16 / 32 / 48 / 64 / 96 / 128（共 210 筆，216 筆中 6 筆無容量欄位）。

## 測試結果

| 測試層 | 指令 | 結果 |
|--------|------|------|
| Python parser/unit | `.venv/bin/pytest crawler/tests scripts/tests tests -q` | **254 passed** |
| 前端 unit/元件 | `cd web && npx vitest run` | **115 passed（14 files）** |
| 前端 typecheck | `cd web && npx vue-tsc --noEmit` | 通過 |
| E2E | `cd web && npx playwright test` | **14 passed（1 worker）** |

E2E 新增 4 案例（003 記憶體篩選回歸）：
1. 搜尋 16GB/GB/DDR5 命中、「>1GB」literal 空結果
2. `記憶體≥16GB`（ram_gb）結果集合正確且不含 SSD/HDD
3. `記憶體≥32GB`（ram_gb）高門檻動態 oracle
4. `儲存容量≥500GB`（capacity_gb）僅命中 SSD/HDD

## 遺留風險

1. **未重爬驗證 parser**：依任務邊界禁止 live 爬蟲，parser 修正僅以離線 fixture 驗證；
   下次排程爬蟲（crawl.yml）產出的新資料會自然帶入 `ram_gb`，屆時
   `scripts/version_data.py` 會因 items payload 異動而版本號 +1 並覆蓋 `web/public/data/`。
2. **歷史資料已遷移、但 `data/items.v1.json` 為舊快照**（記憶體 0 筆）無影響；若未來回溯
   更舊快照需再跑遷移腳本（已冪等）。
3. **`web/dist/` 為 build 產物（gitignored）**：本次直接同步 `items.v2.json`；下次正式
   `npm run build` 時由 vite `copyDataPlugin` 自動把 `data/items.v{version}.json` 複製進
   dist，兩者來源一致，不需額外動作。
4. **「>1GB」空結果依賴搜尋字面比對語意**：已寫死為預期以防回歸；若未來搜尋引擎改為
   解析比較運算子，此斷言需同步調整。
