"""store.py 單元測試（BDD #2 新商品、#3 價格異動、#4 gone、#5 平價日仍累積一點、
#18 重複名稱、#19 價格缺失、#21 同日重複執行 + 原子寫入 + meta；
refreshed：flags/spec/subcategory/name 異動傳播（code review 發現 #1 修復））。

每日一點語意：每次成功爬取（商品出現在今日清單）都 append 當日價格點，含平價日；
同日重跑（末筆歷史已是今日且價格相同）不重複 append。
失敗分類商品（今日未成功爬取）→ carryover_ids → 原樣保留。

store 測試一律使用 pytest tmp_path，不碰真實檔案系統。
今日商品以「提議歷史 [[今日, 價格]]」傳入 diff；價格缺失時 history=[]。
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

import crawler.store as store_module
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


# ── load ────────────────────────────────────────────────────────────────────

class TestLoad:
    def test_first_run_no_files_returns_empty(self, tmp_path):
        store = Store(tmp_path)
        items, meta = store.load()
        assert items == {}
        assert meta == {}

    def test_load_existing_items_json_indexed_by_id(self, tmp_path):
        payload = {
            "meta": {"crawled_at": "2026-08-15T06:00:00Z"},
            "items": [
                {"id": "a1", "category": "CPU", "subcategory": "Intel 第14代",
                 "name": "Intel i5-13600K", "spec": {"brand": "Intel"},
                 "flags": {"hot": True}, "status": "in_stock",
                 "first_seen": "2026-08-15", "last_seen": "2026-08-15",
                 "history": [["2026-08-15", 9990]]},
                {"id": "a2", "category": "顯示卡", "subcategory": "RTX 4060",
                 "name": "MSI RTX 4060", "spec": {}, "flags": {},
                 "status": "gone", "first_seen": "2026-08-15", "last_seen": "2026-08-15",
                 "history": [["2026-08-15", 9990]]},
            ],
        }
        (tmp_path / "items.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        items, meta = Store(tmp_path).load()
        assert set(items) == {"a1", "a2"}
        assert items["a1"].name == "Intel i5-13600K"
        assert items["a1"].history == [["2026-08-15", 9990]]
        assert items["a1"].price == 9990
        assert items["a2"].status == STATUS_GONE

    def test_load_meta_from_items_json_when_meta_json_absent(self, tmp_path):
        (tmp_path / "items.json").write_text(
            json.dumps({"meta": {"crawled_at": "2026-08-15T06:00:00Z"}, "items": []}, ensure_ascii=False),
            encoding="utf-8")
        _, meta = Store(tmp_path).load()
        assert meta == {"crawled_at": "2026-08-15T06:00:00Z"}

    def test_load_meta_json_takes_precedence(self, tmp_path):
        (tmp_path / "items.json").write_text(
            json.dumps({"meta": {"embedded": 1}, "items": []}, ensure_ascii=False), encoding="utf-8")
        (tmp_path / "meta.json").write_text(
            json.dumps({"crawled_at": "2026-08-15T06:00:00Z", "previous_total": 2}), encoding="utf-8")
        _, meta = Store(tmp_path).load()
        assert meta == {"crawled_at": "2026-08-15T06:00:00Z", "previous_total": 2}

    def test_load_corrupt_items_json_raises(self, tmp_path):
        (tmp_path / "items.json").write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ValueError):
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


# ── save ────────────────────────────────────────────────────────────────────

class TestSave:
    def test_save_writes_items_json_with_all_fields(self, tmp_path):
        store = Store(tmp_path)
        items = [
            make_item("a1", name="Intel i5-13600K", price=9790, status=STATUS_IN_STOCK,
                      first_seen=YESTERDAY_STR, last_seen=TODAY_STR,
                      history=[[YESTERDAY_STR, 9990], [TODAY_STR, 9790]],
                      spec={"brand": "Intel", "model": "i5-13600K"}, flags={"hot": True}),
        ]
        meta = {"crawled_at": "2026-08-16T06:00:00Z", "status": "ok"}
        store.save(items, meta)
        doc = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
        assert doc["meta"] == meta
        assert len(doc["items"]) == 1
        assert doc["items"][0] == {
            "id": "a1", "category": "CPU", "subcategory": "Intel 第14代",
            "name": "Intel i5-13600K",
            "spec": {"brand": "Intel", "model": "i5-13600K"},
            "flags": {"hot": True},
            "status": "in_stock",
            "first_seen": "2026-08-15", "last_seen": "2026-08-16",
            "history": [["2026-08-15", 9990], ["2026-08-16", 9790]],
        }
        assert json.loads((tmp_path / "meta.json").read_text(encoding="utf-8")) == meta

    def test_save_atomic_os_replace_failure_keeps_existing(self, tmp_path, monkeypatch):
        """原子寫入：os.replace 拋例外 → 既有檔案不受影響、不留暫存檔。"""
        store = Store(tmp_path)
        store.save([make_item("a1", price=9990, history=[[YESTERDAY_STR, 9990]],
                              first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR)],
                   {"crawled_at": "first"})
        original_items = (tmp_path / "items.json").read_text(encoding="utf-8")
        original_meta = (tmp_path / "meta.json").read_text(encoding="utf-8")

        def boom(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(store_module.os, "replace", boom)
        with pytest.raises(OSError):
            store.save([make_item("a1", price=1, history=[[TODAY_STR, 1]],
                                  first_seen=TODAY_STR, last_seen=TODAY_STR)],
                       {"crawled_at": "second"})
        assert (tmp_path / "items.json").read_text(encoding="utf-8") == original_items
        assert (tmp_path / "meta.json").read_text(encoding="utf-8") == original_meta
        assert sorted(p.name for p in tmp_path.iterdir()) == ["items.json", "meta.json"]

    def test_save_round_trip_with_load(self, tmp_path):
        """save 產生的 JSON 可被 load 回讀（round-trip）。"""
        store = Store(tmp_path)
        items = [
            make_item("a1", name="Intel i5-13600K", price=9790,
                      first_seen=YESTERDAY_STR, last_seen=TODAY_STR,
                      history=[[YESTERDAY_STR, 9990], [TODAY_STR, 9790]],
                      spec={"brand": "Intel"}, flags={"hot": True}),
            make_item("a2", name="MSI RTX 4060", price=None, status=STATUS_GONE,
                      first_seen=YESTERDAY_STR, last_seen=YESTERDAY_STR,
                      history=[[YESTERDAY_STR, 9990]]),
        ]
        meta = {"crawled_at": "2026-08-16T06:00:00Z", "total": 2, "status": "ok"}
        store.save(items, meta)
        loaded_items, loaded_meta = store.load()
        assert loaded_meta == meta
        assert set(loaded_items) == {"a1", "a2"}
        assert loaded_items["a1"] == items[0]
        assert loaded_items["a2"] == items[1]


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
