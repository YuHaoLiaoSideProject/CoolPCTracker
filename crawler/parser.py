"""HTML table → RawItem。過濾 disabled/贈品列；G=9 子分類過濾；標記解析。

來源：Tech Decision §2.2（手機版 m-list.php 乾淨 table：
<th>=子分類標題、<td>=商品列）、開發規格 §1.5（BDD #8/#9/#10/#16/#19）。
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

        1. 找 table → 以 <th> 切分子分類區塊
        2. 逐商品列 parse → RawItem
        3. 過濾 disabled 加購列 / 贈品列
        4. G=9：僅保留子分類名稱含 category.subcategory_keyword 的商品
        5. 無任何商品列 → 回傳空 list，不拋例外（BDD 空表格）
        """
        tree = HTMLParser(html)
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
