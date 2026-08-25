"""categories.py 單元測試（BDD #6 商品 ID 跨日穩定、#7 僅追蹤 9 分類）。

覆蓋：normalize_name 正規化規則、make_item_id ID 穩定/相異性、
CATEGORIES 白名單（9 分類、G 索引、子分類關鍵字、deep_spec）、
Category.url 格式、get_category 查詢與未知 G 拋 KeyError。
"""
from __future__ import annotations

import re

import pytest

from crawler.categories import CATEGORIES, Category, get_category, make_item_id, normalize_name


# ── normalize_name ──────────────────────────────────────────────────────────

class TestNormalizeName:
    def test_nfkc_fullwidth_to_halfwidth(self):
        # 全形英數（ｉｎｔｅｌ、１３６００）→ 半形
        assert normalize_name("ｉｎｔｅｌ i5-１３６００K") == "intel i5-13600k"

    def test_casefold_lowercases(self):
        assert normalize_name("Intel i5-13600K") == "intel i5-13600k"

    def test_consecutive_whitespace_collapsed(self):
        assert normalize_name("Intel  i5-13600K") == "intel i5-13600k"

    def test_strip_leading_trailing_whitespace(self):
        assert normalize_name("  Intel i5-13600K  ") == "intel i5-13600k"

    def test_fullwidth_and_ascii_spelling_equivalent(self):
        # 「Intel  i5-13600K」與「ｉｎｔｅｌ i5-13600k」正規化後一致
        assert normalize_name("Intel  i5-13600K") == normalize_name("ｉｎｔｅｌ i5-13600k")

    def test_tab_and_newline_treated_as_space(self):
        assert normalize_name("Intel\ti5-13600K\n(盒裝)") == "intel i5-13600k (盒裝)"

    def test_curly_braces_removed(self):
        # 全形花括號（｛｝）與半形花括號（{}）皆移除
        assert normalize_name("｛UMAX 8GB DDR3-1600｝") == "umax 8gb ddr3-1600"
        assert normalize_name("{UMAX 8GB DDR3-1600}") == "umax 8gb ddr3-1600"
        assert normalize_name("UMAX 8GB DDR3-1600(512*8)") == "umax 8gb ddr3-1600(512*8)"

    def test_curly_braces_stable_id(self):
        # 含/不含花括號的商品名稱應產生相同 ID
        id_with = make_item_id("記憶體", "｛UMAX 8GB DDR3-1600｝(512*8)")
        id_without = make_item_id("記憶體", "UMAX 8GB DDR3-1600(512*8)")
        assert id_with == id_without


# ── make_item_id ────────────────────────────────────────────────────────────

class TestMakeItemId:
    def test_output_is_16_hex_digits(self):
        item_id = make_item_id("CPU", "Intel i5-13600K")
        assert re.fullmatch(r"[0-9a-f]{16}", item_id) is not None
        assert len(item_id) == 16

    def test_same_item_stable_across_days(self):
        # 同商品跨日（名稱細節變化如空格/全形）重複計算 ID 不變
        day1 = make_item_id("CPU", "Intel i5-13600K【14核/20緒】")
        day2 = make_item_id("CPU", "Intel  i5-13600K【14核/20緒】")
        day3 = make_item_id("CPU", "ＩＮＴＥＬ i5-13600K【14核/20緒】")
        assert day1 == day2 == day3

    def test_different_category_different_id(self):
        assert make_item_id("CPU", "Intel i5-13600K") != make_item_id("主機板", "Intel i5-13600K")

    def test_different_name_different_id(self):
        assert make_item_id("CPU", "Intel i5-13600K") != make_item_id("CPU", "AMD R5 7600")

    def test_name_whitespace_only_affects_via_normalize(self):
        # 前後空白不影響 ID（正規化已 strip）
        assert make_item_id("CPU", "Intel i5-13600K") == make_item_id("CPU", "  Intel i5-13600K  ")


# ── CATEGORIES 白名單 ───────────────────────────────────────────────────────

class TestCategories:
    def test_exactly_nine_categories(self):
        assert len(CATEGORIES) == 9

    def test_g_indexes(self):
        assert tuple(c.g_index for c in CATEGORIES) == (1, 3, 4, 5, 6, 7, 8, 9, 12)

    def test_main_category_names_in_order(self):
        assert [c.name for c in CATEGORIES] == [
            "套裝/準系統", "劈發價組合區", "CPU", "主機板", "記憶體",
            "SSD", "HDD", "記憶卡", "顯示卡",
        ]

    def test_g9_subcategory_keyword_is_memory_card(self):
        g9 = next(c for c in CATEGORIES if c.g_index == 9)
        assert g9.subcategory_keyword == "記憶卡"

    def test_other_categories_have_no_subcategory_keyword(self):
        for c in CATEGORIES:
            if c.g_index != 9:
                assert c.subcategory_keyword is None

    def test_deep_spec_exactly_six_categories(self):
        deep = {c.g_index for c in CATEGORIES if c.deep_spec}
        assert deep == {4, 5, 6, 7, 8, 12}  # CPU/主機板/記憶體/SSD/HDD/顯示卡


# ── Category.url ────────────────────────────────────────────────────────────

class TestCategoryUrl:
    @pytest.mark.parametrize("g_index,expected", [
        (1, "https://www.coolpc.com.tw/m/m-list.php?G=1"),
        (9, "https://www.coolpc.com.tw/m/m-list.php?G=9"),
        (12, "https://www.coolpc.com.tw/m/m-list.php?G=12"),
    ])
    def test_url_format(self, g_index, expected):
        assert Category(g_index, "測試").url == expected

    def test_url_matches_category_urls(self):
        for c in CATEGORIES:
            assert c.url == f"https://www.coolpc.com.tw/m/m-list.php?G={c.g_index}"


# ── get_category ────────────────────────────────────────────────────────────

class TestGetCategory:
    def test_known_g_returns_matching_category(self):
        assert get_category(4).name == "CPU"
        assert get_category(9).subcategory_keyword == "記憶卡"
        assert get_category(1).name == "套裝/準系統"

    def test_unknown_g_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_category(2)
        with pytest.raises(KeyError):
            get_category(999)
