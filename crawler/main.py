"""總排程：fetch → parse → spec → ID → diff → 健康檢查 → apply → save。

功能 001 的管道編排（開發規格 §1.8），同時是 007 健康檢查與 002 排程的整合點：

- **驟降保護**（#14/#15）：total==0 或降幅 > DROP_THRESHOLD → 判定 failed →
  不覆寫 items 分類檔（data/items/）、以 notify hook 發中文警報（007 telegram_bot 注入）、
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

**counts/total 語意**（去重計數）：counts/total = 「本次解析（去重後）商品數」，
以 unique id 計（store.diff 的 by_id dict 覆蓋同名同 ID，BDD #18）；失敗分類維持 0，
無 failed/gone carryover 時與 data/items/ 各分類檔合併筆數一致。

**寫檔分工**：ok/partial → store.save(items, meta)（依分類分組原子寫
 data/items/{g}.json 分類檔 + meta.json，meta 含完整欄位）＋
store.write_daily(day, 當日價格點)（O4：data/daily/{YYYYMMDD}.json，
只含當日成功爬取且價格存在的商品）；failed → store.write_meta(...)（僅寫 meta.json
標記失敗，items 分類檔與 daily 檔均保持原狀）。
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
from .store import STATUS_IN_STOCK, SOURCE_URL, CHECKPOINT_INTERVAL_DAYS, DiffResult, Item, Store

logger = logging.getLogger(__name__)

DROP_THRESHOLD = 0.20  # 商品數驟降保護門檻（與 007 功能共用；邊界恰 80% 不判異常）
NotifyFn = Callable[[str], None]  # 007 telegram 警報 hook

STATUS_OK = "ok"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"


def run_crawler(data_dir: Path, today: date | None = None,
                notify: NotifyFn | None = None) -> int:
    """執行完整管道（規格 §1.8 步驟 1-7），回傳 exit code。

    0 = 成功（含 partial）；1 = 健康檢查擋下（failed，不覆寫 items 檔）；
    2 = 其他執行失敗（由 main() 捕捉意外例外後回傳）。

    counts/total = 「本次解析（去重後）商品數」：以 unique id 計（同名同 ID 重複只算
    一筆，與 store.diff 的 by_id 覆蓋一致）；無 failed/gone carryover 時
    與 data/items/ 各分類檔合併筆數相同。失敗分類 counts=0、previous_total 語意不變。
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
        today_items.extend(items)

    # 去重計數：store.diff 以 by_id dict 覆蓋同名同 ID（BDD #18，最後解析者勝出），
    # 因此 counts/total 依「去重後的今日商品 unique id」計數，與實際儲存筆數一致；
    # 失敗分類不在今日清單 → counts 維持 0（「本次解析數」語意不變）。
    # unique_today 即「今日商品」（去重後），供 write_daily 產出當日價格點檔。
    by_id: dict[str, Item] = {}
    for item in today_items:
        by_id[item.id] = item  # 同名同 ID → 最後解析者覆蓋（與 store.diff 一致）
    unique_today: list[Item] = list(by_id.values())
    counts: dict[str, int] = {c.name: 0 for c in CATEGORIES}
    for item in unique_today:
        counts[item.category] += 1

    # BDD #16 / 007 rule 4：解析出 0 商品但上次有商品的分類 → 視為失敗分類（沿用舊資料）
    for category in CATEGORIES:
        if (counts[category.name] == 0 and category.name not in failed_categories
                and any(i.category == category.name for i in previous_items.values())):
            failed_categories.append(category.name)

    total = len(unique_today)  # == sum(counts.values())（各分類 unique id 數加總）
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
        logger.error("crawler %s: %s（不覆寫 items 分類檔）", day.isoformat(), reason)
        return 1

    # 5. diff → apply（partial：失敗分類既有商品視為「今日未成功爬取」→ carryover，
    #    不誤判 gone、不 append 當日點）
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
    # 5b. 008 稀疏異動價格清單：只取 changed+new 且價格存在者
    sparse_prices: dict[str, int] = {}
    for item in list(diff.changed_items) + list(diff.new_items):
        if item.price is not None:            # 價格缺失（None）不寫入（BDD edge）
            sparse_prices[item.id] = item.price

    # 5c. D2 items gating：僅實質異動分類重寫
    changed_g = _changed_categories(diff, previous_items)

    # 6. meta + save（D2：僅實質異動分類重寫）
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
    """失敗分類（本次無新資料）既有商品視為「今日未成功爬取」：自 gone_ids 移出，
    併入 carryover_ids（apply 原樣保留：last_seen/status/history 不動、不 append 當日點、
    不誤判 gone；規格 §6.2 / BDD #12、#16）。
    refreshed_items 原樣帶過（失敗分類商品不在今日清單 → 天然不會進入 refreshed）。"""
    failed_ids = {iid for iid, item in previous_items.items()
                  if item.category in failed_categories}
    gone_ids = [iid for iid in diff.gone_ids if iid not in failed_ids]
    return DiffResult(new_items=diff.new_items, changed_items=diff.changed_items,
                      refreshed_items=diff.refreshed_items,
                      gone_ids=gone_ids,
                      unchanged_ids=set(diff.unchanged_ids),
                      carryover_ids=set(diff.carryover_ids) | failed_ids)


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


def _changed_categories(diff: DiffResult,
                        previous_items: dict[str, Item] | None = None) -> set[int]:
    """本 run 有「實質異動」的分類 g 集合（D2 gating 基準）：

    new_items / changed_items / refreshed_items（refresh 傳播到 items 檔，不得凍結）
    / gone_ids（標記 gone 須落盤）——任一命中該分類即需重寫；
    純 unchanged / carryover 分類不重寫。回傳 g 索引集合。"""
    from .categories import CATEGORIES
    g_map = {c.name: c.g_index for c in CATEGORIES}
    result: set[int] = set()
    for item in diff.new_items + diff.changed_items + diff.refreshed_items:
        g = g_map.get(item.category)
        if g is not None:
            result.add(g)
    if previous_items:
        for iid in diff.gone_ids:
            item = previous_items.get(iid)
            if item:
                g = g_map.get(item.category)
                if g is not None:
                    result.add(g)
    return result


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
        "已取消覆寫 data/items/ 分類檔，既有資料保持原狀。"
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
