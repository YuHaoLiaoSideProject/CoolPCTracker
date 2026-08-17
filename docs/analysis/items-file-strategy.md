# api/items/ 日期制快照分析：後綴規則驗證 + 單檔策略評估

> ⚠️ **已取代**：本分析已被 `docs/tech-decisions/tech-decision-資料拆檔方案-2026-08-17.md`（方案 O4）取代，
> **`api/items/` 日期快照已移除**（O4 定稿：D1 = 最小嵌入（data/items.json 每筆 history 僅 ≤2 點）、D2 = 詳情趨勢圖走 api/trends/{id}.json；
> 對外改為 `api/latest.json` + `api/daily/YYYYMMDD.json` + `api/trends/{item_id}.json` + `api/index.json`（latest_file/daily_files/trends_prefix），repo 年度成長約 ~45MB；**2026-08-17 契約 v2 再演進**：`data/items.json`/`api/latest.json`/`latest_file` 移除，改為 `data/items/{g}.json`/`api/items/{g}.json` 每分類一檔＋`api/index.json` 的 `categories[]`）。
> 本文保留作為決策歷程參考，契約以資料拆檔決策文件（含 v2 演進註記）與現行 development/BDD 規格、README「資料/API 組織」為準。

> 日期：2026-08-17 ・ 性質：只讀分析（未修改任何程式碼/測試/設定檔）
> 範圍：`scripts/version_data.py`、`crawler/main.py`、`crawler/store.py`、
> `.github/workflows/crawl.yml`、`web/src/composables/useItems.ts`、
> `web/vite.config.ts`、測試（`scripts/tests/test_version_data.py`、
> `tests/test_crawl_workflow.py`、`tests/test_gitignore.py`、`web/e2e/helpers/oracle.ts`）、
> `docs/bdds/002-*.feature`、`docs/development/002-*.md`、`README.md`。

---

## 0. 摘要（TL;DR）

- **假設成立**：`api/items/YYYYMMDD[_n].json` 由 `scripts/version_data.py` 產生；
  「目標日期檔已存在 → 以 `_1`、`_2` 後綴遞增新檔」的規則**確實存在**且已被測試鎖定
  （`scripts/version_data.py:121-133` `_next_filename`；測試 `scripts/tests/test_version_data.py` `TestDateSuffix`）。
  但**觸發條件**不是「同日重跑」本身，而是「同日重跑後 `items` payload 與最新快照**有異動**」；
  同日重跑若資料完全相同 → `changed=false` → 不寫任何檔。
- **repo 內實際觀察到的 4 個檔（兩組同日期雙檔）並非 cron/手動補爬造成的**，
  而是「人工改 `data/items.json` 後重跑 version_data（api 重建）」的產物：
  每組雙檔的 `crawled_at` 完全相同（`2026-08-15T15:40:15.770082`、
  `2026-08-16T06:20:49.650053`），且其中 `20260815.json` 只有 16 筆「垃圾資料」
  （商品名是頁面 UI 字串，如「輸入email才可建立清單」）。
- **結論：單檔制（每天保留一份、同日期覆寫）對現有全部消費者都足夠**，
  且會讓 `api/index.json` 的 `files[]` 不再累積壞快照。建議方向見 §4。

---

## 1. data/ 與 api/items/ 的關係（同源？何時產生？）

### 1.1 資料真相 vs 衍生 API 面

兩者**同源但分工不同**，是「AirTicketsPrice 模式」：

```
crawler/main.py ──寫──▶ data/items.json + data/meta.json   （唯一真相，git 版控）
                             │
scripts/version_data.py ──讀 data/ 比對 api/items/ 最新快照──▶
    ├─ 有異動：寫 api/items/{YYYYMMDD[_n]}.json（= {crawled_at, items}）
    │          寫 api/latest.json（穩定端點，同內容）
    │          重建 api/index.json（files[] + latest_file + merged meta）
    └─ 無異動：不動任何檔案（workflow 跳過 commit）
```

- **`crawler/store.py` 只寫 `data/`**：`store.py:72-73`（`_items_path` / `_meta_path`）、
  `store.py:209-216`（`save()` 原子寫 `items.json` + `meta.json`）。模組 docstring
  （`store.py:2-5`）明示「對外 API 成品（api/index.json + api/items/）由
  scripts/version_data.py 依本目錄資料重建，本模組不寫 api/」。
- **`scripts/version_data.py` 是 `api/` 唯一寫入者**：`version_data.py:194-210`。
  `api/items/*.json` 的內容 = 當時 `data/items.json` 的 `items` payload + `crawled_at`，
  所以兩者是**同一爬蟲 run 的同一份資料**，只是 api/ 是「該時間點的靜態快照」。
- **何時產生**：每次 CI run 中、crawler 成功後緊接著執行
  （`.github/workflows/crawl.yml:55` `python scripts/version_data.py`），與 `data/`
  一起 commit（`crawl.yml:75` `git add data/ api/`）；也可手動在本機跑。

### 1.2 PROJECT-REPORT.md 已過時

`PROJECT-REPORT.md` 記載「`data/items.json` + 版本化快照 `items.v{n}.json`」是**舊方案**。
git 歷史顯示已改造為日期制命名：

- `43b083c` 建立 `api/`（v1/v2/v3 命名）
- `2b23519` 「switch data snapshots to date-based filenames (YYYYMMDD[_n])」——
  把 `v1.json→20260815.json`、`v2.json→20260815_1.json`、`v3.json→20260816.json`（R100 改名）
- `8319a76` cleanup 死腳本與過時資料路徑引用
- `aefb3c8` 文件同步 + runtime discovery
- `f474e92` 「api 重建」新增 `20260816_1.json`

以實際程式碼為準：**現行資料組織 = `data/`（真相）+ `api/`（衍生、日期制）**，
與 README.md:67-97 一致。

---

## 2. 任務一：假設驗證「同日已存在 → `_1`、`_2` 後綴」

### 2.1 產生檔案的邏輯位置

`scripts/version_data.py`：

- `_next_filename()`（`version_data.py:121-133`）— **後綴規則唯一實作點**
- `main()` 的異動判定與檔名決定（`version_data.py:194-210`）
- 檔名日期來源 `_taipei_date()`（`version_data.py:59-67`）— `meta.crawled_at` 轉台北日期

### 2.2 關鍵程式碼（節錄）

```python
# version_data.py:121-133
def _next_filename(api_dir: Path, date_str: str) -> str:
    """依 api/items/ 既有同日期檔決定下一檔名：無 → {date}.json；有 → {date}_N.json。"""
    items_dir = api_dir / "items"
    suffixes: set[int] = set()
    if items_dir.is_dir():
        for p in items_dir.glob(f"{date_str}*.json"):
            key = _file_key(p.name)
            if key is not None and key[0] == int(date_str):
                suffixes.add(key[1])
    suffix = 0
    while suffix in suffixes:
        suffix += 1
    return f"{date_str}.json" if suffix == 0 else f"{date_str}_{suffix}.json"
```

```python
# version_data.py:194-210（main 流程）
paths = _snapshot_paths(api_dir)          # 依 (日期, 後綴) 升冪；baseline = 最大者
changed = False
if not paths:
    changed = True                        # 首次執行：無基準 → 視為異動
else:
    baseline = json.loads(paths[-1].read_text(encoding="utf-8"))
    changed = canonical(items["items"]) != canonical(baseline["items"])

if changed:
    date_str = _taipei_date(meta["crawled_at"])
    filename = _next_filename(api_dir, date_str)
    ...寫 api/items/{filename} + api/latest.json + 重建 api/index.json
```

### 2.3 假設驗證結果

**成立（有條件）**。逐點拆解：

| 面向 | 結論 | 證據 |
|---|---|---|
| 後綴規則存在 | ✅ 同台北日期已有檔 → `_1` → `_2`…，取**最小未使用**整數後綴 | `version_data.py:125-133` |
| 遞增條件 | 只有「本次 `items` payload ≠ 最新快照」時才會寫檔並遞增；資料相同 → `changed=false` → 不寫任何檔 | `version_data.py:199-200` |
| 檔名日期 | 不是爬蟲的 `--date`，而是 `meta.crawled_at`（爬蟲實際執行時間）轉 **Asia/Taipei（UTC+8）** 日期 | `version_data.py:59-67`、`crawler/main.py:134`（`crawled_at=_utc_now()`） |
| 誰觸發 | cron `0 6 * * *` UTC 與 `workflow_dispatch` 共用同一管線（`crawl.yml:9-11`），兩者都會跑到 version_data；後綴與觸發類型無關，只與「同台北日已有一檔＋資料有異動」有關 | `crawl.yml:9-11,55` |
| 失敗重跑 | 健康檢查擋下（exit 1）→ **workflow 在 version_data 之前就失敗**，`api/` 完全不會被寫 → 失敗不會製造 `_N` | `crawl.yml` crawl job step 順序；`crawler/main.py:118`（failed 只寫 meta） |

### 2.4 後綴什麼時候實際出現（情境推演）

- **cron（06:00 UTC = 14:00 台北）通常是該台北日的第一次寫檔** → `{date}.json`。
- **同日 workflow_dispatch 重跑**：crawler 冪等（同日同價不 append，
  `crawler/store.py` `_append_daily_point` / `_is_same_day_same_price`，BDD #21）
  → 資料**沒變** → `changed=false` → **不會**產生 `_1`。
  只有重跑時價格/狀態/flags/spec **真的異動**（例如早晚各跑一次且中間漲價），
  `data/items.json` 出現同日新點 → 比對最新快照有異動 → `{date}_1.json`。
- **`--date` 補爬**：`--date` 只影響 history 點的日期（`crawler/main.py:55,64`），
  `crawled_at` 仍是實際執行時間 → 補爬產出的快照檔名是**執行當天**（台北日），
  若當天已有一檔且資料有異動 → `_N`。
- **人工資料手術＋重跑 version_data（本次觀察到的實際成因）**：
  兩組雙檔的 `crawled_at` 各自完全相同，且 `20260815.json` 是 16 筆垃圾快照 →
  都是「改 `data/items.json` 後重跑 version_data / api 重建」的產物
  （`2b23519` 改名前的 v1/v2 同源；`f474e92`「api 重建」新增 `20260816_1.json`）。
  後綴機制在此正確避免了覆寫既有快照，但也讓壞快照永久留在 `index.files[]` 與 git 歷史。

### 2.5 後綴規則的兩個小細節

1. `_file_key`（`version_data.py:70-85`）只認 `YYYYMMDD.json` / `YYYYMMDD_N.json`，
   其他檔名（如舊 `v1.json`）會被忽略不參與排序與後綴計算。
2. 後綴取「最小未使用整數」：若同時存在 `{date}.json` 與 `{date}_2.json`
   （`_1` 被刪），下一次是 `_1`（`while suffix in suffixes` 語意）。

---

## 3. 任務二：評估「每天只保留一份檔案是否足夠」

### 3.1 消費者盤點（誰讀 api/）

| 消費者 | 讀取方式 | 對多檔的依賴 | 單檔制影響 |
|---|---|---|---|
| **Web 前端**（`web/src/composables/useItems.ts`） | 兩段式：`fetch(BASE_URL+"api/index.json")` → `latest_file` → 快照檔（`useItems.ts:22,38-48`）；**只讀 `latest_file`，從不讀 `files[]`** | 無 | 無影響；`latest_file` 指向單一 `{date}.json` 照常運作 |
| **api/latest.json**（穩定端點） | 每次異動即整檔覆寫 | 無（本就是覆寫語意） | 無影響；「覆寫」模式已有先例 |
| **版本化 script**（`version_data.py`） | baseline = 依 (date, suffix) 升冪取最大快照 | 有（`_snapshot_paths` / `_next_filename`） | 需改為「同日覆寫」邏輯 |
| **測試：`scripts/tests/test_version_data.py`** | 直接斷言 `_1`/`_2` 後綴與 `files[]` 順序 | 有（`TestDateSuffix` 3 個 + `TestIndexHistory` 1 個 + `TestNoChange` 2 個） | 需同步改約 6 個測試 |
| **測試：`tests/test_crawl_workflow.py`** | 只斷言 workflow 結構（version_data 被呼叫、`git add data/ api/`、if changed） | 無 | 無影響 |
| **測試：`tests/test_gitignore.py`** | 斷言 `api/items/20260815_1.json` 不被忽略（範例檔名） | 弱 | 範例檔名可保留或清理；`.gitignore` 本身用 `api/items/*.json` 泛規則，不影響 |
| **E2E oracle**（`web/e2e/helpers/oracle.ts`、`web/scripts/smoke-004.py`） | 讀 `api/index.json` 的 `latest_file` 動態解析（oracle.ts:30-45） | 無 | 無影響（runtime discovery 與命名解耦） |
| **前端單元測試**（`useItems.test.ts`） | mock 檔名寫死 `api/items/20260816.json` | 無（純 mock） | 無影響 |
| **CI 排程**（`crawl.yml`） | `steps.version.outputs.filename` 只用於 commit message | 弱 | 同日重複 commit 時 message 檔名相同，無礙 |

**重點**：唯一「硬依賴多檔」的消費者只有 version_data 自己與它的單元測試；
真正面向使用者的前端、oracle、smoke 全是 `latest_file` 動態發現，
**對檔名方案完全不敏感**。

### 3.2 多檔產生的實際情境（要不要保留多檔的理由）

| 情境 | 頻率 | 多檔是否帶來價值 |
|---|---|---|
| cron 每日正常跑 | 每天 1 次 | 無（每檔一天一個，本就不會撞名） |
| workflow_dispatch 同日重跑、資料真的異動 | 罕見（手動） | 保留「當天早/晚兩份」可對照同日價格變化；但資料層 `data/items.json` 的 history 已含同日兩點，api 多檔是重複冗餘 |
| `--date` 補爬 | 罕見 | 產生的是「執行當天」檔名；多檔在此只是意外副產品 |
| 失敗重跑 | — | 不會產生任何檔（§2.3） |
| 人工手術＋重跑 version_data（repo 實況） | 已發生 2 次 | **反面教材**：`20260815.json`（16 筆垃圾）永久留在 `files[]`；多檔反而累積壞快照 |

### 3.3 改為單檔的影響與風險

**覆寫策略**：`{date}.json` 永遠指向該台北日最新資料（同 `api/latest.json` 的覆寫先例）。
「合併」語意在此**不成立**——`data/items.json` 才是累積真相，api 快照只是當時的衍生副本，
最新一份即最正確，無需合併。

| 面向 | 影響 | 風險與緩解 |
|---|---|---|
| git 歷史 | 同日多次異動 = 同檔多次 commit；git 仍保留每次內容（`git log -p api/items/20260816.json`） | 無資料遺失；同日版本差異仍可從 git diff 取得。壞快照（16 筆）不再永久佔據 `files[]`，下一次成功 run 即自我修復 |
| 前端引用 | 完全不受影響（`latest_file` 動態） | — |
| cache-busting | 跨日仍天然失效（新日期 = 新 URL）；**同日覆寫失去檔案名級 cache-busting**，Pages 預設 `max-age=600`（dev 002 文件 §338）→ 回頭客最長 10 分鐘看到舊資料 | 同日異動本就罕見；如需，可讓前端 fetch 快照時帶 `?v={crawled_at}`（小改動，可選） |
| 健康檢查保護（total==0 不覆寫） | crawler 層已有：`total==0` 或降幅 >20% → failed → 不覆寫 `data/items.json`（`crawler/main.py:106-113,118`），且 workflow 在 version_data 前就失敗 → api 不會被寫 | **缺口**：健康檢查只在 crawler 執行時生效；人工手術改壞 `data/items.json` 後重跑 version_data 不會被擋（16 筆垃圾快照即此類）。建議單檔制下在 version_data 加防線：`meta.status == "failed"` 或 `total == 0` → 不寫檔（§4） |
| repo 大小 | 每快照 ~630KB；多檔制同日多份會額外複製整份 | 單檔制同日只多一次覆寫，git 物件壓縮後影響很小，但 `files[]` 與歷史更乾淨 |

### 3.4 結論建議

**單檔制足夠，建議改**。理由：

1. 唯一真正消費 `files[]`/多檔的是 version_data 自身與其測試；前端、oracle、smoke、
   workflow 全部與檔名方案解耦。
2. 多檔的實際來源（同日重跑資料異動）罕見，且資料層 history 已保留同日兩點，
   api 多檔是冗餘；多檔反而把壞快照（16 筆垃圾）永久固化進 `index.files[]`。
3. 單檔覆寫符合既有 `api/latest.json` 的穩定端點語意，且壞資料會在下一次成功 run 自我修復。

**具體方向**（若實作，屬另一項工作）：

- `_next_filename` 改為：同台北日期檔存在 → **覆寫** `{date}.json`（不再 `_N`）；
  不存在 → 新建 `{date}.json`。檔名保留日期（跨日 cache-busting 不變）。
- version_data 增加防線：`meta.status == "failed"` 或 `meta.get("total") == 0` →
  判定 `changed=false` 不寫檔（健康檢查保護延伸到衍生層，防人工手術/壞資料覆寫好快照）。
- `index.json` 維持 `latest_file` + `files[]`（變成每日一列的乾淨日誌，
  未來「選日期」功能反而更好用）。
- 同日重跑資料未變 → 維持 `changed=false`（不產生空 commit）。

### 3.5 影響檔案清單（若改單檔制）

| 檔案 | 變更性質 |
|---|---|
| `scripts/version_data.py` | 命名/覆寫邏輯 + 防線（核心） |
| `scripts/tests/test_version_data.py` | `TestDateSuffix`（3）、`TestIndexHistory`（1）、`TestNoChange`（2）改覆寫語意（~6 測試） |
| `docs/bdds/002-scheduler-and-pages-deploy.feature` | Scenario Outline Examples（`20260816_1`/`_2` 列） |
| `docs/development/002-scheduler-and-pages-deploy.md` | §1.5 命名契約、§1.7 快取說明 |
| `README.md` | 「資料 / API 組織」段落（:67-97） |
| `tests/test_gitignore.py` | 範例檔名 `20260815_1.json` 可清理（非必要） |
| `tests/test_crawl_workflow.py`、`web/**`、`.github/workflows/crawl.yml` | **不需改**（結構斷言與 runtime discovery 與命名解耦） |

---

## 4. 附錄：repo 現況實測

```text
api/items/
  20260815.json   3.8KB   16 筆（垃圾快照：商品名含「輸入email才可建立清單」等 UI 字串）
  20260815_1.json 633KB  1447 筆（crawled_at 與上者相同：2026-08-15T15:40:15.770082）
  20260816.json   633KB  1448 筆（crawled_at：2026-08-16T06:20:49.650053）
  20260816_1.json 663KB  1448 筆（crawled_at 與上者相同；changed=1；即 f474e92「api 重建」產物）
api/index.json  latest_file = "api/items/20260816_1.json"（指向最新，前端不受壞快照影響）
api/latest.json = 最新快照內容（覆寫語意先例）
data/items.json ≈ 1.0MB（真相；20260816_1 與其 items 完全一致）
```

git 歷史（`git log --name-status -- api/items/`）：
`43b083c` 新增 v1/v2/v3 → `2b23519` R100 改名為日期制 → `f474e92` 新增 `20260816_1.json`。
兩組雙檔皆為**人工手術/重建**產物，非 cron 或 dispatch 的自然產物。
