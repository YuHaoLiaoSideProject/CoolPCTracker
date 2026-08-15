#!/usr/bin/env python3
"""Telegram 通知整合點（功能 006 預留，規格 §1.6）。

- 位置：crawl job 中「爬蟲 + version_data 之後、資料 commit 之前」的 step；
  每 run 皆觸發（資料異動或無異動皆會經過），telegram.json 異動併入本次 commit。
- 006 實作前：讀不到 TELEGRAM_BOT_TOKEN → 印 notice；有 token → 印 placeholder；
  兩者皆回傳 0（配合工作流 continue-on-error: true，不中斷 run）。
- 006 實作後：置換主體為 crawler.telegram_bot 每日流程
  （getUpdates 輪詢 + 目標價比對 + 降價/消失通知，以 asyncio.run 驅動）；
  token 無效或網路失敗僅記 log，不影響資料爬取與 commit（006 BDD @error-handling）。

對應 BDD：@integration @placeholder（整合點尚未實作時工作流不因此中斷）。
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    """讀 TELEGRAM_BOT_TOKEN：無 token → notice；有 token → placeholder。皆回傳 0。"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("[telegram-hook] 未設定 TELEGRAM_BOT_TOKEN；整合點已觸發但尚未啟用（功能 006 預留）")
        return 0
    # TODO(006): from crawler.telegram_bot import run_daily; asyncio.run(run_daily(...))
    print("[telegram-hook] placeholder：006 實作待接入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
