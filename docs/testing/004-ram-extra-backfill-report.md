# 004 記憶體 spec.extra 回填報告（Biwin / Origin code）

> ⚠️ 歷史紀錄：本文撰寫於資料改為 api/ + 日期制命名之前，路徑（data/items.v{n}.json、web/public/data/ 等）已過時，現行架構見 README「資料/API 組織」。

日期：2026-08-16
狀態：完成（全部測試通過）

## 摘要

修復 6 筆記憶體 `spec.extra` 為空（brand/model/ram_gb 缺失）的資料缺口：
- 根因：`crawler/spec_parser.py` 的 `_RAM_BRANDS` 缺「Biwin / 佰維」「Origin code」中英別名，
  品牌剝離失敗 → `_parse_ram` 回傳最少欄位 Spec（brand=None, model=None, extra={}）。
- 修正：`_RAM_BRANDS` 補 `"Biwin"`, `"佰維"`, `"Origin code"`, `"Origin"`。
- 回填：以修正後 parser 離線重新解析這 6 筆（不跑 live 爬蟲），補回 brand/model/ram_gb/spec/clock_mhz。

## 6 筆名稱（category=記憶體 / subcategory=桌上型記憶體 DDR5 雙通道）

1. `Biwin 佰維 Black Opal HX100 48GB(雙通24GBx2) DDR5-6000 CL28 黑` → ram_gb=48
2. `Biwin 佰維 Black Opal DW100 RGB 32GB(雙通16GBx2) DDR5-6000 CL28 黑` → ram_gb=32
3. `Biwin 佰維 Black Opal DW100 RGB 48GB(雙通24GBx2) DDR5-6000 CL28 黑` → ram_gb=48
4. `Biwin 佰維 Black Opal DW100 RGB 48GB(雙通24GBx2) DDR5-6000 CL28 白` → ram_gb=48
5. `Origin code Vortex RGB 32GB(雙通16GBx2) DDR5-6200(CL26)銀(獨立風扇)` → ram_gb=32
6. `Origin code Vortex RGB 48GB(雙通24GBx2) DDR5-6000(CL26)銀(獨立風扇)` → ram_gb=48

雙語前綴「Biwin 佰維」沿用既有慣例（如 SSD「MSI 微星 M470PRO」→ brand=MSI、model 保留
「微星」）：剝離英文品牌 token，中文別名保留於 model。

## 改動檔案

- `crawler/spec_parser.py`：`_RAM_BRANDS` 補 `"Biwin"`, `"佰維"`, `"Origin code"`, `"Origin"`。
- `crawler/tests/test_spec_parser.py`：新增 `test_biwin_origin_code_brand_parse`
  （6 例參數化，斷言 brand/model/ram_gb/spec/clock_mhz、且無 capacity_gb）。
- `scripts/backfill_ram_extra.py`：一次性回填腳本（冪等、可 `--check`、可重跑；
  僅 category==="記憶體" 且 re-parse 後與既有 spec 不同才寫入）。
- 已回填檔案：`data/items.json`、`data/items.v2.json`、`web/public/data/items.v2.json`
  （web/dist/data/items.v2.json 為 build 產物同步，gitignored）。

## 回填後統計（不變量）

- 記憶體 `ram_gb`：210 → **216**；記憶體空 `spec.extra`：6 → **0**。
- `meta.json` total/counts 不變（total=1449、記憶體=216、SSD=171、HDD=89）。
- SSD `capacity_gb`=77、HDD `capacity_gb`=89 不受影響。
- `spec.extra` 形狀維持 `{brand, model, extra:{ram_gb, spec, clock_mhz}}`（ram_gb 為數字），
  與 `useItems.normalizeSpec` 平鋪契約相容。

## 驗證

- `pytest crawler/tests scripts/tests tests -q`：260 passed。
- `cd web && npx vitest run`：115 passed。
- `cd web && npx playwright test`：14 passed。
- `cd web && npm run build`：vue-tsc + vite build 通過（chunk >500kB 警告不處理）。
