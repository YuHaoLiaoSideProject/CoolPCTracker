"""store.py 單元測試（BDD #2 新商品、#3 價格異動、#4 gone、#5 平價日仍累積一點、
#18 重複名稱、#19 價格缺失、#21 同日重複執行 + 原子寫入 + meta；
refreshed：flags/spec/subcategory/name 異動傳播（code review 發現 #1 修復））。

每日一點語意：每次成功爬取（商品出現在今日清單）都 append 當日價格點，含平價日；
同日重跑（末筆歷史已是今日且價格相同）不重複 append。
失敗分類商品（今日未成功爬取）→ carryover_ids → 原樣保留。

V2 拆檔契約：items 依分類分檔 data/items/{g}.json（g = 分類 G 頁索引，檔名 g{index}；
頂層即 array——無 meta 包裝、無 category 欄位；category 是內部欄位，load 由檔名
回填、save 不序列化）；meta 唯一檔 data/meta.json（不再有內嵌 meta；meta.json
缺失 → 視為首次執行、items 空）。save 在序列化層把每個 item 的 history 截到最近
2 點（不影響記憶體中完整 history、不影響 load/diff/apply）；每日價格點由
write_daily 寫入 data/daily/{YYYYMMDD}.json = {id: price}；所有寫入皆 compact JSON。

store 測試一律使用 pytest tmp_path，不碰真實檔案系統。
今日商品以「提議歷史 [[今日, 價格]]」傳入 diff；價格缺失時 history=[]。
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

import crawler.store as store_module
from crawler.categories import CATEGORIES
from crawler.store import DiffResult, Item, STATUS_GONE, STATUS_IN_STOCK, Store

TODAY = date(2026, 8, 16)
TODAY_STR = "2026-08-16"
YESTERDAY = date(2026, 8, 15)
YESTERDAY_STR = "2026-08-15"


def make_item(item_id: str = "a1", name: str = "測試商品", category: str = "CPU",
              subcategory: str = "Intel 第14代", price: int | None = None, *,
              spec: dict | None = None, flags: dict | None = None,
              status: str = STATUS_IN_STOCK, first_seen: str = "",
              last_seen: str = "", history: list[list] | None = None,
              day: str = TODAY_STR) -> Item:
    """建立 Item。history 未指定時以「當日提議歷史」[[day, price]] 表示（價格 None → []）。"""
    if history is None:
        history = [[day, price]] if price is not None else []
    return Item(id=item_id, category=category, subcategory=subcategory, name=name,
                spec=spec or {}, flags=flags or {}, status=status,
                first_seen=first_seen, last_seen=last_seen, history=history)


def write_items_file(tmp_path: Path, g_index: int, entries: list[dict]) -> Path:
    """直接寫一個分類檔 data/items/g{g_index}.json（模擬既有資料；頂層 array）。"""
    items_dir = tmp_path / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    path = items_dir / f"g{g_index}.json"
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


def write_meta_file(tmp_path: Path, meta: dict) -> Path:
    path = tmp_path / "meta.json"
    path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return path


def g_filename(category_name: str) -> str:
    """分類 name → 預期檔名 g{index}.json（與 categories.py 白名單一致）。"""
    g = next(c.g_index for c in CATEGORIES if c.name == category_name)
    return f"g{g}.json"


# ── load ────────────────────────────────────────────────────────────────────

class TestLoad:
    def test_first_run_no_files_returns_empty(self, tmp_path):
        store = Store(tmp_path)
        items, meta = store.load()
        assert items == {}
        assert meta == {}

    def test_meta_missing_treats_as_first_run_items_empty(self, tmp_path):
        """V2：meta.json 缺失 → 視為首次執行 → items 空（即使 items/ 有殘檔也不採信）。"""
        write_items_file(tmp_path, 4, [
            {"id": "a1", "subcategory": "Intel 第14代", "name": "Intel i5-13600K",
             "spec": {}, "flags": {}, "status": "in_stock",
             "first_seen": "2026-08-15", "last_seen": "2026-08-15",
             "history": [["2026-08-15", 9990]]},
        ])
        items, meta = Store(tmp_path).load()
        assert items == {}
        assert meta == {}

    def test_load_merges_all_category_files_and_backfills_category(self, tmp_path):
        """V2：讀 data/items/{g}.json 全部檔合併；category 由檔名 g{i} 回填。"""
        write_meta_file(tmp_path, {"crawled_at": "2026-08-15T06:00:00Z"})
        write_items_file(tmp_path, 4, [
            {"id": "a1", "subcategory": "Intel 第14代", "name": "Intel i5-13600K",
             "spec": {"brand": "Intel"}, "flags": {"hot": True}, "status": "in_stock",
             "first_seen": "2026-08-15", "last_seen": "2026-08-15",
             "history": [["2026-08-15", 9990]]},
        ])
        write_items_file(tmp_path, 12, [
            {"id": "a2", "subcategory": "RTX 4060", "name": "MSI RTX 4060",
             "spec": {}, "flags": {}, "status": "gone",
             "first_seen": "2026-08-15", "last_seen": "2026-08-15",
             "history": [["2026-08-15", 9990]]},
        ])
        items, meta = Store(tmp_path).load()
        assert set(items) == {"a1", "a2"}
        assert items["a1"].category == "CPU"       # 檔名 g4.json → CPU
        assert items["a2"].category == "顯示卡"    # 檔名 g12.json → 顯示卡
        assert items["a1"].name == "Intel i5-13600K"
        assert items["a1"].history == [["2026-08-15", 9990]]
        assert items["a1"].price == 9990
        assert items["a2"].status == STATUS_GONE
        assert meta == {"crawled_at": "2026-08-15T06:00:00Z"}

    def test_load_meta_reads_only_meta_json(self, tmp_path):
        """V2：meta 一律讀 data/meta.json；items 檔無任何內嵌 meta 可回退。"""
        write_meta_file(tmp_path, {"crawled_at": "2026-08-15T06:00:00Z", "previous_total": 2})
        write_items_file(tmp_path, 4, [
            {"id": "a1", "name": "Intel i5-13600K", "subcategory": "", "spec": {},
             "flags": {}, "status": "in_stock", "first_seen": "2026-08-15",
             "last_seen": "2026-08-15", "history": [["2026-08-15", 9990]]},
        ])
        _, meta = Store(tmp_path).load()
        assert meta == {"crawled_at": "2026-08-15T06:00:00Z", "previous_total": 2}

    def test_load_missing_items_dir_returns_empty(self, tmp_path):
        """meta.json 存在但 items/ 不存在 → items 空（後續正常建立分類檔）。"""
        write_meta_file(tmp_path, {"status": "ok"})
        items, meta = Store(tmp_path).load()
        assert items == {}
        assert meta == {"status": "ok"}

    def test_load_entry_optional_fields_default(self, tmp_path):
        """無 category 欄位 + 缺省欄位 → 預設值；category 由檔名回填。"""
        write_meta_file(tmp_path, {"status": "ok"})
        write_items_file(tmp_path, 6, [{"id": "m1", "name": "DDR5 32G"}])
        items, _ = Store(tmp_path).load()
        r = items["m1"]
        assert r.category == "記憶體"  # g6.json → 記憶體
        assert r.subcategory == ""
        assert r.spec == {}
        assert r.flags == {}
        assert r.status == STATUS_IN_STOCK
        assert r.first_seen == ""
        assert r.history == []
        assert r.price is None

    def test_load_corrupt_meta_json_raises(self, tmp_path):
        (tmp_path / "meta.json").write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ValueError):
            Store(tmp_path).load()

    def test_load_corrupt_items_file_raises(self, tmp_path):
        write_meta_file(tmp_path, {"status": "ok"})
        write_items_file(tmp_path, 4, [{"id": "a1", "name": "x"}])
        (tmp_path / "items" / "g6.json").write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ValueError):
            Store(tmp_path).load()

    def test_load_items_file_must_be_array(self, tmp_path):
        """單檔頂層必須是 array（無 meta 包裝）：object → ValueError。"""
        write_meta_file(tmp_path, {"status": "ok"})
        (tmp_path / "items").mkdir()
        (tmp_path / "items" / "g4.json").write_text(
            json.dumps({"meta": {}, "items": []}), encoding="utf-8")
        with pytest.raises(ValueError):
            Store(tmp_path).load()

    def test_load_rejects_malformed_filename(self, tmp_path):
        write_meta_file(tmp_path, {"status": "ok"})
        (tmp_path / "items").mkdir()
        (tmp_path / "items" / "gx.json").write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError, match="檔名格式錯誤"):
            Store(tmp_path).load()

    def test_load_rejects_untracked_g_index(self, tmp_path):
        """檔名 G 超出追蹤白名單（如 g2）→ ValueError（白名單外永不抓取）。"""
        write_meta_file(tmp_path, {"status": "ok"})
        write_items_file(tmp_path, 2, [{"id": "x1", "name": "未知分類商品"}])
        with pytest.raises(ValueError, match="未追蹤分類"):
            Store(tmp_path).load()


# ── diff ────────────────────────────────────────────────────────────────────

class TestDiff:
    def test_classifies_new_changed_gone_unchanged(self, tmp_path):
        store = Store(tmp_path)
        previous = {
            "old": make_item("old", name="既有同價", price=9990,
                             history=[[YESTERDAY_STR, 9990]],
                             first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
            "changed": make_item("changed", name="漲價", price=9990,
                                 history=[[YESTERDAY_STR, 9990]],
                                 first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
            "gone": make_item("gone", name="消失", price=8888,
                              history=[[YESTERDAY_STR, 8888]],
                              first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        today_items = [
            make_item("old", name="既有同價", price=9990),      # #5 無異動 → unchanged
            make_item("changed", name="漲價", price=10490),     # #3 價格異動 → changed
            make_item("brand_new", name="新商品", price=7990),  # #2 新商品 → new
        ]
        diff = store.diff(today_items, previous)
        assert [i.id for i in diff.new_items] == ["brand_new"]
        assert [i.id for i in diff.changed_items] == ["changed"]
        assert diff.gone_ids == ["gone"]
        assert diff.unchanged_ids == {"old"}

    def test_status_change_gone_to_in_stock_is_changed(self, tmp_path):
        store = Store(tmp_path)
        previous = {
            "r1": make_item("r1", name="重新上架", price=8888, status=STATUS_GONE,
                            history=[[YESTERDAY_STR, 8888]],
                            first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        today_items = [make_item("r1", name="重新上架", price=8888)]
        diff = store.diff(today_items, previous)
        assert [i.id for i in diff.changed_items] == ["r1"]
        assert diff.gone_ids == []
        assert diff.unchanged_ids == set()

    def test_duplicate_name_same_id_last_price_wins(self, tmp_path):
        """#18 同分類同名（同 ID）兩筆 → 只產生一筆，以最後解析到的價格為準。"""
        store = Store(tmp_path)
        today_items = [
            make_item("dup", name="Intel i5-13600K", price=9990),
            make_item("dup", name="Intel i5-13600K", price=9790),  # 最後解析者
        ]
        diff = store.diff(today_items, {})
        assert len(diff.new_items) == 1
        assert diff.new_items[0].id == "dup"
        assert diff.new_items[0].price == 9790

    def test_duplicate_name_with_previous_single_changed_entry(self, tmp_path):
        """#18 既有商品同名重複時亦僅一筆 changed，價格以最後解析者為準。"""
        store = Store(tmp_path)
        previous = {
            "dup": make_item("dup", name="Intel i5-13600K", price=9990,
                             history=[[YESTERDAY_STR, 9990]],
                             first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        today_items = [
            make_item("dup", name="Intel i5-13600K", price=9990),
            make_item("dup", name="Intel i5-13600K", price=9790),
        ]
        diff = store.diff(today_items, previous)
        assert len(diff.new_items) == 0
        assert [i.id for i in diff.changed_items] == ["dup"]
        assert diff.changed_items[0].price == 9790


# ── apply ───────────────────────────────────────────────────────────────────

class TestApply:
    def test_new_item(self, tmp_path):
        """#2 新商品：first_seen=last_seen=今日、status=in_stock、history 一筆今日價格。"""
        store = Store(tmp_path)
        new_item = make_item("n1", name="Intel i5-13600K", price=9990)
        diff = DiffResult(new_items=[new_item], changed_items=[], refreshed_items=[],
                          gone_ids=[], unchanged_ids=set())
        result = store.apply(diff, TODAY, {})
        assert len(result) == 1
        r = result[0]
        assert r.id == "n1"
        assert r.status == STATUS_IN_STOCK
        assert r.first_seen == TODAY_STR
        assert r.last_seen == TODAY_STR
        assert r.history == [[TODAY_STR, 9990]]

    def test_new_item_without_price_empty_history(self, tmp_path):
        """#19 新商品價格缺失：history=[]，狀態仍 in_stock。"""
        store = Store(tmp_path)
        new_item = make_item("n2", name="無標價新品", price=None)
        assert new_item.history == []
        diff = DiffResult(new_items=[new_item], changed_items=[], refreshed_items=[],
                          gone_ids=[], unchanged_ids=set())
        result = store.apply(diff, TODAY, {})
        r = result[0]
        assert r.history == []
        assert r.status == STATUS_IN_STOCK
        assert r.first_seen == TODAY_STR
        assert r.last_seen == TODAY_STR

    def test_price_change_appends_history(self, tmp_path):
        """#3 價格異動：history 尾端 append [今日, 新價]、last_seen=今日、原歷史保留。"""
        store = Store(tmp_path)
        prev = {
            "c1": make_item("c1", name="Intel i5-13600K", price=9990,
                            history=[[YESTERDAY_STR, 9990]],
                            first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        changed = make_item("c1", name="Intel i5-13600K", price=9790)
        diff = DiffResult(new_items=[], changed_items=[changed], refreshed_items=[],
                          gone_ids=[], unchanged_ids=set())
        result = store.apply(diff, TODAY, prev)
        assert len(result) == 1
        r = result[0]
        assert r.history == [[YESTERDAY_STR, 9990], [TODAY_STR, 9790]]
        assert r.last_seen == TODAY_STR
        assert r.first_seen == YESTERDAY_STR
        assert r.status == STATUS_IN_STOCK

    def test_gone_keeps_last_seen_no_new_history(self, tmp_path):
        """#4 gone：status=gone、last_seen 保持最後出現日（昨日）、不新增今日歷史。"""
        store = Store(tmp_path)
        prev = {
            "g1": make_item("g1", name="AMD R5 7600 主機板套餐", price=8888,
                            history=[[YESTERDAY_STR, 8888]],
                            first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        diff = DiffResult(new_items=[], changed_items=[], refreshed_items=[],
                          gone_ids=["g1"], unchanged_ids=set())
        result = store.apply(diff, TODAY, prev)
        r = result[0]
        assert r.status == STATUS_GONE
        assert r.last_seen == YESTERDAY_STR
        assert r.first_seen == YESTERDAY_STR
        assert r.history == [[YESTERDAY_STR, 8888]]

    def test_unchanged_flat_day_appends_daily_point(self, tmp_path):
        """#5 新語意（每日一點）：價格/狀態皆無異動 → 仍 append 當日平價點、last_seen=今日。"""
        store = Store(tmp_path)
        prev_item = make_item("u1", price=9990, history=[[YESTERDAY_STR, 9990]],
                              first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR)
        diff = DiffResult(new_items=[], changed_items=[], refreshed_items=[],
                          gone_ids=[], unchanged_ids={"u1"})
        result = store.apply(diff, TODAY, {"u1": prev_item})
        assert result[0] is not prev_item
        assert result[0].history == [[YESTERDAY_STR, 9990], [TODAY_STR, 9990]]  # 平價日仍累積
        assert result[0].last_seen == TODAY_STR
        assert result[0].first_seen == YESTERDAY_STR
        assert result[0].status == STATUS_IN_STOCK

    def test_carryover_failed_category_kept_as_is(self, tmp_path):
        """失敗分類（今日未成功爬取，carryover）：原樣保留，不 append 當日點、last_seen 不更新。"""
        store = Store(tmp_path)
        prev_item = make_item("m1", price=9990, history=[[YESTERDAY_STR, 9990]],
                              first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR)
        diff = DiffResult(new_items=[], changed_items=[], refreshed_items=[],
                          gone_ids=[], unchanged_ids=set(), carryover_ids={"m1"})
        result = store.apply(diff, TODAY, {"m1": prev_item})
        assert result[0] is prev_item
        assert result[0].history == [[YESTERDAY_STR, 9990]]  # 不 append 當日點
        assert result[0].last_seen == YESTERDAY_STR
        assert result[0].status == STATUS_IN_STOCK

    def test_missing_price_no_history_but_in_stock(self, tmp_path):
        """#19 價格缺失：不記錄該日歷史、商品仍依出現與否判定 status（in_stock）。"""
        store = Store(tmp_path)
        prev = {
            "p1": make_item("p1", price=9990, history=[[YESTERDAY_STR, 9990]],
                            first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        changed = make_item("p1", price=None)
        assert changed.price is None
        diff = DiffResult(new_items=[], changed_items=[changed], refreshed_items=[],
                          gone_ids=[], unchanged_ids=set())
        result = store.apply(diff, TODAY, prev)
        r = result[0]
        assert r.history == [[YESTERDAY_STR, 9990]]  # 不 append
        assert r.last_seen == TODAY_STR              # 今日仍出現 → last_seen 更新
        assert r.status == STATUS_IN_STOCK

    def test_same_day_rerun_unchanged_no_duplicate(self, tmp_path):
        """#21 同日重複執行（diff+apply 全流程）：末筆歷史已是今日且價格相同 →
        不重複 append（平價日亦不重複）。"""
        store = Store(tmp_path)
        prev = {
            "u1": make_item("u1", price=9990, history=[[YESTERDAY_STR, 9990], [TODAY_STR, 9990]],
                            first_seen=YESTERDAY_STR, last_seen=TODAY_STR),
        }
        today_items = [make_item("u1", price=9990)]  # 價格/狀態皆無異動
        diff = store.diff(today_items, prev)
        assert diff.unchanged_ids == {"u1"}
        result = store.apply(diff, TODAY, prev)
        assert result[0].history == [[YESTERDAY_STR, 9990], [TODAY_STR, 9990]]

    def test_apply_guard_prevents_same_day_same_price_append(self, tmp_path):
        """#21 apply 層級防護：changed 但末筆歷史已是今日且價格相同 → 不重複 append（冪等）。"""
        store = Store(tmp_path)
        prev = {
            "c1": make_item("c1", price=9990, history=[[TODAY_STR, 9990]],
                            first_seen=YESTERDAY_STR, last_seen=TODAY_STR),
        }
        changed = make_item("c1", price=9990)
        diff = DiffResult(new_items=[], changed_items=[changed], refreshed_items=[],
                          gone_ids=[], unchanged_ids=set())
        result = store.apply(diff, TODAY, prev)
        assert result[0].history == [[TODAY_STR, 9990]]

    def test_reappear_after_gone_updates_status_and_last_seen(self, tmp_path):
        """gone 商品重新出現：status 回 in_stock、append 今日價格、last_seen=今日。"""
        store = Store(tmp_path)
        prev = {
            "r1": make_item("r1", price=8888, status=STATUS_GONE, history=[[YESTERDAY_STR, 8888]],
                            first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        today_items = [make_item("r1", price=8888)]
        diff = store.diff(today_items, prev)
        assert [i.id for i in diff.changed_items] == ["r1"]
        result = store.apply(diff, TODAY, prev)
        r = result[0]
        assert r.status == STATUS_IN_STOCK
        assert r.last_seen == TODAY_STR
        assert r.history == [[YESTERDAY_STR, 8888], [TODAY_STR, 8888]]


# ── refreshed（flags/spec 凍結缺陷修復：動態標記與 spec 修正須傳播） ──────────

class TestRefreshed:
    def test_flags_only_change_is_refreshed_not_unchanged(self, tmp_path):
        """flags 變動（Hot！出現）、價格/狀態不變 → refreshed（非 changed、非 unchanged）。"""
        store = Store(tmp_path)
        prev = {
            "f1": make_item("f1", name="Intel i5-13600K", price=9990,
                            history=[[YESTERDAY_STR, 9990]],
                            first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        today_items = [make_item("f1", name="Intel i5-13600K", price=9990,
                                 flags={"hot": True})]
        diff = store.diff(today_items, prev)
        assert [i.id for i in diff.refreshed_items] == ["f1"]
        assert diff.changed_items == []
        assert diff.unchanged_ids == set()

    def test_spec_fix_is_refreshed(self, tmp_path):
        """spec 修正（brand 補上）→ refreshed。"""
        store = Store(tmp_path)
        prev = {
            "s1": make_item("s1", name="Intel i5-13600K", price=9990,
                            spec={"brand": None, "model": None, "extra": {}},
                            history=[[YESTERDAY_STR, 9990]],
                            first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        today_items = [make_item("s1", name="Intel i5-13600K", price=9990,
                                 spec={"brand": "Intel", "model": "i5-13600K", "extra": {}})]
        diff = store.diff(today_items, prev)
        assert [i.id for i in diff.refreshed_items] == ["s1"]
        assert diff.unchanged_ids == set()

    def test_name_or_subcategory_change_is_refreshed(self, tmp_path):
        """name/subcategory 異動（price/status 相同）→ refreshed。"""
        store = Store(tmp_path)
        prev = {
            "n1": make_item("n1", name="舊名稱", subcategory="舊子分類", price=9990,
                            history=[[YESTERDAY_STR, 9990]],
                            first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        today_items = [make_item("n1", name="新名稱", subcategory="新子分類", price=9990)]
        diff = store.diff(today_items, prev)
        assert [i.id for i in diff.refreshed_items] == ["n1"]
        assert diff.changed_items == []
        assert diff.unchanged_ids == set()

    def test_apply_refreshed_updates_fields_appends_daily_point(self, tmp_path):
        """refreshed：name/subcategory/spec/flags 更新為今日值；append 當日平價點（每日一點）、
        last_seen=今日（今日成功爬取）。"""
        store = Store(tmp_path)
        prev = {
            "f1": make_item("f1", name="舊名稱", subcategory="舊子分類", price=9990,
                            spec={"brand": None}, flags={},
                            history=[[YESTERDAY_STR, 9990]],
                            first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        refreshed = make_item("f1", name="新名稱", subcategory="新子分類", price=9990,
                              spec={"brand": "Intel"}, flags={"hot": True})
        diff = DiffResult(new_items=[], changed_items=[], refreshed_items=[refreshed],
                          gone_ids=[], unchanged_ids=set())
        result = store.apply(diff, TODAY, prev)
        assert len(result) == 1
        r = result[0]
        assert r.name == "新名稱"
        assert r.subcategory == "新子分類"
        assert r.spec == {"brand": "Intel"}
        assert r.flags == {"hot": True}
        assert r.history == [[YESTERDAY_STR, 9990], [TODAY_STR, 9990]]  # 平價日仍 append
        assert r.last_seen == TODAY_STR           # 今日成功爬取 → last_seen 更新
        assert r.first_seen == YESTERDAY_STR
        assert r.status == STATUS_IN_STOCK
        assert r.price == 9990

    def test_changed_with_flags_updates_flags_and_appends_history(self, tmp_path):
        """價格異動同時 flags 變動 → changed 分支：flags/spec 一併更新、歷史照常 append。"""
        store = Store(tmp_path)
        prev = {
            "c1": make_item("c1", name="Intel i5-13600K", price=9990, flags={},
                            history=[[YESTERDAY_STR, 9990]],
                            first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        }
        changed = make_item("c1", name="Intel i5-13600K", price=9790,
                            flags={"hot": True, "price_drop": True},
                            spec={"brand": "Intel"})
        diff = DiffResult(new_items=[], changed_items=[changed], refreshed_items=[],
                          gone_ids=[], unchanged_ids=set())
        result = store.apply(diff, TODAY, prev)
        r = result[0]
        assert r.flags == {"hot": True, "price_drop": True}
        assert r.spec == {"brand": "Intel"}
        assert r.history == [[YESTERDAY_STR, 9990], [TODAY_STR, 9790]]
        assert r.last_seen == TODAY_STR

    def test_unchanged_no_flags_diff_appends_daily_point(self, tmp_path):
        """完全無異動（含 flags/spec/name/subcategory）→ unchanged：append 當日平價點、
        last_seen=今日（每日一點語意）。"""
        store = Store(tmp_path)
        prev_item = make_item("u1", name="Intel i5-13600K", price=9990,
                              flags={"hot": True}, spec={"brand": "Intel"},
                              history=[[YESTERDAY_STR, 9990]],
                              first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR)
        today_items = [make_item("u1", name="Intel i5-13600K", price=9990,
                                 flags={"hot": True}, spec={"brand": "Intel"})]
        diff = store.diff(today_items, {"u1": prev_item})
        assert diff.refreshed_items == []
        assert diff.changed_items == []
        assert diff.unchanged_ids == {"u1"}
        result = store.apply(diff, TODAY, {"u1": prev_item})
        assert result[0] is not prev_item
        assert result[0].history == [[YESTERDAY_STR, 9990], [TODAY_STR, 9990]]  # 平價日仍累積
        assert result[0].last_seen == TODAY_STR


# ── save（V2：依分類分檔 data/items/{g}.json） ───────────────────────────────

class TestSave:
    @staticmethod
    def _assert_compact(path: Path) -> None:
        """全檔 compact（separators=(",",":")）：重新序列化自己的內容應逐字元相同。"""
        raw = path.read_text(encoding="utf-8")
        assert raw == json.dumps(json.loads(raw), ensure_ascii=False,
                                 separators=(",", ":")) + "\n"

    def test_save_writes_per_category_files_without_meta_or_category(self, tmp_path):
        """V2：依分類分組寫 data/items/g{index}.json——頂層 array、無 meta 包裝、
        無 category 欄位；meta 唯一檔 data/meta.json。"""
        store = Store(tmp_path)
        items = [
            make_item("a1", name="Intel i5-13600K", price=9790, status=STATUS_IN_STOCK,
                      first_seen=YESTERDAY_STR, last_seen=TODAY_STR,
                      history=[[YESTERDAY_STR, 9990], [TODAY_STR, 9790]],
                      spec={"brand": "Intel", "model": "i5-13600K"}, flags={"hot": True}),
            make_item("gpu1", name="RTX 5090", category="顯示卡", price=49990,
                      first_seen=YESTERDAY_STR, last_seen=TODAY_STR,
                      history=[[YESTERDAY_STR, 50990], [TODAY_STR, 49990]]),
        ]
        meta = {"crawled_at": "2026-08-16T06:00:00Z", "status": "ok"}
        store.save(items, meta)

        cpu_file = tmp_path / "items" / g_filename("CPU")        # g4.json
        gpu_file = tmp_path / "items" / g_filename("顯示卡")     # g12.json
        assert cpu_file.exists()
        assert gpu_file.exists()
        # 無 meta 包裝：頂層就是 array
        cpu_doc = json.loads(cpu_file.read_text(encoding="utf-8"))
        assert isinstance(cpu_doc, list)
        assert len(cpu_doc) == 1
        # 無 category 欄位；其餘欄位完整保留
        assert cpu_doc[0] == {
            "id": "a1", "subcategory": "Intel 第14代",
            "name": "Intel i5-13600K",
            "spec": {"brand": "Intel", "model": "i5-13600K"},
            "flags": {"hot": True},
            "status": "in_stock",
            "first_seen": "2026-08-15", "last_seen": "2026-08-16",
            "history": [["2026-08-15", 9990], ["2026-08-16", 9790]],
        }
        gpu_doc = json.loads(gpu_file.read_text(encoding="utf-8"))
        assert len(gpu_doc) == 1
        assert gpu_doc[0]["id"] == "gpu1"
        assert "category" not in gpu_doc[0]
        assert "meta" not in gpu_doc  # 檔內無任何 meta 包裝
        # meta 唯一檔
        assert json.loads((tmp_path / "meta.json").read_text(encoding="utf-8")) == meta
        # data/items.json 不存在（由 data/items/ 目錄取代）
        assert not (tmp_path / "items.json").exists()
        self._assert_compact(cpu_file)  # V2：分類檔全檔 compact 寫入
        self._assert_compact(gpu_file)
        self._assert_compact(tmp_path / "meta.json")

    def test_save_truncates_history_to_last_two_points(self, tmp_path):
        """O4：save 序列化層把 history 截到最近 2 點（保留末 2 點）；不足 2 點原樣。
        截斷只發生在寫檔層，記憶體中 item 的完整 history 不受影響。"""
        store = Store(tmp_path)
        full_history = [
            ["2026-08-10", 9990], ["2026-08-11", 9990], ["2026-08-12", 10490],
            ["2026-08-15", 10490], ["2026-08-16", 9790],
        ]
        item = make_item("a1", name="Intel i5-13600K", price=9790,
                         first_seen="2026-08-10", last_seen=TODAY_STR,
                         history=full_history)
        store.save([item], {"status": "ok"})

        doc = json.loads((tmp_path / "items" / g_filename("CPU")).read_text(encoding="utf-8"))
        assert doc[0]["history"] == [["2026-08-15", 10490], ["2026-08-16", 9790]]
        assert item.history == full_history  # 記憶體中的完整 history 不受截斷影響

    def test_save_short_history_kept_as_is(self, tmp_path):
        """O4：history 不足 2 點（1 點或空）→ 原樣寫出。"""
        store = Store(tmp_path)
        one_point = make_item("a1", price=9990, history=[[TODAY_STR, 9990]],
                              first_seen=TODAY_STR, last_seen=TODAY_STR)
        no_history = make_item("a2", price=None, history=[])
        store.save([one_point, no_history], {"status": "ok"})
        doc = json.loads((tmp_path / "items" / g_filename("CPU")).read_text(encoding="utf-8"))
        by_id = {i["id"]: i for i in doc}
        assert by_id["a1"]["history"] == [[TODAY_STR, 9990]]
        assert by_id["a2"]["history"] == []

    def test_save_atomic_os_replace_failure_keeps_existing(self, tmp_path, monkeypatch):
        """原子寫入：os.replace 拋例外 → 既有分類檔與 meta 不受影響、不留暫存檔。"""
        store = Store(tmp_path)
        store.save([
            make_item("a1", price=9990, history=[[YESTERDAY_STR, 9990]],
                      first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
            make_item("gpu1", name="RTX 5090", category="顯示卡", price=49990,
                      history=[[YESTERDAY_STR, 50990]],
                      first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR),
        ], {"crawled_at": "first"})
        cpu_file = tmp_path / "items" / g_filename("CPU")
        gpu_file = tmp_path / "items" / g_filename("顯示卡")
        original_cpu = cpu_file.read_text(encoding="utf-8")
        original_gpu = gpu_file.read_text(encoding="utf-8")
        original_meta = (tmp_path / "meta.json").read_text(encoding="utf-8")

        def boom(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(store_module.os, "replace", boom)
        with pytest.raises(OSError):
            store.save([make_item("a1", price=1, history=[[TODAY_STR, 1]],
                                  first_seen=TODAY_STR, last_seen=TODAY_STR)],
                       {"crawled_at": "second"})
        assert cpu_file.read_text(encoding="utf-8") == original_cpu
        assert gpu_file.read_text(encoding="utf-8") == original_gpu
        assert (tmp_path / "meta.json").read_text(encoding="utf-8") == original_meta
        # 無暫存檔殘留
        assert sorted(p.name for p in (tmp_path / "items").iterdir()) == \
            sorted([cpu_file.name, gpu_file.name])
        assert sorted(p.name for p in tmp_path.iterdir()) == ["items", "meta.json"]

    def test_save_round_trip_with_load(self, tmp_path):
        """save 產生的分類檔可被 load 回讀（round-trip；category 由檔名回填）。"""
        store = Store(tmp_path)
        items = [
            make_item("a1", name="Intel i5-13600K", price=9790,
                      first_seen=YESTERDAY_STR, last_seen=TODAY_STR,
                      history=[[YESTERDAY_STR, 9990], [TODAY_STR, 9790]],
                      spec={"brand": "Intel"}, flags={"hot": True}),
            make_item("a2", name="MSI RTX 4060", category="顯示卡", price=None,
                      status=STATUS_GONE, first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR,
                      history=[[YESTERDAY_STR, 9990]]),
            make_item("b1", name="DDR5 32G", category="記憶體", price=2999,
                      first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR,
                      history=[[YESTERDAY_STR, 2999]]),
        ]
        meta = {"crawled_at": "2026-08-16T06:00:00Z", "total": 3, "status": "ok"}
        store.save(items, meta)
        loaded_items, loaded_meta = store.load()
        assert loaded_meta == meta
        assert set(loaded_items) == {"a1", "a2", "b1"}
        assert loaded_items["a1"] == items[0]
        assert loaded_items["a2"] == items[1]     # category（顯示卡）由 g12.json 回填
        assert loaded_items["b1"] == items[2]     # category（記憶體）由 g6.json 回填
        assert loaded_items["a1"].category == "CPU"

    def test_save_unknown_category_raises(self, tmp_path):
        """未知分類無法決定檔名 → ValueError，且不寫任何 items/meta 檔。"""
        store = Store(tmp_path)
        item = make_item("x1", name="幽靈商品", category="不存在分類", price=1000)
        with pytest.raises(ValueError, match="未知分類"):
            store.save([item], {"status": "ok"})
        assert not (tmp_path / "items").exists()
        assert not (tmp_path / "meta.json").exists()

    def test_save_filenames_match_categories_g_indexes(self, tmp_path):
        """檔名 g{index} = categories.py 的 G 頁索引（所有追蹤分類皆可對映）。"""
        store = Store(tmp_path)
        items = [make_item(f"i{i}", name=f"商品{i}", category=c.name, price=1000 + i)
                 for i, c in enumerate(CATEGORIES)]
        store.save(items, {"status": "ok"})
        files = sorted(p.name for p in (tmp_path / "items").iterdir())
        assert files == sorted(f"g{c.g_index}.json" for c in CATEGORIES)
        assert set(files) == {f"g{c.g_index}.json" for c in CATEGORIES}  # 每分類一檔
        # 各檔筆數 = 該分類商品數
        for c in CATEGORIES:
            doc = json.loads((tmp_path / "items" / f"g{c.g_index}.json").read_text(encoding="utf-8"))
            assert len(doc) == 1
            assert doc[0]["id"] == f"i{CATEGORIES.index(c)}"


# ── write_daily（O4 每日價格點檔 data/daily/YYYYMMDD.json） ──────────────────


class TestWriteDaily:
    def test_writes_price_map_compact(self, tmp_path):
        """O4：write_daily 把 {id: price} 以 compact JSON 寫入 data/daily/{YYYYMMDD}.json。"""
        store = Store(tmp_path)
        store.write_daily(date(2026, 8, 16), {"a1": 9990, "a2": 9790})
        path = tmp_path / "daily" / "20260816.json"
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == {"a1": 9990, "a2": 9790}
        raw = path.read_text(encoding="utf-8")
        assert raw == json.dumps({"a1": 9990, "a2": 9790}, ensure_ascii=False,
                                 separators=(",", ":")) + "\n"  # compact

    def test_filename_uses_execution_date(self, tmp_path):
        """檔名 = 執行日 YYYYMMDD（date 物件格式化）；不同日期各自成檔。"""
        store = Store(tmp_path)
        store.write_daily(date(2026, 8, 15), {"a1": 9990})
        store.write_daily(date(2026, 8, 16), {"a1": 9790})
        assert json.loads((tmp_path / "daily" / "20260815.json").read_text(encoding="utf-8")) == {"a1": 9990}
        assert json.loads((tmp_path / "daily" / "20260816.json").read_text(encoding="utf-8")) == {"a1": 9790}

    def test_overwrite_same_day(self, tmp_path):
        """同日重跑：覆寫同一 YYYYMMDD.json（不產生 _N 後綴或重複檔）。"""
        store = Store(tmp_path)
        store.write_daily(date(2026, 8, 16), {"a1": 9990, "a2": 8888})
        store.write_daily(date(2026, 8, 16), {"a1": 9990})  # 同日新結果覆寫
        files = sorted(p.name for p in (tmp_path / "daily").iterdir())
        assert files == ["20260816.json"]
        assert json.loads((tmp_path / "daily" / "20260816.json").read_text(encoding="utf-8")) == {"a1": 9990}

    def test_atomic_failure_keeps_existing(self, tmp_path, monkeypatch):
        """原子寫入：os.replace 拋例外 → 既有 daily 檔不受影響、不留暫存檔。"""
        store = Store(tmp_path)
        store.write_daily(date(2026, 8, 16), {"a1": 9990})
        original = (tmp_path / "daily" / "20260816.json").read_text(encoding="utf-8")

        def boom(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(store_module.os, "replace", boom)
        with pytest.raises(OSError):
            store.write_daily(date(2026, 8, 16), {"a1": 1})
        assert (tmp_path / "daily" / "20260816.json").read_text(encoding="utf-8") == original
        assert sorted(p.name for p in (tmp_path / "daily").iterdir()) == ["20260816.json"]

    def test_empty_price_map_writes_empty_object(self, tmp_path):
        """當日無價格商品 → 仍寫出空物件檔（成功 run 的 daily 檔一律存在）。"""
        store = Store(tmp_path)
        store.write_daily(date(2026, 8, 16), {})
        assert json.loads((tmp_path / "daily" / "20260816.json").read_text(encoding="utf-8")) == {}


# ── write_meta ──────────────────────────────────────────────────────────────

class TestWriteMeta:
    def test_write_meta_base_fields(self, tmp_path):
        store = Store(tmp_path)
        store.write_meta(crawled_at="2026-08-16T06:00:00Z",
                         counts={"CPU": 48, "記憶體": 216},
                         total=264, changed=12,
                         failed_categories=["主機板"], status="partial")
        meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert meta["crawled_at"] == "2026-08-16T06:00:00Z"
        assert meta["counts"] == {"CPU": 48, "記憶體": 216}
        assert meta["total"] == 264
        assert meta["changed"] == 12
        assert meta["failed_categories"] == ["主機板"]
        assert meta["status"] == "partial"
        assert "version" not in meta  # 日期制快照：不再寫整數版本
        assert meta["previous_total"] is None  # 不存在 → None

    def test_write_meta_carries_previous_total(self, tmp_path):
        """沿用既有 meta 的 previous_total（007 驟降基準不得遺失）；version 不再寫入。"""
        (tmp_path / "meta.json").write_text(
            json.dumps({"version": 3, "previous_total": 1449}), encoding="utf-8")
        store = Store(tmp_path)
        store.write_meta(crawled_at="2026-08-16T06:00:00Z", counts={}, total=0,
                         changed=0, failed_categories=[], status="ok")
        meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert "version" not in meta
        assert meta["previous_total"] == 1449

    def test_write_meta_keeps_007_extension_fields(self, tmp_path):
        """007 擴充欄位（sources/anomaly 等）不因覆寫而遺失。"""
        existing = {"previous_total": 1200,
                    "sources": {"5": {"g": 5}}, "anomaly": {"kind": "none"}}
        (tmp_path / "meta.json").write_text(json.dumps(existing), encoding="utf-8")
        store = Store(tmp_path)
        store.write_meta(crawled_at="2026-08-16T06:00:00Z", counts={}, total=1449,
                         changed=5, failed_categories=[], status="ok")
        meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert "version" not in meta
        assert meta["previous_total"] == 1200
        assert meta["sources"] == {"5": {"g": 5}}
        assert meta["anomaly"] == {"kind": "none"}

    @pytest.mark.parametrize("status", ["ok", "partial", "failed"])
    def test_valid_statuses_accepted(self, tmp_path, status):
        store = Store(tmp_path)
        store.write_meta(crawled_at="x", counts={}, total=0, changed=0,
                         failed_categories=[], status=status)
        meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert meta["status"] == status

    def test_invalid_status_rejected(self, tmp_path):
        """status 僅 ok/partial/failed 三態（007 定義，不再有 aborted）。"""
        store = Store(tmp_path)
        with pytest.raises(ValueError):
            store.write_meta(crawled_at="x", counts={}, total=0, changed=0,
                             failed_categories=[], status="aborted")
