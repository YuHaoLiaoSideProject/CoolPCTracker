#!/usr/bin/env python3
"""Telegram 告警 hook：以 Bot API `sendMessage` 實際發送排程結果通知。

用途（兩條呼叫路徑共用本檔的 `send_message` / `notify`）：

1. **程式內告警**：`crawler.main` 在 `status=failed`（驟降/0 商品）或執行期例外時，
   以 `notify(text)` 注入（`main.py` 由本檔載入 `notify`）。
2. **工作流整合點**：`python scripts/telegram_hook.py --data-dir data`
   （`crawl.yml` 的 Telegram step，位於資料 commit 之前）：讀 `data/meta.json`
   組出本次 run 摘要並發送；成功 run 亦發一封（可用 `TELEGRAM_NOTIFY_SUCCESS=0` 關閉）。

契約（與 006 BDD @error-handling 一致）：

- 憑證由環境變數提供：`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`。
- **缺少憑證 → graceful skip**：印 warning、回傳 False / exit 0，不 crash、不中斷排程。
- **發送失敗（網路錯誤、token 無效、HTTP 非 200）→ 只記 log，絕不拋例外**，
  因此不會掩蓋呼叫端原本的錯誤。
- 訊息長度截斷至 Telegram 上限 4096 字元（保留截斷提示）。
- `TELEGRAM_API_BASE` 可覆寫 API 根網址（預設 `https://api.telegram.org`），
  供本地 stub / 測試使用，不影響正式行為。

HTTP client 沿用專案既有依賴 `httpx`（`crawler/pyproject.toml` 已列），未新增依賴。
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("telegram_hook")

DEFAULT_API_BASE = "https://api.telegram.org"
TELEGRAM_MAX_LEN = 4096  # Telegram sendMessage text 上限
TRUNCATION_MARK = "\n…（訊息過長，已截斷）"
DEFAULT_TIMEOUT = 10.0
# 錯誤訊息細節上限（保留 traceback 給 Actions log，訊息只帶摘要）
MAX_DETAIL_LEN = 800

STATUS_OK = "ok"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"


def truncate(text: str, limit: int = TELEGRAM_MAX_LEN) -> str:
    """截斷至 Telegram 上限內（含截斷提示字樣），確保 request 不會被 API 拒絕。"""
    if len(text) <= limit:
        return text
    keep = max(limit - len(TRUNCATION_MARK), 0)
    return text[:keep] + TRUNCATION_MARK[: limit - keep]


def _redact(text: str, token: str | None) -> str:
    """避免把 bot token 寫進 log（token 會出現在 endpoint URL 內）。"""
    if token:
        return text.replace(token, "***")
    return text


def _credentials() -> tuple[str | None, str | None]:
    return os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")


def send_message(
    text: str,
    *,
    token: str | None = None,
    chat_id: str | None = None,
    api_base: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: Any = None,
    client: Any = None,
) -> bool:
    """發送一則 Telegram 訊息。永不拋例外，回傳是否成功送出。

    - `token` / `chat_id` 未給 → 讀環境變數；兩者任一缺 →warning + False。
    - `transport` / `client` 僅供測試注入（httpx.MockTransport / stub client）。
    """
    env_token, env_chat_id = _credentials()
    token = token if token is not None else env_token
    chat_id = chat_id if chat_id is not None else env_chat_id

    if not token or not chat_id:
        missing = []
        if not token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        logger.warning(
            "[telegram-hook] 缺少 %s；略過 Telegram 通知（不中斷排程）", "、".join(missing)
        )
        return False

    base = (api_base or os.environ.get("TELEGRAM_API_BASE") or DEFAULT_API_BASE).rstrip("/")
    url = f"{base}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": truncate(text),
        "disable_web_page_preview": True,
    }

    try:
        status_code, body = _post_json(url, payload, timeout=timeout,
                                       transport=transport, client=client)
    except Exception as exc:  # noqa: BLE001 — 通知失敗不得影響排程
        logger.warning("[telegram-hook] 發送失敗（%s）：%s",
                       type(exc).__name__, _redact(str(exc), token))
        return False

    if status_code != 200:
        logger.warning("[telegram-hook] Telegram API 回應 HTTP %s：%s",
                       status_code, _redact(_short(body), token))
        return False
    if not _is_ok_response(body):
        logger.warning("[telegram-hook] Telegram API 回應非 ok：%s",
                       _redact(_short(body), token))
        return False

    logger.info("[telegram-hook] 已發送 Telegram 通知（%d 字元）", len(payload["text"]))
    return True


def _post_json(url: str, payload: dict[str, Any], *, timeout: float,
               transport: Any = None, client: Any = None) -> tuple[int, str]:
    """POST JSON；回傳 (status_code, body text)。例外由呼叫端處理。"""
    if client is not None:  # 測試注入
        response = client.post(url, json=payload)
        return response.status_code, response.text

    import httpx  # 專案既有依賴（crawler/pyproject.toml）

    with httpx.Client(timeout=timeout, transport=transport) as http:
        response = http.post(url, json=payload)
        return response.status_code, response.text


def _is_ok_response(body: str) -> bool:
    try:
        doc = json.loads(body)
    except (ValueError, TypeError):
        return False
    return isinstance(doc, dict) and doc.get("ok") is True


def _short(text: str, limit: int = MAX_DETAIL_LEN) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def notify(text: str) -> None:
    """`crawler.main.NotifyFn` 介面（`Callable[[str], None]`）：失敗永不外拋。"""
    send_message(text)


def format_summary(meta: dict[str, Any], *, day: str | None = None) -> str:
    """由 `data/meta.json` 組出中文 run 摘要（成功／部分／失敗共用）。"""
    status = str(meta.get("status") or "unknown")
    crawled_at = str(meta.get("crawled_at") or "（未知）")
    total = meta.get("total")
    previous_total = meta.get("previous_total")
    changed = meta.get("changed")
    failed = meta.get("failed_categories") or []
    failed_text = "、".join(str(x) for x in failed) if failed else "無"
    day_text = day or (crawled_at[:10] if len(crawled_at) >= 10 else date.today().isoformat())

    if status == STATUS_OK:
        head = f"✅ [CoolPC 排程] {day_text} 執行成功"
    elif status == STATUS_PARTIAL:
        head = f"⚠️ [CoolPC 排程] {day_text} 部分分類失敗（已沿用舊資料）"
    else:
        head = f"🚨 [CoolPC 排程] {day_text} 執行失敗"
    prev_text = previous_total if previous_total is not None else "無"
    return (
        f"{head}\n"
        f"執行時間（UTC）：{crawled_at}\n"
        f"狀態：{status}\n"
        f"本次解析：{total} 商品（前次基準 {prev_text}）\n"
        f"異動商品：{changed}\n"
        f"失敗分類：{failed_text}"
    )


def _success_notifications_enabled() -> bool:
    """成功 run 是否也發摘要（預設開；`TELEGRAM_NOTIFY_SUCCESS=0/false/no` 可關閉）。"""
    raw = os.environ.get("TELEGRAM_NOTIFY_SUCCESS")
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _load_meta(data_dir: Path) -> dict[str, Any] | None:
    path = data_dir / "meta.json"
    try:
        with path.open("r", encoding="utf-8") as handle:
            doc = json.load(handle)
    except FileNotFoundError:
        logger.warning("[telegram-hook] 找不到 %s；略過本次通知", path)
        return None
    except (OSError, ValueError) as exc:
        logger.warning("[telegram-hook] 讀取 %s 失敗（%s）；略過本次通知",
                       path, type(exc).__name__)
        return None
    if not isinstance(doc, dict):
        logger.warning("[telegram-hook] %s 格式非 object；略過本次通知", path)
        return None
    return doc


def build_cli_text(data_dir: Path, *, explicit_text: str | None = None,
                   day: str | None = None) -> str | None:
    """決定 CLI 要發送的訊息；回傳 None = 本次無需發送（附 warning）。"""
    if explicit_text:
        return explicit_text
    meta = _load_meta(data_dir)
    if meta is None:
        return None
    status = str(meta.get("status") or "")
    if status == STATUS_OK and not _success_notifications_enabled():
        logger.info("[telegram-hook] status=ok 且 TELEGRAM_NOTIFY_SUCCESS 關閉；不發送")
        return None
    return format_summary(meta, day=day)


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：讀 meta.json → 組摘要 → 發送。永遠回傳 0（不中斷工作流）。"""
    parser = argparse.ArgumentParser(prog="telegram_hook")
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--text", default=None, help="直接發送指定文字（略過 meta.json）")
    parser.add_argument("--date", default=None, help="顯示用日期 YYYY-MM-DD（預設取自 meta）")
    parser.add_argument("--dry-run", action="store_true", help="只印出訊息，不發送")
    args = parser.parse_args(argv)

    try:
        text = build_cli_text(args.data_dir, explicit_text=args.text, day=args.date)
        if text is None:
            return 0
        if args.dry_run:
            print(text)
            return 0
        sent = send_message(text)
        print("[telegram-hook] 已發送" if sent else "[telegram-hook] 未發送（見上方 warning）")
    except Exception:  # noqa: BLE001 — CLI 絕不因通知問題中斷工作流
        logger.warning("[telegram-hook] 未預期錯誤，略過通知", exc_info=True)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
