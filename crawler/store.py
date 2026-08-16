"""diff → 歷史 append → 原子寫檔。資料真相：data/items.json + data/meta.json
（crawler 唯一寫入者）；對外 API 成品（api/index.json + api/items/）由
scripts/version_data.py 依本目錄資料重建，本模組不寫 api/。

本模組是資料的唯一寫入者（IF §5）：載入既有資料、與今日商品比對、
僅在價格/狀態異動時增量 append 歷史 [d, p]、以 tempfile + os.replace 原子寫出。

約定：今日商品的「目前價格」以提議歷史 [[今日, 價格]] 表示（價格缺失 → []），
Item.price property 讀取歷史末筆；既有商品的價格即其最後記錄價格。
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

STATUS_IN_STOCK = "in_stock"
STATUS_GONE = "gone"

META_STATUSES = frozenset({"ok", "partial", "failed"})  # 007 三態（不再有 aborted）
SOURCE_URL = "https://www.coolpc.com.tw/m/m-list.php"


@dataclass
class Item:
    """單一商品。history 為 compact [[d, p], ...]，僅價格/狀態異動時 append。"""

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

    @property
    def price(self) -> int | None:
        """目前價格 = 歷史末筆價格（今日商品以提議歷史 [[今日, 價格]] 表示）。"""
        if not self.history:
            return None
        return self.history[-1][1]


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

    # ── load ────────────────────────────────────────────────────────────────

    def load(self) -> tuple[dict[str, Item], dict[str, Any]]:
        """讀取 items.json（依 id 建索引）與 meta.json。
        首次執行（檔案不存在）回傳空 dict；檔案損壞 → 拋例外，由 main 判定不覆寫。"""
        items: dict[str, Item] = {}
        embedded_meta: dict[str, Any] = {}
        if self._items_path.exists():
            doc = json.loads(self._items_path.read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
                raise ValueError(f"items.json 格式錯誤：缺少 items 陣列（{self._items_path}）")
            if isinstance(doc.get("meta"), dict):
                embedded_meta = doc["meta"]
            for entry in doc["items"]:
                item = Item(
                    id=entry["id"],
                    category=entry.get("category", ""),
                    subcategory=entry.get("subcategory", ""),
                    name=entry.get("name", ""),
                    spec=entry.get("spec") or {},
                    flags=entry.get("flags") or {},
                    status=entry.get("status", STATUS_IN_STOCK),
                    first_seen=entry.get("first_seen", ""),
                    last_seen=entry.get("last_seen", ""),
                    history=entry.get("history") or [],
                )
                items[item.id] = item
        meta: dict[str, Any] = {}
        if self._meta_path.exists():
            meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                raise ValueError(f"meta.json 格式錯誤：預期 object（{self._meta_path}）")
        elif embedded_meta:
            meta = embedded_meta
        return items, meta

    # ── diff ────────────────────────────────────────────────────────────────

    def diff(self, today_items: list[Item], previous: dict[str, Item]) -> DiffResult:
        """逐商品分類：
        - 今日有、舊無 → new_items
        - 兩者皆有且價格或 status 異動 → changed_items
        - 今日無、舊有 → gone_ids
        - 其餘 → unchanged_ids
        重複名稱同 ID 時以最後解析到的價格為準（dict 覆蓋，BDD #18）。"""
        by_id: dict[str, Item] = {}
        for item in today_items:
            by_id[item.id] = item  # 同名同 ID → 最後解析者覆蓋

        new_items: list[Item] = []
        changed_items: list[Item] = []
        unchanged_ids: set[str] = set()
        for item in by_id.values():
            prev = previous.get(item.id)
            if prev is None:
                new_items.append(item)
            elif item.price != prev.price or item.status != prev.status:
                changed_items.append(item)
            else:
                unchanged_ids.add(item.id)

        gone_ids = [iid for iid in previous if iid not in by_id]
        return DiffResult(new_items=new_items, changed_items=changed_items,
                          gone_ids=gone_ids, unchanged_ids=unchanged_ids)

    # ── apply ───────────────────────────────────────────────────────────────

    def apply(self, diff: DiffResult, today: date, previous: dict[str, Item]) -> list[Item]:
        """產生新的完整 items 清單：
        - new：first_seen=last_seen=今日，history=[[今日, 價格]]（價格 None → 空）
        - changed：append [今日, 新價格]（價格 None 不 append），last_seen=今日；
          冪等防護：末筆歷史已是今日且價格相同 → 不重複 append（BDD #21）
        - gone：status=gone，last_seen 保持，不新增歷史（BDD #4）
        - 無異動：原樣保留（BDD #5）"""
        today_str = today.isoformat()
        changed_by_id = {item.id: item for item in diff.changed_items}
        unchanged = set(diff.unchanged_ids)
        gone = set(diff.gone_ids)

        result: list[Item] = []
        for iid, prev in previous.items():
            if iid in unchanged:
                result.append(prev)  # 原樣保留，不 append
            elif iid in gone:
                result.append(replace(prev, status=STATUS_GONE))  # last_seen 保持
            elif iid in changed_by_id:
                current = changed_by_id[iid]
                history = list(prev.history)
                price = current.price
                if price is not None and not _is_same_day_same_price(history, today_str, price):
                    history.append([today_str, price])
                result.append(replace(prev, status=current.status,
                                      last_seen=today_str, history=history))
            else:  # 防禦：diff 未涵蓋的既有 id（不應發生）→ 不誤刪，維持原樣
                result.append(prev)

        for new_item in diff.new_items:
            price = new_item.price
            history = [[today_str, price]] if price is not None else []
            result.append(replace(new_item, status=STATUS_IN_STOCK,
                                  first_seen=today_str, last_seen=today_str,
                                  history=history))
        return result

    # ── save ────────────────────────────────────────────────────────────────

    def save(self, items: list[Item], meta: dict[str, Any]) -> None:
        """原子寫入 items.json（{"meta": ..., "items": [...]}）與 meta.json。
        兩檔皆 tempfile + os.replace；失敗拋例外且不影響既有檔案。"""
        doc = {"meta": meta, "items": [asdict(item) for item in items]}
        self._write_json_atomic(self._items_path, doc)
        self._write_json_atomic(self._meta_path, meta)

    def write_meta(self, *, crawled_at: str, counts: dict[str, int], total: int,
                   changed: int, failed_categories: list[str], status: str) -> None:
        """輸出 meta.json 基礎欄位。status 僅 ok/partial/failed（007 三態）。
        自既有 meta 沿用 version（002 cache-busting）與 previous_total（007 驟降基準），
        並保留 007 擴充欄位（sources/anomaly/checked_at…），不得因覆寫而遺失。"""
        if status not in META_STATUSES:
            raise ValueError(f"無效 meta status：{status!r}，僅允許 {sorted(META_STATUSES)}")

        old: dict[str, Any] = {}
        if self._meta_path.exists():
            old = json.loads(self._meta_path.read_text(encoding="utf-8"))
            if not isinstance(old, dict):
                raise ValueError(f"meta.json 格式錯誤：預期 object（{self._meta_path}）")

        new_meta = dict(old)
        new_meta.update({
            "crawled_at": crawled_at,
            "source": SOURCE_URL,
            "counts": counts,
            "total": total,
            "previous_total": old.get("previous_total"),  # 沿用；不存在 → None
            "changed": changed,
            "failed_categories": failed_categories,
            "status": status,
        })
        new_meta.setdefault("version", 0)  # 沿用；不存在 → 0
        self._write_json_atomic(self._meta_path, new_meta)

    # ── 內部工具 ────────────────────────────────────────────────────────────

    def _write_json_atomic(self, path: Path, payload: Any) -> None:
        """同目錄 tempfile + os.replace 原子寫入；任何失敗清理暫存檔並 re-raise。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def _is_same_day_same_price(history: list[list], day: str, price: int | None) -> bool:
    """末筆歷史已是今日且價格相同（BDD #21 同日冪等判準）。"""
    return bool(history) and history[-1][0] == day and history[-1][1] == price
