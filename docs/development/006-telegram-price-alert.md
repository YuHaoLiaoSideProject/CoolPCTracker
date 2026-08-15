# Telegram 降價通知 — 開發規格

> **對應 Roadmap**：Phase 2（P2）— `docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md` §4.1「Telegram bot：輪詢 /watch、目標價、降價通知」
> **技術決策**：`docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md`（§3.1 技術棧、§3.2 步驟⑤ telegram、§3.3 `data/telegram.json`、§5 風險登錄）
> **操作流程**：`docs/interaction-flows/006-telegram-price-alert.md`
> **BDD**：`docs/bdds/006-telegram-price-alert.feature`
> **整合功能**：001（`data/items.json` 來源）、002（每日 run 觸發與 commit）、007（管理員警報共用傳訊）
> **狀態**：設計完成，待開發

## 概述

讓 Telegram 使用者以 Bot 指令（`/start` `/watch` `/unwatch` `/list` `/help`）訂閱原價屋商品與目標價，系統在每日爬蟲 run 中輪詢指令、比對當日價格，現價 ≤ 目標價（等於也算）或商品消失時主動推送通知。核心包含：

1. **`crawler/telegram_bot.py`**：Bot API 薄客戶端（httpx 直呼 getUpdates/sendMessage，無 framework）＋指令處理＋通知產生＋`data/telegram.json` 狀態維護
2. **`data/telegram.json`**：update offset + 使用者追蹤清單（git 版控），本次 run 的狀態持久化點
3. **`scripts/telegram_hook.py` 整合點（002 預留）**：每日 run 中「telegram 階段」的進入點，呼叫 `crawler.telegram_bot.run_telegram_phase`，token 存 GitHub Actions secrets
4. **通知產生器**：降價通知（商品名/現價/目標價/歷史最低）與消失通知（商品名/最後價格/消失日期）

一句話：**免安裝 App、免註冊、免常駐伺服器**，每日一次的 getUpdates 輪詢即可完成指令處理與降價通知。

---

## 1. 後端實作規格

### 1.1 依賴

| 依賴 | 版本 | 用途 | 狀態 |
|------|------|------|------|
| Python | 3.12 | 執行環境 | 已在（002 setup-python） |
| httpx | 最新 | Telegram Bot API HTTP 呼叫 | 已存在（001 fetcher 共用），**無新增依賴** |
| pytest | - | telegram 模組單元測試 | 已在（tech-decision §3.1） |

無 framework、無 `python-telegram-bot`：依 tech-decision 決策直接以 httpx 呼叫 REST API，控制面與量級完全可預期。

### 1.2 檔案改動總覽

```
coolpc-tracker/
├── crawler/
│   ├── telegram_bot.py               ← 新增：本功能核心模組（見 §1.3）
│   └── telegram_bot_test.py          ← 新增：pytest 單元測試（指令/比對/通知/run）
├── scripts/
│   └── telegram_hook.py              ← 修改：置換 002 預留的整合點佔位，呼叫 run_telegram_phase()（§1.4）
├── data/
│   └── telegram.json                 ← 首次 run 建立（git 版控）：offset + 使用者追蹤清單
└── .github/workflows/
    └── crawl.yml                     ← 修改：env 注入 TELEGRAM_BOT_TOKEN（§1.4、002 整合）
```

### 1.3 `crawler/telegram_bot.py` 模組規格

模組職責與對外介面：

```
職責：
 1. getUpdates 輪詢（offset 推進、去重）處理使用者指令
 2. 依追蹤清單比對當日 items.json → 降價 / 消失通知
 3. 維護 data/telegram.json（offset + 追蹤清單）並原子寫回
 4. token 無效 / 網路失敗時降級：記錄錯誤、不影響資料 commit 與部署（BDD S24/S25）

對外介面：
 async run_telegram_phase(items, token) -> TelegramRunResult   ← 002 整合點 scripts/telegram_hook.py 的唯一進入點
 load_state() / save_state() / parse_command() / fuzzy_match()  ← 供單元測試直接呼叫

並發模型：無並發。每日單一 run 依序處理（002 concurrency group 已保證單一 run），
           每日訊息量低，不需 rate limit 節流（flow §6）。
```

#### 1.3.1 資料模型與 `telegram.json` I/O

```python
# crawler/telegram_bot.py
"""Telegram 降價通知 Bot（功能 006）。無框架，httpx 直呼 Telegram Bot API。"""

from __future__ import annotations

import json, logging, os, re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"
MAX_WATCH_PER_USER = 20            # 每使用者追蹤上限（flow §6 / BDD S12）
TELEGRAM_STATE_PATH = Path("data/telegram.json")
LONG_POLL_TIMEOUT = 30             # getUpdates long-poll 秒數
NETWORK_TIMEOUT = 60.0             # httpx 逾時，須 > LONG_POLL_TIMEOUT
POLL_RETRIES = 2                   # getUpdates 網路失敗重試次數（BDD S25）

@dataclass
class WatchItem:
    """單筆追蹤商品（telegram.json users[chat_id] 的元素）。"""
    item_id: str          # items.json 的商品 id（001 產生，跨日穩定）
    name: str             # 商品名稱快照（消失後通知/清單仍可顯示）
    target_price: int     # 目標價（正整數，新台幣）
    added_at: str         # 加入日期 YYYY-MM-DD

@dataclass
class TelegramState:
    """data/telegram.json 的記憶體表示。"""
    offset: int | None                 # 已處理的最後一筆 update_id（None = 首次）
    users: dict[str, list[WatchItem]]  # Telegram chat_id(str) → 追蹤清單

    def to_dict(self) -> dict[str, Any]:
        """序列化（含 schema_version，供日後遷移）。"""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelegramState:
        """反序列化；缺欄位以安全預設補齊（向前相容）。"""

@dataclass(frozen=True)
class ItemRef:
    """telegram 模組所需的商品視圖（由 001 store 結果轉換，不直接依賴 items.json schema）。"""
    item_id: str
    name: str
    price: int | None        # 當日現價；None = 當日無價格資料
    status: str              # "in_stock" | "gone"
    lowest_price: int | None # history 最小值（含今日）；None = 無歷史
    gone_date: str | None    # 消失日期（status=gone 時 = last_seen）

@dataclass
class TelegramRunResult:
    """單次 telegram 階段執行結果（供 telegram_hook 判斷）。"""
    success: bool            # False = token 無效 / getUpdates 重試仍失敗
    updates_processed: int
    notifications_sent: int
    error: str | None

def load_state(path: Path = TELEGRAM_STATE_PATH) -> TelegramState:
    """讀取 telegram.json；檔案不存在 → 空狀態（offset=None, users={}）。
    解析失敗（狀態損毀）→ 備份壞檔為 *.corrupt-<ts> 後回傳空狀態，避免 run 無法啟動。"""

def save_state(state: TelegramState, path: Path = TELEGRAM_STATE_PATH) -> None:
    """寫入暫存檔後 os.replace() 原子替換；僅在本次 run 有變更時呼叫。"""
```

#### 1.3.2 Bot API 客戶端

```python
class TelegramAuthError(Exception):
    """Bot token 無效（HTTP 401）。"""

class TelegramBot:
    """Telegram Bot API 客戶端（httpx 薄封裝）。"""

    def __init__(self, token: str, client: httpx.AsyncClient | None = None) -> None:
        self._token = token
        self._client = client or httpx.AsyncClient(timeout=NETWORK_TIMEOUT)

    def _url(self, method: str) -> str:
        return API_BASE.format(token=self._token, method=method)

    async def get_updates(self, offset: int | None, timeout: int = LONG_POLL_TIMEOUT) -> list[dict[str, Any]]:
        """呼叫 getUpdates。
        - offset: state.offset + 1（跳過已處理；見 §5 offset 狀態機）；None = 首次
        - 回傳 updates 列表（每筆含 update_id / message）
        - 401 → raise TelegramAuthError
        - 網路錯誤 → 由呼叫端重試（POLL_RETRIES 次）
        """

    async def send_message(self, chat_id: int | str, text: str) -> bool:
        """呼叫 sendMessage；成功 True。
        401 → raise TelegramAuthError；其餘失敗 log 後回傳 False（不中斷階段）。"""

    async def aclose(self) -> None:
        """關閉 httpx client。"""
```

#### 1.3.3 指令解析

```python
COMMANDS = {"/start", "/watch", "/unwatch", "/list", "/help"}

def parse_command(text: str) -> tuple[str, list[str]] | None:
    """解析指令文字。
    "/watch i5-13600K 9000" → ("watch", ["i5-13600K", "9000"])
    "/list"                → ("list", [])
    非 / 開頭、非已知指令、或無 text 的訊息（貼圖/照片）→ None（回覆「不認識」或忽略）"""

def parse_watch_args(args: list[str]) -> tuple[str, int] | None:
    """解析 /watch 參數：最後一個 token 必須為正整數（≥1），其餘 join 為關鍵字。
    - args < 2（缺目標價）→ None（格式錯誤）
    - 目標價非純數字、為 0、負數、含小數/逗號 → None（格式錯誤）
    - 回傳 (關鍵字, 目標價)；前導零允許（"09000" → 9000）"""
```

#### 1.3.4 模糊比對（設計決策：關鍵字型態比對）

```python
def normalize_text(s: str) -> str:
    """正規化：lower、全形→半形、移除空白/全形空白/星號等。
    「rtx 4060」與「RTX 4060」→ 同一 token，BDD S4 三種關鍵字型態皆可命中。"""

def fuzzy_match(keyword: str, items: list[ItemRef]) -> list[ItemRef]:
    """關鍵字模糊比對當日商品清單（僅限當日 9 分類 ≈ 1,449 商品，非全站）。
    規則：keyword 與 name 皆 normalize_text() 後，name 包含 keyword（substring）即符合。
    回傳全部符合者；呼叫端依數量分支：0 個 → 找不到；1 個 → 加入/更新；≥2 個 → 候選清單。"""
```

#### 1.3.5 指令處理（純函式：輸入 state + items，輸出回覆文字 + 新 state）

```python
def build_help_text() -> str:
    """使用說明（/start 與 /help 共用，BDD S1/S2）。"""

def handle_start() -> str:
    """回覆使用說明。"""

def handle_watch(chat_id: str, args: list[str], state: TelegramState,
                 items: list[ItemRef]) -> tuple[str, TelegramState]:
    """處理 /watch（BDD S3–S12）。
    流程：
    1. parse_watch_args 失敗 → 格式錯誤訊息（含範例），state 不變
    2. fuzzy_match：0 個 → 找不到提示；≥2 個 → 候選清單（名稱+現價），不自動加入，state 不變
       1 個 → 繼續
    3. 新增檢查：len(users[chat_id]) >= MAX_WATCH_PER_USER → 上限訊息，state 不變
       （更新既有商品目標價不受上限限制）
    4. 已存在（同 item_id）→ 更新 target_price，回覆「目標價已更新」
    5. 新增 WatchItem；若現價 ≤ 目標價 → 回覆確認 + 「目前價格已達目標價」"""

def handle_unwatch(chat_id: str, args: list[str], state: TelegramState) -> tuple[str, TelegramState]:
    """處理 /unwatch（BDD S13/S14）：
    以關鍵字對「追蹤清單內商品名稱」做 fuzzy_match，唯一符合才移除；
    多個符合 → 回覆候選請更精確（不自動移除）；不在清單 → 「該商品不在追蹤清單」。"""

def handle_list(chat_id: str, state: TelegramState, items_by_id: dict[str, ItemRef]) -> str:
    """處理 /list（BDD S15/S16）：
    空清單 → 「目前沒有追蹤任何商品」+ 提示 /watch；
    否則逐筆：商品名、目前價格（當日無資料顯示「—」）、目標價。"""

def handle_unknown() -> str:
    """未知指令回覆（BDD S17）。"""
```

#### 1.3.6 每日通知（系統自動觸發）

```python
def evaluate_notifications(state: TelegramState,
                           items_by_id: dict[str, ItemRef]) -> list[tuple[str, str]]:
    """比對追蹤清單與當日 items.json（BDD S18–S22）。
    每筆 WatchItem：
    - 商品有當日價格：price <= target_price → 降價通知（等於也算，BDD S19）
                         否則 → 不發送（未達標且未消失，BDD S21）
    - status=gone → 消失通知（BDD S20）
    - 商品不在 items_by_id 或 price=None → 跳過，保留於追蹤清單（BDD S22）
    回傳 [(chat_id, message_text), ...]"""

def format_price_alert(item: WatchItem, current_price: int, lowest_price: int | None) -> str:
    """降價通知範本（見 §3.4）。"""

def format_gone_alert(item: WatchItem, last_price: int | None, gone_date: str) -> str:
    """消失通知範本（見 §3.4）。"""
```

#### 1.3.7 run 整合入口

```python
async def run_telegram_phase(items: list[ItemRef], token: str,
                             state_path: Path = TELEGRAM_STATE_PATH) -> TelegramRunResult:
    """每日 telegram 階段（002 整合點，爬蟲成功後、commit 前執行；見 §5.3）。

    順序：
    1. load_state()
    2. getUpdates(offset=state.offset + 1 if state.offset is not None else None)
       - TelegramAuthError → log + 回傳 success=False（不發送任何訊息；不寫回）
       - 網路失敗 → 退避重試 POLL_RETRIES 次，仍失敗 → log + 回傳 success=False
         （offset 不變 → 下次 run 不遺漏，BDD S25）
    3. 逐筆處理新 update：parse_command → 對應 handler → send_message 回覆
       - 每筆成功處理後記錄 update_id，最終 state.offset = max(已處理 update_id)（BDD S23）
       - 本次 run 內以「已處理 update_id 集合」防呆去重
       - 單筆 send_message 失敗（非 401）→ log 後繼續，不中斷
    4. evaluate_notifications() → 逐筆 send_message
    5. 僅在 2–4 無致命失敗時 save_state() 原子寫回（token 無效/網路失敗 → 不寫回，
       BDD S24/S25：telegram.json 維持不變）
    """
```

### 1.4 `scripts/telegram_hook.py`（002 整合點）

002 已於 crawl job 中預留「Telegram 通知整合點」step（位於**資料 commit 之前**，見 002 §1.4/§1.6）；006 實作時置換該 script 主體，呼叫 `run_telegram_phase`：

```python
#!/usr/bin/env python3
# scripts/telegram_hook.py（006 實作後）
import asyncio
import json
import os
import sys
from pathlib import Path
from crawler.telegram_bot import run_telegram_phase, ItemRef


def to_item_refs() -> list[ItemRef]:
    """由 001 產出的 data/items.json 轉換 ItemRef（001 store 結果即當日商品清單）：
    price=末筆歷史 p、status=in_stock/gone、lowest_price=history 最小值（無歷史視同現價）、
    gone_date=status=gone 時的 last_seen。"""
    # TODO: 讀 data/items.json → 逐筆建 ItemRef（item_id/name/price/status/lowest_price/gone_date）


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("[telegram-hook] 未設定 TELEGRAM_BOT_TOKEN；整合點已觸發但尚未啟用")
        return 0
    items = to_item_refs()
    result = asyncio.run(run_telegram_phase(items=items, token=token))
    if not result.success:
        # token 無效 / 網路失敗：僅 log；不影響資料 commit 與部署（BDD S24/S25）
        print(f"[telegram-hook] telegram 階段失敗（不影響資料 commit 與部署）: {result.error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

> 說明：telegram 階段**不寫入 crawler/main.py**（001 保持純資料管道、exit code 契約不受影響）；健康檢查 failed 時爬蟲步驟以非 0 結束 → 工作流在 telegram step 前即停止，telegram 階段自然略過（對應 007 flow §5「爬蟲整體失敗 → telegram 通知階段不執行」）。

`crawl.yml` 修改（002 整合）：

```yaml
jobs:
  crawl:
    env:
      TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}   # 006 需要
      TELEGRAM_ADMIN_CHAT_ID: ${{ secrets.TELEGRAM_ADMIN_CHAT_ID }}  # 007 需要
    steps:
      # ... checkout / setup-python / pip install ...
      - run: python -m crawler.main          # 001（含 007 健康檢查與管理員警報）
      - run: python scripts/version_data.py  # 002：異動判定 + 版本化
      - run: python scripts/telegram_hook.py # 006：commit 前執行，telegram.json 異動併入本次 commit
        continue-on-error: true
      # ... commit data/（items.json + meta.json + telegram.json）→ build → deploy（002）...
```

> **整合點調整說明（002）**：002 已依 006 flow §B5「telegram.json 與 items.json 一併 commit」調整順序為 **store 寫檔 → telegram 階段 → 單次 commit（items.json + meta.json + telegram.json）→ build → deploy**，單一 commit 保持兩檔一致；telegram 階段無異動時（token 未設定/無新訊息）telegram.json 不變，commit 照常僅含資料檔。

### 1.5 跨功能整合點

| 功能 | 整合方式 |
|------|---------|
| **001（items.json 來源）** | telegram 階段的比對資料完全來自 001 store 產出的當日商品清單（hook 讀取 data/items.json 轉換 ItemRef）；`ItemRef` 轉換規則：`price`=當日現價、`status`=in_stock/gone、`lowest_price`=history 最小值（無歷史時視同現價）、`gone_date`=status=gone 時的 last_seen。001 商品數驟降保護（007）失敗時 telegram 階段不執行（爬蟲步驟非 0 結束 → 後續 step 不執行） |
| **002（每日 run 觸發）** | telegram 階段由 `scripts/telegram_hook.py` 在爬蟲成功後、**資料 commit 前**執行（002 §1.6 預留整合點）；token 由 crawl.yml secrets 注入；本階段失敗不影響資料 commit、build 與 Pages 部署（BDD S24） |
| **007（警報共用傳訊）** | 007 管理員警報與 006 共用同一 Bot token 與 sendMessage 機制：007 為單向警報（chat_id 固定為 secrets 的 `TELEGRAM_ADMIN_CHAT_ID`），006 為互動式（chat_id 來自使用者訊息）。實作上建議將「token 讀取 + sendMessage 原語」抽為共用小工具（如 `crawler/notify.py`）供兩模組使用；兩者職責分離，互不阻塞 |

---

## 3. API / Message 合約（Telegram Bot API）

### 3.1 getUpdates（指令輪詢）

| 方法 | 端點 | 方向 |
|------|------|------|
| getUpdates | `https://api.telegram.org/bot<token>/getUpdates` | Bot → Telegram |

| 參數 | 型別 | 必填 | 值 | 說明 |
|------|------|:---:|------|------|
| offset | int | 否 | `state.offset + 1`；首次省略 | 第一筆要回傳的 update id；`offset = 已處理最後一筆 + 1` 同時確認（confirm）已讀訊息，避免重複處理（BDD S23/S25） |
| timeout | int | 否 | 30 | long-poll 秒數；httpx 網路 timeout 設 60 須大於此值，避免網路層先逾時 |

成功 Response：

```jsonc
{ "ok": true, "result": [ {
    "update_id": 102,
    "message": {
      "message_id": 9,
      "from": { "id": 123456789, "is_bot": false, "first_name": "Alice", "username": "alice" },
      "chat": { "id": 123456789, "type": "private" },
      "date": 1786946400,
      "text": "/watch i5-13600K 9000"
    } } ] }
```

失敗 Response（token 無效）：

```jsonc
{ "ok": false, "error_code": 401, "description": "Unauthorized" }
```

| 錯誤碼 | 意義 | 006 行為 |
|------|------|---------|
| 401 | token 無效 | 中止階段、記錄日誌、不發送任何訊息、不寫回 telegram.json（BDD S24） |
| 409 | 另一輪詢進行中 | 不應發生（每日單一 run）；log 警告 |
| 429 | rate limit | 每日量低，預期不發生；發生則退避重試 |

### 3.2 sendMessage（回覆與通知）

| 方法 | 端點 | 方向 |
|------|------|------|
| sendMessage | `https://api.telegram.org/bot<token>/sendMessage` | Bot → Telegram |

| 參數 | 型別 | 必填 | 值 | 說明 |
|------|------|:---:|------|------|
| chat_id | int | 是 | 使用者 `chat.id`（private 對話中與 from.id 相同） | 007 警報則為管理員 chat_id |
| text | string | 是 | 見 §3.3 / §3.4 | ≤ 4096 字元；純文字，不使用 parse_mode（避免 HTML/emoji 轉義問題） |

### 3.3 指令格式合約

| 指令 | 格式 | 範例 | 回覆內容 |
|------|------|------|---------|
| `/start` | `/start` | `/start` | 使用說明（§3.5） |
| `/help` | `/help` | `/help` | 同 `/start`（BDD S2） |
| `/watch` | `/watch 關鍵字 目標價` | `/watch RTX 4060 9000` | 成功確認 / 格式錯誤 / 找不到 / 候選清單 / 已達標提示 / 上限拒絕 |
| `/unwatch` | `/unwatch 關鍵字` | `/unwatch i5-13600K` | 已移除 / 不在追蹤清單 |
| `/list` | `/list` | `/list` | 追蹤清單（名稱/現價/目標價）或空清單提示 |
| 其他 | 任意文字/指令 | `/price` | 「不認識這個指令，輸入 /help 查看使用說明」 |

`/watch` 回覆範本（§1.3.5 handle_watch）：

```
✅ 已加入追蹤
商品：Intel i5-13600K【14核/20緒】…
目前價格：9990 元
目標價：9000 元
```

```
🎯 目前價格已達目標價（8500 ≤ 9000），下次執行將推送通知   ← 追加於確認訊息尾
```

```
✅ 目標價已更新：Intel i5-13600K
新目標價：9000 元
```

```
⚠️ 格式錯誤
正確格式：/watch 關鍵字 目標價
範例：/watch RTX 4060 9000
```

```
⚠️ 目標價必須為正整數（例如 9000）
正確格式：/watch 關鍵字 目標價
```

```
❌ 找不到符合「3080Ti 水冷版」的商品，請檢查關鍵字或改用較短關鍵字
```

```
⚠️ 有多個商品符合「RTX 4060」，請改用更精確的關鍵字重送：
1. 微星 RTX 4060 8G — 8490 元
2. 技嘉 RTX 4060 8G — 8590 元
3. 華碩 RTX 4060 8G — 8690 元
```

```
⚠️ 追蹤數量已達上限 20 個，請先 /unwatch
```

`/unwatch` 回覆範本：

```
🗑️ 已移除：Intel i5-13600K
```

```
❌ 該商品不在追蹤清單
```

`/list` 回覆範本：

```
📋 追蹤清單（2/20）：
1. Intel i5-13600K — 目前 9990 元 / 目標 9000 元
2. 微星 RTX 4060 8G — 目前 8490 元 / 目標 8000 元
```

```
📋 目前沒有追蹤任何商品
使用 /watch 關鍵字 目標價 開始追蹤
```

### 3.4 通知訊息範本

降價通知（現價 ≤ 目標價，含歷史最低）：

```
📉 降價通知
商品：Intel i5-13600K【14核/20緒】…
目前價格：8500 元
目標價：9000 元
歷史最低：8200 元
```

消失通知（商品當日清單已無，status=gone）：

```
⚠️ 商品已停售/下架
商品：Intel i5-13600K
最後價格：9990 元
消失日期：2026-08-18
（可用 /unwatch 移除本追蹤）
```

### 3.5 使用說明範本（/start 與 /help 共用）

```
📦 原價屋降價通知

每天下午自動比對商品價格，降價到目標價就通知你！

指令：
/watch 關鍵字 目標價 — 追蹤商品（例：/watch RTX 4060 9000）
/unwatch 關鍵字     — 取消追蹤
/list               — 查看追蹤清單
/help               — 顯示本說明

規則：現價 ≤ 目標價即通知；每人最多追蹤 20 個商品。
```

---

## 5. 生命週期

### 5.1 `data/telegram.json` 狀態機（offset）

```
UNINITIALIZED ──首次 run，無檔案──▶ 讀取失敗/不存在 → 空狀態 (offset=None)
      │
      ▼
   POLLING   getUpdates(offset=state.offset+1)  ← 無檔案時 offset=None（從頭）
      │
      ├── 401 / 網路失敗重試後 ──▶ FAILED：log、不寫回、回傳 success=False（S24/S25）
      │
      ▼
  PROCESSING  逐筆處理新 update → 每筆成功記錄 update_id
      │          （本次 run 內以已處理 update_id 集合防呆去重）
      ▼
   ADVANCED  state.offset = max(已處理 update_id)（無新訊息則維持原值）
      │
      ▼
   PERSISTED save_state() 原子寫入（僅有變更時；token 無效/網路失敗時不寫回）
```

| 轉移 | 條件 | 動作 |
|------|------|------|
| UNINITIALIZED → POLLING | telegram.json 不存在 | 以空狀態啟動（首次） |
| POLLING → FAILED | HTTP 401 | log「token 無效」，不發送任何訊息、不寫回（BDD S24） |
| POLLING → FAILED | 網路錯誤重試 POLL_RETRIES 次仍失敗 | log，offset 不變 → 下次 run 不遺漏（BDD S25） |
| POLLING → PROCESSING | getUpdates 成功且有新 update | 逐筆處理 |
| PROCESSING → ADVANCED | 所有 update 處理完畢 | `offset = max(processed_ids)`（BDD S23） |
| ADVANCED → PERSISTED | 無致命失敗 | 原子寫回 telegram.json；無任何變更則不寫（避免無意義 commit） |

### 5.2 `telegram.json` 讀寫時機

| 時機 | 動作 |
|------|------|
| 每日 run 的 telegram 階段開始（爬蟲成功後） | `load_state()` 讀取（含 offset 與全部使用者追蹤清單） |
| 處理指令過程中（記憶體中） | 追蹤清單與 offset 持續變更，不落盤 |
| 階段結束（成功） | `save_state()` 原子寫入（tmp + os.replace） |
| token 無效 / getUpdates 重試仍失敗 | **不寫回**——telegram.json 維持本次 run 前的狀態（BDD S24/S25） |
| 狀態損毀（json 解析失敗） | 備份 `.corrupt-<ts>` 後以空狀態啟動，避免卡死 |
| git commit | 與 items.json 一併 commit（§1.4 整合點調整說明） |

`telegram.json` schema（首次 run 建立）：

```jsonc
{
  "schema_version": 1,
  "offset": 102,
  "users": {
    "123456789": [
      { "item_id": "3f9a1c2b8e4d5f6a",
        "name": "微星 RTX 4060 8G",
        "target_price": 8000,
        "added_at": "2026-08-16" }
    ]
  }
}
```

### 5.3 每日 run 的處理順序（與 001 / 002 / 007 整合）

```
00 觸發（002：cron 06:00 UTC / workflow_dispatch；concurrency group 保證單一 run）
 1. 001 爬蟲：fetch → parse → spec → store（更新 items.json、meta.json）
 2. 007 健康檢查：商品數驟降 >20% / parser 例外？
      ├─ 是 → 保留舊資料 + 管理員 Telegram 警報 → 略過 telegram 階段 → 結束
      └─ 否 → 繼續
 3. 006 telegram 階段（scripts/telegram_hook.py 呼叫 run_telegram_phase）：
      a. load_state() 讀 telegram.json
      b. getUpdates 輪詢 → 處理 /start /watch /unwatch /list /help → 回覆 → 推進 offset
      c. evaluate_notifications 比對追蹤清單與當日 items → 推送降價/消失通知
      d. save_state() 寫回 telegram.json
      e. 失敗（token 無效/網路）→ log、不寫回、不影響後續
 4. 002 commit data/（items.json + meta.json + telegram.json 一併）
 5. 002 Vite build → 部署 GitHub Pages
 6. 結束（等待下次 run）
```

---

## 6. 邊界條件處理

### 6.1 BDD 覆蓋矩陣（25 個 Scenario 全數對應）

| # | BDD Scenario | 類別 | 對應規格 |
|---|-------------|------|---------|
| S1 | /start 回覆使用說明（含 4 指令 + 範例） | happy-path | §1.3.5 build_help_text / §3.5 |
| S2 | /help 同 /start | happy-path | §1.3.5 handle_start |
| S3 | /watch 唯一符合加入追蹤（訊息含名稱/現價/目標價） | happy-path | §1.3.5 handle_watch / §3.3 |
| S4 | 模糊比對多關鍵字型態（i5-13600K / rtx 4060 / 金士頓 32G） | data-driven | §1.3.4 normalize_text + fuzzy_match |
| S5 | /watch 缺目標價 → 格式錯誤、清單不變 | validation | §1.3.3 parse_watch_args / §3.3 |
| S6 | /watch 目標價非正整數 → 拒絕、清單不變 | validation | §1.3.3 parse_watch_args |
| S7 | /watch 目標價 0 → 拒絕、清單不變 | boundary | §1.3.3 parse_watch_args（≥1 才合法） |
| S8 | /watch 無符合 → 「找不到」提示、清單不變 | error | §1.3.5 handle_watch 分支 2 |
| S9 | /watch 多個符合 → 候選清單、不自動加入 | error | §1.3.5 handle_watch 分支 2 / §3.3 |
| S10 | 重複 /watch → 更新目標價、單一記錄 | business | §1.3.5 handle_watch 步驟 4 |
| S11 | 訂閱時現價已 ≤ 目標價 → 提示已達標並加入 | boundary | §1.3.5 handle_watch 步驟 5 |
| S12 | 追蹤達上限 20 → 拒絕並提示先 /unwatch | business | §1.3.5 handle_watch 步驟 3 |
| S13 | /unwatch 移除成功 | happy-path | §1.3.5 handle_unwatch |
| S14 | /unwatch 不在清單 → 提示、清單不變 | error | §1.3.5 handle_unwatch |
| S15 | /list 顯示名稱/現價/目標價 | happy-path | §1.3.5 handle_list |
| S16 | /list 空清單 → 提示 + /watch 教學 | edge-case | §1.3.5 handle_list |
| S17 | 未知指令 → 不認識 + /help 提示 | error | §1.3.5 handle_unknown |
| S18 | 每日執行：現價 < 目標價 → 降價通知（含歷史最低） | system | §1.3.6 evaluate_notifications + format_price_alert |
| S19 | 現價 = 目標價亦觸發（等於算達標） | boundary | §1.3.6 `price <= target_price` |
| S20 | 商品消失 → 消失通知（最後價格 + 消失日期） | system | §1.3.6 evaluate_notifications + format_gone_alert |
| S21 | 未達標且未消失 → 不發送任何訊息 | edge-case | §1.3.6 evaluate_notifications |
| S22 | 當日無價格資料 → 跳過、保留於追蹤清單 | edge-case | §1.3.6 evaluate_notifications |
| S23 | getUpdates 後 offset 推進至最後一筆 update_id | edge-case | §5.1 狀態機 ADVANCED |
| S24 | token 無效 → telegram 失敗、不影響資料與 commit | error | §1.3.7 run_telegram_phase 步驟 2 |
| S25 | getUpdates 網路失敗 → 略過、offset 不變、下次不遺漏 | error | §1.3.7 run_telegram_phase 步驟 2 / §5.1 FAILED |

### 6.2 邊界情境處理明細

| 邊界情境 | 處理行為 | 來源 |
|---------|---------|------|
| **指令格式錯誤**（缺參數、亂格式） | 回覆格式錯誤訊息含範例「/watch 關鍵字 目標價」；state 不變 | S5 |
| **缺目標價**（`/watch i5-13600K`） | 同上格式錯誤；不查商品清單 | S5 |
| **目標價非正整數**（`abc`、`-9000`、`9000.5`、`9,000`） | 回覆「目標價必須為正整數」；state 不變 | S6 |
| **目標價為 0** | 同非正整數處理（正整數定義 ≥1） | S7 |
| **無符合商品**（模糊比對 0 個） | 回覆「找不到符合商品，請檢查關鍵字或改用較短關鍵字」 | S8 |
| **多個符合**（模糊比對 ≥2 個） | 回覆候選清單（名稱+現價），**不自動加入任何商品** | S9 |
| **重複 /watch 同一商品** | 更新目標價、維持單一記錄、回覆「目標價已更新」；不受上限限制 | S10 |
| **訂閱時現價已 ≤ 目標價** | 照常加入並於回覆追加「目前價格已達目標價」；下次 run 即推送 | S11 |
| **追蹤達上限 20** | 回覆「追蹤數量已達上限 20 個，請先 /unwatch」；state 不變（更新既有商品不受限） | S12 |
| **/unwatch 多個名稱符合** | 回覆候選要求更精確，不自動移除（與 /watch 同策略） | 擴充 |
| **現價 = 目標價** | **達標**，觸發降價通知（`<=` 比較） | S19 |
| **現價 > 目標價且商品仍在** | 不發送任何訊息 | S21 |
| **商品當日無價格資料**（爬蟲漏抓、price=None） | 跳過不推送、保留於追蹤清單、下次 run 恢復比對 | S22 |
| **商品消失（gone）** | 推送消失通知（含最後價格 = 歷史最後一筆價格、消失日期 = last_seen） | S20 |
| **offset 推進與去重** | 輪詢帶 `state.offset + 1`；處理完 `offset = max(update_id)`；本次 run 內以已處理 update_id 集合防呆；下次 run 不重複處理 | S23/S25 |
| **getUpdates 網路失敗** | 退避重試 2 次，仍失敗 → log、offset 不變（維持 100）、不寫回、成功略過本階段 | S25 |
| **token 無效（401）** | log 錯誤、不發送任何訊息、不寫回 telegram.json（追蹤清單與 offset 不變）；資料爬取與 commit 仍正常完成 | S24 |
| **telegram.json 不存在（首次）** | 空狀態啟動；有指令處理時建立檔案 | §5.1 |
| **telegram.json 解析失敗（損毀）** | 備份 `.corrupt-<ts>` 後以空狀態啟動，run 不卡死 | §5.2 |
| **非文字訊息**（貼圖/照片/按鈕回傳） | 無 text → 忽略不回應（不視為未知指令刷錯誤訊息） | §1.3.3 |
| **關鍵字含多空白 / 全形字元** | normalize_text（lower、全形→半形、去空白）後 substring 比對 | §1.3.4 |
| **歷史無資料**（商品首日） | lowest_price 視同當日現價；不影響達標判定（判定僅用現價） | §1.3.6 |
| **商品消失後重新出現** | status 回 in_stock；追蹤記錄保留，恢復正常比對 | 擴充 |

---

## 8. 開發順序

| 步驟 | 內容 | 依賴 |
|------|------|------|
| 1 | 資料模型與 I/O：`TelegramState` / `WatchItem` / `ItemRef` / `load_state` / `save_state`（原子寫入、損毀備份）+ pytest | - |
| 2 | 指令解析：`parse_command` / `parse_watch_args` + 測試（含缺目標價、非正整數、0、前導零） | - |
| 3 | Bot API 客戶端：`TelegramBot.get_updates` / `send_message`（401 偵測、httpx MockTransport 測試） | - |
| 4 | 模糊比對：`normalize_text` / `fuzzy_match` + 測試（data-driven：i5-13600K / rtx 4060 / 金士頓 32G） | - |
| 5 | 指令 handlers：/start /help /watch /unwatch /list /unknown + 測試（上限 20、重複 watch 更新目標價、已達標提示、候選清單） | 1, 2, 4 |
| 6 | 通知評估：`evaluate_notifications` + `format_price_alert` / `format_gone_alert` + 測試（`<=` 含等於、gone、無價格跳過、未達標不發送、歷史最低） | 1, 4 |
| 7 | run 整合：`run_telegram_phase`（offset 推進、run 內去重、token 無效不寫回、網路失敗重試不寫回）+ 測試 | 3, 5, 6 |
| 8 | 整合點：`scripts/telegram_hook.py` 呼叫 `run_telegram_phase`（002 預留 step，commit 前）+ crawl.yml 注入 `TELEGRAM_BOT_TOKEN`（+ 007 所需 `TELEGRAM_ADMIN_CHAT_ID`）；commit 順序為 store → telegram → commit（items.json + telegram.json 一併） | 7 |
| 9 | E2E fixture 驗收：以 fixture items.json + telegram.json 跑完整 run，逐項對照 BDD 驗收清單（25 Scenario） | 8 |

```
DAG：1,2,3,4 並行 → 5(依 1,2,4) → 6(依 1,4) → 7(依 3,5,6) → 8(依 7) → 9(依 8)
（無循環；後端模組先於整合與驗收）
```

---

## 附錄：與上游文件的一致性聲明

- 所有 BDD Scenario（S1–S25）均可於 §1 / §3 / §5 / §6 找到對應（見 §6.1 覆蓋矩陣）
- 設計決策與 flow §6 一致：追蹤上限 20（`MAX_WATCH_PER_USER`）、現價 ≤ 目標價即達標（`price <= target_price`）、多符合不自動加入、模糊比對以關鍵字型態（substring）
- Code skeleton 為開發藍圖，非完整實作；`// TODO: handle error` 類別的分支在實作階段補齊
