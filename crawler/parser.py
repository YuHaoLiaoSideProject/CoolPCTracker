"""m-list.php 真實結構 → RawItem（issue #11 重寫，對齊真實頁面）。

**真實結構**（2026-08-15 spike #2 實測，fixtures：`scripts/tests/fixtures/mobile/G*.html`）：
`<span class=Q>` 內「每個子分類一個 table」——thead/tr/th = 子分類標題（無
`</th>` 收尾，selectolax 容錯），tbody/tr/td = 商品列；**td 內名稱與價格同格**
（`名稱, $價格[↗|↘$異動價] <i>標記</i>`）；class=y（↪ 限量/加贈通知）、
class=z（❤ 專業性產品說明）、disabled 皆為非商品列。

舊版 parser 假設單 table（`tree.css_first("table")` 取到的第一個 table 為本頁
logo 表頭），對真實頁面每分類僅產 3 筆錯誤資料——此為 spike 發現，本版依真實
結構重寫；並保留舊單 table 結構（th=子分類、td 名稱/價格分格）作為 fallback：
既有 `crawler/tests/fixtures/*.html`（設計期結構）與頁面改版時皆可降級解析。

來源：issue #11、spike 報告 `docs/spike/ab-source-compare-2026-08-15.md`、
開發規格 §1.5（BDD #8/#9/#10/#16/#19）。parse() 介面不變：
`parse_page(html, category) -> ParseResult`（items: list[RawItem]）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from selectolax.parser import HTMLParser, Node

from .categories import Category

FLAG_HOT = "hot"  # Hot！ 熱賣
FLAG_PROMO = "promo"  # 任搭↓N 促銷（值如 "任搭190"）
FLAG_PRICE_DROP = "price_drop"  # ↘ 降價顯示
FLAG_CLEARANCE = "clearance"  # 尾盤 清倉

# 四種標記字面互不重疊，可任意順序逐個掃描與剝離。
_FLAG_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Hot！"), FLAG_HOT),
    (re.compile(r"任搭↓(\d+)"), FLAG_PROMO),
    (re.compile(r"↘"), FLAG_PRICE_DROP),
    (re.compile(r"尾盤"), FLAG_CLEARANCE),
)

_GIFT_KEYWORD = "贈品"
_DISABLED_CLASS = "disabled"
# 真實頁面通知列 class（非商品）：y=↪ 限量/加贈通知、z=❤ 專業性產品說明
_NOTICE_CLASSES = frozenset({"y", "z"})
_NOTICE_PREFIXES = ("❤", "↪")  # 防禦：class 遺失時以文字字首判別
# 價格段：`名稱, $N` 或 `名稱, $N↗$M` / `名稱, $N↘$M`（N=列表價、M=異動後價）
_PRICE_SEGMENT_RE = re.compile(r",\s*\$(\d[\d,]*)(?:[↗↘]\$(\d[\d,]*))?")


@dataclass
class RawItem:
    category: str
    subcategory: str
    name: str
    price: int | None
    flags: dict[str, Any] = field(default_factory=dict)  # hot/promo/price_drop/clearance


@dataclass
class ParseResult:
    category: Category
    items: list[RawItem]
    subcategories: list[str]  # 該頁出現的子分類標題（G=9 過濾判斷依據）


class Parser:
    """selectolax 解析（Spike：vs BeautifulSoup4 擇一，本類別介面不變）。"""

    def parse_page(self, html: str, category: Category) -> ParseResult:
        """完整解析一頁：

        1. 真實結構優先：`<span class=Q>` 多 table（th=子分類、td 名稱＋價格同格）
        2. 過濾 disabled / class=y,z 通知列 / 贈品列
        3. G=9：僅保留子分類名稱含 category.subcategory_keyword 的商品
        4. 無 span.Q → 舊單 table 結構 fallback（既有 fixtures 相容）
        5. 無任何商品列 → 回傳空 list，不拋例外（BDD 空表格）
        """
        tree = HTMLParser(html)
        span_q = tree.css_first("span.Q")
        if span_q is not None:
            return self._parse_span_q(span_q, category)
        return self._parse_legacy(tree, category)

    # ── 真實 m-list.php 結構（span.Q 多 table、td 名稱＋價格同格） ───────────

    def _parse_span_q(self, span_q: Node, category: Category) -> ParseResult:
        """真實頁面（spike #2 / issue #11）。

        span.Q 內每子分類一個 table：thead/tr/th = 子分類標題；tbody/tr/td =
        商品列（td 內 `名稱, $價格[↗|↘$異動價] <i>標記</i>`）。
        class=y/z 通知列與 disabled 列非商品，一律過濾。
        """
        items: list[RawItem] = []
        subcategories: list[str] = []
        current_subcategory = ""

        for table in span_q.css("table"):
            th = table.css_first("th")
            if th is not None:
                current_subcategory = th.text().strip()
                subcategories.append(current_subcategory)
            # 防禦：table 無 th（真實頁面未見過）→ 沿用上一子分類
            for tr in table.css("tr"):
                if tr.css_first("th") is not None:
                    continue  # 標題列（thead）
                cell = self._product_cell_text(tr)
                if cell is None:
                    continue
                name, price, flags = self._parse_cell_text(cell)
                if not name or _GIFT_KEYWORD in name:
                    continue
                if (
                    category.subcategory_keyword is not None
                    and category.subcategory_keyword not in current_subcategory
                ):
                    continue

                items.append(
                    RawItem(
                        category=category.name,
                        subcategory=current_subcategory,
                        name=name,
                        price=price,
                        flags=flags,
                    )
                )

        return ParseResult(category=category, items=items, subcategories=subcategories)

    def _product_cell_text(self, tr: Node) -> str | None:
        """回傳商品列 td 文字；非商品列（disabled / class=y,z / 無 td / 空 cell）回傳 None。"""
        td = tr.css_first("td")
        if td is None:
            return None
        classes = set((tr.attributes.get("class") or "").split())
        classes |= set((td.attributes.get("class") or "").split())
        if _DISABLED_CLASS in classes or classes & _NOTICE_CLASSES:
            return None
        if td.attributes.get("disabled") is not None:
            return None
        cell = td.text().strip()
        if not cell or cell.startswith(_NOTICE_PREFIXES):
            return None  # 防禦：❤/↪ 通知列（真實頁面帶 class=y/z，舊結構可能無）
        return cell

    def _parse_cell_text(self, cell: str) -> tuple[str, int | None, dict[str, Any]]:
        """真實結構 td 文字解析：`名稱, $N[↗|↘$M] <i>標記</i>` → (名稱, 價格, flags)。

        價格 = 列表價 `, $N`（與 spike 一致；↗/↘ 後為異動價，不影響本欄）。
        flags 偵測自完整 cell（Hot！/任搭↓N/↘/尾盤），標記文字自名稱剝離
        （與偵測同一輪掃描，確保兩者永遠一致，不污染 ID 正規化）。
        """
        match = _PRICE_SEGMENT_RE.search(cell)
        if match is not None:
            name = cell[: match.start()]
            price = int(match.group(1).replace(",", ""))
        else:
            name = cell
            price = None

        # 移除花括號（全形｛｝或半形{}）：原價屋 HTML 輔助標記，不影響商品識別
        name = re.sub(r"[{}｛｝]", "", name)

        flags: dict[str, Any] = {}
        stripped = name
        for pattern, key in _FLAG_PATTERNS:
            flag_match = pattern.search(cell)
            if flag_match is None:
                continue
            if key == FLAG_PROMO:
                flags[key] = f"任搭{flag_match.group(1)}"
            else:
                flags[key] = True
            stripped = pattern.sub("", stripped)
        return re.sub(r"\s+", " ", stripped).strip(), price, flags

    # ── 舊單 table 結構 fallback（設計期 fixtures / 頁面改版降級） ───────────

    def _parse_legacy(self, tree: HTMLParser, category: Category) -> ParseResult:
        """單 table、<th>=子分類、td 名稱/價格分格的舊結構。

        既有 `crawler/tests/fixtures/*.html`（設計期樣式）與 test_main 自訂
        頁面以此路徑解析；真實頁面改版（無 span.Q）時亦降級至此，避免全數漏品。
        """
        table = tree.css_first("table")
        if table is None:
            return ParseResult(category=category, items=[], subcategories=[])

        items: list[RawItem] = []
        subcategories: list[str] = []
        current_subcategory = ""

        for tr in table.css("tr"):
            th = tr.css_first("th")
            if th is not None:
                current_subcategory = th.text().strip()
                subcategories.append(current_subcategory)
                continue

            tds = tr.css("td")
            if not tds:
                continue
            if self._is_disabled_row(tr):
                continue

            name, flags = self._parse_cell(tds[0].text())
            if _GIFT_KEYWORD in name:
                continue

            price = self._parse_price_from_cells(tds[1:])
            if (
                category.subcategory_keyword is not None
                and category.subcategory_keyword not in current_subcategory
            ):
                continue

            items.append(
                RawItem(
                    category=category.name,
                    subcategory=current_subcategory,
                    name=name,
                    price=price,
                    flags=flags,
                )
            )

        return ParseResult(category=category, items=items, subcategories=subcategories)

    def _parse_flags(self, cell_text: str) -> dict[str, Any]:
        """標記解析（BDD 商品標記解析 Outline）：

        'Hot！' → {hot: True}；'任搭↓N' → {promo: '任搭<N>'}；
        '↘' → {price_drop: True}；'尾盤' → {clearance: True}；可同時多個。
        """
        return self._parse_cell(cell_text)[1]

    def _parse_price(self, cell_text: str) -> int | None:
        """價格欄解析（"9,790" → 9790）；無價格回傳 None（不拋例外）。"""
        match = re.search(r"\d[\d,]*", cell_text or "")
        if match is None:
            return None
        return int(match.group(0).replace(",", ""))

    def _parse_cell(self, cell_text: str) -> tuple[str, dict[str, Any]]:
        """單一 pass 解析名稱欄：回傳 (剝離標記後名稱, flags)。

        flags 偵測與標記剝離共用同一輪 regex 掃描，確保兩者永遠一致
        （偵測到的標記一定被剝離，名稱不會污染 ID 正規化）。
        """
        # 移除花括號（全形｛｝或半形{}）：原價屋 HTML 輔助標記，不影響商品識別
        cell_text = re.sub(r"[{}｛｝]", "", cell_text)
        flags: dict[str, Any] = {}
        stripped = cell_text
        for pattern, key in _FLAG_PATTERNS:
            match = pattern.search(stripped)
            if match is None:
                continue
            if key == FLAG_PROMO:
                flags[key] = f"任搭{match.group(1)}"
            else:
                flags[key] = True
            stripped = pattern.sub("", stripped)
        return re.sub(r"\s+", " ", stripped).strip(), flags

    def _parse_price_from_cells(self, cells: list[Node]) -> int | None:
        """依序掃描價格欄（名稱欄之後的 td）；第一個可解析數字即為價格。"""
        for td in cells:
            price = self._parse_price(td.text())
            if price is not None:
                return price
        return None

    def _is_disabled_row(self, tr: Node) -> bool:
        """disabled 加購列：class 含 disabled，或列內含 disabled input/checkbox。"""
        classes = (tr.attributes.get("class") or "").split()
        if _DISABLED_CLASS in classes:
            return True
        return any("disabled" in node.attributes for node in tr.css("input"))
