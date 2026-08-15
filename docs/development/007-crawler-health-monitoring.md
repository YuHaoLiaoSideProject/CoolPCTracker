# 007 爬蟲健康監控（crawler-health-monitoring）— 開發規格

> **對應 Roadmap**：Phase 2（P2 任務）— `docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md` §4.1「健康監控：解析異常（商品數驟降 >20%）→ Telegram 管理員警報，不覆寫資料」、§5 風險登錄（原價屋改版 → parser 失效之緩解措施）
> **技術決策**：`docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md`
> **操作流程**：`docs/interaction-flows/007-crawler-health-monitoring.md`
> **BDD**：`docs/bdds/007-crawler-health-monitoring.feature`
> **測試計畫**：由 `test-plan-generator` 依 007 BDD 產出（本文件 §1.5 列出單元測試重點）
> **狀態**：設計完成，待開發

---

## 概述

爬蟲在每次執行時自動偵測解析異常（商品數驟降、parser 例外、抓取失敗），異常時**保留既有資料、發出管理員 Telegram 警報**，並透過 `data/meta.json` 記錄健康指標、於前端顯示資料新鮮度，避免一次壞資料覆寫整站商品。

核心包含：

1. **health.py 健康檢查模組**：以純函數判定 `ok` / `partial` / `failed` 三態，封裝 20% 驟降門檻、首次執行跳過偵測、異常類型與計數比對規則（本功能核心，pytest 可測）。
2. **meta.json 健康指標模型**：完整記錄 `crawled_at`、各分類計數、解析狀態、來源頁面資訊（URL / G 索引 / 抓取結果）、失敗分類與異常原因；**健康指標恆更新，items.json 依狀態決定是否覆寫，兩者分離**。
3. **管理員 Telegram 警報**：與 006 共用傳訊工具，異常時向管理員推送含異常類型、失敗分類、本次/上次計數的警報（單向通知，不要求回覆）。
4. **管道整合**：與 001 的 fetcher/parser 例外傳遞、002 的 exit code 契約與手動補爬保護串接，讓健康檢查成為每日管道的強制關卡。
5. **前端新鮮度顯示**：讀取 `meta.json` 的 `crawled_at` 顯示「今日 / 昨日 / N 天前」，超過 7 天顯示「資料可能過期」提示。

> 本功能定位為**後端 + 資料流**功能：核心實作在 crawler 套件，前端僅新增一個 meta.json 消費點（無新 API）。

---

## 1. 後端實作規格

### 1.1 依賴新增

**無新增 runtime 依賴**。健康檢查僅使用 Python 3.12 標準庫（`datetime`、`typing`、`enum`、`dataclasses`）；測試沿用既有 pytest（tech-decision §3.1）。

```bash
# 無需 pip install；若 crawler/pyproject.toml 尚無 pytest 則加入 dev 依賴：
pip install pytest
```

### 1.2 檔案改動總覽

```
crawler/
├── pyproject.toml              ← 修改：dev 依賴確認（pytest）
├── main.py                     ← 修改：管道加入健康檢查階段（health 決策 → 分支寫入 → exit code）
├── fetcher.py                  ← 修改：重試 3 次仍失敗時拋出 FetchError（含 G 索引與 url）
├── parser.py                   ← 修改：解析失敗時拋出 ParserError（含分類與例外訊息）
├── health.py                   ← 新增：健康檢查核心（狀態判定 + meta 模型建構 + 警報文案）★本功能
├── health_test.py              ← 新增：pytest 單元測試（20% 邊界、首次、partial、parser 例外）★本功能
├── store.py                    ← 修改：read_meta / write_meta（原子寫入）、merge_items（partial 合併）
└── telegram_bot.py             ← 修改：send_admin_alert（006 共用 send_message + 管理員 chat id）

web/src/
├── composables/
│   └── useDataFreshness.ts     ← 新增：crawled_at → 新鮮度文案（0/1/2/7 天、>7 過期）★本功能（簡易消費點）
└── App.vue 或 SiteHeader        ← 修改：顯示新鮮度標籤與過期提示
```

### 1.3 `crawler/health.py` — 健康檢查模組

**職責**：接收 001 管道逐分類產生的結果，判定本次 run 的解析狀態（`ok` / `partial` / `failed`），產出新的 meta.json 內容，並生成管理員警報文案。**不直接碰 items.json**（寫入決策由 main.py 依回傳狀態執行，store.py 負責 I/O）。

**對外 interface**：

```python
# crawler/health.py
"""爬蟲健康檢查：狀態判定、meta.json 健康指標模型、管理員警報文案。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TypedDict

class HealthStatus(str, Enum):
    """解析狀態：僅此三值（BDD：meta.json 解析狀態僅為 ok、partial、failed 之一）"""
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"

class AnomalyType(str, Enum):
    """異常類型（管理員警報必含欄位）"""
    DROP = "drop"                # 商品數驟降（本次 < 上次 × 80%）
    PARSER_ERROR = "parser_error"  # parser 拋出例外（疑似改版訊號）
    FETCH_FAILED = "fetch_failed"  # 全部分類頁抓取失敗
    PARTIAL = "partial"            # 部分分類失敗（其餘成功）→ meta.status=partial 的 anomaly 標記

@dataclass
class CategoryResult:
    """001 管道傳入：單一分類頁的抓取與解析結果。"""
    g: int                                   # 分類 G 索引（1,3,4,5,6,7,8,9,12）
    url: str                                 # m-list.php?G=<g> 完整 URL（meta.sources 用）
    fetched: bool = True                     # 抓取成功（重試 ≤3 次後）
    parsed: bool = True                      # 解析成功（未拋 ParserError）
    count: Optional[int] = None              # 解析商品數；失敗為 None
    error: Optional[str] = None              # FetchError / ParserError 訊息

class MetaDoc(TypedDict):
    """data/meta.json 健康指標模型（007 完整版）。"""
    crawled_at: str                          # ISO 8601 UTC：ok/partial 更新為本次，failed 沿用上次（反映資料真實新鮮度）
    checked_at: str                          # 本次執行時間（恆更新，記錄系統仍在運作）
    status: str                              # HealthStatus 之一
    total: int                               # 有效商品總數（失敗分類沿用上次計數）
    previous_total: int                      # 上次有效總數（下次驟降偵測基準）
    counts: dict[str, int]                   # 9 個分類各自的商品數（失敗分類沿用上次值）
    sources: dict[str, dict]                 # G 索引 → {g, url, fetched, parsed, count, error}
    failed_categories: list[str]             # 失敗分類（抓取失敗 / parser 例外 / 空表格 count==0）清單
    anomaly: Optional[dict]                  # 異常時才有：{type, reason, current_total, previous_total, detail}
    version: int                             # cache-busting 版本號（002 共用）

@dataclass
class HealthReport:
    """健康檢查決策結果。"""
    status: HealthStatus
    anomaly: Optional[AnomalyType] = None
    reason: Optional[str] = None
    current_total: Optional[int] = None
    previous_total: Optional[int] = None
    failed_categories: list[str] = field(default_factory=list)
    alert_text: Optional[str] = None         # 非 None → main.py 呼叫 send_admin_alert

def compute_status(
    previous: Optional[MetaDoc],
    results: list[CategoryResult],
    exception_map: dict[int, str],           # g → ParserError 訊息（parser 例外集中傳遞）
) -> HealthReport:
    """狀態判定（規則依優先序，先命中先決）：
    1. 全部分類抓取失敗（fetched 全為 False）→ failed(fetch_failed)
    2. 任一分類 parser 例外 → failed(parser_error)（改版訊號：整批不寫入，BDD 明訂）
    3. 有基準且全部分類成功，total < prev_total × 80% → failed(drop)
       （邊界：恰等於 80% 不判異常；整數安全比較 current*5 < prev*4；
         total==0（全部分類皆 0 商品）時 0 < prev×80% 必成立 → 同規則 3 判 failed，
         對應 001 BDD「HTML 結構改版導致解析出 0 商品」；首次執行無基準則跳過本規則）
    4. 部分分類失敗（抓取失敗）或分類解析出 0 商品（空表格：count==0 且上次該分類有商品，
       以 previous.counts[get_category(g).name] > 0 判定）→ partial：
       失敗/空表格分類列入 failed_categories 並沿用舊資料（merge_items 不標 gone），
       成功分類照常更新（對應 001 BDD「分類頁為空表格」沿用既有資料）
    5. 其餘 → ok
    """
    # TODO: 依規則 1-5 實作；規則 3 僅在 previous 存在且所有結果 fetched&parsed 且無空表格分類時執行
    #       （空表格分類 count==0 由規則 4 判 partial，故規則 3 的「全部分類成功」不包含空表格分類）

def build_meta(
    previous: Optional[MetaDoc],
    report: HealthReport,
    results: list[CategoryResult],
    now: datetime,
) -> MetaDoc:
    """依決策結果建構新的 meta.json：
    - ok / partial：crawled_at = now（資料已實際更新）
    - failed：crawled_at 沿用 previous（items.json 未動，新鮮度不可造假）；checked_at 恆為 now
    - 失敗分類計數沿用 previous 值；成功分類計數用本次值
    - anomaly 區塊僅在 failed/partial 且有異常原因時輸出
    - version 欄位必須沿用 previous['version']（不存在則 0）——002 version_data.py 以此為 prev 判定基準，
      build_meta 覆寫時不得遺失（與 001 write_meta 同一規則）
    """

def build_alert_text(report: HealthReport) -> Optional[str]:
    """管理員警報文案（BDD 要求含：異常類型、失敗分類清單、本次/上次商品數對比、例外訊息）。
    - drop:        ⚠️ 爬蟲異常：商品數驟降\n本次 N 筆 vs 上次 M 筆（-x%）...
    - parser_error: ⚠️ 爬蟲異常：parser 例外\n失敗分類: X\n例外: ...\n舊資料已保留
    - fetch_failed: ⚠️ 爬蟲異常：全部分類抓取失敗\n...
    - partial:     ⚠️ 爬蟲部分失敗（partial）\n失敗分類: X\n其餘分類已正常更新
    """
```

**關鍵規則（與 BDD 對應）**：

| 規則 | 說明 | BDD 來源 |
|------|------|---------|
| 驟降門檻 | `current_total < previous_total × 80%` 才判異常；**恰等於 80% 正常** | Scenario Outline：1000→800 ok、1000→799 failed |
| 首次執行 | `previous is None` 時**跳過驟降偵測**，直接 ok 寫入、不發警報 | Scenario：首次執行無 meta.json |
| 邊界計算 | 使用整數比較 `current*5 < prev*4` 避免浮點誤差 | 同上 |
| parser 例外 | 任一分類 parser 拋例外 → 整批 `failed`、items.json 不覆寫（防改版污染） | Scenario：parser 拋出例外 |
| 部分失敗 | 抓取失敗（非 parser）且非全部失敗 → `partial`：成功分類更新、失敗分類保留 | Scenario：顯示卡頁失敗 |
| 空表格分類 | 單一分類解析出 0 商品（count==0）且上次該分類有商品 → 視為失敗分類：`partial`、failed_categories 記錄、沿用舊資料不標 gone（成功分類照常更新） | 001 BDD「分類頁為空表格」沿用 |
| 全部失敗 | 9 頁重試後全敗 → `failed(fetch_failed)` | Scenario：全部抓取失敗 |
| 0 商品 | 解析出 0 商品必觸發規則 3（0 < prev×80%）→ failed | 001 BDD「解析 0 商品」沿用 |
| 健康指標恆更新 | 無論 ok/partial/failed，meta.json 都寫入（異常時記錄異常；資料不覆寫） | Flow §6「資料一致性」 |

### 1.4 `crawler/main.py` — 管道整合與錯誤傳遞（001 整合點）

**整合點 001（錯誤傳遞契約）**：fetcher 對單頁重試 ≤3 次後失敗 → **拋出 `FetchError`**（含 G 索引與 url）；parser 對單頁解析失敗 → **拋出 `ParserError`**（含分類與例外訊息）。main.py **逐分類捕獲**，轉成 `CategoryResult` 列表傳給 health，**單頁失敗不中斷整批**（僅 parser 例外在 health 判定階段升級為 failed）。

```python
# crawler/main.py（007 加入健康檢查階段；片段，API 沿用 001 的 Fetcher/Parser/Store）
from crawler import fetcher, parser, store, health, telegram_bot
from crawler.fetcher import Fetcher, FetchError
from crawler.parser import Parser, ParserError
from crawler.health import CategoryResult, HealthStatus, compute_status, build_meta

def run() -> int:
    """完整管道：fetch → parse → health → write → alert。回傳 exit code（002 契約）。"""
    categories = load_categories()                      # 9 個 G 索引（001 categories.CATEGORIES）
    fetcher_ = Fetcher()                                # 001 §1.4：fetch_page() 重試 ≤3 次，仍敗拋 FetchError
    parser_ = Parser()
    results: list[CategoryResult] = []
    exception_map: dict[int, str] = {}
    new_items: list = []

    # ① fetch + parse（001）：逐分類處理，失敗不中斷（001 §1.4 fetch_all / §1.5 parse_page 之逐分類展開）
    for cat in categories:
        try:
            html = fetcher_.fetch_page(cat)             # 重試 ≤3 次，仍敗拋 FetchError（含 G 索引與 url）
        except FetchError as exc:
            results.append(CategoryResult(g=cat.g_index, url=cat.url, fetched=False, error=str(exc)))
            continue
        try:
            parsed = parser_.parse_page(html, cat)      # 可能拋 ParserError（HTML 結構異常；空表格不拋，回傳 0 商品）
        except ParserError as exc:
            exception_map[cat.g_index] = str(exc)
            results.append(CategoryResult(g=cat.g_index, url=cat.url, parsed=False, error=str(exc)))
            continue
        results.append(CategoryResult(g=cat.g_index, url=cat.url, count=len(parsed.items)))
        new_items.extend(parsed.items)

    # ② 健康檢查（007）
    previous = store.read_meta()                        # None = 首次執行
    report = compute_status(previous, results, exception_map)

    # ③ 依狀態分支寫入（001 store diff→apply→save 原子寫入；不覆寫原則在此落實）
    if report.status == HealthStatus.OK:
        # 001：diff → apply（僅異動 append [d,p]、gone 標記）→ 全量覆寫
        applied = store.apply(store.diff(new_items, previous_items), today, previous_items)
        store.save(applied, meta={})                    # items.json 原子寫入（meta 由步驟 ④ 輸出）
    elif report.status == HealthStatus.PARTIAL:
        # 007 §1.5：成功分類跑 001 diff/append 邏輯；失敗分類沿用既有資料（不 append、不標 gone）
        merged = store.merge_items(previous_items, new_items, report.failed_categories)
        store.save(merged, meta={})
    else:                                               # FAILED
        pass                                            # items.json 不動（保留既有資料）

    # ④ 健康指標恆更新（與 items.json 分離；build_meta 需沿用 previous 的 version 供 002 cache-busting）
    meta = build_meta(previous, report, results, now=utcnow())
    store.write_meta(meta)

    # ⑤ 管理員警報（006 共用 send_message；發送失敗僅 log，不影響 exit code）
    if report.alert_text:
        try:
            telegram_bot.send_admin_alert(report.alert_text)
        except Exception as exc:                        # token 失效/網路失敗
            log.warning("admin alert failed: %s", exc)

    # ⑥ exit code 契約（002）：0 = ok/partial（可 commit+deploy）；1 = failed（健康檢查擋下，工作流停止、不部署）
    #    其他執行例外（如寫檔失敗）→ 非 0（建議 2），同樣使工作流停止；002 僅以 0/非 0 判斷
    return 0 if report.status != HealthStatus.FAILED else 1

if __name__ == "__main__":
    sys.exit(run())
```

### 1.5 `crawler/store.py` — meta 讀寫與 partial 合併

```python
# crawler/store.py（007 擴充；沿用 001 原子寫入）
def read_meta() -> MetaDoc | None:
    """讀取 data/meta.json；不存在（首次執行）回傳 None。"""

def write_meta(meta: MetaDoc) -> None:
    """原子寫入 data/meta.json（temp + rename，001 既有模式）。
    此為 001 §1.7 write_meta 的 007 擴充版：改收完整 MetaDoc（001 的基礎欄位
    crawled_at/counts/total/changed/failed_categories/status 整合其中，並新增
    checked_at/previous_total/sources/anomaly/version）。"""

def merge_items(previous_items: list[Item], new_items: list[Item],
                failed_categories: list[str]) -> list[Item]:
    """partial 合併：失敗分類（依 item.category 歸類）沿用既有資料（不 append 歷史、不標 gone），
    成功分類以本次解析結果更新（含 diff / history append，001 邏輯）。"""
```

**partial 合併語意**：`items.json` 以「商品 category」歸屬分類。失敗分類中既有商品**保持原狀態與歷史不變**（不含本日資料）；成功分類照常跑 001 的 diff → append → gone 邏輯。合併後寫入 items.json。

**測試重點（health_test.py）**：
- 20% 邊界：1000→900/800/799/500 四例（BDD Examples 全覆蓋）
- 首次執行（meta 不存在）跳過偵測、不發警報
- partial：8 成功 + 1 失敗 → 狀態 partial、成功分類更新、失敗分類保留、meta 記錄失敗清單
- 全部失敗 → failed(fetch_failed)；任一 parser 例外 → failed(parser_error)
- build_meta：failed 時 crawled_at 沿用、checked_at 更新；anomaly 區塊欄位完整

### 1.6 `crawler/telegram_bot.py` — 管理員警報（006 整合點）

**整合點 006**：006 已提供 `send_message(chat_id, text)`（token 取自 GitHub Actions secret `TELEGRAM_BOT_TOKEN`，絕不進 repo）。007 新增管理員專用入口，僅多一個 secret：

```python
# crawler/telegram_bot.py（007 新增）
def send_admin_alert(text: str) -> None:
    """發送管理員警報（單向通知）。chat id 取自 secret TELEGRAM_ADMIN_CHAT_ID；
    共用 006 的 send_message 與 token。發送失敗由呼叫端 log 處理，不影響爬蟲 exit code。"""
```

> 與 001 的 `notify` hook 契約對接：001 `run_crawler(notify: Callable[[str], None])` 所注入的 hook 即本函式（`notify=send_admin_alert`）；007 正式化後 main.py 直接呼叫或注入皆可，簽名相容（`str -> None`）。

警報與 006 一般使用者通知**互不干擾**（不同 chat id、不同時機）；006 flow §5 已預留「爬蟲整體失敗 → 依健康監控規則發出管理員警報」之整合點，此處落實。

### 1.7 前端消費點（meta.json 新鮮度顯示）

BDD 之「前端新鮮度」場景由一個 composable 消費 meta.json（無新 API）：

```typescript
// web/src/composables/useDataFreshness.ts
export interface Freshness {
  text: string;        // 「更新於今日」/「更新於昨日」/「更新於 N 天前」
  stale: boolean;      // 超過 7 天（≥8 天）→ true，顯示「資料可能過期」
}
export function useDataFreshness(meta: { crawled_at: string } | null): Freshness {
  // days = 以「日期」差計算（非 24 小時差，昨日 23:00 仍顯示「昨日」）
  // 0 → 今日；1 → 昨日；≥2 → N 天前；>7 → stale: true（7 天不警告，BDD 邊界）
  // meta 缺失（首次部署）→ 視為過期，顯示「資料可能過期」
}
```

### 1.8 與 001 / 002 / 006 整合點總表

| 功能 | 整合點 | 契約 |
|------|--------|------|
| **001 爬蟲管道** | fetcher 拋 `FetchError`、parser 拋 `ParserError`（逐分類捕獲，單頁失敗不中斷）；store 原子寫入共用；meta.json 欄位擴充（001 已有 crawled_at / counts / failed_categories，007 新增 status / sources / anomaly / previous_total）；001 BDD「驟降 >20% 不覆寫 + 警報」與「解析 0 商品」場景由 health 模組正式化 | `CategoryResult` 為管道與健康檢查的資料契約 |
| **002 排程與部署** | **exit code 契約**：`0` = ok/partial（工作流繼續 commit + deploy）；`1` = failed（健康檢查擋下，工作流停止後續步驟、不部署，對應 002 BDD「爬蟲失敗保留舊資料且不部署」）；`2` = 其他執行失敗（寫檔失敗等），同樣使工作流停止（002 僅以 0/非 0 判斷）；`workflow_dispatch` 手動補爬走相同管道 → **同受健康檢查保護**；concurrency 控制沿用（防並發 commit）；meta.json `version` 供 cache-busting（build_meta 沿用 previous 值，002 維護） | exit code 為健康狀態對工作流的唯一通道 |
| **006 Telegram** | 共用 `send_message`（token 存 secrets `TELEGRAM_BOT_TOKEN`）；新增管理員 chat id secret `TELEGRAM_ADMIN_CHAT_ID`；警報發送失敗僅 log、**不影響資料 commit 與 exit code**（006 同規則：token 失效不影響資料更新） | 管理員警報為單向通知，無需回覆處理 |

---

## 4. 資料流

```
解析結果（9 分類 items + CategoryResult[]，含 FetchError/ParserError 傳遞）
        │
        ▼
   健康檢查 compute_status（main.py ①→②）
        │
   ┌────┼─────────────────────────────────────────────┐
   │ ok                                               │ partial                        │ failed
   ▼                                                 ▼                                ▼
store.write_items（全量覆寫）                store.merge_items（成功分類更新        items.json 不動
   │                                             + 失敗分類沿用舊資料）                │
   ▼                                                 ▼                                ▼
build_meta：                              build_meta：                           build_meta：
  crawled_at = now                         crawled_at = now                      crawled_at 沿用上次
  status = ok                              status = partial                     status = failed
                                           failed_categories = [...]            anomaly = {type, counts, detail}
   └──────────────┬──────────────────────────────┴──────────────────────────────────┬┘
                  ▼（三路皆執行）                                                    │
          store.write_meta（meta.json 恆更新，與 items.json 分離）◄───────────────────┘
                  │
                  ▼
      report.alert_text 非 None？（僅 partial / failed 有）
                  │ 有
                  ▼
      telegram_bot.send_admin_alert（006 共用傳訊 → 管理員 Telegram）
                  │
                  ▼
      exit code：ok/partial → 0（002：commit data/ + deploy Pages）
                failed → 1（002：工作流停止，舊資料保留、不部署）
                  │
                  ▼
      前端載入 meta.json → useDataFreshness(crawled_at)
                  → 「今日 / 昨日 / N 天前」+ 「資料可能過期」（>7 天）
```

**核心原則（資料一致性）**：
1. **items.json 只在資料可信時被覆寫**：ok 全量覆寫；partial 僅成功分類覆寫；failed 完全不動。
2. **meta.json 恆更新**：健康指標記錄每次執行的結果，異常資訊不會因資料保留而遺失。
3. **crawled_at 反映資料真實新鮮度**：failed 時不更新（避免「今天爬過」的假象），另以 `checked_at` 記錄系統仍在運作。

---

## 6. 邊界條件處理

### 6.1 商品數驟降門檻（20% 邊界）— BDD Scenario Outline 全覆蓋

判定式：`current_total < previous_total × 80%`（整數比較 `current*5 < prev*4`，**恰等於 80% 不判異常**）。

| 上次 | 本次 | 降幅 | 比較 | 狀態 | items.json | 警報 |
|------|------|------|------|:---:|:---:|:---:|
| 1000 | 900 | 10% | 900 ≥ 800 | ok | 覆寫 | 不發送 |
| 1000 | 800 | 20%（邊界） | 800 = 800 → **不**異常 | ok | 覆寫 | 不發送 |
| 1000 | 799 | 20.1% | 799 < 800 → 異常 | failed | 不被覆寫 | 發送 |
| 1000 | 500 | 50% | 500 < 800 → 異常 | failed | 不被覆寫 | 發送 |
| 1449 | 1100 | 24%（BDD 主場景） | 1100 < 1159.2 → 異常 | failed | 不被覆寫 | 發送（含異常分類與計數對比） |
| N | 0 | 100%（解析 0 商品） | 0 < prev×80% → 異常 | failed | 不被覆寫 | 發送（001 規則沿用） |

### 6.2 首次執行（無 meta.json 基準）

- `store.read_meta()` 回傳 `None` → **跳過驟降偵測**（無基準可比較），直接寫入首次資料。
- meta.json 狀態 `ok`；**不發警報**。
- 注意：首次執行後 meta 的 `previous_total` 即建立，**下次執行起驟降偵測生效**。

### 6.3 partial / 全失敗 / parser 例外

| 情境 | 判定 | items.json | meta.json | 警報內容 |
|------|:---:|------|------|------|
| 部分分類頁抓取失敗（如僅顯示卡 G=12，重試後仍敗） | `partial` | 成功分類（其餘 8 頁）正常更新；失敗分類沿用舊資料 | status=partial、failed_categories=[顯示卡] | 含失敗分類清單 |
| 單一分類解析出 0 商品（空表格，上次該分類有商品） | `partial` | 成功分類正常更新；空表格分類沿用舊資料（不標 gone） | status=partial、failed_categories 含該分類 | 含失敗分類清單 |
| 全部分類頁抓取失敗 | `failed(fetch_failed)` | 不覆寫 | failed + anomaly.type=fetch_failed | 異常類型 + 失敗分類清單 |
| 任一 parser 拋例外（疑似改版） | `failed(parser_error)` | **不覆寫**（防改版污染整批） | failed + 失敗分類 + 例外訊息 | 失敗分類 + 例外訊息 |
| 部分失敗 + parser 例外混合 | `failed(parser_error)`（優先序最高） | 不覆寫 | 同上 | 同上 |

> 設計決策：**partial 不執行驟降偵測**。失敗分類缺資料會扭曲總數基準，故僅在「全部分類成功」時才做總數比對；partial 的異常資訊改由 failed_categories 呈現，交由管理員判斷。

### 6.4 前端新鮮度顯示 — BDD Examples 全覆蓋

以「日期差」（`crawled_at` 當日 vs 當日 UTC）計算天數：

| crawled_at 距今 | 顯示 | 過期提示 |
|:---:|------|:---:|
| 0 天 | 更新於今日 | 無 |
| 1 天 | 更新於昨日 | 無 |
| 2 天 | 更新於 2 天前 | 無 |
| 7 天 | 更新於 7 天前 | 無（邊界：**7 天不警告**） |
| 8 天 | 更新於 8 天前 | 「資料可能過期」 |

- 邊界規則：**超過 7 天**（≥8 天）才顯示過期提示。
- meta.json 缺失（首次部署尚未爬取）→ 視為過期，顯示「資料可能過期」。
- 若 meta status 為 failed/partial，可選擇性顯示健康徽章（BDD 未要求，列為可選擴充，不影響驗收）。

### 6.5 手動補爬受保護（無法繞過健康檢查）

- `workflow_dispatch` 手動補爬執行**與 cron 完全相同的管道**，健康檢查位於同一關卡，**無 bypass 開關**。
- 手動補爬時若商品數較上次低於 20% → 與 cron 相同：items.json 不覆寫、meta status=failed、發警報（BDD 明訂）。
- 手動補爬成功且商品數正常 → 正常覆寫、meta status=ok、不發警報。
- 並發保護沿用 002：concurrency 確保同一時間僅一個 run 寫入。

### 6.6 meta.json 完整欄位（BDD「記錄完整健康指標欄位」）

```jsonc
// data/meta.json（007 完整版）
{
  "crawled_at": "2026-08-15T06:00:00Z",          // ISO 8601 UTC；ok/partial 更新、failed 沿用
  "checked_at": "2026-08-16T06:00:05Z",          // 本次執行時間（恆更新）
  "status": "partial",                           // 僅 ok | partial | failed 之一（僅顯示卡 G=12 失敗 → partial）
  "total": 1449,                                 // 有效總數（失敗分類沿用上次）
  "previous_total": 1449,                        // 上次有效總數（驟降偵測基準）
  "counts": { "CPU": 48, "主機板": 373, "記憶體": 216, "顯示卡": 255,
              "SSD": 171, "HDD": 89, "套裝/準系統": 157, "劈發價組合區": 86, "記憶卡": 54 },
  "sources": {
    "1":  { "g": 1, "url": "https://www.coolpc.com.tw/m/m-list.php?G=1", "fetched": true,  "parsed": true,  "count": 157 },
    "12": { "g": 12, "url": "https://www.coolpc.com.tw/m/m-list.php?G=12", "fetched": false, "parsed": false, "count": null, "error": "timeout after 3 retries" }
  },
  "failed_categories": ["顯示卡"],
  "anomaly": {                                   // 僅異常時存在
    "type": "partial",
    "reason": "部分分類頁抓取失敗（partial）",
    "current_total": 1194,
    "previous_total": 1449,
    "detail": "G=12 timeout after 3 retries"
  },
  "version": 3                                   // cache-busting（002）
}
```

### 6.7 BDD Scenario 覆蓋矩陣

| # | BDD Scenario | 規格對應 |
|---|--------------|---------|
| 1 | 每日排程正常 → 覆寫 + meta ok + 不警報 | §1.4 ①–④、§4 正常路徑 |
| 2 | 手動補爬正常 → 更新 + ok + 不警報 | §1.4、§6.5 |
| 3 | 驟降 24% → failed + 保留 + 警報（含計數對比） | §1.3 規則 3、§4 異常路徑 |
| 4 | parser 例外 → failed + 保留 + 警報（含分類與訊息） | §1.3 規則 2、§1.4 錯誤傳遞 |
| 5 | 全部抓取失敗 → failed + 保留 + 警報 | §1.3 規則 1、§6.3 |
| 6 | 20% 門檻邊界（10/20/20.1/50%） | §6.1 |
| 7 | 首次執行無基準 → 直接寫入 + ok + 不警報 | §1.3 `previous is None`、§6.2 |
| 8 | 部分失敗 → partial + 成功更新 + 失敗保留 + 警報 | §1.3 規則 4、§1.5 merge_items、§4 |
| 9 | 新鮮度 0/1/2/7 天 | §1.7、§6.4 |
| 10 | 超過 7 天（8 天）→ 過期提示 | §6.4 |
| 11 | meta.json 完整欄位（ISO 時間、分類計數、三態之一、來源頁面） | §1.3 `build_meta`、§6.6 |
| 12 | 手動補爬受驟降偵測保護 | §6.5 |

---

## 8. 開發順序

依賴關係為 DAG（後端基礎 → 管道整合 → 外部整合 → 前端 → E2E）：

| 步驟 | 內容 | 依賴 |
|------|------|------|
| 1 | meta.json 資料模型與讀寫：`MetaDoc` 型別 + `store.read_meta` / `store.write_meta`（沿用 001 原子寫入） | 001 store 完成 |
| 2 | `health.compute_status` 決策核心（純函數）：20% 門檻（整數比較）、首次跳過、partial/failed/parser 優先序；`health_test.py` 單元測試 20% 邊界四例 | #1 |
| 3 | `health.build_meta` + `build_alert_text`：完整健康指標輸出（sources / failed_categories / anomaly、crawled_at 更新規則）、警報文案模板 | #2 |
| 4 | `main.py` 管道整合：fetcher/parser 例外傳遞（`FetchError` / `ParserError` 分類級捕獲）、呼叫 health、三路分支寫入、exit code 0/1 | #2、#3、001 fetcher/parser |
| 5 | `store.merge_items`：partial 合併（成功分類更新、失敗分類沿用舊資料、不 append 歷史） | #4 |
| 6 | `telegram_bot.send_admin_alert`：006 共用 send_message + `TELEGRAM_ADMIN_CHAT_ID` secret；發送失敗僅 log 不影響 exit code | #4、006 telegram_bot |
| 7 | 前端 `useDataFreshness`：crawled_at → 今日/昨日/N 天前/>7 天過期提示，掛載於 App 全域 | #3 |
| 8 | crawl.yml 整合（002）：exit code 契約（failed → 停止 commit/deploy）、workflow_dispatch 同管道受保護、concurrency | #4、#6 |
| 9 | 整合測試與 fixture：模擬 9 分類結果組合（全成功/部分失敗/全失敗/parser 例外/首次）驗證 meta 與 items 輸出；警報觸發與內容驗證 | #4、#5、#6 |
| 10 | 驗收走查：對照 §6.7 覆蓋矩陣逐項驗證 BDD 12 個 Scenario | #7、#8、#9 |

---

## 附錄：與上游文件的雙向引用

- 本文件實作上游：`docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md`（§3.3 專案結構、§4.1 P2 健康監控、§5 風險登錄）、`docs/interaction-flows/007-crawler-health-monitoring.md`、`docs/bdds/007-crawler-health-monitoring.feature`。
- 本文件整合上游：`docs/bdds/001-crawler-data-collection.feature`（驟降/0 商品規則、meta 基礎欄位）、`docs/bdds/002-scheduler-and-pages-deploy.feature`（失敗不部署、手動補爬、concurrency）、`docs/bdds/006-telegram-price-alert.feature`（共用傳訊、token 失效語意）。
- 下游：`test-plan-generator` 依 007 BDD 產出測試計畫時，以本文件 §1.5、§6、§8 為實作依據。
