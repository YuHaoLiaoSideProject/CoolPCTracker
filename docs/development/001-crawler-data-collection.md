# crawler-data-collection — 開發規格

> **對應 Roadmap**：Phase 1 — 對應 `docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md` §4.1 行動計畫 P0 任務群（fetcher / parser / store）與 P1 spec_parser
> **技術決策**：`docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md`
> **操作流程**：`docs/interaction-flows/001-crawler-data-collection.md`
> **BDD**：`docs/bdds/001-crawler-data-collection.feature`
> **測試計畫**：`docs/test-plans/001-crawler-data-collection測試計畫.md`（尚未產出，本規格之 BDD 覆蓋矩陣 §6.1 可作為測試設計依據）
> **狀態**：設計完成，待開發

---

## 概述

每日自動抓取原價屋手機版 9 個分類頁、解析約 1,449 個商品、產生跨日穩定 ID，與既有資料 diff 後僅在價格/狀態異動時增量記錄歷史，並以原子方式輸出 `data/items.json` 與 `data/meta.json`，供前端展示與後續追蹤功能使用。核心包含：

1. **categories.py**：9 個分類頁白名單（G 索引、主分類名、G=9 子分類過濾關鍵字）＋ 名稱正規化 ＋ 商品 ID 產生規則
2. **fetcher.py**：依序抓取 `m-list.php?G=1,3,4,5,6,7,8,9,12`（手機版 UA、CP950 解碼、單頁重試 ≤ 3 次指數退避）
3. **parser.py**：HTML table → RawItem（`<th>` 子分類、`<td>` 商品列、disabled 加購/贈品列過濾、G=9 記憶卡子分類過濾、Hot！/任搭↓N/↘/尾盤標記解析）
4. **spec_parser.py**：商品名 → 結構化規格（深度：CPU/GPU/RAM/SSD/HDD/主機板；輕量：記憶卡/套裝/劈發價組合區）
5. **store.py**：與 `data/items.json` diff（新/價格異動/狀態異動/未變動/gone）、僅異動 append 歷史 `[d,p]`、原子寫檔、`meta.json` 健康指標
6. **main.py**：管道編排（fetch → parse → spec → ID → diff → 健康檢查 → apply → save）+ 驟降保護整合點（007 功能警報 hook）

> 本功能為**純後端資料管道**，無前端、無 HTTP API、無 WebSocket、無 UI。因此 SKILL 章節模板中 §2（前端實作）、§3（API 合約）、§5（生命週期）、§7（CSS）、§9（基礎架構）於本規格標記 N/A。排程 `crawl.yml` 屬功能 002，本規格僅保留其整合點（CLI 冪等、`--date` 手動補爬）。

---

## 1. 後端實作規格

### 1.1 依賴新增

```bash
pip install httpx selectolax pytest
```

- **httpx** ≥ 0.27：HTTP 客戶端（同步 client、timeout、UA headers）
- **selectolax** ≥ 0.3：HTML 解析（Big5 頁面解析速度與健壯性經 Spike 驗證；若遇問題可替換 BeautifulSoup4，parser 介面不變）
- **pytest** ≥ 8：測試框架（parser 以 fixture HTML 測試）

`crawler/pyproject.toml` 宣告：

```toml
[project]
name = "coolpc-crawler"
requires-python = ">=3.12"
dependencies = ["httpx>=0.27", "selectolax>=0.3"]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-mock"]
```

### 1.2 檔案改動總覽

```
coolpc-tracker/
├── .gitignore                        ← 新增：排除 __pycache__、.venv、*.pyc
├── crawler/                          ← 新增：爬蟲套件（本功能）
│   ├── pyproject.toml                ← 新增：依賴與工具設定（上節）
│   ├── __init__.py                   ← 新增：套件標記
│   ├── main.py                       ← 新增：總排程（管道編排 + 驟降保護整合點）
│   ├── fetcher.py                    ← 新增：抓頁 + CP950 解碼 + 重試退避
│   ├── categories.py                 ← 新增：分類白名單 + 名稱正規化 + 商品 ID
│   ├── parser.py                     ← 新增：HTML table → RawItem（過濾 + 標記）
│   ├── spec_parser.py                ← 新增：商品名 → 結構化規格
│   ├── store.py                      ← 新增：diff + 歷史 append + 原子寫檔 + meta
│   └── tests/
│       ├── fixtures/                 ← 新增：9 分類頁 fixture HTML（含特殊字元/disabled/贈品/空表格）
│       ├── test_categories.py        ← 新增：正規化 / ID 穩定
│       ├── test_fetcher.py           ← 新增：重試 / 退避 / CP950（mock httpx）
│       ├── test_parser.py            ← 新增：過濾 / 標記 / G=9 子分類 / 空表格
│       ├── test_spec_parser.py       ← 新增：深度 / 輕量解析
│       └── test_store.py             ← 新增：diff / append / gone / 原子寫入 / meta
├── data/                             ← 新增（git 版控的資料來源真相）
│   ├── items.json                    ← 首次執行由 store 建立
│   └── meta.json                     ← 首次執行由 store 建立
└── docs/
    └── development/
        └── 001-crawler-data-collection.md  ← 本文件
```

### 1.3 categories.py — 分類清單與商品 ID

職責：**單一事實來源**。定義 9 個追蹤分類（Tech Decision §2.3、BDD「爬蟲僅追蹤 9 個指定分類」）、名稱正規化規則、商品 ID 產生規則（BDD「商品 ID 由主分類與正規化名稱的 hash 產生且跨日穩定」）。無外部依賴，任何模組不得硬編碼 G 索引。

```python
"""分類清單與商品 ID 產生規則。來源：Tech Decision §2.3、IF §2 追蹤範圍。"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    """一個手機版分類頁。subcategory_keyword 用於 G=9 混合頁的子分類過濾。"""
    g_index: int                      # m-list.php?G=<index>
    name: str                         # 主分類名稱（ID hash 的輸入之一）
    subcategory_keyword: str | None = None  # G=9 = "記憶卡"，其餘 None
    deep_spec: bool = False           # 深度規格解析分類（CPU/GPU/RAM/SSD/HDD/主機板）

    @property
    def url(self) -> str:
        """完整分類頁 URL（007 meta.sources 與警報所需）。"""
        return f"https://www.coolpc.com.tw/m/m-list.php?G={self.g_index}"


CATEGORIES: tuple[Category, ...] = (
    Category(1, "套裝/準系統"),
    Category(3, "劈發價組合區"),
    Category(4, "CPU", deep_spec=True),
    Category(5, "主機板", deep_spec=True),
    Category(6, "記憶體", deep_spec=True),
    Category(7, "SSD", deep_spec=True),
    Category(8, "HDD", deep_spec=True),
    Category(9, "記憶卡", subcategory_keyword="記憶卡"),  # 僅收錄含「記憶卡」子分類
    Category(12, "顯示卡", deep_spec=True),
)

_CATEGORY_BY_G: dict[int, Category] = {c.g_index: c for c in CATEGORIES}


def get_category(g_index: int) -> Category:
    """依 G 索引取得分類。未知索引拋 KeyError（白名單外的分類永不抓取）。"""


def normalize_name(name: str) -> str:
    """名稱正規化：NFKC（全形→半形）→ casefold → 連續空白收縮 → strip。
    ID 跨日穩定的關鍵；原價屋名稱細節改動不會使 ID 漂移（除非實質改名）。"""
    nfkc = unicodedata.normalize("NFKC", name)
    return re.sub(r"\s+", " ", nfkc).casefold().strip()


def make_item_id(category_name: str, name: str) -> str:
    """商品 ID = sha256(主分類 + '\\0' + 正規化名稱) 取前 16 位 hex。
    同商品跨日重複計算 ID 不變；同日重跑亦不變（BDD ID 穩定）。"""
    payload = f"{category_name}\0{normalize_name(name)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

### 1.4 fetcher.py — 抓頁與解碼

職責：依序抓取 9 個分類頁；單頁失敗自動重試（≤ 3 次、指數退避）；Big5（CP950）解碼（`errors='replace'`）。**並發模型：無**（依序抓取，對來源禮貌性，符合 IF §6「同一時間僅允許一個 run」）。HTTP 逾時上限 20 秒（Tech Decision 建議 10–30 秒區間）。

```python
"""抓取 m-list.php 分類頁：httpx + CP950 解碼 + 重試退避。"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from .categories import CATEGORIES, Category

MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
LIST_URL = "https://www.coolpc.com.tw/m/m-list.php"


class FetchError(Exception):
    """單一頁面在重試上限內仍失敗（由 fetch_all 捕捉並標記 failed）。
    建議攜帶 g_index 與 url（007 警報與 meta.sources 所需），如 FetchError(g, url, msg)。"""


@dataclass
class FetchResult:
    category: Category
    html: str | None      # CP950 解碼後文字；None = 該分類抓取失敗
    raw_bytes: bytes | None


class Fetcher:
    """依序抓取分類頁。重試上限 3 次（BDD「抓取失敗後重試成功恢復」），指數退避 2^n 秒。"""

    def __init__(self, *, timeout: float = 20.0, max_retries: int = 3, backoff_sec: float = 2.0):
        self._client = httpx.Client(timeout=timeout, headers={"User-Agent": MOBILE_UA})

    def fetch_page(self, category: Category) -> bytes:
        """GET m-list.php?G=<g_index> → 回傳原始位元組。
        每次失敗依 retry 次數指數退避；超過 max_retries 拋 FetchError。"""

    def decode(self, raw: bytes) -> str:
        """CP950 解碼，errors='replace'（BDD「CP950 解碼遇特殊字元」：不中斷）。"""

    def fetch_all(self) -> list[FetchResult]:
        """依 CATEGORIES 順序逐頁抓取；單頁失敗 → html=None 記入結果，
        其餘分類照常抓取（BDD「單一分類頁抓取失敗時沿用舊資料並繼續」）。"""
```

### 1.5 parser.py — HTML table 解析

職責：將分類頁 HTML 轉為 RawItem 清單。規則（BDD 商業規則全集）：

- `<th>` = 子分類標題、`<td>` = 商品列
- 過濾 **disabled 加購列**（`input/checkbox` 或 class 含 disabled 之列）與**贈品列**（名稱含「贈品」）
- G=9：僅保留子分類名稱含 `subcategory_keyword`（「記憶卡」）者，排除隨身碟/外接硬碟
- 標記解析：`Hot！` → hot、`任搭↓N` → promo、`↘` → price_drop、`尾盤` → clearance
- 空表格 → 0 商品、不拋例外（BDD edge-case）
- 價格缺失 → `price=None`、不拋例外（BDD edge-case）

```python
"""HTML table → RawItem。過濾 disabled/贈品列；G=9 子分類過濾；標記解析。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .categories import Category

FLAG_HOT = "hot"            # Hot！ 熱賣
FLAG_PROMO = "promo"        # 任搭↓N 促銷（值如 "任搭190"）
FLAG_PRICE_DROP = "price_drop"  # ↘ 降價顯示
FLAG_CLEARANCE = "clearance"    # 尾盤 清倉


@dataclass
class RawItem:
    category: str
    subcategory: str
    name: str
    price: int | None
    flags: dict[str, Any] = field(default_factory=dict)  # hot/promo/price_drop/clearance


@dataclass
class ParseResult:
    category: Category
    items: list[RawItem]
    subcategories: list[str]      # 該頁出現的子分類標題（G=9 過濾判斷依據）


class Parser:
    """selectolax 解析（Spike：vs BeautifulSoup4 擇一，本類別介面不變）。"""

    def parse_page(self, html: str, category: Category) -> ParseResult:
        """完整解析一頁：
        1. 找 table → 以 <th> 切分子分類區塊
        2. 逐商品列 parse → RawItem
        3. 過濾 disabled 加購列 / 贈品列
        4. G=9：僅保留子分類名稱含 category.subcategory_keyword 的商品
        5. 無任何商品列 → 回傳空 list，不拋例外（BDD 空表格）"""

    def _parse_flags(self, cell_text: str) -> dict[str, Any]:
        """標記解析（BDD 商品標記解析 Outline）：
        'Hot！' → {hot: True}；'任搭↓N' → {promo: '任搭<N>'}；
        '↘' → {price_drop: True}；'尾盤' → {clearance: True}；可同時多個。"""

    def _parse_price(self, cell_text: str) -> int | None:
        """價格欄解析；無價格回傳 None（不拋例外）。"""
```

### 1.6 spec_parser.py — 規格解析

職責：依主分類派發解析器。**深度**（CPU/GPU/RAM/SSD/HDD/主機板）：品牌/型號/核心數/執行緒/時脈/TDP/腳位、晶片/VRAM/介面/長度、容量/規格/時脈、容量/介面/轉速等結構化欄位。**輕量**（記憶卡/套裝/劈發價組合區）：僅品牌/型號 + 內容摘要。解析失敗的商品以最少欄位（brand/model=None）輸出，**不得因某欄位缺失而丟棄商品**。

```python
"""商品名 → 結構化規格。深度：CPU/GPU/RAM/SSD/HDD/主機板；輕量：記憶卡/套裝/劈發價。"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Spec:
    """結構化規格（依分類僅填充相關欄位，其餘 None）。"""
    brand: str | None = None
    model: str | None = None
    # 深度分類專屬欄位（範例）：
    # CPU: cores/threads/base_ghz/turbo_ghz/tdp_w/socket
    # 顯示卡: chip/vram_gb/interface/length_mm
    # RAM: capacity/spec/clock_mhz
    # SSD/HDD: capacity_gb/interface/format/rpm
    # 主機板: chipset/socket/form_factor
    extra: dict[str, Any] = field(default_factory=dict)  # 深度分類結構化欄位


# 深度解析器註冊表：主分類名 → 解析函數（正規表示式/關鍵字比對商品名）
_DEEP_PARSERS: dict[str, Callable[[str], Spec]] = {
    "CPU": _parse_cpu,        # 「Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/.../125W」→ cores/threads/ghz/tdp/socket
    "顯示卡": _parse_gpu,     # VRAM、介面、長度
    "記憶體": _parse_ram,     # 容量、規格（DDR4/DDR5）、時脈
    "SSD": _parse_ssd,        # 容量、介面（M.2/SATA）、規格（NVMe）
    "HDD": _parse_hdd,        # 容量、轉速、介面
    "主機板": _parse_mobo,    # 晶片組、腳位、尺寸
}
_LIGHT_PARSERS: dict[str, Callable[[str], Spec]] = {
    "記憶卡": _parse_memory_card,   # 品牌/容量/規格（SD/Micro SD/CFexpress…）
    "套裝/準系統": _parse_prebuilt, # 品牌/型號/用途摘要
    "劈發價組合區": _parse_bundle,  # 組合名稱/內容摘要
}


def parse_spec(category: str, name: str) -> Spec:
    """依主分類派發：深度分類走 _DEEP_PARSERS，輕量分類走 _LIGHT_PARSERS；
    未知分類回傳空 Spec。任何解析例外 → 回傳最少欄位 Spec，不中斷管道（BDD 規格解析 Outline）。"""
```

### 1.7 store.py — diff、歷史 append 與原子寫檔

職責：資料真相的唯一寫入者。與 `data/items.json` 比對、僅異動時 append 歷史、原子寫出 `items.json` + `meta.json`。規則（BDD 全集）：

- 新商品：`first_seen = last_seen = 今日`、`status = in_stock`、history 含一筆 `[今日, 價格]`
- 價格異動：history 尾端 append `[今日, 新價格]`、`last_seen = 今日`
- 消失（今日清單無）：`status = gone`、`last_seen` **保持**最後出現日、**不新增**今日價格歷史
- 價格與狀態皆無異動：**不 append**（BDD 無異動不追加歷史 / 同日重複執行）
- 價格缺失：不記錄該日價格歷史，狀態仍依出現與否判定（BDD 價格缺失）
- 重複名稱：同 ID 視為同一商品，以最後解析到的價格為準（BDD 重複名稱）
- 原子寫入：tempfile + `os.replace`；寫檔失敗不影響既有資料（IF §5）

```python
"""diff → 歷史 append → 原子寫檔。資料真相：data/items.json + data/meta.json。"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

STATUS_IN_STOCK = "in_stock"
STATUS_GONE = "gone"


@dataclass
class Item:
    id: str
    category: str
    subcategory: str
    name: str
    spec: dict[str, Any]
    flags: dict[str, Any]
    status: str = STATUS_IN_STOCK
    first_seen: str = ""
    last_seen: str = ""
    history: list[list] = field(default_factory=list)  # compact [[d, p], ...]；僅異動 append


@dataclass
class DiffResult:
    new_items: list[Item]        # 首次出現
    changed_items: list[Item]    # 價格或狀態異動（將 append 歷史）
    gone_ids: list[str]          # 今日消失（標記 gone）
    unchanged_ids: set[str]      # 維持原樣


class Store:
    """載入既有資料 → diff → apply → 原子寫出。"""

    def __init__(self, data_dir: Path):
        self._items_path = data_dir / "items.json"
        self._meta_path = data_dir / "meta.json"

    def load(self) -> tuple[dict[str, Item], dict[str, Any]]:
        """讀取 items.json（items 依 id 建索引）與 meta.json。
        首次執行（檔案不存在）回傳空 dict；檔案損壞 → 拋例外，由 main 判定不覆寫。"""

    def diff(self, today_items: list[Item], previous: dict[str, Item]) -> DiffResult:
        """逐商品分類：
        - 今日有、舊無 → new_items
        - 兩者皆有且價格或 status 異動 → changed_items
        - 今日無、舊有 → gone_ids
        - 其餘 → unchanged_ids
        重複名稱同 ID 時以最後解析到的價格為準（dict 覆蓋）。"""

    def apply(self, diff: DiffResult, today: date, previous: dict[str, Item]) -> list[Item]:
        """產生新的完整 items 清單：
        - new：first_seen=last_seen=今日，history=[[今日, 價格]]（價格為 None 則空）
        - changed：append [今日, 新價格]（價格為 None 則不 append），last_seen=今日
        - gone：status=gone，last_seen 保持原值，不新增歷史
        - 無異動：原樣保留（含同日重跑 → 末筆歷史已是今日 → 不重複 append）"""

    def save(self, items: list[Item], meta: dict[str, Any]) -> None:
        """原子寫入：tempfile + os.replace（兩檔皆原子）；失敗拋例外且不影響既有檔案。"""

    def write_meta(self, *, crawled_at: str, counts: dict[str, int], total: int,
                   changed: int, failed_categories: list[str], status: str) -> None:
        """輸出 meta.json 基礎欄位（crawled_at / counts / total / changed / failed_categories / status）。
        status 僅取 ok / partial / failed（007 健康模組定義，不再有 aborted）。
        完整模型（含 sources / anomaly / previous_total / checked_at）由 007 build_meta 擴充；
        注意：本方法必須自上次 meta.json 沿用 `previous_total`，
        不得因覆寫而遺失（否則 007 驟降偵測的 prev 判定失效）。"""
```

### 1.8 main.py — 管道編排

職責：串起完整管道並做健康檢查。**驟降保護整合點**：健康檢查規則由功能 007 `crawler/health.py` 正式化（商品總數為 0、較前次驟降 > 20%、parser 例外、全部抓取失敗 → 判定 `failed`）；`failed` → 不覆寫資料、發管理員警報（`notify` hook 由功能 007 telegram_bot 注入）、`meta.status = "failed"`、return 1。**002 整合點**：`python -m crawler.main` 冪等可重跑；`--date` 支援 workflow_dispatch 手動補爬（歷史以實際爬取日記錄）。

```python
"""總排程：fetch → parse → spec → ID → diff → 健康檢查 → apply → save。"""
from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path

from .categories import CATEGORIES, make_item_id
from .fetcher import Fetcher
from .parser import Parser, RawItem
from .spec_parser import parse_spec
from .store import Store, Item

DROP_THRESHOLD = 0.20   # 商品數驟降保護門檻（與 007 功能共用）
NotifyFn = Callable[[str], None]  # 007 telegram 警報 hook


def run_crawler(data_dir: Path, today: date | None = None, notify: NotifyFn | None = None) -> int:
    """執行完整管道，回傳 exit code（002 契約：0 成功含 partial；1 健康檢查擋下（failed）不覆寫；2 其他執行失敗）。

    1.  fetcher.fetch_all() 依序抓 9 頁（單頁失敗 → html=None，記入 failed_categories）
    2.  逐頁 CP950 解碼（fetcher.decode）+ parser.parse_page → RawItem（G=9 子分類過濾含在此）
    3.  每筆 RawItem：parse_spec() 取得 spec → make_item_id() 產生 ID → Item
    4.  健康檢查：規則以 007 health.compute_status 為準（total==0、降幅 > DROP_THRESHOLD、parser 例外、
        全部抓取失敗 → failed；部分分類失敗 → partial）
        → failed：notify(警報文案)、meta.status="failed"、不覆寫 → return 1
        → partial：成功分類更新、失敗分類沿用舊資料（merge）、meta.status="partial" → return 0
    5.  store.diff() → store.apply()（僅異動 append [d,p]）→ store.save()
    6.  meta：crawled_at=UTC now、counts、total、previous_total、changed、failed_categories、
        status（ok/partial/failed）、sources、anomaly（007 擴充）→ 寫出
    7.  輸出執行摘要 log（各分類商品數、異動數、失敗分類）"""


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：
    python -m crawler.main [--data-dir data] [--date YYYY-MM-DD]
    --date 供 workflow_dispatch 手動補爬（002 整合點）；重複執行冪等（同日同價不重複 append）。"""
    parser = argparse.ArgumentParser(prog="crawler")
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--date", default=None, help="實際爬取日 YYYY-MM-DD（預設今日 UTC）")
    args = parser.parse_args(argv)
    today = date.fromisoformat(args.date) if args.date else date.today()
    return run_crawler(args.data_dir, today=today)


if __name__ == "__main__":
    raise SystemExit(main())
```

### 1.9 測試策略

- **fixture 為先**：`tests/fixtures/` 存放 9 個分類頁的樣本 HTML（含特殊字元、disabled 加購列、贈品列、空表格、四種標記），parser 測試不依賴真實網路
- fetcher 以 `pytest-mock` mock `httpx.Client`（首次失敗 → 重試成功、連 3 次失敗、逾時）
- store 以 tmp_path 驗證原子寫入與既有資料不被破壞
- 端到端冒煙：以 fixture 資料跑完整 `run_crawler()` 兩天，驗證 ID 穩定、僅異動 append、同日重跑冪等

---

## 2. 前端實作規格

N/A — 本功能為純後端資料管道，無前端改動（前端讀取 `data/*.json` 屬功能 003+）。

## 3. API / Message 合約

N/A — 爬蟲輸出直接寫入 git 版控的 `data/*.json`，不經 HTTP API。唯一「外部介面」為 CLI（§1.8）與 007 功能的 `notify` hook。

## 4. 資料流

### 4.1 管道總覽

```mermaid
flowchart TD
    A[依序抓取 9 分類頁<br/>m-list.php?G=1,3,4,5,6,7,8,9,12] --> B[CP950 解碼<br/>errors=replace]
    B --> C[table 解析 → RawItem<br/>過濾 disabled/贈品列]
    C --> D[G=9 子分類過濾<br/>子分類名含「記憶卡」]
    D --> E[spec_parser<br/>深度/輕量規格解析]
    E --> F[make_item_id<br/>sha256 主分類+正規化名稱]
    F --> G{diff 與 items.json 比對}
    G --> H1[新商品]
    G --> H2[價格/狀態異動]
    G --> H3[今日消失]
    G --> H4[無異動]
    H1 --> I[first_seen=last_seen=今日<br/>history=[[今日,價格]]]
    H2 --> I2[append [今日,新價格]<br/>last_seen=今日]
    H3 --> I3[status=gone<br/>last_seen 保持<br/>不新增歷史]
    H4 --> I4[維持原樣不 append]
    I & I2 & I3 & I4 --> J{健康檢查<br/>total=0 或驟降>20%?}
    J -- 否 --> K[原子寫入 items.json + meta.json]
    J -- 是 --> L[不覆寫 + 007 警報 hook<br/>meta.status=failed]
    K --> M[結束<br/>meta 記錄 crawled_at/計數/失敗分類]
```

### 4.2 步驟分解

| 步驟 | 產出 | 模組 | 關鍵規則 |
|------|------|------|---------|
| 1 抓取 | 9 頁原始位元組 | fetcher | 依序、單頁重試 ≤3 次退避、失敗頁 html=None |
| 2 解碼 | UTF-8 文字 | fetcher | CP950 + errors='replace' |
| 3 解析 | RawItem 清單 | parser | `<th>` 子分類、`<td>` 商品列、過濾 disabled/贈品、標記解析 |
| 4 過濾 | 收斂後清單 | parser | G=9 僅子分類含「記憶卡」（4 子分類收錄、隨身碟/外接碟排除） |
| 5 規格化 | Spec | spec_parser | 深度 6 類 / 輕量 3 類；解析失敗不丟商品 |
| 6 diff | DiffResult | store | 新/異動/gone/未變動；同 ID 重複名稱取最後價格 |
| 7 append | 新 items 清單 | store | 僅異動 append `[d,p]`；gone 不新增；無異動原樣 |
| 8 健康檢查 | 通過/擋下 | main | 規則依 007 health 正式化：total=0 / 降幅 >20% / parser 例外 / 全部失敗 → failed 不覆寫 + 警報；部分失敗 → partial 合併 |
| 9 寫檔 | items.json + meta.json | store | 原子寫入；meta 含 crawled_at/計數/失敗分類/健康指標 |

### 4.3 data/items.json 結構

```jsonc
{
  "meta": {
    "crawled_at": "2026-08-16T06:00:00Z",
    "source": "https://www.coolpc.com.tw/m/m-list.php"
  },
  "items": [
    {
      "id": "3f9a1c2b8e4d5f6a",
      "category": "CPU",
      "subcategory": "Intel 第14代",
      "name": "Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】",
      "spec": {
        "brand": "Intel", "model": "i5-13600K",
        "cores": 14, "threads": 20,
        "base_ghz": 3.5, "turbo_ghz": 5.1, "tdp_w": 125, "socket": "LGA1700"
      },
      "flags": { "hot": false, "promo": "任搭190", "price_drop": true, "clearance": false },
      "status": "in_stock",              // in_stock / gone
      "first_seen": "2026-08-15",
      "last_seen": "2026-08-16",
      "history": [                       // compact [d, p]；僅價格/狀態異動時 append
        ["2026-08-15", 9990],
        ["2026-08-16", 9790]
      ]
    }
  ]
}
```

> **格式決策**：history 採用 compact `[d, p]` 陣列（即 Tech Decision §4.1 P2「minify（compact arrays）」自第一天落實），控制 repo 體積。若日後需可讀性可切回 `{"d": ..., "p": ...}` object，diff/apply 介面不變。

### 4.4 data/meta.json 結構

```jsonc
{
  "crawled_at": "2026-08-16T06:00:00Z",
  "source": "https://www.coolpc.com.tw/m/m-list.php",
  "counts": { "CPU": 48, "主機板": 373, "記憶體": 216, "顯示卡": 255, "SSD": 171, "HDD": 89, "套裝/準系統": 157, "劈發價組合區": 86, "記憶卡": 54 },
  "total": 1449,
  "previous_total": 1449,               // 上次有效總數（007 驟降偵測基準，本次沿用上次）
  "changed": 12,
  "failed_categories": ["主機板"],       // 本次抓取失敗而沿用舊資料的分類
  "status": "partial",                  // ok / partial / failed（007 三態；部分分類失敗為 partial）
  "sources": {                           // 007 擴充：來源頁面資訊（URL / G 索引 / 抓取結果）
    "5": { "g": 5, "url": "https://www.coolpc.com.tw/m/m-list.php?G=5", "fetched": false, "parsed": false, "count": null, "error": "timeout after 3 retries" }
  }
}

> **meta.json 完整模型**：`checked_at` / `anomaly` / `previous_total` / `sources` 等欄位由功能 007（§1.3 / §6.6）擴充並維護；本節為 001 產出的基礎欄位，status 語意與三態枚舉以 007 為準。meta.json **不再含 `version`**（版本發現改由前端 runtime 讀 `api/index.json` 的 `latest_file`／`files[]`，由 002 `version_data.py` 維護）。
```

---

## 5. 生命週期

N/A — 無連線管理/狀態機（爬蟲為一次性的排程批次；「同一時間僅允許一個 run」由 GitHub Actions 單一 cron 行程保證，無需程式內鎖）。

## 6. 邊界條件處理

### 6.1 BDD 覆蓋矩陣

| # | BDD Scenario | 對應處理 | 實作位置 |
|---|-------------|---------|---------|
| 1 | 每日排程完整執行爬蟲管道（smoke） | §1.8 管道編排、§4 資料流 | main.py |
| 2 | 新商品首次出現 | first_seen/last_seen=今日、in_stock、history 一筆 | store.apply |
| 3 | 商品價格異動時追加歷史（Outline） | append `[今日, 新價格]`、last_seen=今日 | store.apply |
| 4 | 商品從分類頁消失時標記為 gone | status=gone、last_seen 保持、不新增歷史 | store.apply |
| 5 | 價格與狀態皆無異動時不追加歷史 | diff 未變動 → 原樣 | store.diff/apply |
| 6 | 商品 ID 由主分類與正規化名稱 hash 產生且跨日穩定 | §1.3 normalize_name + make_item_id | categories |
| 7 | 爬蟲僅追蹤 9 個指定分類 | CATEGORIES 白名單，其餘 G 不抓取 | categories/fetcher |
| 8 | G=9 僅收錄子分類名稱含「記憶卡」 | subcategory_keyword 過濾（4 收錄/2 排除） | categories/parser |
| 9 | parser 過濾 disabled 加購列與贈品列 | 列特徵過濾 | parser.parse_page |
| 10 | 商品標記解析（Outline 4 例） | hot/promo/price_drop/clearance | parser._parse_flags |
| 11 | 規格解析依分類深度或輕量（Outline 9 例） | _DEEP_PARSERS / _LIGHT_PARSERS 派發 | spec_parser |
| 12 | 單一分類頁抓取失敗沿用舊資料並繼續 | fetch_all html=None → 舊資料合併 + meta failed | fetcher/store/main |
| 13 | 抓取失敗後重試成功恢復（Outline） | 重試 ≤3 次退避，成功即繼續 | fetcher.fetch_page |
| 14 | 商品數驟降 >20% 不覆寫資料並發警報 | DROP_THRESHOLD 健康檢查 + notify hook（007 health 判定 failed） | main/health |
| 15 | HTML 改版解析出 0 商品 | total=0 → 同驟降處理（007 規則 3），meta.status=failed | main/health |
| 16 | 分類頁為空表格 | 0 商品不拋例外；該分類沿用既有資料（007 health 規則 4 判 partial → merge_items 保留） | parser/main、007 health |
| 17 | CP950 解碼遇特殊字元 | errors='replace'，不中斷 | fetcher.decode |
| 18 | 同分類重複名稱商品 | 同 ID 視同一商品，最後解析價為準 | store.diff |
| 19 | 商品價格資訊缺失 | 不記錄該日價格歷史、狀態照判 | parser/store |
| 20 | 排程延遲後手動補爬 | CLI `--date` / workflow_dispatch（002） | main |
| 21 | 同日重複執行不重複追加歷史 | 末筆歷史已是今日 → 不重複 append | store.apply |

### 6.2 邊界情境細節

| 情境 | 策略 |
|------|------|
| **G=9 混合頁過濾**（BDD #8） | 子分類標題（`<th>`）含「記憶卡」才收錄（Micro SD / SD / CFexpress / MicroSDXC Express 4 個子分類）；隨身碟、外接硬碟、其他子分類整段排除 |
| **disabled 加購列 / 贈品列**（BDD #9） | disabled 列以 HTML 特徵（disabled input/checkbox、class 含 disabled）判斷；贈品列以名稱含「贈品」判斷；兩者皆不進入 RawItem |
| **標記組合**（BDD #10） | 四種標記可同時存在（如「Hot！＋任搭↓190」→ flags 同時含 hot 與 promo）；標記文字須自商品名剝離，不污染名稱正規化 |
| **無異動不 append**（BDD #5、#21） | diff 以「價格 + status」為異動判準；同日重跑時末筆歷史日期 == 今日且價格相同 → 視為無異動，不重複 append |
| **ID 穩定**（BDD #6） | NFKC + casefold + 空白收縮後 hash；商品名稱細節改動（全形/半形、空格）不影響 ID；實質改名則視為「消失 + 新增」（IF §5 列為已知限制，merge 策略屬後續強化） |
| **驟降保護**（BDD #14、#15） | total==0 或降幅 > DROP_THRESHOLD（0.20）→ 不覆寫 items.json、notify 警報（007 hook）、meta.status="failed"（007 三態之一）、return 1；邊界：恰等於 80% 不判異常（007 §6.1） |
| **分類頁失敗沿用舊資料**（BDD #12、#16） | 該分類本次無新資料 → diff 時該分類既有商品視為「未變動」保留原樣（不誤判 gone）；meta.failed_categories 記錄之 |
| **價格缺失**（BDD #19） | `price=None` → 該日不 append 歷史；商品若在清單中 status 仍 in_stock |
| **重複名稱**（BDD #18） | 同分類同名 → 同 ID → dict 合併以最後解析價格為準，不產生第二筆 |
| **特殊字元**（BDD #17） | CP950 解碼 errors='replace'；fixture 涵蓋（如「·」「◆」等） |
| **空表格**（BDD #16） | parse 回傳空 list 不拋例外；該分類由 007 health 規則 4 判定為失敗分類（count==0 且上次有商品）→ partial → merge_items 沿用既有資料、不標 gone；全部分類皆 0 → 規則 3（total==0）判 failed |

## 7. CSS 關鍵樣式

N/A — 無 UI 元件。

## 8. 開發順序

依賴為 DAG（categories 為所有模組的基礎，main 為最後整合）：

| 步驟 | 內容 | 依賴 |
|------|------|------|
| 1 | 專案初始化：`crawler/` 套件、pyproject.toml、pytest 設定、.gitignore、`data/` 目錄 | - |
| 2 | `categories.py` + test_categories（正規化、ID 穩定、9 分類白名單） | #1 |
| 3 | `fetcher.py` + test_fetcher（mock httpx：重試/退避/CP950/失敗頁） | #1, #2 |
| 4 | `parser.py` + fixture HTML + test_parser（disabled/贈品/G=9 子分類/標記/空表格/重複名稱/價格缺失） | #2 |
| 5 | `spec_parser.py` + test_spec_parser（9 分類深度/輕量、解析失敗不丟商品） | #2 |
| 6 | `store.py` + test_store（diff 分類、append 條件、gone、原子寫入、meta、同日冪等） | #2 |
| 7 | `main.py` 整合 + 端到端冒煙測試（fixture 資料連跑兩日：ID 穩定、僅異動 append、meta 輸出） | #3, #4, #5, #6 |
| 8 | A/B 來源驗證 spike：手機版 vs 桌面版商品集合比對，確認無漏品（Tech Decision §4.2） | #4 |
| 9 | 健康檢查整合點驗收：降幅 >20% / 0 商品 / parser 例外 → 不覆寫 + notify hook + meta.status="failed"（007 正式化） | #7 |
| 10 | 002 整合點預留：CLI `--date`、冪等重跑（供 workflow_dispatch 手動補爬與 cron 串接） | #7 |

**驗收檢查清單**（對應 IF §7）：每日 06:00 UTC cron 觸發（002 驗證）、9 頁依序抓取成功、CP950 正確解碼、解析約 1,449 商品且主/子分類正確、disabled 加購與贈品列排除、G=9 僅 4 個記憶卡子分類、四種標記正確、深度/輕量規格正確、ID 跨日/同日重跑一致、僅異動 append `[d,p]`、新商品 first_seen=今日、消失標記 gone 且 last_seen 保持、單頁失敗重試 ≤3 次且沿用舊資料並標記 meta、驟降 >20% 或 0 商品不覆寫並警報、items.json/meta.json 正確輸出（meta 含 crawled_at/計數/健康指標）、寫檔失敗不影響既有資料。

## 9. 基礎架構設定

N/A（本功能）— GitHub Actions 排程與 Pages 部署屬功能 002（`crawl.yml`）。本規格僅定義其整合契約：

- **觸發**：`cron: 0 6 * * *`（每日 06:00 UTC）+ `workflow_dispatch`（手動補爬）
- **執行**：`pip install -e crawler/ && python -m crawler.main --data-dir data`（冪等，可安全重跑）
- **資料提交**：run 成功後 git commit `data/items.json` + `data/meta.json`（僅異動時 commit）
- **警報**：007 功能將 `telegram_bot.py` 包裝為 `notify` hook 注入 `run_crawler()`，本功能僅定義簽名 `Callable[[str], None]`
