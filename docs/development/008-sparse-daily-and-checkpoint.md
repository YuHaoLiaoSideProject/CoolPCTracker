# 008 稀疏異動日誌 + 週全量 Checkpoint（sparse-daily-and-checkpoint）— 開發規格

> **對應 Roadmap**：GitHub Issue **#15** — `feat(P1): daily/ 改為稀疏異動日誌 + 週全量 checkpoint`（`docs/tech-decisions/tech-decision-資料拆檔方案-2026-08-17.md` §6.3 契約 v2 演進之連續決策）
> **技術決策**：`docs/tech-decisions/tech-decision-008-sparse-daily-checkpoint-2026-08-17.md`（決策點 D1–D6）
> **背景契約**：`docs/tech-decisions/tech-decision-資料拆檔方案-2026-08-17.md`（現行 `data/daily` 契約 v2）
> **操作流程**：`docs/interaction-flows/008-sparse-daily-and-checkpoint.md`
> **BDD**：`docs/bdds/008-sparse-daily-and-checkpoint.feature`
> **測試計畫**：由 `test-plan-generator` 依 008 BDD 產出（本文件 §1.8 列出單元測試重點、§7 覆蓋矩陣為實作依據）
> **技術棧**：Python 3.13（crawler 純標準庫 json/dataclasses/pathlib/tempfile/os + argparse + logging）· pytest · scripts/version_data.py · 前端 web/（Vue 3.5，**本功能零前端改動**）
> **狀態**：設計完成，待開發

---

## 概述

讓 `data/daily/{YYYYMMDD}.json` 語意從「每日全量」改為「**稀疏異動日誌**」——只寫當日真正異動（`changed_items` + `new_items`、價格存在者）的 `{id: price}`，平價日不寫檔；並新增 `data/checkpoints/{YYYYMMDD}.json` 每 7 天（距上次 ≥7 天）的全量快照作為自癒錨點，`version_data.build_trends` 改為「**最新 checkpoint（全量起點）＋ 回放其後稀疏異動 → 逐日 carry forward**」重建完整歷史；對外 API 面完全 **不變**（零前端改動）。

核心包含：

1. **`store.write_daily` 稀疏化**：只收「異動商品 `{id: price}`」（不含 unchanged）；空 map **不寫檔**（D3，平價日零 git 變動）；保留原簽名、docstring 註明語意改為「異動日誌」，避免大量 refactor。
2. **`store.write_checkpoint`（新增）＋ checkpoint 讀取**：全量快照 `{id: price}` 原子寫入 `data/checkpoints/{YYYYMMDD}.json`＝舊 daily 全量格式，作為回放自癒錨點；提供「找最新 checkpoint」讀取介面。
3. **`main.py` checkpoint 調度**：`write_daily` 改收 `diff.changed_items + diff.new_items`；依「距上次 checkpoint ≥7 天 / 首次純新增不寫 / 累積 ≥7 天補首個」判定是否寫全量 checkpoint。
4. **`version_data.build_trends` 回放重建**：「最新 checkpoint → 之後稀疏 delta 逐日 carry forward → 之前 legacy 全量回放」輸出完整 `history`；無 checkpoint → 走 legacy 全量回放（遷移相容），純函數、冪等。
5. **遷移腳本 `scripts/migrate_checkpoints.py`**：舊全量 `data/daily/` → 以最舊全量檔 seed 一份 checkpoint + 保留既有 daily 為 legacy 回放源（非破壞式、等價可驗證）。

> **本功能為純後端／資料流功能**：無新 API endpoint、無新 UI 元件、無 WebSocket／連線生命週期。章節 2（前端實作）、3（API 合約）、5（生命週期）、7（CSS）、9（基礎架構）**不適用**，對外 API 契約不變（見 §1.7）。資料流見 §4、邊界見 §6、BDD 覆蓋見 §7。

---

## 1. 後端實作規格

### 1.1 依賴新增

**無新增 runtime 依賴**。所有改動僅使用 Python 3.13 標準庫（`dataclasses`、`pathlib`、`tempfile`、`os`、`json`、`datetime`、`typing`），測試沿用既有 pytest。遷移腳本亦為純標準庫。

```bash
# 無需 pip install 任何東西；若需確保 pytest 存在（既有 dev 依賴）：
pip install pytest
```

### 1.2 檔案改動總覽

```
crawler/
├── store.py                       ← 修改：write_daily 稀疏化（空 map 不寫檔）；新增
│                                    write_checkpoint / latest_checkpoint / 最舊 daily 讀取；
│                                    save 新增 D2 items gating（僅實質異動分類重寫）
├── main.py                        ← 修改：write_daily 改傳 diff.changed+new；checkpoint
│                                    調度（_decide_checkpoint）；checkpoint 日寫全量快照
└── tests/
    ├── test_store.py              ← 修改：write_daily 稀疏寫入/空 map 不寫檔；新增 write_checkpoint、
    │                                latest_checkpoint、save gating 案例
    └── test_main.py               ← 修改：assert sparse daily + checkpoint 調度 + 邊界

scripts/
├── version_data.py                ← 修改：build_trends 改「checkpoint 錨點 + 稀疏回放」；無 checkpoint
│                                    → legacy 全量回放；新增 checkpoint 掃描/讀取
├── migrate_checkpoints.py         ← 新增：008 遷移腳本（seed checkpoint + 保留 legacy delta）★本功能
└── tests/
    ├── test_version_data.py       ← 修改：build_trends 回放/等價/冪等/壞檔/遺失案例 + checkpoint
    └── test_migrate_checkpoints.py← 新增：遷移 seed/防線/冪等/非破壞案例

tests/
├── test_crawl_workflow.py         ← 修改：（參照 008）等價回歸（legacy 全量 ↔ checkpoint+稀疏 同輸出）
└── test_gitignore.py              ← 修改：data/checkpoints/ 入庫斷言

docs/**、README.md、.gitignore    ← T9 同步（本規格為 development/；README「資料/API 組織」補 checkpoint）
.github/workflows/crawl.yml        ← T8：commit `git add data/` 已涵蓋 data/checkpoints/（無需新 path）
```

### 1.3 `crawler/store.py` — 稀疏 daily + checkpoint 讀寫

**職責**：`write_daily` 語意改為「稀疏異動日誌」；新增全量 checkpoint 寫入與讀取；`save` 依 D2 對「無實質異動分類」跳過重寫。沿用既有 `_write_json_atomic`（tempfile + os.replace）、compact JSON、原子語意。

新增常數與目錄：

```python
CHECKPOINT_INTERVAL_DAYS = 7  # 距上次 checkpoint ≥ 7 天 → 寫全量快照（008，邊界恰 7 天為是）

class Store:
    def __init__(self, data_dir: Path):
        self._items_dir = data_dir / "items"
        self._meta_path = data_dir / "meta.json"
        self._daily_dir = data_dir / "daily"
        self._checkpoints_dir = data_dir / "checkpoints"   # 008 新增
```

**改寫 `write_daily`（語意：稀疏異動日誌）**：

```python
def write_daily(self, day: date, price_map: dict[str, int]) -> None:
    """原子寫入 data/daily/{YYYYMMDD}.json = {item_id: price}（008 語意：稀疏異動日誌）。

    只收「當日真正異動的商品」——diff.changed_items + diff.new_items 且價格存在的
    {id: price}；不含 unchanged（平價日不寫入，根除 git noise，D3）。
    price_map 為空（純平價日）→ **不寫檔**（平價日零 git 變動；checkpoint 日即使
    無異動仍由 write_checkpoint 寫全量錨點）。
    維持 compact JSON + tempfile/os.replace 原子寫入；失敗拋例外且不影響既有檔案。
    """
    if not price_map:
        return  # 平價日：不產生 daily 檔（D3）
    path = self._daily_dir / f"{day.strftime('%Y%m%d')}.json"
    self._write_json_atomic(path, price_map)
```

**新增 `write_checkpoint`**：

```python
def write_checkpoint(self, day: date, full_price_map: dict[str, int]) -> None:
    """原子寫入 data/checkpoints/{YYYYMMDD}.json = 當日全量 {item_id: price}（008）。

    等同舊 daily 全量格式——當日「所有成功爬取且價格存在」的商品 {id: price}；
    作為 version_data 回放的自癒錨點（delta 遺失最多回放 7 天）。compact +
    tempfile/os.replace 原子寫入。checkpoint 不進 api/（前端無需，D5）。"""
    path = self._checkpoints_dir / f"{day.strftime('%Y%m%d')}.json"
    self._write_json_atomic(path, full_price_map)
```

**新增 checkpoint / 最舊 daily 讀取**：

```python
def latest_checkpoint(self) -> tuple[date, dict[str, int]] | None:
    """data/checkpoints/ 中日期最大者 → (date, {id: price})；無任何 checkpoint → None。

    檔名僅認 YYYYMMDD.json（8 位數字）；損壞（JSON 解析失敗）→ 跳過不採信；
    排序誤差由「取最大」而非常見排序清單規避。由 main / version_data 共用。"""

def earliest_daily(self) -> date | None:
    """data/daily/ 中日期最小者 → date（純新增模式首次 checkpoint 的判定基準）；無 → None。

    檔名僅認 YYYYMMDD.json；損壞檔忽略。主要供 main._decide_checkpoint 在無 checkpoint
    時以「距最早 daily ≥ 7 天」補首個錨點。"""
```

**`save` D2 items gating（僅實質異動分類重寫）**：

```python
def save(self, items: list[Item], meta: dict[str, Any],
         rewrite_g: set[int] | None = None) -> None:
    """依分類分組原子寫 data/items/{g}.json（頂層 array）+ data/meta.json。

    V2 契約不變；008 新增 D2 gating：
    - rewrite_g=None → 照舊全部分類重寫（既有呼叫相容）
    - rewrite_g 給定 → 僅重寫「本 run 有實質異動（new/changed/refreshed/gone/status 變化）
      的分類 g；其他分類（純平價）跳過 → 平價日 items 檔零重寫、last_seen 不更新
      （根除痛點 B，D2；last_seen 保留最後異動日，前端為被動欄位可接受）
    history 序列化仍截最近 2 點（D1 維持 ≤2 點，不因 checkpoint 改策略）。"""
```

### 1.4 `crawler/main.py` — 稀疏 write_daily + checkpoint 調度

**職責**：`write_daily` 呼叫從 `unique_today`（全量）改為 `diff.changed_items + diff.new_items`（稀疏）；新增 `_decide_checkpoint` 調度與 checkpoint 日全量寫入；`save` 傳入 `rewrite_g`（D2）。健康檢查防線（failed 提前 return 1）不變，故 checkpoint 日爬取失敗天然不會寫 checkpoint / 覆寫 items。

```python
# crawler/main.py（008 改動片段；import/既有流程沿用 001/007）
CHECKPOINT_INTERVAL_DAYS = 7

def run_crawler(data_dir: Path, today: date | None = None,
                notify: NotifyFn | None = None) -> int:
    ...
    # 5. diff → apply（001/007 語意不變；partial 時 failed 分類 carryover 原樣保留）
    diff = store.diff(today_items, previous_items)
    if failed_categories:
        diff = _exclude_failed_from_gone(diff, failed_categories, previous_items)
    items = store.apply(diff, day, previous_items)
    changed = len(diff.new_items) + len(diff.changed_items)

    # 5b. 008 稀疏異動價格清單：只取 changed+new 且價格存在者
    sparse_prices: dict[str, int] = {}
    for item in list(diff.changed_items) + list(diff.new_items):
        if item.price is not None:            # 價格缺失（None）不寫入（BDD edge）
            sparse_prices[item.id] = item.price

    # 6. meta + save（D2：僅實質異動分類重寫）
    meta = dict(old_meta)
    meta.update({...})                        # 007 完整欄位，欄位不變
    changed_g = _changed_categories(diff)     # new/changed/refreshed/gone/status 有異動的分類 g 集合
    store.save(items, meta, rewrite_g=changed_g)

    # 6b. 008 稀疏 daily：只寫 changed+new；空 → 不寫檔（平價日零 git 變動）
    store.write_daily(day, sparse_prices)

    # 6c. 008 checkpoint 調度：距上次 ≥ 7 天 / 無 checkpoint 且累積 ≥ 7 天 → 寫全量快照
    latest_cp = store.latest_checkpoint()     # (date, prices) | None
    cp_date = latest_cp[0] if latest_cp else None
    if _decide_checkpoint(cp_date, day, store.earliest_daily()):
        full_prices = {item.id: item.price for item in unique_today
                       if item.price is not None}   # 當日全量（成功爬取 + 價格存在）
        store.write_checkpoint(day, full_prices)
    ...
    return 0


def _decide_checkpoint(latest_cp_date: date | None, today: date,
                       earliest_daily: date | None) -> bool:
    """今天是否為 checkpoint 日（008 調度核心，純函數可單測）：

    - 有 checkpoint：today - latest_cp_date ≥ CHECKPOINT_INTERVAL_DAYS（≥7 天）→ True
      （邊界：恰 7 天 → True；3/6 天 → False；12 天 → True）
    - 無 checkpoint 且無任何 daily（純新增首次 run）→ False（無全量基準可依，不寫）
    - 無 checkpoint 但已有 daily（遷移未跑或純新增累積期）：
      距最早 daily ≥ 7 天 → True（補首個錨點，之後正常每 7 天排程）；否則 False
        （遷移腳本已 seed 時 latest_cp 存在 → 走第一條規則）
    """
    if latest_cp_date is not None:
        return (today - latest_cp_date).days >= CHECKPOINT_INTERVAL_DAYS
    if earliest_daily is None:
        return False
    return (today - earliest_daily).days >= CHECKPOINT_INTERVAL_DAYS


def _changed_categories(diff: DiffResult) -> set[int]:
    """本 run 有「實質異動」的分類 g 集合（D2 gating 基準）：

    new_items / changed_items / refreshed_items（refresh 傳播到 items 檔，不得凍結）
    / gone_ids（標記 gone 須落盤）/ status 異動——任一命中該分類即需重寫；
    純 unchanged / carryover 分類不重寫。回傳 g 索引集合（save 依分類名分組，故以
    分類名 → g 轉換）。"""
```

> `_decide_checkpoint` 以「距上次 ≥ 7 天」為唯一準則，與 BDD Scenario Outline（3/6/7/12 天）對應。**checkpoint 日同時照常寫稀疏 daily**（D3 取捨 (a)：daily 序列連續、workflow 依賴的 `filename` 不破）。

### 1.5 `scripts/version_data.py` — build_trends 回放重建

**職責**：`build_trends` 由「全量聚合所有 daily」改為「**依序 chain 所有 checkpoint（各全量重置 carrier）＋ 其間稀疏 delta 逐日 carry forward（全窗口重建）**」；無 checkpoint → legacy 全量回放（涵蓋純新增累積期）；**純函數、冪等**（同輸入 → 同輸出）。`write_trends` / `mirror_daily` / `build_index` / `write_index` 對外組裝不變；`index.json` / `daily_files[]` 不含 checkpoint（D5：checkpoint 不進 api/）。

```python
def _checkpoint_paths(data_dir: Path) -> list[Path]:
    """掃 data/checkpoints/*.json（只認 YYYYMMDD.json 檔名），依檔名升冪排序。
    非 8 位數字檔名 / 損壞檔忽略。data/checkpoints/ 不存在 → []。"""

def _latest_checkpoint(data_dir: Path) -> tuple[str, dict] | None:
    """最新（日期最大）checkpoint → (YYYY-MM-DD, {id: price})；無 → None。
    （同 main 的「取最大」語意；損壞檔跳過。）"""

def build_trends(data_dir: Path) -> dict[str, list[list]]:
    """{item_id: [[d, p], ...]}，依日期升冪、每日一點、冪等。008 核心：

    有 checkpoint（C1<C2<...<Cn 日）：
      - 從最早 checkpoint C1 日期開始，遍歷每個日曆日至資料最晚日：
        - 當日有 checkpoint → carrier = checkpoint 全量覆寫（重置）
        - 當日有 daily → carrier[商品] = daily 值（更新異動者）
        - 無檔案日（平價/遺失）→ carrier 不變（carry forward）
        - 每日輸出 carrier 中所有 alive 商品一點
      - 遷移相容：舊全量 daily 在 checkpoint 錨點之間仍以「每日全量覆寫」語意更新 carrier（全量 daily 含所有商品 → 自然重置）
    無 checkpoint：
      - legacy 全量回放（現行行為）：所有 daily 依序全量聚合；涵蓋純新增累積期
    損壞 / 遺失的 daily → 跳過不中斷（該日 carrier 不變 = carry forward）；
    中途消失商品：保留最後值 ≤7 天暫存尾巴，下一個 checkpoint 自校正（D6）。
    回傳前每 bucket 依日期升冪、同日去重。
    """
    daily = _daily_records_sorted(data_dir)       # [(date_str, prices)] 升冪（含壞檔過濾）
    checkpoints = _checkpoint_records_sorted(data_dir)  # [(date_str, full_prices)] 升冪
    if not checkpoints:
        return _replay_full_all(daily)            # legacy 全量回放（純新增/無 checkpoint）

    # 統一時間軸重建：chain 所有 checkpoint + daily + carry forward 每天
    events: dict[str, list] = {}  # day → [("cp", full_prices) | ("delta", prices)]
    for d, prices in checkpoints:
        events.setdefault(d, []).append(("cp", prices))
    for d, prices in daily:
        events.setdefault(d, []).append(("delta", prices))
    all_days = sorted(events.keys())
    earliest = all_days[0]
    latest = all_days[-1]

    carrier: dict[str, int] = {}  # item_id → last known price
    trends: dict[str, list[list]] = {}
    day = earliest
    while day <= latest:
        for kind, prices in events.get(day, []):
            if kind == "cp":
                carrier = dict(prices)       # checkpoint 全量重置
            else:  # delta
                carrier.update(prices)       # 異動者更新；未異動者保持
        # 輸出 carrier 中所有 alive 商品當日一點（含平價/遺失日 = carry forward）
        for iid, price in carrier.items():
            bucket = trends.setdefault(iid, [])
            if not bucket or bucket[-1][0] != day:
                bucket.append([day, price])
        day = _next_day(day)
    return _dedupe_by_date(trends)

def _next_day(d: str) -> str:
    """YYYY-MM-DD → 下一日 YYYY-MM-DD（用 datetime.date 遞增）。"""
    from datetime import date, timedelta
    y, m, day = int(d[:4]), int(d[5:7]), int(d[8:10])
    nxt = date(y, m, day) + timedelta(days=1)
    return nxt.isoformat()

def _checkpoint_records_sorted(data_dir: Path) -> list[tuple[str, dict]]:
    """data/checkpoints/*.json → [(YYYY-MM-DD, {id: price})] 依日期升冪；壞檔跳過。"""
    cp_dir = data_dir / "checkpoints"
    if not cp_dir.is_dir():
        return []
    entries: list[tuple[str, dict]] = []
    for p in sorted(cp_dir.glob("*.json")):
        stem = p.stem
        if not (len(stem) == 8 and stem.isdigit()):
            continue
        prices = _read_daily_prices(p)  # 共用解析邏輯
        if prices is not None:
            entries.append((_daily_date(stem), prices))
    return sorted(entries, key=lambda e: e[0])

def _replay_full_all(daily: list[tuple[str, dict]]) -> dict[str, list[list]]:
    """legacy 全量回放：每個 daily 檔當天全量覆寫該商品該日值（現行 build_trends 語意）。"""

def _daily_records_sorted(data_dir: Path) -> list[tuple[str, dict]]:
    """data/daily/*.json → [(YYYY-MM-DD, {id: price})] 依日期升冪；壞檔（不可解析/非 object）跳過。"""

def _dedupe_by_date(trends: dict[str, list[list]]) -> dict[str, list[list]]:
    """每 bucket 依日期升冪排序、同日期只留一點（防回放重複點，遷移 seed 防同名衝突）。"""
```

> **回放 etc 相關**：carry-forward 使 `build_trends` compute cost 維持 <1ms（1448 商品 × ≤7 天）。`build_trends` 保持純函數（只讀 data_dir、不寫檔），`write_trends` 才寫 api/——沿用現行「全量重建、冪等」責任分割。

### 1.6 遷移腳本 `scripts/migrate_checkpoints.py`（新增）

**職責**：一次性遷移既有舊全量 `data/daily/` → 建立 seed checkpoint（最舊全量 daily） + 保留所有 legacy 回放源；非破壞式、等價可驗證。

```python
#!/usr/bin/env python3
"""008 遷移：舊全量 data/daily/ → seed checkpoint + 保留 legacy delta。

非破壞式：不刪任何既存 daily；等價可驗證：version_data 對「無 checkpoint」走
legacy 全量回放，與遷移前輸出一致（BDD Scenario 5 / 11 equivalence test）。
防線：meta.status == 'failed' 或 total == 0 → 不遷移（健康檢查延伸，防人工手術
壞資料污染）。冪等：data/checkpoints/ 已有 checkpoint → 已遷移，直接略過。
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import TypedDict, Optional

class MigrateResult(TypedDict):
    seeded: bool                  # 是否新建 checkpoint
    checkpoint_file: Optional[str]# 建立的 checkpoint 檔名（YYYYMMDD.json）或 None
    kept_daily: list[str]         # 保留為 legacy delta 的 daily 檔名
    skipped: Optional[str]        # 防線/已遷移跳過原因

def migrate(data_dir: Path, keep_days: int = 7) -> MigrateResult:
    """執行遷移（純標準庫）：
    1. 讀 data/meta.json；防線：status=='failed' 或 total==0 → skipped，不遷移
    2. 冪等：data/checkpoints/ 已有 checkpoint → skipped，回傳現況
    3. 掃 data/daily/ 舊全量檔（只認 YYYYMMDD.json；壞檔跳過）
    4. seed：取最舊（檔名最小）全量 daily 內容 → 寫入 data/checkpoints/{最舊日}.json
       （以最舊為錨點 → 之後所有 daily 均 ≥ 錨點，作為 legacy delta 全量保留，
        版本化重建等價）
    5. 保留所有舊 daily 為 legacy 全量回放源（**不刪除、不歸檔任何 daily**；等價保證：每日歷史點不可遺失）
    6. 印出 summary + 等價驗證指引（執行 version_data + equivalence test）
    """
    # TODO: 依 1-6 實作；seed=最舊全量 daily（BDD/IF/tech-decision 三方已統一）

def main(argv: list[str] | None = None) -> int:
    """CLI：python scripts/migrate_checkpoints.py [--data-dir data]"""
    # argparse；呼叫 migrate；印 JSON summary；回傳 0
```

> **seed 錨點已定案（loop-review 確認）**：seed=最舊全量 daily 為歷史錨點，保留所有舊 daily 為 legacy 全量回放源（不刪除任何舊檔）。tech-decision D4、BDD S10、IF §8 三方已統一。

### 1.7 對外 API 契約（不變）

對外層（`api/items/{g}.json`、`api/daily/YYYYMMDD.json`、`api/trends/{item_id}.json`、`api/index.json`）欄位與語意**完全不變**：

| 對外檔 | 008 影響 |
|--------|---------|
| `api/items/{g}.json` | 不變（仍鏡像 data/items/{g}；D2 平價日不重寫 → api 端 items_changed 依 canonical 判定天然不觸發） |
| `api/daily/YYYYMMDD.json` | 結構不變，內容為稀疏（僅異動日有檔；平價日無新檔）；由 `mirror_daily` 鏡像 `data/daily` |
| `api/trends/{item_id}.json` | **輸出不變**（`{"id","history":[[d,p],...]}`）；history 由「checkpoint + 稀疏回放」重建，語意等價 |
| `api/index.json` | 不變（categories[]、daily_files[]、trends_prefix）；**不含 checkpoint**（D5：checkpoint 為真相層內部錨點，前端無需） |

> 對外 API 無新增 / 刪除 / 欄位變更，前端零改動（無新 API endpoint）。章節 3（API 合約）因此 **不適用**。

### 1.8 測試重點

- **`crawler/tests/test_store.py`**（修改加案例）：
  - `write_daily` 收稀疏 map 寫檔、`{}` 空 map **不寫檔**（平價日零檔案）
  - `write_checkpoint` 寫入 `data/checkpoints/YYYYMMDD.json` 全量、compact、原子失敗不影響既有
  - `latest_checkpoint`：多檔取最大、無 checkpoint → None、損壞檔跳過
  - `earliest_daily`：取最小日期、無檔 → None
  - `save` D2 gating：`rewrite_g` 給定時僅重寫指定分類、其他分類檔 mtime/內容不變
- **`crawler/tests/test_main.py`**：稀疏 daily 只含 changed+new（價格存在者）；平價日不產 daily 檔；checkpoint 調度邊界（3/6/7/12 天）由 `_decide_checkpoint` 直接單測 + main 端（monkeypatch `latest_checkpoint`/`earliest_daily`）驗證；checkpoint 日寫全量快照；failed 路徑不寫 daily / 不寫 checkpoint / 不覆寫 items。
- **`scripts/tests/test_version_data.py`**（新增案例）：
  - build_trends chain 所有 checkpoint + delta carry-forward（合成 legacy 全量 ↔ checkpoint+稀疏 → **同輸出**等價）
  - 無 checkpoint → legacy 全量回放（與現行 build_trends 相同）
  - 冪等（同輸入 → 同輸出）；壞檔跳過不崩潰；遺失檔跳過自癒（缺失 ≤7 天）；中途消失商品暫存尾巴 ≤7 天（D6）
  - 逐 bucket 日期升冪、同日去重
- **`scripts/tests/test_migrate_checkpoints.py`**（新增）：seed=最舊全量 daily、**保留所有舊 daily**（不刪除不歸檔）、防線（failed/total=0 不遷移）、冪等（已遷移略過）、非破壞（不刪任何 daily）。
- **`tests/test_gitignore.py`**（修改）：`data/checkpoints/` 入庫斷言（`!data/checkpoints/` + `!data/checkpoints/**` 加入 `.gitignore`）。
- **`tests/test_crawl_workflow.py`**：參照等價回歸（legacy ↔ checkpoint+稀疏 同輸出）可放 scripts/tests 或此處；workflow 結構斷言不變（`git add data/` 涵蓋 data/checkpoints/）。
- **BDD 回歸**：`tests/test_crawl_workflow.py`（002）、`crawler/tests/` full suite、`scripts/tests/` full suite 全綠。

---

## 4. 資料流

```text
每日 06:00 UTC cron / workflow_dispatch 手動補爬 ── 同一管道（002）
        │
        ▼
抓取 9 分類 → 解析（001）→ verify（健康檢查 007）
        │
        ▼ store.diff（001，語意不變）
   new / changed / refreshed / unchanged / gone / carryover
        │
   ┌────┴─────────────────────────────────────────────────────┐
   │ ok / partial（成功路徑）                              │ failed（007 防線）
   ▼                                                        ▼
sparse_prices = diff.changed_items + diff.new_items、      不寫 daily、不寫 checkpoint、
               價格存在者                                    不覆寫 items/{g}
   │                                                        │
   ▼                                                        ▼
store.write_daily(day, sparse_prices)                    store.write_meta(status=failed)
   空 map → 不寫檔（平價日零 git）                      → return 1（002：不 commit、不部署）
   │                            
   ▼
store.save(items, meta, rewrite_g=改變分類)              // D2：平價日分類不重寫 items/{g}
   │                            
   ▼
 _decide_checkpoint(latest_cp, today, earliest_daily)
   │ 是（距上次 ≥7 天 / 無 cp 且累積 ≥7 天）
   ▼
store.write_checkpoint(day, 當日全量 {id: price})        // 自癒錨點（錨點日無異動也寫，BDD edge）
   │
   ▼
scripts/version_data.py（deploy 前重建 api/）
   │
   ▼ build_trends（008 純函數）
   chain 所有 checkpoint（各全量重置 carrier）
   → 其間稀疏 daily 逐日 carry forward（含平價/遺失日 = carrier 繼續輸出）
   → 無 checkpoint → legacy 全量回放（現行行為）
   │
   ▼
api/trends/{id}.json（完整 history 升冪、每日一點）＋
api/items/{g} 鏡像＋ api/daily 鏡像＋ api/index.json（對外契約不變）
   │
   ▼
前端（003/004）讀 index → items/{g}（列表）/ trends/{id}（詳情圖）→ 零改動

【遷移（一次性，維護者手動）】scripts/migrate_checkpoints.py
  舊全量 data/daily/ ── 最舊全量 → seed data/checkpoints/{最舊日}.json
                          所有舊 daily → 保留為 legacy 全量回放源（不刪除不歸檔）
```

**核心原則**：
1. **真相層雙儲存**：`data/daily/`（稀疏異動 delta）＋ `data/checkpoints/`（每 7 天全量錨點）共同承載歷史；兩者皆 crawler 唯一寫入者。
2. **對外零衝擊**：`api/` 由 version_data 重建、契約不變；checkpoint 不進 `api/`（D5）。
3. **自癒**：任何 delta 遺失/損壞 → 以 checkpoint 為錨點回放其餘有效 delta，缺失片段 ≤7 天，下一 checkpoint 全量校正（D6）。

---

## 6. 邊界條件處理

| 情境 | 來源 | 處理方式 |
|------|------|---------|
| checkpoint 日門檻邊界 | BDD Scenario Outline（3/6/7/12 天） | `_decide_checkpoint`：`today - latest_cp ≥ 7` → 寫；**恰 7 天為「是」**（邊界）、3/6 天「否」、12 天「是」。整數日期差比較，無浮點 |
| 純平價日 | BDD Scenario 2、D3 | `write_daily` 收空 map → **不寫檔**；D2 `save` 不重寫任何分類 items；meta.json 仍更新 crawled_at（資料新鮮度不造假） |
| checkpoint 日即使無異動 | BDD Scenario 16 | daily 不產生（平價日），但 `write_checkpoint` **仍寫**當日全量快照（7 天錨點不缺席） |
| checkpoint 日爬取失敗（status=failed） | BDD Scenario 7、IF §5 | 007 防線在 diff/寫入前 return 1：不寫 daily、不寫 checkpoint、不覆寫 items；meta.status=failed。下次成功 run 距上次 ≥7 天仍成立 → 自動補寫（自癒） |
| 某天 delta 遺失 | BDD Scenario 8 | build_trends 跳過缺失檔（不存在即不入列）；以 checkpoint 錨點回放其餘；缺失 ≤7 天（checkpoint 頻率上限） |
| 某天 delta 損壞（JSON 無法解析） | BDD Scenario 9 | `_read_daily_prices` 回 None → 跳過不中斷；重建不拋例外、其餘商品不受影響 |
| 首次執行純新增模式（無 cp 無 daily） | BDD Scenario 12 | 寫全部 new_items 為稀疏 daily；不因缺錨點失敗；`_decide_checkpoint` 無 cp 且無 earliest_daily → 不寫；之後每 7 天（距最早 daily ≥7）補首個 |
| carryover（失敗分類）不寫入 daily | BDD Scenario 13 | 失敗分類商品不在唯一 today 清單 → 不入 changed/new → 不寫入稀疏 daily；僅成功分類中異動+新增且價格存在者寫入 |
| 異動商品價格缺失（None） | BDD Scenario 14 | 稀疏清單過濾 `price is not None`；None 不寫入 daily（亦不影響 items 歷史，沿用 001） |
| 稀疏寫入範圍限定 changed+new | BDD Scenario Outline 15 | `write_daily` 只收 `changed_items + new_items`；`refreshed/unchanged/carryover/gone` 一律排除（見 §7 覆蓋矩陣對應） |
| gone 中途消失的回放尾巴 | BDD @error、tech-decision D6 | carry-forward 期間保留最後價格 ≤7 天暫存尾巴；下一 checkpoint（全量 alive 集合）自動校正；等價測試以「無中途消失」受控資料驗證 S 與 legacy 一致 |
| 遷移 seed 錨點（已定案） | BDD/IF/tech-decision 三方統一 | **seed=最舊全量 daily**：保留所有舊 daily 為 legacy 全量回放源（不刪除不歸檔）；等價保證：每日歷史點不可遺失 |
| 遷移防線 | BDD Scenario 10、tech-decision | meta.status==failed 或 total==0 → migrate 不執行（不污染既有） |
| checkpoint 不進 api/ | tech-decision D5 | `index.json`/`daily_files[]` 不含 checkpoint；僅 data/ 內部回放源 |
| items/{g} last_seen 平價日停滯 | tech-decision D2 | 平價日不重寫 items → last_seen 保留最後異動日；前端 useItems 為被動欄位、無計算依賴；文件化語意「最近異動/錨點日」；meta.crawled_at 仍每日更新 |
| items history 截斷策略 | tech-decision D1 定稿 | **維持 ≤2 點**，不因 checkpoint 改「只留 checkpoint 後異動點」（漲跌徽章只需末 2 點） |
| items history 截斷策略 | tech-decision D1 | **維持 ≤2 點（現狀）**，不因 checkpoint 改「只留 checkpoint 後異動點」（漲跌徽章只需末 2 點） |
| repo 體積 | tech-decision §2.3 | daily 35KB/天→1-2KB/天、平價日零；checkpoint 新增 52×35KB/年≈1.8MB；合計 ~2.8MB/年（舊 12.5MB → 淨減 ~78%） |
| checkpoint 日同時寫稀疏 daily | tech-decision D3(a) | daily 序列連續、workflow `filename`（最新 daily 檔名）不破；冗餘僅 checkpoint 日一份 |
| version_data changed 判定 | tech-decision 風險 | `changed` 判準需涵蓋「新 checkpoint」（flat checkpoint 日無 daily 但有 checkpoint → 仍需 rebuild api/trends）；checkpoint 日正常寫稀疏 daily 維持 filename 連續（flat checkpoint 日例外） |

---

## 7. BDD Scenario 覆蓋矩陣

| # | BDD Scenario | 來源標籤 | 規格對應 |
|---|--------------|---------|---------|
| 1 | 價格異動日僅寫入異動與新增商品（稀疏 delta） | @smoke @happy-path @p0 | §1.3 `write_daily`、§1.4 `sparse_prices`、§4 成功路徑 |
| 2 | 平價日不產生額外 daily 寫入、避免 git noise | @happy-path @p0 | §1.3 `write_daily` 空 map 不寫檔、§1.4、§6 純平價日 |
| 3 | 距上次 checkpoint ≥7 天寫入全量 checkpoint | @happy-path @p0 | §1.3 `write_checkpoint`、§1.4 `_decide_checkpoint` |
| 4 | version_data 以 checkpoint 為起點、回放 delta carry forward | @happy-path @p1 | §1.5 `build_trends`、§4 |
| 5 | 遷移後首次 run 的 api/trends 與遷移前完全等價 | @regression @p0 | §1.5 `_replay_full_all`（等價路徑）、§1.6、§1.8 equivalence test |
| 6 | checkpoint 日門檻邊界（3/6/7/12 天。Examples 4 行） | @edge-case @boundary | §1.4 `_decide_checkpoint`、§6 門檻邊界（3/6→否，7/12→是） |
| 7 | checkpoint 日爬取失敗不覆寫 items、不寫 checkpoint | @error-handling @p0 | §1.4 failed 路徑、§6 checkpoint 日失敗 |
| 8 | 某天 delta 遺失自癒，最多補回 7 天 | @error-handling @p1 | §1.5 跳過遺失檔、§6 遺失 |
| 9 | 某天 delta 損壞跳過、不崩潰 | @error-handling @p1 | §1.5 `_read_daily_prices` None 跳過、§6 損壞 |
| 10 | 遷移腳本 seed checkpoint + 保留所有 daily | @business-rules @p0 | §1.6 `migrate`（seed=最舊、保留所有 daily）、§6 遷移 |
| 11 | 遷移後首次執行以 checkpoint 回放、等價 | @business-rules @p0 | §1.5 build_trends 回放、§1.6、§1.8 equivalence |
| 12 | 首次執行純新增模式、不寫 checkpoint | @edge-case @p0 | §1.4 `_decide_checkpoint`（無 cp 無 earliest_daily → 否）、§6 純新增 |
| 13 | 失敗分類（carryover）不寫入稀疏 daily | @edge-case | §1.4 `sparse_prices`（carryover 不在 changed/new）、§6 carryover |
| 14 | 異動商品價格缺失（None）不寫入 | @edge-case | §1.4 `price is not None` 過濾、§6 價格缺失 |
| 15 | 稀疏寫入範圍僅限 changed+new 且價格存在（Examples 8 行） | @business-rules | §1.3 `write_daily`、§1.4 `sparse_prices`；逐行對應：changed/new 有價→寫；changed/new 價 None→不寫；refreshed→不寫；unchanged→不寫；carryover→不寫；gone→不寫（見下） |
| 16 | checkpoint 日即使無異動仍寫全量 checkpoint | @edge-case | §1.3 `write_checkpoint` 獨立於 daily 寫入、§6 checkpoint 日無異動 |

**Scenario Outline 15 Examples 追蹤**：

| category | hasPrice | 對應 | 寫入？ |
|----------|:---:|------|:---:|
| changed_items | 價格存在 | §1.4 `sparse_prices`（diff.changed_items & price 非 None） | ✅ 寫 |
| new_items | 價格存在 | §1.4 `sparse_prices`（diff.new_items & price 非 None） | ✅ 寫 |
| changed_items | 價格缺失 None | §1.4 `price is not None` 過濾 | ❌ 不寫 |
| new_items | 價格缺失 None | 同上 | ❌ 不寫 |
| refreshed_items | 價格存在 | §1.3/§1.4 只收 changed+new（refresh 不在內） | ❌ 不寫 |
| unchanged_ids | 價格存在 | 只收 changed+new | ❌ 不寫 |
| carryover_ids | 價格未知 | 不在唯一 today 清單 | ❌ 不寫 |
| gone_ids | 無 | 不收 gone | ❌ 不寫 |

---

## 8. 開發順序

依賴為 DAG（後端基礎 → 管道整合 → 衍生層 → 遷移 → 回歸；本功能無前端，故無前端整合步）。對應 tech-decision §5.3 Phase 1–4：

| 步驟 | 內容 | 依賴 | Phase |
|------|------|------|:---:|
| 1 | `store` 新增 checkpoint 讀寫：`write_checkpoint`、`latest_checkpoint`、`earliest_daily` ＋ `write_daily` 稀疏化（空 map 不寫檔）；`test_store` 案例 | store 基礎 | 2 |
| 2 | `build_trends` 回放核心（純函數）：checkpoint 錨點 + 稀疏 carry-forward + legacy 全量回放 + 壞檔/遺失跳過 + 冪等；`test_version_data` 回放與等價案例（合成 legacy ↔ checkpoint+稀疏 同輸出） | —（可先做，獨立於 crawler） | 1 |
| 3 | `migrate_checkpoints.py` 實作：seed=最舊全量 daily + 保留所有舊 daily（不刪除不歸檔）；`test_migrate_checkpoints` | #1、#2 | 3 |
| 4 | `save` D2 items gating（`rewrite_g` 參數，僅實質異動分類重寫）；`test_store` gating 案例 | #1 | 2 |
| 5 | `main` 整合：`write_daily` 改傳 sparse（changed+new）、`_decide_checkpoint` 調度、checkpoint 日寫全量；`_changed_categories`；`test_main` 稀疏 + 調度邊界（3/6/7/12 天）案例 | #1、#4 | 2 |
| 6 | `version_data.build_trends` 接入回放（取代現行全量聚合）；`build_index`/`daily_files` 不含 checkpoint（D5）；`test_version_data` | #2 | 1 |
| 7 | `.gitignore` 加入 `data/checkpoints/` 入庫 + `test_gitignore` 斷言；workflow 註記（`git add data/` 已涵蓋；changed 判定含新 checkpoint） | #5、#3 | 3 |
| 8 | 等價回歸整合：`test_crawl_workflow` / scripts 回歸（legacy ↔ checkpoint+稀疏 雙向等價、遷移後首次 run 等價、failed 防線） | #2、#5、#6（#3 若可用） | 4 |
| 9 | 文件同步：README「資料/API 組織」補 `data/checkpoints/` 與 daily 語意、IF/BDD 一致性走查 | #7、#8（本規格 §7 覆蓋矩陣為依據） | 3/4 |
| 10 | 驗收走查：對照 §7 覆蓋矩陣逐項驗證 16 個 Scenario（含 Outline Examples） | #8、#9 | 4 |

> **Phase 依賴說明**：Phase 1（step 2/6）純衍生層可先做、獨立於 crawler；Phase 2（step 1/4/5）crawler 語意；Phase 3（step 3/7/9）遷移與基礎架構；Phase 4（step 8/10）回歸。無循環依賴。

---

## 附錄：與上游文件的雙向引用

- **本文件實作上游**：
  - `docs/bdds/008-sparse-daily-and-checkpoint.feature`（16 Scenario／2 Outline，§7 覆蓋矩陣全對應）
  - `docs/interaction-flows/008-sparse-daily-and-checkpoint.md`（步驟、異常、邊界；§4/§6 對應）
  - `docs/tech-decisions/tech-decision-008-sparse-daily-checkpoint-2026-08-17.md`（方案 S、決策點 D1–D6、任務拆分 T1–T10、Phase 1–4、風險）
  - `docs/tech-decisions/tech-decision-資料拆檔方案-2026-08-17.md`（背景：現行 `data/daily` 契約 v2）
- **本文件整合上游（既有功能契約）**：
  - 001 crawler 管道（diff/apply/save/write_daily 基礎語意）、002 排程與部署（exit code、手動補爬、changed/filename）、007 健康檢查（failed 防線延伸至不寫 / 不遷移）。
- **下游**：`test-plan-generator` 依 008 BDD 產出測試計畫時，以本文件 §1.5/§1.6/§1.8、§6、§8 為實作依據；`loop-review` 可依 §7 覆蓋矩陣與 §8 DAG 檢查完整性。
- **已定案（loop-review 確認）**：遷移 seed=最舊全量 daily、保留所有舊 daily（BDD/IF/tech-decision 三方統一）。
- **已定案**：D2 items gating 影響（`last_seen` 平價日不更新）之既有測試相容性已驗證。
