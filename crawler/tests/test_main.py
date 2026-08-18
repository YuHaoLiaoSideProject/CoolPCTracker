"""main.py 端到端冒煙測試（功能 001 驗收；BDD #1/#12/#14/#15/#20/#21 等）。

以 FakeFetcher 取代 crawler.main.Fetcher：依 Category.g_index 回傳 fixture HTML，
可指定失敗分類（html=None）、改價頁、自訂頁面或全空頁——完全不觸及真實網路。
Store 一律以 pytest tmp_path 作為 data_dir。

V2 拆檔契約：items 依分類分檔 data/items/{g}.json（g = 分類 G 頁索引；頂層 array、
無 meta 包裝、無 category 欄位——category 由檔名回填，測試讀取時注入以便斷言）；
ok/partial 成功路徑額外寫出 data/daily/{YYYYMMDD}.json = {id: price}（只含當日
成功爬取且價格存在的商品，與 counts 去重一致）；failed 路徑不寫任何 items 檔
（保留舊分類檔）也不寫 daily。items 的 history 在 save 序列化層截到最近 2 點。

覆蓋矩陣（對應 BDD）：
- #1   完整管道兩日連跑：data/items/{g}.json 產生、first_seen=last_seen=爬取日、
       meta.status=ok、異動商品 history append [D2, 新價]、同商品 ID 跨日不變、
       meta.previous_total 沿用；每日價格點檔 data/daily/20260815.json / 20260816.json
       依執行日產生
- #21  同日重跑冪等：history 不重複 append、meta.crawled_at 更新、return 0；
       daily 檔同日覆寫不重複
- #14  降幅 >20%：notify 警報（含「降幅」）、items 分類檔不被覆寫、meta.status=failed、
       return 1、不寫當日 daily 檔
- #15  解析 0 商品：notify 警報（含「0 商品」）、不覆寫、meta.status=failed、return 1、
       不寫當日 daily 檔
- #12  單一分類抓取失敗 partial：其餘 8 分類照常更新、failed_categories=[主機板]、
       status=partial、return 0、主機板既有商品保留原樣（不誤判 gone）；
       daily 檔只含成功爬取分類（26 筆，不含主機板）
- 邊界 降幅恰為 20%（本次 = 前次 80%）：不判異常、正常寫入（007 §6.1）
- 去重計數：同名同 ID 重複（BDD #18 最後解析者勝出）→ counts/total 以 unique id 計，
  sum(counts) == total == items 合併筆數；daily 檔同步去重（最後解析者價格勝出）
- #20  CLI --date 手動補爬（first_seen=指定日、daily 檔名=指定日）；無 --date 預設今日
- meta 完整欄位（crawled_at ISO UTC、counts、total、previous_total、changed、
       failed_categories、status；日期制快照改造後不再含 version）
- exit code 2（其他執行失敗：meta.json 損壞，不寫 items/daily）
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from crawler.categories import CATEGORIES, get_category
from crawler.fetcher import FetchResult
from crawler.main import DROP_THRESHOLD, main, run_crawler

FIXTURES = Path(__file__).parent / "fixtures"

FIXTURE_BY_G = {
    1: "prebuilt.html",
    3: "bundle.html",
    4: "cpu.html",
    5: "mobo.html",
    6: "ram.html",
    7: "ssd.html",
    8: "hdd.html",
    9: "memcard.html",
    12: "gpu.html",
}
FIXTURE_COUNTS = {1: 3, 3: 2, 4: 4, 5: 2, 6: 3, 7: 3, 8: 3, 9: 5, 12: 3}
TOTAL_ITEMS = sum(FIXTURE_COUNTS.values())  # 28

CPU_13600K = "Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】"
AMD_7600 = "AMD R5 7600【6核/12緒】3.8G(↑5.1G)/65W【代理盒裝】"
D1 = date(2026, 8, 15)
D2 = date(2026, 8, 16)


# ── 工具 ─────────────────────────────────────────────────────────────────────


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_items(data_dir: Path, *, with_category: bool = True) -> list[dict]:
    """讀取 data/items/{g}.json 全部分類檔，合併為 items 清單（V2：頂層 array、
    無 meta 包裝、無 category 欄位）。with_category=True 時依檔名注入 category
    以便斷言（純讀取工具，不改檔案內容）。"""
    items: list[dict] = []
    items_dir = data_dir / "items"
    for path in sorted(items_dir.glob("g*.json")):
        category = get_category(int(path.stem[1:])).name  # 檔名 g{i} → 分類 name
        for entry in json.loads(path.read_text(encoding="utf-8")):
            items.append({**entry, "category": category} if with_category else entry)
    return items


def load_daily(data_dir: Path, day: date) -> dict:
    """讀取 data/daily/{YYYYMMDD}.json（O4 每日價格點檔）。"""
    path = data_dir / "daily" / f"{day.strftime('%Y%m%d')}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_meta(data_dir: Path) -> dict:
    return json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))


def item_by_name(items: list[dict], name: str) -> dict:
    return next(i for i in items if i["name"] == name)


def items_files(data_dir: Path) -> list[str]:
    """data/items/ 下既有分類檔名（排序；失敗路徑不得增刪任何檔）。"""
    items_dir = data_dir / "items"
    if not items_dir.is_dir():
        return []
    return sorted(p.name for p in items_dir.iterdir())


def make_page(items: list[tuple[str, int]], subcategory: str = "邊界區") -> str:
    """依 (名稱, 價格) 清單產生最小可用分類頁 HTML（子分類 <th> + 商品列）。

    subcategory 可自訂：G=9 記憶卡頁必須含「記憶卡」子分類才能通過過濾。
    """
    rows = [f"<tr><th>{subcategory}</th></tr>"]
    for name, price in items:
        rows.append(f'<tr><td>{name}</td><td align="right">{price:,}</td></tr>')
    return "<html><body><table>" + "".join(rows) + "</table></body></html>"


class FakeFetcher:
    """取代 crawler.main.Fetcher：依 Category.g_index 回傳 fixture HTML（無真實網路）。

    - fail_g：指定 G 索引 → html=None（抓取失敗，BDD #12）
    - pages：G → HTML 字串覆蓋（例如改價後的 cpu.html、自訂邊界頁）
    - others_empty：未在 pages 的分類回傳 edge_empty.html（0 商品）
    - empty_all：全部分類回傳 edge_empty.html（BDD #15）
    """

    def __init__(self, *, fail_g: set[int] | None = None,
                 pages: dict[int, str] | None = None,
                 others_empty: bool = False, empty_all: bool = False):
        self.fail_g = set(fail_g or [])
        self.pages = dict(pages or {})
        self.others_empty = others_empty
        self.empty_all = empty_all

    def __call__(self, *args, **kwargs):  # main 以 Fetcher() 建構 → 直接回傳自身
        return self

    def fetch_all(self) -> list[FetchResult]:
        results: list[FetchResult] = []
        for category in CATEGORIES:
            g = category.g_index
            if g in self.fail_g:
                results.append(FetchResult(category, None, None))
            elif self.empty_all or (self.others_empty and g not in self.pages):
                results.append(FetchResult(category, load_fixture("edge_empty.html"), b""))
            else:
                html = self.pages.get(g)
                if html is None:
                    html = load_fixture(FIXTURE_BY_G[g])
                results.append(FetchResult(category, html, html.encode("utf-8")))
        return results


@pytest.fixture
def install_fake(monkeypatch):
    """安裝 FakeFetcher 至 crawler.main.Fetcher 名稱。"""
    def _install(fake: FakeFetcher) -> FakeFetcher:
        monkeypatch.setattr("crawler.main.Fetcher", fake)
        return fake
    return _install


# ── #1 完整管道（兩日連跑冒煙） ───────────────────────────────────────────────


class TestFullPipeline:
    def test_two_days_smoke_ids_stable_history_appends(self, tmp_path, install_fake):
        install_fake(FakeFetcher())

        # Day1：全 9 分類成功 → data/items/{g}.json 建立
        assert run_crawler(tmp_path, today=D1) == 0
        doc1 = load_items(tmp_path)
        assert len(doc1) == TOTAL_ITEMS
        for item in doc1:
            assert item["first_seen"] == "2026-08-15"
            assert item["last_seen"] == "2026-08-15"
            assert item["status"] == "in_stock"
            assert item["history"] == [["2026-08-15", item["history"][0][1]]]
        assert item_by_name(doc1, CPU_13600K)["spec"]["brand"] == "Intel"  # spec 貫穿管道
        # V2：9 個分類檔各一、無 meta 包裝、無 category 欄位
        assert items_files(tmp_path) == sorted(f"g{c.g_index}.json" for c in CATEGORIES)
        for path in sorted((tmp_path / "items").glob("g*.json")):
            raw_doc = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(raw_doc, list)          # 頂層 array
            assert "meta" not in raw_doc
            assert all("category" not in e for e in raw_doc)  # 序列化不含 category
        assert not (tmp_path / "items.json").exists()  # data/items.json 已不存在
        # 008：Day1 稀疏 daily = 全部今日商品（全部為 new_items，皆異動）
        daily1 = load_daily(tmp_path, D1)
        assert set(daily1) == {i["id"] for i in doc1}
        assert len(daily1) == TOTAL_ITEMS
        assert all(isinstance(p, int) for p in daily1.values())

        meta1 = load_meta(tmp_path)
        assert meta1["status"] == "ok"

        # Day2：CPU i5-13600K 改價 9,790 → 8,990（其餘不變）
        cpu_new = load_fixture("cpu.html").replace("9,790", "8,990")
        install_fake(FakeFetcher(pages={4: cpu_new}))
        assert run_crawler(tmp_path, today=D2) == 0

        doc2 = load_items(tmp_path)
        # 同商品 ID 跨日不變（集合相等）
        assert {i["id"] for i in doc2} == {i["id"] for i in doc1}
        # 異動商品：history append [D2, 新價]、last_seen 更新、first_seen 保持
        cpu = item_by_name(doc2, CPU_13600K)
        assert cpu["history"] == [["2026-08-15", 9790], ["2026-08-16", 8990]]
        assert cpu["last_seen"] == "2026-08-16"
        assert cpu["first_seen"] == "2026-08-15"
        # 無異動商品：每日一點語意 → 仍 append 當日平價點、last_seen 更新（BDD #5）
        amd = item_by_name(doc2, AMD_7600)
        assert amd["history"] == [["2026-08-15", 6990], ["2026-08-16", 6990]]
        assert amd["last_seen"] == "2026-08-16"
        assert amd["first_seen"] == "2026-08-15"
        # O4：history 截到最近 2 點（漲跌徽章只需前後兩點）
        assert all(len(i["history"]) <= 2 for i in doc2)

        # 008：Day2 稀疏 daily = 僅異動商品（CPU 改價），不含平價商品
        daily2 = load_daily(tmp_path, D2)
        cpu_id = item_by_name(doc2, CPU_13600K)["id"]
        assert cpu_id in daily2
        assert daily2[cpu_id] == 8990
        # AMD 未改價 → 不在稀疏 daily 中
        amd_id = item_by_name(doc2, AMD_7600)["id"]
        assert amd_id not in daily2

        meta2 = load_meta(tmp_path)
        assert meta2["status"] == "ok"
        assert meta2["total"] == TOTAL_ITEMS
        assert meta2["previous_total"] == TOTAL_ITEMS  # 沿用/更新為上次有效總數
        assert meta2["changed"] == 1


# ── #21 同日重跑冪等 ─────────────────────────────────────────────────────────


class TestSameDayIdempotent:
    def test_same_day_rerun_no_duplicate_history(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        assert run_crawler(tmp_path, today=D2) == 0
        doc1 = load_items(tmp_path)
        meta1 = load_meta(tmp_path)
        daily_before = load_daily(tmp_path, D2)  # O4：首跑已寫當日價格點檔

        assert run_crawler(tmp_path, today=D2) == 0  # 同日同 fixture 重跑
        doc2 = load_items(tmp_path)
        meta2 = load_meta(tmp_path)

        # history 不重複 append（長度與內容皆不變）
        assert [i["history"] for i in doc2] == [i["history"] for i in doc1]
        assert all(len(i["history"]) == 1 for i in doc2)
        assert meta2["changed"] == 0
        assert meta2["crawled_at"] != meta1["crawled_at"]  # crawled_at 更新
        # 008：daily 檔同日無異動 → 不覆寫（平價日零 git 變動），舊檔內容不變
        daily_rerun = load_daily(tmp_path, D2)
        assert daily_rerun == daily_before  # 內容不變（file 未被覆寫）
        assert len(daily_before) == TOTAL_ITEMS  # 首跑寫入全部商品（全部為 new）
        assert sorted(p.name for p in (tmp_path / "daily").iterdir()) == ["20260816.json"]
        # V2：分類檔數量不變（同為 9 檔，無重複/殘留）
        assert items_files(tmp_path) == sorted(f"g{c.g_index}.json" for c in CATEGORIES)


# ── #14 驟降 >20% 不覆寫 + 警報 ──────────────────────────────────────────────


class TestDropProtection:
    def test_drop_over_20_percent_blocks_and_notifies(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        assert run_crawler(tmp_path, today=D1) == 0
        doc_before = load_items(tmp_path)
        files_before = items_files(tmp_path)

        # 本次僅 CPU 分類有商品（4 個），其餘 8 分類 edge_empty → 降幅 > 20%
        install_fake(FakeFetcher(pages={4: load_fixture("cpu.html")}, others_empty=True))
        notified: list[str] = []
        rc = run_crawler(tmp_path, today=D2, notify=notified.append)

        assert rc == 1
        assert len(notified) == 1
        assert "降幅" in notified[0]  # 警報含原因（中文）
        # V2：failed 不寫任何 items 檔——分類檔內容與檔名皆不變（不覆寫）
        assert load_items(tmp_path) == doc_before
        assert items_files(tmp_path) == files_before
        assert not (tmp_path / "daily" / "20260816.json").exists()  # O4：failed 不寫當日 daily
        meta = load_meta(tmp_path)
        assert meta["status"] == "failed"
        assert meta["total"] == 4
        assert meta["previous_total"] == TOTAL_ITEMS  # 驟降基準保留


# ── #15 解析出 0 商品 ────────────────────────────────────────────────────────


class TestZeroItems:
    def test_zero_items_parsed_blocks_and_notifies(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        assert run_crawler(tmp_path, today=D1) == 0
        doc_before = load_items(tmp_path)

        install_fake(FakeFetcher(empty_all=True))  # 全部分類 edge_empty
        notified: list[str] = []
        rc = run_crawler(tmp_path, today=D2, notify=notified.append)

        assert rc == 1
        assert len(notified) == 1
        assert "0 商品" in notified[0]
        assert load_items(tmp_path) == doc_before  # V2：分類檔不被覆寫
        assert items_files(tmp_path) == sorted(f"g{c.g_index}.json" for c in CATEGORIES)
        assert not (tmp_path / "daily" / "20260816.json").exists()  # O4：failed 不寫當日 daily
        meta = load_meta(tmp_path)
        assert meta["status"] == "failed"


# ── #12 單一分類抓取失敗 → partial ───────────────────────────────────────────


class TestPartialFailure:
    def test_single_category_fetch_failure_partial_keeps_old_data(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        assert run_crawler(tmp_path, today=D1) == 0
        doc1 = load_items(tmp_path)
        mobo_before = {i["id"]: i for i in doc1 if i["category"] == "主機板"}
        assert len(mobo_before) == 2

        # G=5 主機板抓取失敗；同時 CPU 改價驗證其餘 8 分類照常更新
        cpu_new = load_fixture("cpu.html").replace("9,790", "8,990")
        install_fake(FakeFetcher(fail_g={5}, pages={4: cpu_new}))
        notified: list[str] = []
        rc = run_crawler(tmp_path, today=D2, notify=notified.append)

        assert rc == 0
        assert notified == []  # partial 不觸發警報
        meta = load_meta(tmp_path)
        assert meta["status"] == "partial"
        assert meta["failed_categories"] == ["主機板"]
        assert meta["total"] == TOTAL_ITEMS - 2  # 今日解析 26（主機板缺）

        doc2 = load_items(tmp_path)
        # 無誤判 gone：全部既有商品 ID 保留
        assert {i["id"] for i in doc2} == {i["id"] for i in doc1}
        # 主機板既有商品原樣保留（今日未成功爬取 → 不 append 當日點、last_seen/status/history 不變）
        mobo_after = {i["id"]: i for i in doc2 if i["category"] == "主機板"}
        assert set(mobo_after) == set(mobo_before)
        for iid, before in mobo_before.items():
            after = mobo_after[iid]
            assert after["last_seen"] == before["last_seen"] == "2026-08-15"
            assert after["status"] == "in_stock"
            assert after["history"] == before["history"]
        # 其餘成功爬取分類（含無異動者）：每日一點 → 皆有 [D2, 平價]
        amd = item_by_name(doc2, AMD_7600)
        assert amd["history"] == [["2026-08-15", 6990], ["2026-08-16", 6990]]
        # CPU 異動照常更新
        cpu = item_by_name(doc2, CPU_13600K)
        assert cpu["history"] == [["2026-08-15", 9790], ["2026-08-16", 8990]]
        # 008：sparse daily 只含異動商品（CPU 改價），不含主機板、不含平價商品
        daily2 = load_daily(tmp_path, D2)
        cpu_id = item_by_name(doc2, CPU_13600K)["id"]
        assert cpu_id in daily2
        assert daily2[cpu_id] == 8990
        assert not any(iid in daily2 for iid in mobo_before)


# ── 驟降邊界：恰等於 80% 不判異常（007 §6.1） ────────────────────────────────


class TestDropBoundary:
    def test_exactly_80_percent_is_not_anomaly(self, tmp_path, install_fake):
        all_g = list(FIXTURE_BY_G)
        sub = {g: ("記憶卡" if g == 9 else "邊界區") for g in all_g}
        page5 = {g: make_page([(f"邊界商品{i}", 1000 + i) for i in range(5)], sub[g]) for g in all_g}
        page4 = {g: make_page([(f"邊界商品{i}", 1000 + i) for i in range(4)], sub[g]) for g in all_g}

        install_fake(FakeFetcher(pages=page5))
        assert run_crawler(tmp_path, today=D1) == 0
        assert load_meta(tmp_path)["total"] == 45

        install_fake(FakeFetcher(pages=page4))  # 36 = 45 * 80%，降幅恰為 20%
        notified: list[str] = []
        rc = run_crawler(tmp_path, today=D2, notify=notified.append)

        assert rc == 0
        assert notified == []
        assert 36 >= 45 * (1 - DROP_THRESHOLD)  # 邊界：不低於門檻 → 不判異常
        meta = load_meta(tmp_path)
        assert meta["status"] == "ok"
        assert meta["total"] == 36
        assert meta["previous_total"] == 36  # 上次有效總數 = 本次成功 run 總數（下次基準）
        doc2 = load_items(tmp_path)
        assert len(doc2) == 45  # 36 現存 + 9 個消失標記 gone
        # 008：sparse daily 只含異動商品（無異動 → 不寫 daily）
        daily_path = tmp_path / "daily" / "20260816.json"
        if daily_path.exists():
            daily2 = load_daily(tmp_path, D2)
            assert len(daily2) == 0  # 無價格異動 → sparse 為空
        else:
            pass  # 平價日不寫 daily 檔（D3）


# ── 去重計數：counts/total 以 unique id 計（與 store.diff 覆蓋一致） ──────────────


class TestDedupCount:
    def test_counts_total_count_unique_ids_not_raw_rows(self, tmp_path, install_fake):
        """同名同 ID 重複（BDD #18 最後解析者勝出）→ counts/total 依去重後 unique id。

        修正前：counts/total 以 raw 解析筆數計（含重複）→ 與 items 實際筆數漂移；
        修正後：以去重後計數，sum(counts) == total == items 合併筆數。
        """
        dup_page = make_page([
            ("重複商品A", 1000), ("重複商品A", 1200),  # 同名同 ID → 最後一筆（1200）勝出
            ("唯一商品B", 2000),
        ])
        install_fake(FakeFetcher(pages={4: dup_page}, others_empty=True))
        assert run_crawler(tmp_path, today=D1) == 0

        doc = load_items(tmp_path)
        meta = load_meta(tmp_path)
        assert len(doc) == 2  # raw 3 筆 → 去重 2 筆
        assert meta["total"] == 2
        assert meta["counts"]["CPU"] == 2
        assert meta["counts"]["主機板"] == 0
        assert sum(meta["counts"].values()) == meta["total"] == len(doc)
        assert meta["previous_total"] == 2
        dup = item_by_name(doc, "重複商品A")
        assert dup["history"] == [["2026-08-15", 1200]]  # 覆蓋語意：最後解析者價格勝出
        # O4：daily 檔同步去重（2 筆），重複商品以最後解析者價格（1200）寫入
        daily = load_daily(tmp_path, D1)
        assert len(daily) == 2
        assert daily[dup["id"]] == 1200
        assert daily == {i["id"]: i["history"][-1][1] for i in doc}


# ── #20 CLI --date 手動補爬 ──────────────────────────────────────────────────


class TestCli:
    def test_date_flag_records_actual_crawl_day(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        rc = main(["--data-dir", str(tmp_path), "--date", "2026-08-14"])
        assert rc == 0
        doc = load_items(tmp_path)
        assert all(i["first_seen"] == "2026-08-14" for i in doc)
        assert all(i["last_seen"] == "2026-08-14" for i in doc)
        assert load_meta(tmp_path)["status"] == "ok"
        # O4：daily 檔名 = 執行日（--date 指定日）
        daily = load_daily(tmp_path, date(2026, 8, 14))
        assert len(daily) == TOTAL_ITEMS

    def test_no_date_defaults_to_today(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        rc = main(["--data-dir", str(tmp_path)])
        assert rc == 0
        doc = load_items(tmp_path)
        assert all(i["first_seen"] == date.today().isoformat() for i in doc)
        # O4：daily 檔名 = 今日
        assert len(load_daily(tmp_path, date.today())) == TOTAL_ITEMS

    def test_unexpected_failure_returns_2(self, tmp_path):
        # V2：load 先讀 meta.json（缺失 → 首次執行；損壞 → exit 2 不寫任何檔）
        (tmp_path / "meta.json").write_text("{ 損壞的 JSON", encoding="utf-8")
        rc = main(["--data-dir", str(tmp_path), "--date", "2026-08-15"])
        assert rc == 2
        assert not (tmp_path / "items").exists()   # V2：執行失敗不寫任何 items 檔
        assert not (tmp_path / "daily").exists()   # O4：執行失敗不寫 daily


# ── meta 完整欄位 ────────────────────────────────────────────────────────────


class TestMetaComplete:
    def test_meta_has_all_required_fields(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        assert run_crawler(tmp_path, today=D1) == 0

        meta = load_meta(tmp_path)
        # crawled_at：ISO 8601 UTC
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$", meta["crawled_at"])
        assert meta["counts"] == {
            "套裝/準系統": 3, "劈發價組合區": 2, "CPU": 4, "主機板": 2,
            "記憶體": 3, "SSD": 3, "HDD": 3, "記憶卡": 5, "顯示卡": 3,
        }
        assert meta["total"] == TOTAL_ITEMS
        assert meta["previous_total"] == TOTAL_ITEMS
        assert meta["changed"] == TOTAL_ITEMS  # 首次執行全部為新商品
        assert meta["failed_categories"] == []
        assert meta["status"] == "ok"
        assert "version" not in meta  # 日期制快照：不再寫整數版本
        # O4：daily 檔 = 當日全部成功爬取商品（去重後 = counts 總數）
        assert len(load_daily(tmp_path, D1)) == meta["total"] == TOTAL_ITEMS
        # V2：每個分類檔單行 compact（無 meta 包裝、無 category 欄位）；meta 亦單行
        for path in sorted((tmp_path / "items").glob("g*.json")):
            raw = path.read_text(encoding="utf-8")
            assert raw.count("\n") == 1
            assert raw == json.dumps(json.loads(raw), ensure_ascii=False,
                                     separators=(",", ":")) + "\n"
            assert isinstance(json.loads(raw), list)
        raw_meta = (tmp_path / "meta.json").read_text(encoding="utf-8")
        assert raw_meta.count("\n") == 1
        assert raw_meta == json.dumps(meta, ensure_ascii=False, separators=(",", ":")) + "\n"


# ── 008 _decide_checkpoint ──────────────────────────────────────────────────

from crawler.main import _decide_checkpoint


class TestDecideCheckpoint:
    """_decide_checkpoint 邊界判定（BDD Scenario Outline S6：3/6/7/12 天）。"""

    def test_3_days_ago_false(self):
        """距上次 checkpoint 3 天 → 不寫。"""
        assert _decide_checkpoint(date(2026, 8, 1), date(2026, 8, 4), None) is False

    def test_6_days_ago_false(self):
        """距上次 checkpoint 6 天 → 不寫。"""
        assert _decide_checkpoint(date(2026, 8, 1), date(2026, 8, 7), None) is False

    def test_7_days_ago_true(self):
        """距上次 checkpoint 7 天（邊界）→ 寫。"""
        assert _decide_checkpoint(date(2026, 8, 1), date(2026, 8, 8), None) is True

    def test_12_days_ago_true(self):
        """距上次 checkpoint 12 天 → 寫。"""
        assert _decide_checkpoint(date(2026, 8, 1), date(2026, 8, 13), None) is True

    def test_no_checkpoint_no_daily_false(self):
        """無 checkpoint 無 daily → 不寫（純新增首次）。"""
        assert _decide_checkpoint(None, date(2026, 8, 15), None) is False

    def test_no_checkpoint_7_days_from_earliest_true(self):
        """無 checkpoint 但距最早 daily ≥7 天 → 補首個錨點。"""
        assert _decide_checkpoint(None, date(2026, 8, 8), date(2026, 8, 1)) is True

    def test_no_checkpoint_6_days_from_earliest_false(self):
        """無 checkpoint 距最早 daily 6 天 → 不寫。"""
        assert _decide_checkpoint(None, date(2026, 8, 7), date(2026, 8, 1)) is False

    def test_exactly_7_days_boundary(self):
        """邊界：恰 7 天 → 寫（>=7 為 True）。"""
        assert _decide_checkpoint(date(2026, 8, 1), date(2026, 8, 8), None) is True
