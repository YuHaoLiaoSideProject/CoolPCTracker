# web/public/data/ — 前端 dev 資料來源（002 §1.7 cache-busting 契約）

| 檔案 | 內容 | 用途 |
|------|------|------|
| `items.v3.json` | **真資料**（2026-08-16 爬蟲實跑，`../data/items.v3.json` 副本） | dev 資料來源（`__DATA_VERSION__=3` 時 useItems 抓取此檔） |
| `items.v2.json` | 真資料 1,447 筆（2026-08-15 爬蟲實跑，歷史快照） | 保留供比對/回退；`__DATA_VERSION__≠2` 時不會被 fetch |
| `items.v0.json` | **mock** 43 筆（離線測試用，非真資料） | 保留供離線/無真資料環境測試；`__DATA_VERSION__≠0` 時不會被 fetch |

## 更新方式（真資料版本遞增後）

```bash
cp ../data/items.v{n}.json web/public/data/items.v{n}.json
```

版本號 `n` 由 `../data/meta.json` 的 `version` 驅動（vite.config.ts 讀取後以
`__DATA_VERSION__` 注入；E2E oracle 亦讀同一 meta.json 動態解析檔名）。
`items.v0.json` 為歷史 mock，勿刪（離線測試參考）。

⚠️ 爬蟲工作流（crawl.yml）只 commit `data/`，不會自動同步本目錄；版本遞增後
需手動執行上方 `cp`（或於 workflow 補同步步驟），否則 dev/E2E 會因 fetch
`items.v{n}.json` 404 而失敗。
