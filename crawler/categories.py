"""分類清單與商品 ID 產生規則。來源：Tech Decision §2.3、IF §2 追蹤範圍。

本模組為追蹤範圍的「單一事實來源」：定義 9 個分類白名單、
名稱正規化規則與商品 ID 產生規則。無外部依賴；任何模組不得硬編碼 G 索引。
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    """一個手機版分類頁。subcategory_keyword 用於 G=9 混合頁的子分類過濾。"""

    g_index: int  # m-list.php?G=<index>
    name: str  # 主分類名稱（ID hash 的輸入之一）
    subcategory_keyword: str | None = None  # G=9 = "記憶卡"，其餘 None
    deep_spec: bool = False  # 深度規格解析分類（CPU/GPU/RAM/SSD/HDD/主機板）

    @property
    def url(self) -> str:
        """完整分類頁 URL（007 meta.sources 與警報所需）。"""
        return f"https://www.coolpc.com.tw/m/m-list.php?G={self.g_index}"


CATEGORIES: tuple[Category, ...] = (
    Category(1, "套裝/準系統"),
    Category(3, "劈發價組合區"),
    Category(4, "CPU", deep_spec=True),
    Category(5, "主機板", deep_spec=True),
    Category(6, "記憶體", deep_spec=True),
    Category(7, "SSD", deep_spec=True),
    Category(8, "HDD", deep_spec=True),
    Category(9, "記憶卡", subcategory_keyword="記憶卡"),  # 僅收錄含「記憶卡」子分類
    Category(12, "顯示卡", deep_spec=True),
)

_CATEGORY_BY_G: dict[int, Category] = {c.g_index: c for c in CATEGORIES}


def get_category(g_index: int) -> Category:
    """依 G 索引取得分類。未知索引拋 KeyError（白名單外的分類永不抓取）。"""
    return _CATEGORY_BY_G[g_index]


def normalize_name(name: str) -> str:
    """名稱正規化：NFKC（全形→半形）→ 移除花括號 → casefold → 連續空白收縮 → strip。
    ID 跨日穩定的關鍵；原價屋名稱細節改動不會使 ID 漂移（除非實質改名）。
    花括號（全形｛｝或半形{}）為原價屋 HTML 輔助標記，不影響商品識別。"""
    nfkc = unicodedata.normalize("NFKC", name)
    no_braces = re.sub(r"[{}]", "", nfkc)  # 移除全形/半形花括號
    return re.sub(r"\s+", " ", no_braces).casefold().strip()


def make_item_id(category_name: str, name: str) -> str:
    """商品 ID = sha256(主分類 + '\\0' + 正規化名稱) 取前 16 位 hex。
    同商品跨日重複計算 ID 不變；同日重跑亦不變（BDD ID 穩定）。"""
    payload = f"{category_name}\0{normalize_name(name)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
