"""parser.py 單元測試（BDD #8 G=9 子分類過濾、#9 disabled/贈品列、#10 標記解析、
#16 空表格、#17 特殊字元、#18 重複名稱、#19 價格缺失）。

測試資料全部來自 tests/fixtures/ 樣本 HTML（不依賴真實網路），
涵蓋 9 個分類頁 + 4 個邊界頁 + 1 個混合標記頁，供後續 main E2E 重用。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from crawler.categories import get_category
from crawler.parser import (
    FLAG_CLEARANCE,
    FLAG_HOT,
    FLAG_PRICE_DROP,
    FLAG_PROMO,
    Parser,
)

FIXTURES = Path(__file__).parent / "fixtures"
# 真實 m-list.php 頁面快照（2026-08-15 spike #2 抓取存檔，issue #11 解析基準）
REAL_FIXTURES = Path(__file__).resolve().parents[2] / "scripts" / "tests" / "fixtures" / "mobile"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def parse_fixture(name: str, g_index: int):
    return Parser().parse_page(load_fixture(name), get_category(g_index))


def parse_real(g_index: int):
    return Parser().parse_page(
        (REAL_FIXTURES / f"G{g_index}.html").read_text(encoding="utf-8"),
        get_category(g_index),
    )


# spike #2 統計：9 分類合計 1,449（G=9 已套「記憶卡」子分類過濾）
REAL_COUNTS = {1: 157, 3: 86, 4: 48, 5: 373, 6: 216, 7: 171, 8: 89, 9: 54, 12: 255}


# ── parse_page 基本：<th> 子分類 + <td> 商品列 ─────────────────────────────

class TestParsePageBasics:
    def test_curly_braces_stripped_from_name(self):
        """花括號（全形｛｝或半形{}）自名稱剝離（原價屋 HTML 輔助標記）。"""
        html = """
        <table>
        <thead><tr><th>桌上型記憶體 DDR3</th></tr></thead>
        <tbody>
        <tr><td>｛UMAX 8GB DDR3-1600｝(512*8)</td><td>$679</td></tr>
        <tr><td>{UMAX 16GB DDR4-2666}(2048*8)CL19</td><td>$3500</td></tr>
        <tr><td>UMAX 8GB DDR4-3200(1024*8)超頻CL16</td><td>$1990</td></tr>
        </tbody>
        </table>
        """
        result = Parser().parse_page(html, get_category(6))
        names = [i.name for i in result.items]
        assert "UMAX 8GB DDR3-1600(512*8)" in names
        assert "UMAX 16GB DDR4-2666(2048*8)CL19" in names
        assert "UMAX 8GB DDR4-3200(1024*8)超頻CL16" in names
        # 確保花括號不出現在名稱中
        for name in names:
            assert "｛" not in name
            assert "｝" not in name
            assert "{" not in name
            assert "}" not in name

    def test_th_becomes_subcategories_td_becomes_items(self):
        html = """
        <table>
          <tr><th>Intel 第13代</th></tr>
          <tr><td>Intel i5-13400【10核/16緒】2.5GHz(↑4.6G)/20M/UHD730/65W【代理盒裝】</td><td>7,990</td></tr>
          <tr><th>AMD</th></tr>
          <tr><td>AMD R5 7600【6核/12緒】3.8G(↑5.1G)/65W【代理盒裝】</td><td>6,990</td></tr>
        </table>
        """
        result = Parser().parse_page(html, get_category(4))

        assert result.subcategories == ["Intel 第13代", "AMD"]
        assert [i.subcategory for i in result.items] == ["Intel 第13代", "AMD"]
        assert [i.category for i in result.items] == ["CPU", "CPU"]
        assert result.items[0].name == "Intel i5-13400【10核/16緒】2.5GHz(↑4.6G)/20M/UHD730/65W【代理盒裝】"
        assert result.items[0].price == 7990
        assert result.items[0].flags == {}
        assert result.category is get_category(4)

    def test_no_table_returns_empty_result(self):
        result = Parser().parse_page("<html><body>改版了</body></html>", get_category(4))
        assert result.items == []
        assert result.subcategories == []


# ── 標記解析（BDD #10 Outline 4 例 + 組合 + 自 name 剝離） ─────────────────

class TestFlagParsing:
    def test_hot_marker(self):
        assert Parser()._parse_flags("Hot！Intel i5-13600K") == {FLAG_HOT: True}

    def test_promo_marker(self):
        assert Parser()._parse_flags("Intel i5-13600K 任搭↓190") == {FLAG_PROMO: "任搭190"}

    def test_price_drop_marker(self):
        assert Parser()._parse_flags("↘Intel i5-13600K") == {FLAG_PRICE_DROP: True}

    def test_clearance_marker(self):
        assert Parser()._parse_flags("Intel i5-13600K 尾盤") == {FLAG_CLEARANCE: True}

    def test_hot_plus_promo_combo(self):
        assert Parser()._parse_flags("Hot！Intel i5-13600K 任搭↓190") == {
            FLAG_HOT: True,
            FLAG_PROMO: "任搭190",
        }

    def test_price_drop_plus_clearance_combo(self):
        assert Parser()._parse_flags("↘Intel i5-11400 尾盤") == {
            FLAG_PRICE_DROP: True,
            FLAG_CLEARANCE: True,
        }

    def test_no_marker_returns_empty_dict(self):
        assert Parser()._parse_flags("Intel i5-13600K") == {}

    def test_markers_stripped_from_name(self):
        """標記文字自 name 剝離（避免污染 ID 正規化，#10 規格要求）。"""
        result = parse_fixture("edge_mixed_flags.html", 4)
        names = [i.name for i in result.items]
        assert "Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】" in names
        for name in names:
            assert "Hot！" not in name
            assert "任搭↓" not in name
            assert "↘" not in name
            assert "尾盤" not in name

    def test_mixed_flags_fixture_all_four_markers(self):
        result = parse_fixture("edge_mixed_flags.html", 4)
        by_name = {i.name: i for i in result.items}

        combo = by_name["Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】"]
        assert combo.flags == {FLAG_HOT: True, FLAG_PROMO: "任搭190"}

        drop = by_name["Intel i5-13500【14核/20緒】2.6GHz(↑4.8G)/24M/UHD770/65W【代理盒裝】"]
        assert drop.flags == {FLAG_PRICE_DROP: True}

        clear = by_name["Intel i5-12400【6核/12緒】2.5GHz(↑4.4G)/18M/UHD730/65W【代理盒裝】"]
        assert clear.flags == {FLAG_CLEARANCE: True}

        both = by_name["Intel i5-11400【6核/12緒】2.6GHz(↑4.4G)/12M/UHD730/65W【代理盒裝】"]
        assert both.flags == {FLAG_PRICE_DROP: True, FLAG_CLEARANCE: True}


# ── disabled 加購列 / 贈品列過濾（BDD #9） ────────────────────────────────

class TestDisabledGiftFilter:
    def test_disabled_and_gift_rows_excluded(self):
        result = parse_fixture("edge_disabled_gift.html", 4)
        assert [i.name for i in result.items] == ["一般商品A 無線滑鼠", "一般商品B 機械鍵盤"]


# ── G=9 子分類過濾（BDD #8 Outline 6 例） ─────────────────────────────────

class TestG9SubcategoryFilter:
    def test_memcard_fixture_keeps_only_memory_card_subcategories(self):
        result = parse_fixture("memcard.html", 9)
        kept = {i.subcategory for i in result.items}
        assert kept == {"Micro SD 記憶卡", "SD 記憶卡", "CFexpress 記憶卡", "MicroSDXC Express 記憶卡"}
        assert "隨身碟" not in kept
        assert "外接硬碟" not in kept
        # 收錄子分類的商品皆在
        names = [i.name for i in result.items]
        assert any("Micro SDXC" in n for n in names)            # Micro SD
        assert any("SDXC U3 記憶卡" in n for n in names)        # SD
        assert any("CFexpress 128GB" in n for n in names)       # CFexpress
        assert any("Express 256GB" in n for n in names)         # MicroSDXC Express
        # 排除子分類的整段商品皆不在
        assert not any("隨身碟" in n for n in names)
        assert not any("外接硬碟" in n for n in names)

    @pytest.mark.parametrize(
        ("subcategory", "expect_kept"),
        [
            ("Micro SD 記憶卡", True),
            ("SD 記憶卡", True),
            ("CFexpress 記憶卡", True),
            ("MicroSDXC Express 記憶卡", True),
            ("隨身碟", False),
            ("外接硬碟", False),
        ],
    )
    def test_outline_keyword_filter(self, subcategory: str, expect_kept: bool):
        html = f"<table><tr><th>{subcategory}</th></tr><tr><td>測試商品</td><td>100</td></tr></table>"
        result = Parser().parse_page(html, get_category(9))
        kept = [i for i in result.items if i.subcategory == subcategory]
        assert (len(kept) == 1) is expect_kept


# ── 非 G=9 分類不套用子分類過濾（全收） ───────────────────────────────────

class TestNonG9NoSubcategoryFilter:
    def test_all_subcategory_rows_kept(self):
        result = parse_fixture("cpu.html", 4)
        assert len(result.items) == 4


# ── 空表格（BDD #16） ─────────────────────────────────────────────────────

class TestEmptyTable:
    def test_empty_table_returns_zero_items_no_exception(self):
        result = parse_fixture("edge_empty.html", 6)
        assert result.items == []
        assert result.subcategories == []


# ── 價格缺失（BDD #19） ───────────────────────────────────────────────────

class TestMissingPrice:
    def test_missing_price_yields_none_and_item_kept(self):
        result = parse_fixture("edge_no_price.html", 8)
        by_name = {i.name: i for i in result.items}
        assert by_name["無價格商品A"].price is None   # 無價格欄
        assert by_name["無價格商品B"].price is None   # 「來電」無數字
        assert by_name["有價格商品C"].price == 3000
        assert len(result.items) == 3


# ── 價格解析 ──────────────────────────────────────────────────────────────

class TestPriceParsing:
    def test_comma_separated_price(self):
        assert Parser()._parse_price("9,790") == 9790

    def test_plain_digits(self):
        assert Parser()._parse_price("1299") == 1299

    def test_no_digits_returns_none(self):
        assert Parser()._parse_price("來電") is None

    def test_empty_returns_none(self):
        assert Parser()._parse_price("") is None


# ── 特殊字元與重複名稱（BDD #17 / #18 前置） ──────────────────────────────

class TestSpecialCharsAndDuplicates:
    def test_special_char_names_parsed(self):
        result = parse_fixture("edge_special_chars.html", 4)
        names = [i.name for i in result.items]
        assert "Intel i5-13600K·特別版◆含風扇" in names

    def test_duplicate_names_both_parsed(self):
        """parser 保留兩筆同名列（去重為 store.diff 職責 #18）。"""
        result = parse_fixture("edge_special_chars.html", 4)
        dup = [i for i in result.items if i.name == "重複名稱商品"]
        assert [i.price for i in dup] == [1000, 1200]


# ── 真實 m-list.php 結構（issue #11：span.Q 多 table、td 名稱＋價格同格） ─

class TestRealMobileStructure:
    """真實頁面：<span class=Q> 內每子分類一個 table（thead/th 標題、
    tbody/td 商品列，td 內 `名稱, $價格[↗|↘$異動價] <i>標記</i>`）。"""

    def test_span_q_multiple_tables_all_subcategories_parsed(self):
        result = parse_real(4)
        # 舊 parser 只取第一個 table（logo 表頭）→ 0 子分類；真實結構須全數取得
        assert len(result.subcategories) == 10
        assert result.subcategories[0] == "Intel Core Ultra 200S系列1851 腳位【內建 NPU 支援 AI】"
        assert len(result.items) == 48  # spike 統計（G=4）

    def test_td_name_and_price_same_cell_separated(self):
        result = parse_real(4)
        first = result.items[0]
        assert first.name == "Intel Core Ultra 5 225F【10核】3.3G(↑4.9G) /20M /無內顯【代理盒裝】"
        assert first.price == 4880
        assert first.subcategory == "Intel Core Ultra 200S系列1851 腳位【內建 NPU 支援 AI】"
        assert first.flags == {}

    def test_special_chars_and_arrow_preserved(self):
        result = parse_real(4)
        assert any("↑4.9G" in i.name for i in result.items)

    def test_hot_flag_from_i_tag_stripped_from_name(self):
        result = parse_real(4)
        hot = next(i for i in result.items if "Intel Core Ultra 5 245K" in i.name)
        assert hot.flags == {FLAG_HOT: True}
        assert hot.name == "Intel Core Ultra 5 245K【14核】4.2G(↑5.2G) /24M /內顯Xe-core /無風扇【代理盒裝】"

    def test_price_drop_segment_sets_flag_and_keeps_listed_price(self):
        """`$16150↘$15900`：price=列表價（第一個 $N，與 spike 一致）、price_drop=True。"""
        result = parse_real(4)
        item = next(i for i in result.items
                    if i.name == "AMD R7 9800X3D代理盒裝【8核/16緒】4.7G(↑5.2G)120W /96M /具RDNA內顯")
        assert item.price == 16150
        assert item.flags == {FLAG_PRICE_DROP: True}
        assert "↘" not in item.name


class TestRealMobileNoticeAndDisabledRows:
    """真實頁面 class=y（↪ 限量/加贈通知）、class=z（❤ 專業性產品說明）、
    disabled td 皆非商品列，必須過濾（G=1 含 23 列 y、46 列 z）。"""

    def test_notice_rows_filtered(self):
        result = parse_real(1)
        assert len(result.items) == 157  # spike 統計（G=1）
        for item in result.items:
            assert not item.name.startswith(("❤", "↪"))


class TestRealMobileG9Filter:
    """G=9 混合頁：僅保留子分類含「記憶卡」的 4 段（spike 驗證：保留 54 / 過濾 157）。"""

    def test_memory_card_subcategories_only(self):
        result = parse_real(9)
        kept = {i.subcategory for i in result.items}
        assert kept == {"Micro SD 記憶卡", "SD 記憶卡", "CFexpress記憶卡",
                        "MicroSDXC Express 記憶卡(Switch 2專用)"}
        assert all("記憶卡" in s for s in kept)
        assert len(result.items) == 54  # spike 統計（G=9 過濾後）


class TestRealMobileFlags:
    """真實頁面標記：<i>Hot！</i>、名稱內 尾盤、價格段後 任搭↓N、價格段 ↘。"""

    def test_promo_marker_after_price_segment(self):
        result = parse_real(12)
        item = next(i for i in result.items if "微星 N730-2GD3V3" in i.name)
        assert item.flags == {FLAG_PROMO: "任搭90"}
        assert item.name == "微星 N730-2GD3V3(700MHz/2G DDR3 128Bit/14.5cm/三年保)雪精靈系列"

    def test_clearance_marker_in_name_stripped(self):
        result = parse_real(12)
        item = next(i for i in result.items if "ZOTAC GT710-2GD3-L" in i.name)
        assert item.flags == {FLAG_CLEARANCE: True}
        assert "尾盤" not in item.name

    def test_price_drop_marker(self):
        result = parse_real(12)
        item = next(i for i in result.items if "ZOTAC GT710-2GD3(" in i.name)
        assert item.flags == {FLAG_PRICE_DROP: True}
        assert item.price == 2990

    def test_hot_flag(self):
        result = parse_real(12)
        hot = [i for i in result.items if i.flags.get(FLAG_HOT)]
        assert hot
        assert all("Hot！" not in i.name for i in hot)


class TestRealMobileCategoryCounts:
    """驗收基準：9 分類合計 ≈ 1,449（與 spike 報告統計逐分類對齊，fixture 釘選）。"""

    @pytest.mark.parametrize("g_index", [1, 3, 4, 5, 6, 7, 8, 9, 12])
    def test_count_matches_spike(self, g_index: int):
        result = parse_real(g_index)
        assert len(result.items) == REAL_COUNTS[g_index]

    def test_total_1449(self):
        total = sum(len(parse_real(g).items) for g in REAL_COUNTS)
        assert total == 1449


# ── 依分類實例驗證（fixture 重用基礎，供 main E2E） ───────────────────────

class TestCategoryFixtures:
    def test_cpu_fixture_i5_13600k(self):
        result = parse_fixture("cpu.html", 4)
        item = next(i for i in result.items if "i5-13600K" in i.name)
        assert item.name == "Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】"
        assert item.price == 9790
        assert item.subcategory == "Intel 第13代"
        assert item.flags == {FLAG_HOT: True, FLAG_PROMO: "任搭190"}

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

    @pytest.mark.parametrize("g_index", [1, 3, 4, 5, 6, 7, 8, 9, 12])
    def test_each_category_fixture_parses_without_exception(self, g_index: int):
        result = parse_fixture(self.FIXTURE_BY_G[g_index], g_index)
        assert result.category.g_index == g_index
        assert len(result.items) >= 1
        for item in result.items:
            assert item.category == result.category.name
            assert item.name

    @pytest.mark.parametrize("g_index", [1, 3, 4, 5, 6, 7, 8, 9, 12])
    def test_each_real_category_fixture_parses_without_exception(self, g_index: int):
        """真實頁面 9 分類全數可解析（含 G=9 過濾、Deep spec 名稱欄位）。"""
        result = parse_real(g_index)
        assert result.category.g_index == g_index
        assert len(result.items) >= 1
        for item in result.items:
            assert item.category == result.category.name
            assert item.name
            assert item.subcategory
