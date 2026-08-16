"""main.py 端到端冒煙測試（功能 001 驗收；BDD #1/#12/#14/#15/#20/#21 等）。

以 FakeFetcher 取代 crawler.main.Fetcher：依 Category.g_index 回傳 fixture HTML，
可指定失敗分類（html=None）、改價頁、自訂頁面或全空頁——完全不觸及真實網路。
Store 一律以 pytest tmp_path 作為 data_dir。

覆蓋矩陣（對應 BDD）：
- #1   完整管道兩日連跑：items.json 產生、first_seen=last_seen=爬取日、meta.status=ok、
       異動商品 history append [D2, 新價]、同商品 ID 跨日不變、meta.previous_total 沿用
- #21  同日重跑冪等：history 不重複 append、meta.crawled_at 更新、return 0
- #14  降幅 >20%：notify 警報（含「降幅」）、items.json 不被覆寫、meta.status=failed、return 1
- #15  解析 0 商品：notify 警報（含「0 商品」）、不覆寫、meta.status=failed、return 1
- #12  單一分類抓取失敗 partial：其餘 8 分類照常更新、failed_categories=[主機板]、
       status=partial、return 0、主機板既有商品保留原樣（不誤判 gone）
- 邊界 降幅恰為 20%（本次 = 前次 80%）：不判異常、正常寫入（007 §6.1）
- #20  CLI --date 手動補爬（first_seen=指定日）；無 --date 預設今日
- meta 完整欄位（crawled_at ISO UTC、counts、total、previous_total、changed、
       failed_categories、status；日期制快照改造後不再含 version）
- exit code 2（其他執行失敗：items.json 損壞）
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from crawler.categories import CATEGORIES
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


def load_items_json(data_dir: Path) -> dict:
    return json.loads((data_dir / "items.json").read_text(encoding="utf-8"))


def load_meta(data_dir: Path) -> dict:
    return json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))


def item_by_name(doc: dict, name: str) -> dict:
    return next(i for i in doc["items"] if i["name"] == name)


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

        # Day1：全 9 分類成功 → items.json 建立
        assert run_crawler(tmp_path, today=D1) == 0
        doc1 = load_items_json(tmp_path)
        assert len(doc1["items"]) == TOTAL_ITEMS
        for item in doc1["items"]:
            assert item["first_seen"] == "2026-08-15"
            assert item["last_seen"] == "2026-08-15"
            assert item["status"] == "in_stock"
            assert item["history"] == [["2026-08-15", item["history"][0][1]]]
        assert item_by_name(doc1, CPU_13600K)["spec"]["brand"] == "Intel"  # spec 貫穿管道

        meta1 = load_meta(tmp_path)
        assert meta1["status"] == "ok"

        # Day2：CPU i5-13600K 改價 9,790 → 8,990（其餘不變）
        cpu_new = load_fixture("cpu.html").replace("9,790", "8,990")
        install_fake(FakeFetcher(pages={4: cpu_new}))
        assert run_crawler(tmp_path, today=D2) == 0

        doc2 = load_items_json(tmp_path)
        # 同商品 ID 跨日不變（集合相等）
        assert {i["id"] for i in doc2["items"]} == {i["id"] for i in doc1["items"]}
        # 異動商品：history append [D2, 新價]、last_seen 更新、first_seen 保持
        cpu = item_by_name(doc2, CPU_13600K)
        assert cpu["history"] == [["2026-08-15", 9790], ["2026-08-16", 8990]]
        assert cpu["last_seen"] == "2026-08-16"
        assert cpu["first_seen"] == "2026-08-15"
        # 無異動商品：原樣保留（不 append、last_seen 不變）
        amd = item_by_name(doc2, AMD_7600)
        assert amd["history"] == [["2026-08-15", 6990]]
        assert amd["last_seen"] == "2026-08-15"

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
        doc1 = load_items_json(tmp_path)
        meta1 = load_meta(tmp_path)

        assert run_crawler(tmp_path, today=D2) == 0  # 同日同 fixture 重跑
        doc2 = load_items_json(tmp_path)
        meta2 = load_meta(tmp_path)

        # history 不重複 append（長度與內容皆不變）
        assert [i["history"] for i in doc2["items"]] == [i["history"] for i in doc1["items"]]
        assert all(len(i["history"]) == 1 for i in doc2["items"])
        assert meta2["changed"] == 0
        assert meta2["crawled_at"] != meta1["crawled_at"]  # crawled_at 更新


# ── #14 驟降 >20% 不覆寫 + 警報 ──────────────────────────────────────────────


class TestDropProtection:
    def test_drop_over_20_percent_blocks_and_notifies(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        assert run_crawler(tmp_path, today=D1) == 0
        doc_before = load_items_json(tmp_path)

        # 本次僅 CPU 分類有商品（4 個），其餘 8 分類 edge_empty → 降幅 > 20%
        install_fake(FakeFetcher(pages={4: load_fixture("cpu.html")}, others_empty=True))
        notified: list[str] = []
        rc = run_crawler(tmp_path, today=D2, notify=notified.append)

        assert rc == 1
        assert len(notified) == 1
        assert "降幅" in notified[0]  # 警報含原因（中文）
        assert load_items_json(tmp_path) == doc_before  # items.json 不被覆寫
        meta = load_meta(tmp_path)
        assert meta["status"] == "failed"
        assert meta["total"] == 4
        assert meta["previous_total"] == TOTAL_ITEMS  # 驟降基準保留


# ── #15 解析出 0 商品 ────────────────────────────────────────────────────────


class TestZeroItems:
    def test_zero_items_parsed_blocks_and_notifies(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        assert run_crawler(tmp_path, today=D1) == 0
        doc_before = load_items_json(tmp_path)

        install_fake(FakeFetcher(empty_all=True))  # 全部分類 edge_empty
        notified: list[str] = []
        rc = run_crawler(tmp_path, today=D2, notify=notified.append)

        assert rc == 1
        assert len(notified) == 1
        assert "0 商品" in notified[0]
        assert load_items_json(tmp_path) == doc_before
        meta = load_meta(tmp_path)
        assert meta["status"] == "failed"


# ── #12 單一分類抓取失敗 → partial ───────────────────────────────────────────


class TestPartialFailure:
    def test_single_category_fetch_failure_partial_keeps_old_data(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        assert run_crawler(tmp_path, today=D1) == 0
        doc1 = load_items_json(tmp_path)
        mobo_before = {i["id"]: i for i in doc1["items"] if i["category"] == "主機板"}
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

        doc2 = load_items_json(tmp_path)
        # 無誤判 gone：全部既有商品 ID 保留
        assert {i["id"] for i in doc2["items"]} == {i["id"] for i in doc1["items"]}
        # 主機板既有商品保留原樣（last_seen / status / history 不變）
        for iid, before in mobo_before.items():
            after = next(i for i in doc2["items"] if i["id"] == iid)
            assert after["last_seen"] == before["last_seen"] == "2026-08-15"
            assert after["status"] == "in_stock"
            assert after["history"] == before["history"]
        # CPU 異動照常更新
        cpu = item_by_name(doc2, CPU_13600K)
        assert cpu["history"] == [["2026-08-15", 9790], ["2026-08-16", 8990]]


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
        doc2 = load_items_json(tmp_path)
        assert len(doc2["items"]) == 45  # 36 現存 + 9 個消失標記 gone


# ── #20 CLI --date 手動補爬 ──────────────────────────────────────────────────


class TestCli:
    def test_date_flag_records_actual_crawl_day(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        rc = main(["--data-dir", str(tmp_path), "--date", "2026-08-14"])
        assert rc == 0
        doc = load_items_json(tmp_path)
        assert all(i["first_seen"] == "2026-08-14" for i in doc["items"])
        assert all(i["last_seen"] == "2026-08-14" for i in doc["items"])
        assert load_meta(tmp_path)["status"] == "ok"

    def test_no_date_defaults_to_today(self, tmp_path, install_fake):
        install_fake(FakeFetcher())
        rc = main(["--data-dir", str(tmp_path)])
        assert rc == 0
        doc = load_items_json(tmp_path)
        assert all(i["first_seen"] == date.today().isoformat() for i in doc["items"])

    def test_unexpected_failure_returns_2(self, tmp_path):
        (tmp_path / "items.json").write_text("{ 損壞的 JSON", encoding="utf-8")
        rc = main(["--data-dir", str(tmp_path), "--date", "2026-08-15"])
        assert rc == 2


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
