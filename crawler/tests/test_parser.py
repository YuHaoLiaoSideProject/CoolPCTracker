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


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def parse_fixture(name: str, g_index: int):
    return Parser().parse_page(load_fixture(name), get_category(g_index))


# ── parse_page 基本：<th> 子分類 + <td> 商品列 ─────────────────────────────

class TestParsePageBasics:
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
