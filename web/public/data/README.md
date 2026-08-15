# web/public/data/ — 前端 dev 資料來源（002 §1.7 cache-busting 契約）

| 檔案 | 內容 | 用途 |
|------|------|------|
| `items.v2.json` | **真資料** 1,447 筆（2026-08-15 爬蟲實跑，`../data/items.v2.json` 副本） | dev 資料來源（`__DATA_VERSION__=2` 時 useItems 抓取此檔） |
| `items.v0.json` | **mock** 43 筆（離線測試用，非真資料） | 保留供離線/無真資料環境測試；`__DATA_VERSION__≠0` 時不會被 fetch |

## 更新方式（真資料版本遞增後）

```bash
cp ../data/items.v{n}.json web/public/data/items.v{n}.json
```

版本號 `n` 由 `../data/meta.json` 的 `version` 驅動（vite.config.ts 讀取後以
`__DATA_VERSION__` 注入）。`items.v0.json` 為歷史 mock，勿刪（離線測試參考）。
