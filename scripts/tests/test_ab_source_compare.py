"""ab_source_compare.py 單元測試（issue #2 A/B 來源驗證 spike）。

涵蓋：
- 名稱正規化對齊：手機版/桌面版裝飾差異（<i>Hot！</i>、◆ ★ 熱賣、↘$…）→ 同一商品
- 名稱/價格分離：`, $N`、`↗$M`、`↘$M` 三種價格型態
- 手機版真實結構解析（span.Q 多 table、thead/th 子分類、td 名稱+價格、
  <i>Hot！</i>、class=y/z 通知列、贈品列、G=9 子分類過濾）
- 手機版舊結構 fallback（單 table、th=子分類、td 分離價格）
- 桌面版 evaluate.php 解析（OPTGROUP/OPTION、disabled 列、❤/↪ 通知列、
  ◆ ★ 熱賣 裝飾、↓任搭N↓/↓酷幣N↓ 促銷標記）
- 桌面→手機分類對應（子分類精確對齊 + 關鍵字 fallback + 未對應清單）
- 差集計算（mobile-only / desktop-only / both，正規化對齊）
- G=9 記憶卡過濾驗證（被過濾項目子分類確實不含「記憶卡」）
- 比對報告格式（含結論欄位）

測試一律離線：使用內嵌 HTML 樣本（與 crawler/tests 同風格），
不依賴真實網路；scripts/tests/conftest.py 已把 scripts/ 加入 sys.path。
"""
from __future__ import annotations

from pathlib import Path

import pytest

import ab_source_compare as asc
from crawler.categories import Category

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# ── 共用樣本 ────────────────────────────────────────────────────────────────

MOBILE_CPU_ROW = (
    "<tr><td onclick=A(this)><img src=img/d.gif>"
    "Intel Core Ultra 5 245K【14核】4.2G(↑5.2G) /24M /內顯Xe-core /無風扇【代理盒裝】, $6990 <i>Hot！</i></tr>"
)
DESKTOP_CPU_OPTION = (
    "<OPTION value=245>Intel Core Ultra 5 245K【14核】4.2G(↑5.2G) /24M /內顯Xe-core /無風扇【代理盒裝】, $6990 ◆ ★ 熱賣</OPTION>"
)


def make_mobile_page(subcats: list[tuple[str, list[str]]]) -> str:
    """依手機版真實結構（span.Q > 多 table > thead/th + tbody/td）組出樣本 HTML。"""
    tables = []
    for subcat, rows in subcats:
        body = "".join(
            f"<tr><td onclick=A(this)><img src=img/d.gif>{name}</tr>" for name in rows
        )
        tables.append(
            f"<table width=100%><thead><tr><th onclick=Pull(this)><img src='p.gif'> {subcat}</tr></thead>"
            f"<tbody class=h>{body}</tbody></table>"
        )
    return f"<html><body><span class=Q>{''.join(tables)}</span></body></html>"


# ── 名稱正規化對齊（RED 1） ─────────────────────────────────────────────────

class TestNameAlignment:
    def test_mobile_and_desktop_same_product_normalize_equal(self):
        # 手機版名稱（含 <i>Hot！</i>、, $price）與桌面版（◆ ★ 熱賣 裝飾）→ 正規化後一致
        mob_name, _, _ = asc.extract_price_info("Intel Core Ultra 5 245K【14核】4.2G(↑5.2G) /24M /內顯Xe-core /無風扇【代理盒裝】, $6990 Hot！")
        desk_name, _, _ = asc.extract_price_info("Intel Core Ultra 5 245K【14核】4.2G(↑5.2G) /24M /內顯Xe-core /無風扇【代理盒裝】, $6990 ◆ ★ 熱賣")
        assert asc.normalize_product_name(mob_name) == asc.normalize_product_name(desk_name)

    def test_fullwidth_halfwidth_equivalent(self):
        # 全形英數與半形 → 正規化一致（重用 crawler.categories.normalize_name）
        a, _, _ = asc.extract_price_info("ｉｎｔｅｌ i5-13600K, $6990")
        b, _, _ = asc.extract_price_info("Intel i5-13600K, $6990")
        assert asc.normalize_product_name(a) == asc.normalize_product_name(b)

    def test_whitespace_variance_equivalent(self):
        a, _, _ = asc.extract_price_info("Intel  i5-13600K【盒裝】, $6990")
        b, _, _ = asc.extract_price_info("Intel i5-13600K【盒裝】, $6990")
        assert asc.normalize_product_name(a) == asc.normalize_product_name(b)

    def test_price_arrow_variants_do_not_pollute_name(self):
        # ↗（漲價）/ ↘（降價）屬於價格段，剝離後不影響名稱
        n1, p1, c1 = asc.extract_price_info("UMAX 16GB 含散熱片, $6350↗$6999")
        n2, p2, c2 = asc.extract_price_info("UMAX 16GB 含散熱片, $17300↘$17200")
        assert asc.normalize_product_name(n1) == asc.normalize_product_name(n2)
        assert (p1, c1) == (6350, 6999)
        assert (p2, c2) == (17300, 17200)


# ── 名稱/價格分離（RED 2） ─────────────────────────────────────────────────

class TestExtractPriceInfo:
    def test_plain_price(self):
        name, price, current = asc.extract_price_info("Intel i5-13600K, $6,990")
        assert name == "Intel i5-13600K"
        assert price == 6990
        assert current is None

    def test_price_up_arrow(self):
        _, price, current = asc.extract_price_info("UMAX 32GB 含散熱片, $11800↗$12300")
        assert (price, current) == (11800, 12300)

    def test_price_down_arrow(self):
        _, price, current = asc.extract_price_info("UMAX 64GB 含散熱片, $17300↘$17200")
        assert (price, current) == (17300, 17200)

    def test_no_price_keeps_name(self):
        name, price, current = asc.extract_price_info("Intel i5-13600K")
        assert name == "Intel i5-13600K"
        assert price is None
        assert current is None

    def test_thousand_separator_parsed(self):
        _, price, _ = asc.extract_price_info("Samsung 9100 PRO 8TB, $83,589")
        assert price == 83589


# ── 手機版真實結構解析（RED 3） ─────────────────────────────────────────────

class TestParseMobile:
    def test_span_q_tables_parse_products(self):
        html = make_mobile_page([
            ("Intel 第13代", ["Intel i5-13400【10核/16緒】, $7990"]),
            ("AMD", ["AMD R5 7600【6核/12緒】, $6990"]),
        ])
        products = asc.parse_mobile(html, Category(4, "CPU"))
        assert [p.subcategory for p in products] == ["Intel 第13代", "AMD"]
        assert [p.name for p in products] == ["Intel i5-13400【10核/16緒】", "AMD R5 7600【6核/12緒】"]
        assert [p.price for p in products] == [7990, 6990]
        assert all(p.category == "CPU" for p in products)

    def test_hot_flag_extracted_and_stripped(self):
        html = make_mobile_page([
            ("Intel 第13代", ["Intel i5-13400【10核/16緒】, $7990 <i>Hot！</i>"]),
        ])
        products = asc.parse_mobile(html, Category(4, "CPU"))
        assert products[0].name == "Intel i5-13400【10核/16緒】"
        assert products[0].flags.get("hot") is True

    def test_yz_notice_rows_skipped(self):
        # class=y / class=z = 通知列（❤ 專業性產品、↪ 限量加贈…），非商品
        html = (
            "<span class=Q>"
            "<table><thead><tr><th>套裝主機</tr></thead><tbody>"
            "<tr><td><img src=img/d.gif>華碩 主機, $29990</tr>"
            "<tr class=y><td><img src=img/d.gif>↪ 微星 獨家限量打造-魔龍姬 特仕版 - 剩餘3 請把握</tr>"
            "<tr><td class=z><img src=img/d.gif>❤ ASUS ROG 系列電競主機</tr>"
            "</tbody></table></span>"
        )
        products = asc.parse_mobile(html, Category(1, "套裝/準系統"))
        assert [p.name for p in products] == ["華碩 主機"]

    def test_disabled_and_gift_rows_skipped(self):
        html = make_mobile_page([
            ("DDR5", [
                "金士頓 32GB DDR5, $2999",
                "金士頓 32GB DDR5 贈品 8GB 隨身碟, $2999",
            ]),
        ])
        products = asc.parse_mobile(html, Category(6, "記憶體"))
        assert [p.name for p in products] == ["金士頓 32GB DDR5"]

    def test_g9_subcategory_filter(self):
        # G=9：僅保留子分類含「記憶卡」的商品，隨身碟/外接硬碟被過濾
        html = make_mobile_page([
            ("Micro SD 記憶卡", ["金士頓 128GB Micro SD 記憶卡, $599"]),
            ("隨身碟 Type-A", ["金士頓 64GB 隨身碟, $399"]),
            ("外接硬碟", ["WD 2TB 外接硬碟, $2799"]),
        ])
        products = asc.parse_mobile(html, Category(9, "記憶卡", subcategory_keyword="記憶卡"))
        assert [p.name for p in products] == ["金士頓 128GB Micro SD 記憶卡"]
        assert [p.subcategory for p in products] == ["Micro SD 記憶卡"]

    def test_non_g9_no_subcategory_filter(self):
        html = make_mobile_page([
            ("M.2 PCIe SSD", ["三星 990 PRO 1TB, $9899"]),
            ("2.5吋 SATA SSD", ["美光 MX500 1TB, $2799"]),
        ])
        products = asc.parse_mobile(html, Category(7, "SSD"))
        assert len(products) == 2

    def test_empty_page_returns_empty_list(self):
        assert asc.parse_mobile("<html><body>改版</body></html>", Category(4, "CPU")) == []

    def test_old_structure_fallback(self):
        # 舊結構（crawler fixtures 樣式）：單 table、th=子分類、td 分離價格
        html = """
        <table border="0" cellspacing="0" width="100%">
          <tr><th colspan="2">Intel 第13代</th></tr>
          <tr><td>Intel i5-13400【10核/16緒】</td><td align="right">7,990</td></tr>
          <tr><th colspan="2">AMD</th></tr>
          <tr><td>AMD R5 7600【6核/12緒】</td><td align="right">6,990</td></tr>
        </table>
        """
        products = asc.parse_mobile(html, Category(4, "CPU"))
        assert [p.subcategory for p in products] == ["Intel 第13代", "AMD"]
        assert [p.price for p in products] == [7990, 6990]

    def test_clearance_marker_stripped_and_aligned_with_desktop(self):
        """委派 crawler.parser 後：名稱內「尾盤」自 name 剝離（flag 保留），
        且與桌面版（normalize 亦剝離尾盤）正規化後一致（差集不誤判）。"""
        mob = asc.parse_mobile(make_mobile_page([
            ("主機板", ["微星 B550M-A PRO(M-ATX/1D1H/LAN 1Gb/註四年)4+2相供電*尾盤, $2990"]),
        ]), Category(5, "主機板"))
        assert mob[0].name == "微星 B550M-A PRO(M-ATX/1D1H/LAN 1Gb/註四年)4+2相供電*"
        assert mob[0].flags.get("clearance") is True
        desk_name, _, _ = asc.extract_price_info(
            "微星 B550M-A PRO(M-ATX/1D1H/LAN 1Gb/註四年)4+2相供電*尾盤, $2990 ◆ ★")
        assert asc.normalize_product_name(mob[0].name) == asc.normalize_product_name(desk_name)


# ── 桌面版 evaluate.php 解析（RED 4） ───────────────────────────────────────

class TestParseDesktop:
    def test_optgroup_option_parsed(self):
        html = (
            "<select>"
            "<OPTGROUP LABEL='Intel Raptor Lake-s 14代1700 腳位'>"
            f"{DESKTOP_CPU_OPTION}"
            "<OPTION value=246>Intel i5-14400【10核/16緒】, $7250 ◆ ★</OPTION>"
            "</OPTGROUP>"
            "</select>"
        )
        groups = asc.parse_desktop(html)
        assert len(groups) == 1
        group = groups[0]
        assert group.label == "Intel Raptor Lake-s 14代1700 腳位"
        assert [p.name for p in group.products] == [
            "Intel Core Ultra 5 245K【14核】4.2G(↑5.2G) /24M /內顯Xe-core /無風扇【代理盒裝】",
            "Intel i5-14400【10核/16緒】",
        ]
        assert [p.price for p in group.products] == [6990, 7250]

    def test_hot_and_promo_flags(self):
        html = (
            "<OPTGROUP LABEL='鍵盤'>"
            "<OPTION value=1>Ducky One X, $3990 ◆ ★ 熱賣</OPTION>"
            "<OPTION value=2>Ducky 鍵帽, $990 ◆ ★ ↓任搭190↓</OPTION>"
            "<OPTION value=3>Ducky 鍵帽 Pro, $1290 ◆ ★ ↓酷幣300↓</OPTION>"
            "</OPTGROUP>"
        )
        groups = asc.parse_desktop(html)
        flags = [p.flags for p in groups[0].products]
        assert flags[0].get("hot") is True
        assert flags[1].get("promo") == "任搭190"
        assert flags[2].get("promo") == "酷幣300"

    def test_disabled_and_notice_options_skipped(self):
        html = (
            "<OPTGROUP LABEL='華碩 ASUS 品牌主機專區'>"
            "<OPTION value=1>華碩 ROG 主機, $29990 ◆ ★</OPTION>"
            "<OPTION disabled style='font-size:9pt' value=2>&#x2764; ASUS ROG 系列電競主機</OPTION>"
            "<OPTION value=3>&#x21AA; 【買就送】買 ASUS 主機就送滑鼠墊</OPTION>"
            "<OPTION disabled value=4>&#x3000;&#x3000;&#x21AA; 微星 獨家限量打造-魔龍姬 特仕版</OPTION>"
            "</OPTGROUP>"
        )
        groups = asc.parse_desktop(html)
        assert [p.name for p in groups[0].products] == ["華碩 ROG 主機"]

    def test_price_arrow_in_desktop(self):
        html = (
            "<OPTGROUP LABEL='桌上型記憶體 DDR5 單條'>"
            "<OPTION value=1>UMAX 16GB(雙通8GB*2) DDR5 5600/CL46 含散熱片, $6350↗$6999 ◆ ★</OPTION>"
            "</OPTGROUP>"
        )
        groups = asc.parse_desktop(html)
        p = groups[0].products[0]
        assert p.name == "UMAX 16GB(雙通8GB*2) DDR5 5600/CL46 含散熱片"
        assert (p.price, p.current_price) == (6350, 6999)

    def test_empty_desktop_returns_no_groups(self):
        assert asc.parse_desktop("<html><body></body></html>") == []


# ── 桌面→手機分類對應（RED 5） ─────────────────────────────────────────────

class TestClassifyDesktop:
    def test_exact_subcategory_match(self):
        groups = [asc.DesktopGroup("Intel Raptor Lake-s 14代1700 腳位", [])]
        mobile_subcats = {"CPU": {"Intel Raptor Lake-s 14代1700 腳位"}}
        mapped, unmapped = asc.classify_desktop(groups, mobile_subcats)
        assert set(mapped) == {"CPU"}
        assert unmapped == []

    def test_unmatched_label_reported(self):
        groups = [asc.DesktopGroup("PAD 智慧平板", [
            asc.Product("", "PAD 智慧平板", "ASUS Pad T3201", 17999, None, {}, "desktop"),
        ])]
        mobile_subcats = {"CPU": {"Intel 第13代"}}
        mapped, unmapped = asc.classify_desktop(groups, mobile_subcats)
        assert mapped == {}
        assert [g.label for g in unmapped] == ["PAD 智慧平板"]

    def test_keyword_fallback_for_socket_labels(self):
        # 子分類未對齊時以關鍵字規則兜底：CPU 先於主機板（兩者 label 都含「腳位」）
        groups = [
            asc.DesktopGroup("Intel Core Ultra 200S系列1851 腳位【內建 NPU 支援 AI】", []),
            asc.DesktopGroup("Intel B760 / 1700腳位(DDR5)-12~14代皆支援", []),
        ]
        mapped, unmapped = asc.classify_desktop(groups, {})
        assert mapped.get("CPU") is not None
        assert mapped.get("主機板") is not None
        assert unmapped == []

    def test_whitespace_variance_still_matches(self):
        groups = [asc.DesktopGroup("Intel  Raptor Lake-s  14代1700 腳位", [])]
        mobile_subcats = {"CPU": {"Intel Raptor Lake-s 14代1700 腳位"}}
        mapped, _ = asc.classify_desktop(groups, mobile_subcats)
        assert set(mapped) == {"CPU"}


# ── 差集計算（RED 6） ──────────────────────────────────────────────────────

class TestComputeDiff:
    def test_both_mobile_only_desktop_only(self):
        mobile = {
            "CPU": [
                asc.Product("CPU", "Intel 第13代", "Intel i5-13400", 7990, None, {}, "mobile"),
                asc.Product("CPU", "Intel 第13代", "Intel i5-13500", 8990, None, {}, "mobile"),
            ]
        }
        desktop = {
            "CPU": [
                asc.Product("CPU", "Intel 第13代", "Intel i5-13400", 7990, None, {}, "desktop"),
                asc.Product("CPU", "Intel 第13代", "AMD R5 7600", 6990, None, {}, "desktop"),
            ]
        }
        diff = asc.compute_diff(mobile, desktop)
        cpu = diff["CPU"]
        assert {p.name for p in cpu.both} == {"Intel i5-13400"}
        assert {p.name for p in cpu.mobile_only} == {"Intel i5-13500"}
        assert {p.name for p in cpu.desktop_only} == {"AMD R5 7600"}

    def test_normalization_aligns_names(self):
        mobile = {
            "CPU": [asc.Product("CPU", "s", "Intel  i5-13600K【盒裝】", 9990, None, {}, "mobile")],
        }
        desktop = {
            "CPU": [asc.Product("CPU", "s", "ｉｎｔｅｌ i5-13600K【盒裝】", 9500, None, {}, "desktop")],
        }
        diff = asc.compute_diff(mobile, desktop)
        assert len(diff["CPU"].both) == 1
        assert diff["CPU"].mobile_only == []
        assert diff["CPU"].desktop_only == []

    def test_empty_desktop_category(self):
        diff = asc.compute_diff({"SSD": []}, {"SSD": []})
        assert diff["SSD"].both == []
        assert diff["SSD"].mobile_only == []
        assert diff["SSD"].desktop_only == []


# ── G=9 記憶卡過濾驗證（RED 7） ────────────────────────────────────────────

class TestVerifyG9Filter:
    def _products(self, subcats: list[tuple[str, str]]) -> list[asc.Product]:
        return [
            asc.Product("記憶卡", sub, name, 100, None, {}, "mobile")
            for sub, name in subcats
        ]

    def test_kept_all_have_keyword_filtered_none_have(self):
        products = self._products([
            ("Micro SD 記憶卡", "金士頓 128GB"),
            ("SD 記憶卡", "SanDisk 64GB"),
            ("隨身碟 Type-A", "金士頓 64GB 隨身碟"),
            ("外接硬碟", "WD 2TB"),
        ])
        result = asc.verify_g9_filter(products, Category(9, "記憶卡", subcategory_keyword="記憶卡"))
        assert [p.name for p in result.kept] == ["金士頓 128GB", "SanDisk 64GB"]
        assert [p.name for p in result.filtered] == ["金士頓 64GB 隨身碟", "WD 2TB"]
        assert result.kept_all_have_keyword is True
        assert result.filtered_none_have_keyword is True

    def test_keyword_boundary_substring(self):
        # 「記憶卡」必須作為子分類子字串；「記憶體」不含「記憶卡」→ 被過濾
        products = self._products([("伺服器專用記憶體 DDR5", "伺服器 RAM"), ("SD 記憶卡", "SanDisk 64GB")])
        result = asc.verify_g9_filter(products, Category(9, "記憶卡", subcategory_keyword="記憶卡"))
        assert [p.name for p in result.filtered] == ["伺服器 RAM"]
        assert result.filtered_none_have_keyword is True

    def test_non_g9_category_verification_skipped(self):
        products = self._products([("DDR5", "金士頓 32GB")])
        result = asc.verify_g9_filter(products, Category(6, "記憶體"))
        assert result.kept == products
        assert result.filtered == []
        assert result.kept_all_have_keyword is True
        assert result.filtered_none_have_keyword is True


# ── 比對報告格式（RED 8） ─────────────────────────────────────────────────

class TestBuildReport:
    def _sample_diff(self) -> dict:
        return {
            "CPU": asc.DiffSets(
                both=[asc.Product("CPU", "s", "Intel i5-13400", 7990, None, {}, "mobile")],
                mobile_only=[asc.Product("CPU", "s", "Intel i5-13500", 8990, None, {}, "mobile")],
                desktop_only=[asc.Product("CPU", "s", "AMD R5 7600", 6990, None, {}, "desktop")],
            )
        }

    def test_report_has_required_keys(self):
        report = asc.build_report(
            fetched_at="2026-08-15T12:00:00+00:00",
            categories=["CPU"],
            mobile_counts={"CPU": 2},
            desktop_counts={"CPU": 2},
            diffs=self._sample_diff(),
            g9=asc.G9FilterResult([], [], True, True),
            unmapped_desktop=[],
            total_mobile=2,
            total_desktop=2,
        )
        for key in ("method", "fetched_at", "categories", "totals", "g9_verification",
                    "conclusion", "diff_summary"):
            assert key in report, f"報告缺少 {key} 欄位"
        assert report["conclusion"]["coverage_complete"] is False  # 有 desktop-only → 不完整
        cpu = report["categories"]["CPU"]
        assert cpu["mobile_count"] == 2
        assert cpu["desktop_count"] == 2
        assert cpu["both"] == 1
        assert cpu["mobile_only"] == 1
        assert cpu["desktop_only"] == 1

    def test_conclusion_fields_for_clean_match(self):
        diff = {"CPU": asc.DiffSets(
            both=[asc.Product("CPU", "s", "Intel i5-13400", 7990, None, {}, "mobile")],
            mobile_only=[], desktop_only=[])}
        report = asc.build_report(
            fetched_at="2026-08-15T12:00:00+00:00",
            categories=["CPU"],
            mobile_counts={"CPU": 1},
            desktop_counts={"CPU": 1},
            diffs=diff,
            g9=asc.G9FilterResult([], [], True, True),
            unmapped_desktop=[],
            total_mobile=1,
            total_desktop=1,
        )
        assert report["conclusion"]["coverage_complete"] is True
        assert report["conclusion"]["total_mobile"] == 1
        assert report["conclusion"]["total_desktop"] == 1

    def test_render_markdown_sections(self):
        report = asc.build_report(
            fetched_at="2026-08-15T12:00:00+00:00",
            categories=["CPU"],
            mobile_counts={"CPU": 2},
            desktop_counts={"CPU": 2},
            diffs=self._sample_diff(),
            g9=asc.G9FilterResult([], [], True, True),
            unmapped_desktop=[],
            total_mobile=2,
            total_desktop=2,
        )
        md = asc.render_markdown(report)
        for section in ("# ", "## ", "差異", "結論"):
            assert section in md


# ── 離線完整管線（fixture 已存檔，不依賴網路） ──────────────────────────────

_HAS_FIXTURES = (FIXTURES_DIR / "mobile" / "G4.html").exists() and (
    FIXTURES_DIR / "desktop" / "evaluate.html").exists()


@pytest.mark.skipif(not _HAS_FIXTURES, reason="尚未執行 --save-html 存檔（離線不可跑）")
class TestOfflinePipeline:
    def test_run_comparison_from_saved_html(self):
        report = asc.run_comparison(FIXTURES_DIR)
        assert report["totals"]["mobile"] > 1000  # 追蹤範圍約 1,449
        assert report["totals"]["desktop"] > 1000
        assert len(report["categories"]) == 9

    def test_mobile_1449_claim_and_full_desktop_coverage(self):
        # spike 核心主張：手機版 9 分類總數 = 1,449，且桌面版涵蓋全部手機版商品
        report = asc.run_comparison(FIXTURES_DIR)
        assert report["conclusion"]["total_mobile"] == 1449
        assert report["conclusion"]["mobile_only_total"] == 0
        assert report["conclusion"]["coverage_complete"] is False  # 有桌面配件區段差

    def test_g9_filter_verified_on_both_sources(self):
        report = asc.run_comparison(FIXTURES_DIR)
        g9 = report["g9_verification"]
        for source in ("mobile", "desktop"):
            assert g9[source]["kept_all_have_keyword"] is True
            assert g9[source]["filtered_none_have_keyword"] is True
            assert g9[source]["filtered"] > 100  # 隨身碟/隨身SSD/外接硬碟 被過濾
