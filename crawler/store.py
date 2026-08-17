"""diff → 每日一點累積 → 原子寫檔。資料真相：data/items/{g}.json（分類分檔）＋
data/meta.json ＋ data/daily/（crawler 唯一寫入者）；對外 API 成品
（api/index.json + api/items/）由 scripts/version_data.py 依本目錄資料重建，
本模組不寫 api/。

本模組是資料的唯一寫入者（IF §5）：載入既有資料、與今日商品比對、
每次成功爬取（商品出現在今日清單且價格存在）都累積當日價格點 [d, p]
（含價格未變的平價日），以 tempfile + os.replace 原子寫出。
今日未成功爬取的商品（失敗分類）原樣保留，不累積當日點。

V2 拆檔（2026-08-17）：items 依分類分檔 data/items/{g}.json——g = 分類 G 頁索引，
檔名 g{index}（g9=記憶卡，其餘 g_index 見 categories.py）。單檔頂層即 array：
無 meta 包裝、無 category 欄位；category 是記憶體內的內部欄位，load 由檔名
回填（檔名 g{i} → categories.get_category(i).name）、save 不序列化。
meta 唯一檔 data/meta.json（不再有內嵌 meta；meta.json 缺失 → 視為首次執行，
items 空）。history 在 save 序列化層截到最近 2 點（漲跌徽章只需前後兩點）；
完整歷史由每日價格點檔 data/daily/{YYYYMMDD}.json（{item_id: price}）承載。
所有 JSON 一律以 compact（separators=(",",":")）寫出；load/diff/apply 邏輯不動
（diff 讀 history[-1] 語意不變）。data/items.json 已不存在。

冪等防護（BDD #21）：同日重跑時末筆歷史已是今日且價格相同 → 不重複 append。

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

from .categories import CATEGORIES, get_category

STATUS_IN_STOCK = "in_stock"
STATUS_GONE = "gone"

META_STATUSES = frozenset({"ok", "partial", "failed"})  # 007 三態（不再有 aborted）
SOURCE_URL = "https://www.coolpc.com.tw/m/m-list.php"

# 分類 name → 檔名用的 G 索引（save 分組寫檔；與 categories.py 白名單一致）
_CATEGORY_G_BY_NAME: dict[str, int] = {c.name: c.g_index for c in CATEGORIES}


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
    history: list[list] = field(default_factory=list)  # compact [[d, p], ...]；每日一點累積（含平價日）

    @property
    def price(self) -> int | None:
        """目前價格 = 歷史末筆價格（今日商品以提議歷史 [[今日, 價格]] 表示）。"""
        if not self.history:
            return None
        return self.history[-1][1]


@dataclass
class DiffResult:
    new_items: list[Item]          # 首次出現
    changed_items: list[Item]      # 價格或狀態異動（將 append 歷史）
    refreshed_items: list[Item]    # flags/spec/subcategory/name 異動（價格/狀態不變；
                                   # 仍 append 當日平價點、更新 last_seen）
    gone_ids: list[str]            # 今日消失（標記 gone）
    unchanged_ids: set[str]        # 今日有且完全無異動（仍 append 當日平價點）
    carryover_ids: set[str] = field(default_factory=set)  # 今日未成功爬取（失敗分類，
                                   # main._exclude_failed_from_gone 併入）：原樣保留、
                                   # 不 append 當日點、不更新 last_seen


class Store:
    """載入既有資料 → diff → apply → 原子寫出（items 依分類分檔）。"""

    def __init__(self, data_dir: Path):
        self._items_dir = data_dir / "items"
        self._meta_path = data_dir / "meta.json"
        self._daily_dir = data_dir / "daily"

    # ── load ────────────────────────────────────────────────────────────────

    def load(self) -> tuple[dict[str, Item], dict[str, Any]]:
        """讀取 meta.json 與 data/items/{g}.json 全部分類檔，合併為 {id: Item}。

        - meta.json 缺失 → 視為首次執行：回傳 (空 dict, 空 dict)，不讀 items 檔
          （items.json 已不存在；首次執行不可能有分類檔；不一致的殘檔不採信）
        - meta.json 存在：逐檔（檔名 g{index}）解析頂層 array，Item.category 由
          「檔名 G 索引 → categories.py name」回填（內部欄位，序列化不含）。
        - 檔案損壞/檔名不符 g{index}.json、G 超出白名單 → 拋 ValueError，
          由 main 判定不覆寫（exit 2）。
        """
        if not self._meta_path.exists():
            return {}, {}
        with self._meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            raise ValueError(f"meta.json 格式錯誤：預期 object（{self._meta_path}）")

        items: dict[str, Item] = {}
        if self._items_dir.is_dir():
            for path in sorted(self._items_dir.glob("g*.json")):
                category = _category_name_from_filename(path)
                with path.open(encoding="utf-8") as f:
                    doc = json.load(f)
                if not isinstance(doc, list):
                    raise ValueError(
                        f"items/{path.name} 格式錯誤：預期頂層 array（{path}）"
                    )
                for entry in doc:
                    if not isinstance(entry, dict) or "id" not in entry:
                        raise ValueError(f"items/{path.name} 格式錯誤：缺少 id（{path}）")
                    item = Item(
                        id=entry["id"],
                        category=category,  # 檔名回填；序列化檔內無 category 欄位
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
        return items, meta

    # ── diff ────────────────────────────────────────────────────────────────

    def diff(self, today_items: list[Item], previous: dict[str, Item]) -> DiffResult:
        """逐商品分類：
        - 今日有、舊無 → new_items
        - 兩者皆有且價格或 status 異動 → changed_items
        - 兩者皆有且價格/status 相同，但 name/subcategory/spec/flags 任一異動 →
          refreshed_items（動態標記 Hot！/任搭↓N/尾盤/↘ 與 spec 修正須傳播，
          不得凍結在 first_seen 當日）
        - 今日無、舊有 → gone_ids
        - 其餘 → unchanged_ids（今日有、價格/status/name/subcategory/spec/flags
          皆無異動；apply 仍會 append 當日平價點，每日一點語意）
        carryover_ids 由本方法保持空（失敗分類商品不在今日清單 → 落入 gone_ids，
        由 main._exclude_failed_from_gone 移入 carryover_ids 原樣保留）。
        重複名稱同 ID 時以最後解析到的價格為準（dict 覆蓋，BDD #18）。"""
        by_id: dict[str, Item] = {}
        for item in today_items:
            by_id[item.id] = item  # 同名同 ID → 最後解析者覆蓋

        new_items: list[Item] = []
        changed_items: list[Item] = []
        refreshed_items: list[Item] = []
        unchanged_ids: set[str] = set()
        for item in by_id.values():
            prev = previous.get(item.id)
            if prev is None:
                new_items.append(item)
            elif item.price != prev.price or item.status != prev.status:
                changed_items.append(item)
            elif (item.name != prev.name or item.subcategory != prev.subcategory
                    or item.spec != prev.spec or item.flags != prev.flags):
                refreshed_items.append(item)
            else:
                unchanged_ids.add(item.id)

        gone_ids = [iid for iid in previous if iid not in by_id]
        return DiffResult(new_items=new_items, changed_items=changed_items,
                          refreshed_items=refreshed_items,
                          gone_ids=gone_ids, unchanged_ids=unchanged_ids)

    # ── apply ───────────────────────────────────────────────────────────────

    def apply(self, diff: DiffResult, today: date, previous: dict[str, Item]) -> list[Item]:
        """產生新的完整 items 清單（每日一點累積語意，含平價日）：
        - new：first_seen=last_seen=今日，history=[[今日, 價格]]（價格 None → 空）
        - changed：append [今日, 新價格]（價格 None 不 append），last_seen=今日；
          name/subcategory/spec/flags 一併更新為今日值
        - refreshed：append [今日, 平價]（每日一點，含平價日）、last_seen=今日；
          name/subcategory/spec/flags 更新為今日值
        - 無異動：append [今日, 平價]（每日一點，含平價日）、last_seen=今日（BDD #5）
        - carryover（今日未成功爬取，失敗分類）：原樣保留，不 append、不更新 last_seen
        - gone：status=gone，last_seen 保持，不新增歷史（BDD #4）
        冪等防護（所有 append 路徑）：末筆歷史已是今日且價格相同 → 不重複 append（BDD #21）"""
        today_str = today.isoformat()
        changed_by_id = {item.id: item for item in diff.changed_items}
        refreshed_by_id = {item.id: item for item in diff.refreshed_items}
        unchanged = set(diff.unchanged_ids)
        carryover = set(diff.carryover_ids)
        gone = set(diff.gone_ids)

        result: list[Item] = []
        for iid, prev in previous.items():
            if iid in carryover:
                result.append(prev)  # 今日未成功爬取（失敗分類）：原樣保留
            elif iid in unchanged:
                history = list(prev.history)
                _append_daily_point(history, today_str, prev.price)
                result.append(replace(prev, last_seen=today_str, history=history))
            elif iid in refreshed_by_id:
                current = refreshed_by_id[iid]
                history = list(prev.history)
                _append_daily_point(history, today_str, current.price)
                result.append(replace(prev, last_seen=today_str, history=history,
                                      name=current.name, subcategory=current.subcategory,
                                      spec=current.spec, flags=current.flags))
            elif iid in gone:
                result.append(replace(prev, status=STATUS_GONE))  # last_seen 保持
            elif iid in changed_by_id:
                current = changed_by_id[iid]
                history = list(prev.history)
                _append_daily_point(history, today_str, current.price)
                result.append(replace(prev, status=current.status,
                                      last_seen=today_str, history=history,
                                      name=current.name, subcategory=current.subcategory,
                                      spec=current.spec, flags=current.flags))
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
        """依分類分組，逐分類原子寫 data/items/{g}.json（頂層 array），並寫 meta.json。

        V2 拆檔契約：
        - 每分類一檔：檔名 g{index} = categories.py 的 G 頁索引（未知分類 → ValueError）；
          檔內純 items array——無 meta 包裝、無 category 欄位（內部欄位不序列化）。
        - 每個 item 的 history 在序列化層截到最近 2 點（不足 2 點原樣）；
          load/diff/apply 仍以完整 history 運作（截斷不影響 diff 讀 history[-1]）。
        - 不再寫任何內嵌 meta；meta 一律唯一檔 data/meta.json。
        - 全部 tempfile + os.replace 原子寫入、compact JSON（separators=(",",":")）；
          任一步失敗拋例外且不影響既有檔案。
        - meta 不再含整數 version 欄位。"""
        meta = {k: v for k, v in meta.items() if k != "version"}
        grouped: dict[int, list[Item]] = {}
        for item in items:
            g = _CATEGORY_G_BY_NAME.get(item.category)
            if g is None:
                raise ValueError(
                    f"未知分類，無法決定 items 檔名（data/items/g{{index}}.json）："
                    f"{item.category!r}"
                )
            grouped.setdefault(g, []).append(item)
        for g in sorted(grouped):
            payload = [dict(asdict(it), history=it.history[-2:]) for it in grouped[g]]
            for entry in payload:
                entry.pop("category", None)  # 序列化不含 category（內部欄位）
            self._write_json_atomic(self._items_dir / f"g{g}.json", payload)
        self._write_json_atomic(self._meta_path, meta)

    def write_daily(self, day: date, price_map: dict[str, int]) -> None:
        """原子寫入 data/daily/{YYYYMMDD}.json = {item_id: price}（O4 每日價格點檔）。

        day 為執行日（date 物件，檔名以 YYYYMMDD 格式化）；price_map 只含當日
        成功爬取且價格存在的商品。全檔 compact JSON（separators=(",",":")），
        tempfile + os.replace 原子寫入；失敗拋例外且不影響既有檔案。"""
        path = self._daily_dir / f"{day.strftime('%Y%m%d')}.json"
        self._write_json_atomic(path, price_map)

    def write_meta(self, *, crawled_at: str, counts: dict[str, int], total: int,
                   changed: int, failed_categories: list[str], status: str) -> None:
        """輸出 meta.json 基礎欄位。status 僅 ok/partial/failed（007 三態）。
        自既有 meta 沿用 previous_total（007 驟降基準），並保留 007 擴充欄位
        （sources/anomaly/checked_at…），不得因覆寫而遺失。
        日期制快照改造後，meta 不再含整數 version 欄位。"""
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
        new_meta.pop("version", None)  # 日期制快照：不再使用整數版本
        self._write_json_atomic(self._meta_path, new_meta)

    # ── 內部工具 ────────────────────────────────────────────────────────────

    def _write_json_atomic(self, path: Path, payload: Any) -> None:
        """同目錄 tempfile + os.replace 原子寫入；任何失敗清理暫存檔並 re-raise。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
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


def _category_name_from_filename(path: Path) -> str:
    """由 items 檔名 g{index}.json 推回分類 name（get_category 白名單查詢）。

    檔名不符 g{index}.json 或 G 超出白名單（非追蹤分類）→ ValueError。"""
    name = path.name
    if not name.startswith("g") or not name.endswith(".json"):
        raise ValueError(
            f"items 檔名格式錯誤（預期 g{{g_index}}.json）：{name}（{path}）"
        )
    stem = name[1:-5]  # 去掉 "g" 前綴與 ".json" 後綴 → 純 G 索引字串
    if not stem.isdigit():
        raise ValueError(
            f"items 檔名格式錯誤（預期 g{{g_index}}.json）：{name}（{path}）"
        )
    g_index = int(stem)
    try:
        return get_category(g_index).name
    except KeyError:
        raise ValueError(
            f"items 檔名對應到未追蹤分類（G={g_index}，白名單外）：{name}（{path}）"
        ) from None


def _append_daily_point(history: list[list], day: str, price: int | None) -> None:
    """每日一點：成功爬取商品當日累積一點（含平價日）；價格缺失不記錄（BDD #19）。
    冪等防護（BDD #21）：末筆歷史已是今日且價格相同 → 不重複 append。"""
    if price is not None and not _is_same_day_same_price(history, day, price):
        history.append([day, price])


def _is_same_day_same_price(history: list[list], day: str, price: int | None) -> bool:
    """末筆歷史已是今日且價格相同（BDD #21 同日冪等判準）。"""
    return bool(history) and history[-1][0] == day and history[-1][1] == price