"""總排程：fetch → parse → spec → ID → diff → 健康檢查 → apply → save。

功能 001 的管道編排（開發規格 §1.8），同時是 007 健康檢查與 002 排程的整合點：

- **驟降保護**（#14/#15）：total==0 或降幅 > DROP_THRESHOLD → 判定 failed →
  不覆寫 items.json、以 notify hook 發中文警報（007 telegram_bot 注入）、
  meta.status="failed"、return 1
- **部分分類失敗**（#12/#16）：成功分類更新、失敗分類既有資料保留
  （diff 時視為未變動、不誤判 gone）、meta.status="partial"、return 0
- **CLI**：`python -m crawler.main [--data-dir data] [--date YYYY-MM-DD]`
  （002 workflow_dispatch 手動補爬整合點；--date 決定實際爬取日）

**exit code 契約**：0 成功（含 partial）；1 健康檢查擋下（failed，不覆寫）；
2 其他執行失敗（main() 以 try/except 捕捉意外例外）。

**meta.previous_total 語意**（007 驟降基準「上次有效總數」）：ok/partial 寫入
本次有效總數（供下次 run 作基準）；failed 路徑經 store.write_meta 沿用既有值，
因此失敗 run 不會污染基準（基準在成功 run 後更新，失敗後保持）。

**寫檔分工**：ok/partial → store.save(items, meta)（原子寫 items.json + meta.json，
meta 含完整欄位）；failed → store.write_meta(...)（僅寫 meta.json 標記失敗，
items.json 保持原狀）。
"""
from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

from .categories import CATEGORIES, make_item_id
from .fetcher import Fetcher
from .parser import Parser, RawItem
from .spec_parser import parse_spec
from .store import STATUS_IN_STOCK, SOURCE_URL, DiffResult, Item, Store

logger = logging.getLogger(__name__)

DROP_THRESHOLD = 0.20  # 商品數驟降保護門檻（與 007 功能共用；邊界恰 80% 不判異常）
NotifyFn = Callable[[str], None]  # 007 telegram 警報 hook

STATUS_OK = "ok"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"


def run_crawler(data_dir: Path, today: date | None = None,
                notify: NotifyFn | None = None) -> int:
    """執行完整管道（規格 §1.8 步驟 1-7），回傳 exit code。

    0 = 成功（含 partial）；1 = 健康檢查擋下（failed，不覆寫 items.json）；
    2 = 其他執行失敗（由 main() 捕捉意外例外後回傳）。
    """
    day = today if today is not None else date.today()
    store = Store(data_dir)
    fetcher = Fetcher()  # 測試以 monkeypatch crawler.main.Fetcher 注入 fake
    parser = Parser()

    previous_items, old_meta = store.load()

    # 1. 依序抓取 9 頁（fetch_all 內部單頁重試 ≤3 次；失敗頁 html=None）
    results = fetcher.fetch_all()

    # 2-3. parse_page → RawItem；parse_spec + make_item_id → Item
    today_items: list[Item] = []
    failed_categories: list[str] = []
    counts: dict[str, int] = {c.name: 0 for c in CATEGORIES}
    day_str = day.isoformat()
    for result in results:
        category = result.category
        if result.html is None:  # 抓取失敗（BDD #12）：沿用舊資料，記入失敗分類
            failed_categories.append(category.name)
            continue
        try:
            parsed = parser.parse_page(result.html, category)
        except Exception:  # noqa: BLE001 — 單頁解析例外不得使整個 run 崩潰
            logger.exception("parse failed for %s (G=%d)", category.name, category.g_index)
            failed_categories.append(category.name)
            continue
        items = [_to_item(raw, day_str) for raw in parsed.items]
        counts[category.name] = len(items)
        today_items.extend(items)

    # BDD #16 / 007 rule 4：解析出 0 商品但上次有商品的分類 → 視為失敗分類（沿用舊資料）
    for category in CATEGORIES:
        if (counts[category.name] == 0 and category.name not in failed_categories
                and any(i.category == category.name for i in previous_items.values())):
            failed_categories.append(category.name)

    total = len(today_items)
    previous_total = old_meta.get("previous_total")
    if previous_total is None:
        previous_total = old_meta.get("total")  # 首次/舊版 meta 無基準 → 沿用上次 run 總數

    # 4. 健康檢查（規則以 007 health 為準，此處為 001 子集）
    status, reason = _compute_status(total, previous_total, failed_categories)
    if status == STATUS_FAILED:
        if notify is not None:
            notify(_build_alert(day, total, previous_total, failed_categories, reason))
        store.write_meta(crawled_at=_utc_now(), counts=counts, total=total, changed=0,
                         failed_categories=failed_categories, status=STATUS_FAILED)
        logger.error("crawler %s: %s（不覆寫 items.json）", day.isoformat(), reason)
        return 1

    # 5. diff → apply（partial：失敗分類既有商品視為未變動，不誤判 gone）
    diff = store.diff(today_items, previous_items)
    if failed_categories:
        diff = _exclude_failed_from_gone(diff, failed_categories, previous_items)
    items = store.apply(diff, day, previous_items)
    changed = len(diff.new_items) + len(diff.changed_items)

    # 6. meta：ok/partial 完整寫出；previous_total = 本次有效總數（下次驟降基準）
    meta = dict(old_meta)  # 保留 007 擴充欄位（sources/anomaly/…）
    meta.update({
        "crawled_at": _utc_now(),
        "source": SOURCE_URL,
        "counts": counts,
        "total": total,
        "previous_total": total,
        "changed": changed,
        "failed_categories": failed_categories,
        "status": status,
    })
    meta.setdefault("version", 0)  # 002 cache-busting 版本號：沿用；不存在 → 0
    store.save(items, meta)

    # 7. 執行摘要 log（各分類商品數、異動數、失敗分類）
    logger.info(
        "crawler %s status=%s total=%d previous_total=%s changed=%d "
        "failed_categories=%s counts=%s",
        day.isoformat(), status, total, previous_total, changed, failed_categories, counts,
    )
    return 0


def _compute_status(total: int, previous_total: int | None,
                    failed_categories: list[str]) -> tuple[str, str]:
    """健康判定（007 規則子集，規格 §6.2）：

    - total==0 → failed（#15：HTML 改版或全部分類抓取失敗）
    - 降幅 > DROP_THRESHOLD（total < previous_total*(1-DROP_THRESHOLD)）→ failed（#14）；
      邊界：恰等於 80% 不判異常（007 §6.1）
    - 部分分類失敗 → partial（#12）
    - 否則 ok
    首次執行（previous_total 為 None）不判驟降。
    回傳 (status, 原因文案)；partial/ok 原因為空字串。
    """
    if total == 0:
        return STATUS_FAILED, "本次解析出 0 商品（HTML 結構可能改版或全部分類抓取失敗）"
    if previous_total is not None and total < previous_total * (1 - DROP_THRESHOLD):
        drop = (previous_total - total) / previous_total
        return STATUS_FAILED, (
            f"商品數由 {previous_total} 驟降至 {total}"
            f"（降幅 {drop:.1%} > {DROP_THRESHOLD:.0%} 門檻）"
        )
    if failed_categories:
        return STATUS_PARTIAL, ""
    return STATUS_OK, ""


def _exclude_failed_from_gone(diff: DiffResult, failed_categories: list[str],
                              previous_items: dict[str, Item]) -> DiffResult:
    """失敗分類（本次無新資料）既有商品視為「未變動」：自 gone_ids 移出併入 unchanged，
    保留原樣（last_seen/status/history 不動，不誤判 gone；規格 §6.2 / BDD #12、#16）。"""
    failed_ids = {iid for iid, item in previous_items.items()
                  if item.category in failed_categories}
    gone_ids = [iid for iid in diff.gone_ids if iid not in failed_ids]
    return DiffResult(new_items=diff.new_items, changed_items=diff.changed_items,
                      gone_ids=gone_ids, unchanged_ids=diff.unchanged_ids | failed_ids)


def _to_item(raw: RawItem, day: str) -> Item:
    """RawItem → Item：parse_spec + make_item_id。

    history 以提議歷史 [[今日, 價格]] 表示（store 契約：今日商品價格 = 歷史末筆；
    價格缺失 → []，BDD #19）。spec 以 asdict 轉為 dict（Item.spec 型別）。"""
    spec = parse_spec(raw.category, raw.name)
    item_id = make_item_id(raw.category, raw.name)
    history = [[day, raw.price]] if raw.price is not None else []
    return Item(id=item_id, category=raw.category, subcategory=raw.subcategory,
                name=raw.name, spec=asdict(spec), flags=dict(raw.flags),
                status=STATUS_IN_STOCK, history=history)


def _build_alert(day: date, total: int, previous_total: int | None,
                 failed_categories: list[str], reason: str) -> str:
    """中文警報文案（007 notify hook）：含本次 run 摘要與失敗原因。"""
    prev = previous_total if previous_total is not None else "無"
    failed = "、".join(failed_categories) if failed_categories else "無"
    return (
        f"⚠️ [CoolPC 爬蟲異常] {day.isoformat()} 執行失敗：{reason}。"
        f"本次解析 {total} 商品（前次基準 {prev}），失敗分類：{failed}。"
        "已取消覆寫 data/items.json，既有資料保持原狀。"
    )


def _utc_now() -> str:
    """ISO 8601 UTC（含微秒，供同日重跑可辨識 crawled_at 更新）。"""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：python -m crawler.main [--data-dir data] [--date YYYY-MM-DD]

    --date 供 workflow_dispatch 手動補爬（002 整合點），歷史以實際爬取日記錄；
    重複執行冪等（同日同價不重複 append 歷史）。
    """
    arg_parser = argparse.ArgumentParser(prog="crawler")
    arg_parser.add_argument("--data-dir", default="data", type=Path)
    arg_parser.add_argument("--date", default=None, help="實際爬取日 YYYY-MM-DD（預設今日 UTC）")
    args = arg_parser.parse_args(argv)
    try:
        today = date.fromisoformat(args.date) if args.date else date.today()
        return run_crawler(args.data_dir, today=today)
    except Exception:  # noqa: BLE001 — exit 2：其他執行失敗（無效 --date、檔案損壞、寫檔失敗…）
        logger.exception("crawler run 意外失敗（exit 2）")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
