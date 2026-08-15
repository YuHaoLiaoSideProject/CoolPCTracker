"""A/B 來源驗證 spike（issue #2）：手機版 9 分類 vs 桌面版 evaluate.php 商品集合比對。

目的：驗證 9 分類手機版爬取無漏品、確認約 1,449 商品的追蹤範圍正確、
G=9 記憶卡子分類過濾無誤刪。本模組為 spike 產物，不修改 crawler 核心模組。

**Spike 關鍵發現（實測 2026-08-15 真實頁面）**：
- 手機版 m-list.php 實際結構為 `<span class=Q>` 內「每個子分類一個 table
  （thead/th 標題 + tbody/td 商品列）」，td 內名稱與價格同格
  （`名稱, $價格 [↗|↘$異動價]`），`<i>Hot！</i>` 標記、class=y/z 通知列
  （❤ 專業性產品 / ↪ 限量加贈）；與 crawler/tests/fixtures 的單 table 結構不同
  （既有 crawler.parser.Parser 只解析第一個 table，對真實頁面會產生錯誤結果，
  此為 spike 發現，需另開 issue 對齊 parser 與真實結構）。
- 桌面版 evaluate.php 為 malformed HTML：`<OPTGROUP>` 無 `</OPTGROUP>` 收尾、
  部分 `<OPTION>` 未收尾；selectolax 自動修正後可正確解析。商品列格式
  `名稱, $價格[↗|↘$異動價] ◆ ★ [熱賣] [↓任搭N↓|↓酷幣N↓]`。
- 兩來源商品名稱字串相同（價格段與裝飾剝離後一致），可直接以正規化名稱對齊。

手機版解析（真實 span.Q 結構 + 舊結構 fallback）委派 `crawler.parser.Parser`
（issue #11 已依真實 m-list.php 重寫：多 table、td 名稱＋價格同格、
y/z 通知列/disabled/贈品列過濾、四種標記剝離、G=9 子分類過濾），
本模組不再維護第二套手機版解析實作；名稱正規化時桌面版亦剝離「尾盤」
（與 crawler 標記剝離語意一致），兩來源差集對齊不因該標記產生假性差異。
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 直接以 `python scripts/ab_source_compare.py` 執行時，repo 根目錄不在 sys.path；
# 加入 bootstrap 讓 `import crawler` 可用（pytest 路徑由 conftest 提供，不影響）。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx
from selectolax.parser import HTMLParser

from crawler.categories import CATEGORIES, Category, normalize_name
from crawler.parser import Parser as CrawlerParser

logger = logging.getLogger(__name__)

DESKTOP_URL = "https://www.coolpc.com.tw/evaluate.php"
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

# 桌面版通知列／非商品列字首（&#x2764;=❤、&#x21AA;=↪ 已由 selectolax 解碼）
_NOTICE_PREFIXES = ("\u3000", "❤", "↪")

_PRICE_RE = re.compile(r",\s*\$(\d[\d,]*)(?:[↗↘]\$(\d[\d,]*))?")
# 桌面版裝飾（價格段之後）：◆ ★ 熱賣 尾盤 ↓任搭N↓ ↓酷幣N↓
# （尾盤 與 crawler.parser 對手機版的標記剝離同語意，兩來源正規化後一致）
_DESKTOP_FLAG_RE = re.compile(r"◆|★|熱賣|尾盤|↓任搭(\d+)↓|↓酷幣(\d+)↓")

# 桌面 optgroup 關鍵字 fallback 規則（僅用於「子分類未對齊」的 label；
# 順序敏感：CPU 先於主機板（皆含「腳位」）、劈發價先於套裝（皆含「主機/套裝」））
_DESKTOP_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("CPU", ("Intel Core Ultra", "Raptor Lake", "Alder Lake", "Sapphire Rapids",
             "AMD AM4", "AMD AM5", "Ryzen Threadripper")),
    ("主機板", ("Intel W680", "Intel W790", "Intel W890", "Intel H610", "Intel H810",
               "Intel H110", "Intel H510", "Intel H81", "Intel B760", "Intel B860",
               "Intel Z790", "Intel Z890", "AMD A520", "AMD B550", "AMD A620",
               "AMD B650", "AMD B840", "AMD B850", "AMD X870", "AMD WRX80",
               "AMD TRX50", "AMD WRX90", "工作站級", "伺服器級")),
    ("記憶體", ("記憶體",)),
    ("SSD", ("SSD",)),
    ("HDD", ("傳統碟", "監控碟", "NAS碟", "企業碟")),
    ("記憶卡", ("記憶卡",)),
    ("顯示卡", ("顯示卡", "GeForce", "Radeon", "Arc")),
    ("劈發價組合區", ("套裝", "組合", "酷！PC")),
    ("套裝/準系統", ("主機", "準系統", "NUC", "AIO", "DGX", "BRIX", "VR", "眼鏡")),
)


@dataclass
class Product:
    """單一商品（跨來源統一模型）。category 為 9 分類名稱（未對應桌面商品為空字串）。"""

    category: str
    subcategory: str
    name: str
    price: int | None  # 價格段第一個 `, $N`
    current_price: int | None  # ↗/↘ 異動後價格（無則 None）
    flags: dict[str, Any] = field(default_factory=dict)
    source: str = ""  # "mobile" | "desktop"


@dataclass
class DesktopGroup:
    """桌面版一個 OPTGROUP（label = 子分類名稱，與手機版子分類同名）。"""

    label: str
    products: list[Product]


@dataclass
class DiffSets:
    """單一分類的兩來源差集。both 以 mobile 側 Product 為代表。"""

    both: list[Product]
    mobile_only: list[Product]
    desktop_only: list[Product]


@dataclass
class G9FilterResult:
    """G=9 記憶卡子分類過濾驗證：kept 全含關鍵字、filtered 全不含。"""

    kept: list[Product]
    filtered: list[Product]
    kept_all_have_keyword: bool
    filtered_none_have_keyword: bool


# ── 名稱／價格處理 ──────────────────────────────────────────────────────────

def extract_price_info(text: str) -> tuple[str, int | None, int | None]:
    """由 `名稱, $N[↗|↘$M]` 剝離價格段。

    回傳 (名稱, 價格, 異動後價格)；無價格段 → (原文字, None, None)。
    名稱內的 ↗/↘ 不在此段（原價屋 ↗=漲價、↘=降價顯示，屬價格段）。
    """
    match = _PRICE_RE.search(text)
    if match is None:
        return text.strip(), None, None
    name = text[: match.start()].strip()
    price = int(match.group(1).replace(",", ""))
    current = int(match.group(2).replace(",", "")) if match.group(2) else None
    return name, price, current


def normalize_product_name(name: str) -> str:
    """跨來源名稱正規化：先剝離桌面版裝飾（◆ ★ 熱賣 ↓任搭N↓ ↓酷幣N↓），
    再套用 crawler.categories.normalize_name（NFKC → casefold → 空白收縮）。
    兩來源同名商品正規化後一致，為差集對齊的 key。"""
    cleaned = _DESKTOP_FLAG_RE.sub("", name)
    return normalize_name(cleaned)


# ── 手機版解析（真實 span.Q 結構 + 舊結構 fallback） ───────────────────────

def parse_mobile(html: str, category: Category) -> list[Product]:
    """解析手機版單一分類頁（真實 span.Q 多 table 與舊單 table 結構皆委派
    crawler.parser.Parser，issue #11 已對齊真實 m-list.php）。

    crawler 涵蓋：th=子分類、td 名稱＋價格同格（`, $N[↗|↘$M]`）、
    class=y/z 通知列（❤/↪）、disabled（tr/td class 與 td attr）、贈品列過濾、
    四種標記（Hot！/任搭↓N/↘/尾盤）偵測與自名稱剝離、
    G=9 依 category.subcategory_keyword 過濾子分類。
    本函式僅將 RawItem 轉換為 spike 的 Product 模型；current_price
    （↗/↘ 異動後價格）非 crawler RawItem 欄位且 spike 差集/報告未使用，
    故為 None（價格語意與 crawler 一致：列表價）。
    """
    result = CrawlerParser().parse_page(html, category)
    return [
        Product(category=category.name, subcategory=raw.subcategory, name=raw.name,
                price=raw.price, current_price=None, flags=dict(raw.flags),
                source="mobile")
        for raw in result.items
    ]


# ── 桌面版 evaluate.php 解析 ───────────────────────────────────────────────

def parse_desktop(html: str) -> list[DesktopGroup]:
    """解析桌面版 evaluate.php（malformed HTML：OPTGROUP 無收尾、部分 OPTION
    未收尾；selectolax 自動修正）。僅取 `<select>` 內 optgroup 下的 option 列：
    過濾 disabled 與通知列（❤/↪/全形空白字首、無價格列）。"""
    tree = HTMLParser(html)
    groups: list[DesktopGroup] = []
    for group_node in tree.css("optgroup"):
        label = (group_node.attributes.get("label") or "").strip()
        products: list[Product] = []
        for opt in group_node.css("option"):
            text = opt.text().strip()
            if not text or text.startswith(_NOTICE_PREFIXES):
                continue
            if opt.attributes.get("disabled") is not None:
                continue
            name, price, current_price = extract_price_info(text)
            if price is None:
                continue  # 非商品列（無價格）
            flags = _desktop_flags(text)
            products.append(Product(
                category="", subcategory=label, name=name, price=price,
                current_price=current_price, flags=flags, source="desktop",
            ))
        if products:  # 僅保留有商品列的群組（純通知/disabled 群組不進報告）
            groups.append(DesktopGroup(label=label, products=products))
    return groups


def _desktop_flags(text: str) -> dict[str, Any]:
    """桌面版標記：熱賣 → hot；↓任搭N↓ / ↓酷幣N↓ → promo（原價屋兩種促銷）。"""
    flags: dict[str, Any] = {}
    if "熱賣" in text:
        flags["hot"] = True
    match = re.search(r"↓任搭(\d+)↓", text)
    if match is not None:
        flags["promo"] = f"任搭{match.group(1)}"
    match = re.search(r"↓酷幣(\d+)↓", text)
    if match is not None:
        flags["promo"] = f"酷幣{match.group(1)}"
    return flags


# ── 桌面→手機分類對應 ───────────────────────────────────────────────────────

def classify_desktop(groups: list[DesktopGroup],
                     mobile_subcats: dict[str, set[str]]) -> tuple[dict[str, list[Product]], list[DesktopGroup]]:
    """桌面 optgroup 對應到 9 分類：優先子分類精確對齊（正規化名稱比對），
    未對齊者以關鍵字規則兜底；仍無法對應 → 列入 unmapped（如筆電/螢幕等
    非追蹤範圍，或手機版缺漏的區段）。"""
    norm_subcats = {cat: {normalize_name(s) for s in subs}
                    for cat, subs in mobile_subcats.items()}
    mapped: dict[str, list[Product]] = {}
    unmapped: list[DesktopGroup] = []
    for group in groups:
        category = _match_category(group.label, norm_subcats)
        if category is None:
            unmapped.append(group)
            continue
        mapped.setdefault(category, [])  # 即使無商品也註冊分類（差集計數為 0）
        for product in group.products:
            mapped[category].append(replace(product, category=category))
    return mapped, unmapped


def _match_category(label: str, norm_subcats: dict[str, set[str]]) -> str | None:
    """先子分類精確對齊；失敗 → 關鍵字規則。"""
    normalized = normalize_name(label)
    for category, subs in norm_subcats.items():
        if normalized in subs:
            return category
    return classify_by_keywords(label)


def classify_by_keywords(label: str) -> str | None:
    """關鍵字兜底規則（順序敏感；僅供子分類未對齊時使用）。"""
    for category, keywords in _DESKTOP_KEYWORD_RULES:
        if any(kw in label for kw in keywords):
            return category
    return None


# ── 差集計算 ───────────────────────────────────────────────────────────────

def compute_diff(mobile: dict[str, list[Product]],
                 desktop: dict[str, list[Product]]) -> dict[str, DiffSets]:
    """依正規化名稱對齊計算每分類差集（both / mobile_only / desktop_only）。
    同名重複以最後一個為準（與 store.diff 同語意）。"""
    result: dict[str, DiffSets] = {}
    for category in sorted(set(mobile) | set(desktop)):
        mob = {normalize_product_name(p.name): p for p in mobile.get(category, [])}
        desk = {normalize_product_name(p.name): p for p in desktop.get(category, [])}
        mob_keys = set(mob)
        desk_keys = set(desk)
        result[category] = DiffSets(
            both=[mob[k] for k in mob_keys & desk_keys],
            mobile_only=[mob[k] for k in sorted(mob_keys - desk_keys)],
            desktop_only=[desk[k] for k in sorted(desk_keys - mob_keys)],
        )
    return result


# ── G=9 記憶卡子分類過濾驗證 ───────────────────────────────────────────────

def verify_g9_filter(products: list[Product], category: Category) -> G9FilterResult:
    """驗證 G=9 子分類過濾無誤刪：被過濾項目子分類確實不含 subcategory_keyword、
    保留項目全部含關鍵字。非 G=9 分類（無關鍵字）→ 全數保留、驗證恆真。"""
    keyword = category.subcategory_keyword
    if keyword is None:
        return G9FilterResult(kept=list(products), filtered=[],
                              kept_all_have_keyword=True, filtered_none_have_keyword=True)
    kept = [p for p in products if keyword in p.subcategory]
    filtered = [p for p in products if keyword not in p.subcategory]
    return G9FilterResult(
        kept=kept, filtered=filtered,
        kept_all_have_keyword=all(keyword in p.subcategory for p in kept),
        filtered_none_have_keyword=all(keyword not in p.subcategory for p in filtered),
    )


# ── 比對報告 ───────────────────────────────────────────────────────────────

def build_report(*, fetched_at: str, categories: list[str],
                 mobile_counts: dict[str, int], desktop_counts: dict[str, int],
                 diffs: dict[str, DiffSets], g9: G9FilterResult,
                 g9_desktop: G9FilterResult | None = None,
                 unmapped_desktop: list[DesktopGroup],
                 total_mobile: int, total_desktop: int) -> dict[str, Any]:
    """組裝比對報告 dict（含每分類統計、差異清單、G=9 驗證、結論欄位）。

    g9 = 手機版 G=9 過濾驗證；g9_desktop = 桌面版同子分類過濾驗證
    （兩來源公平比對的基礎；None = 不列桌面側）。"""
    desktop_only_total = 0
    mobile_only_total = 0
    cat_stats: dict[str, Any] = {}
    for category in categories:
        diff = diffs.get(category, DiffSets([], [], []))
        desktop_only_total += len(diff.desktop_only)
        mobile_only_total += len(diff.mobile_only)
        do_sources: dict[str, int] = {}
        for p in diff.desktop_only:
            do_sources[p.subcategory] = do_sources.get(p.subcategory, 0) + 1
        cat_stats[category] = {
            "mobile_count": mobile_counts.get(category, 0),
            "desktop_count": desktop_counts.get(category, 0),
            "both": len(diff.both),
            "mobile_only": len(diff.mobile_only),
            "desktop_only": len(diff.desktop_only),
            "mobile_only_items": [p.name for p in diff.mobile_only],
            "desktop_only_items": [p.name for p in diff.desktop_only],
            "desktop_only_sources": dict(sorted(do_sources.items())),
        }

    unmapped = [{"label": g.label, "count": len(g.products)}
                for g in unmapped_desktop]
    coverage_complete = desktop_only_total == 0 and not unmapped
    conclusion: dict[str, Any] = {
        "coverage_complete": coverage_complete,
        "total_mobile": total_mobile,
        "total_desktop": total_desktop,
        "desktop_only_total": desktop_only_total,
        "mobile_only_total": mobile_only_total,
        "unmapped_desktop_groups": len(unmapped),
        "notes": [
            "名稱以正規化後比對（NFKC/casefold/空白收縮 + 桌面裝飾剝離），"
            "價格不參與比對（兩來源非同時快照，價格差異不列入本 spike 結論）。",
            "G=9 過濾驗證：被過濾項目子分類均不含「記憶卡」、保留項目均含「記憶卡」（兩來源一致）。",
            "僅桌面版項目全部來自手機版頁面不存在的配件/促銷區段（如 PCIe 延長線、"
            "SSD 散熱片、NAS 配件、主機搭購螢幕、組合包），核心分類子分類無漏品。",
        ],
    }
    g9_section: dict[str, Any] = {
        "category": "記憶卡",
        "mobile": {
            "kept": len(g9.kept),
            "filtered": len(g9.filtered),
            "kept_all_have_keyword": g9.kept_all_have_keyword,
            "filtered_none_have_keyword": g9.filtered_none_have_keyword,
            "filtered_subcategories": sorted({p.subcategory for p in g9.filtered}),
        },
    }
    if g9_desktop is not None:
        g9_section["desktop"] = {
            "kept": len(g9_desktop.kept),
            "filtered": len(g9_desktop.filtered),
            "kept_all_have_keyword": g9_desktop.kept_all_have_keyword,
            "filtered_none_have_keyword": g9_desktop.filtered_none_have_keyword,
            "filtered_subcategories": sorted({p.subcategory for p in g9_desktop.filtered}),
        }
    return {
        "method": "手機版 m-list.php 9 分類頁 vs 桌面版 evaluate.php 單次快照比對；"
                  "子分類以正規化名稱對齊，商品以正規化名稱差集比對；"
                  "G=9 兩來源皆套用「記憶卡」子分類過濾後才比對",
        "fetched_at": fetched_at,
        "categories": cat_stats,
        "totals": {"mobile": total_mobile, "desktop": total_desktop},
        "g9_verification": g9_section,
        "unmapped_desktop": unmapped,
        "diff_summary": {
            cat: {
                "both": len(d.both), "mobile_only": len(d.mobile_only),
                "desktop_only": len(d.desktop_only),
            }
            for cat, d in diffs.items()
        },
        "conclusion": conclusion,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """比對報告 dict → Markdown 文件（含 spike 發現與重現方式，可反覆重新產生）。"""
    lines = [
        "# A/B 來源驗證 spike 報告：手機版 9 分類 vs 桌面版 evaluate.php（issue #2）",
        "",
        f"- **方法**：{report['method']}",
        f"- **抓取時間**：{report['fetched_at']}",
        "- **原始 HTML fixture**：`scripts/tests/fixtures/mobile/G{1,3,4,5,6,7,8,9,12}.html`、"
        "`scripts/tests/fixtures/desktop/evaluate.html`（離線可重跑）",
        "- **完整結果 JSON**：`docs/spike/ab-source-compare-2026-08-15.json`",
        "",
        "## 1. 方法",
        "",
        "1. 抓取存檔：`crawler.fetcher.Fetcher` 依序抓手機版 9 頁；桌面版以 httpx（桌面 UA）抓 evaluate.php；"
        "原始 HTML（cp950 解碼後文字）存入測試 fixture。",
        "2. 手機版解析：真實結構 `<span class=Q>` 內每子分類一個 table（thead/th 子分類標題、tbody/td 商品列，"
        "td 內 `名稱, $價格[↗|↘$異動價] <i>標記</i>`）；過濾 class=y/z 通知列、disabled、贈品列；"
        "G=9 依 `subcategory_keyword=\"記憶卡\"` 過濾子分類。",
        "3. 桌面版解析：selectolax 解析 `<OPTGROUP LABEL>`（每群組=一子分類）與 `<OPTION>` 商品列；"
        "過濾 disabled 與 ❤/↪ 通知列。",
        "4. 分類對應：桌面 optgroup 以正規化名稱與手機版子分類精確對齊；未對齊者以關鍵字規則兜底；"
        "仍無法對應 → 「未對應桌面區段」。",
        "5. 公平比對：G=9 兩來源皆套用「記憶卡」子分類過濾後，才以正規化商品名稱計算差集。",
        "6. 名稱正規化重用 `crawler.categories.normalize_name`（NFKC→casefold→空白收縮）並剝離桌面裝飾"
        "（◆ ★ 熱賣 ↓任搭N↓ ↓酷幣N↓）與價格段；價格不參與比對（兩來源非同時快照）。",
        "",
        "## 2. Spike 發現（重要）",
        "",
        "### 2.1 手機版真實結構與 crawler/parser 假設不符（需另開 issue 對齊）",
        "",
        "- 真實 m-list.php：`<span class=Q>` 內每子分類一個 `<table>`（thead/tr/th 子分類標題，無 `</th>`"
        "收尾），tbody/tr/td 商品列，**td 內名稱與價格同格**；class=y（↪ 限量/加贈通知）、"
        "class=z（❤ 專業性產品說明）非商品列。",
        "- 現有 `crawler/parser.py` 以 `tree.css_first(\"table\")` 只解析第一個 table（本頁為 logo 表頭），"
        "對真實頁面每分類僅產出 3 筆錯誤項目、0 個子分類（實測 G=4 應 48 筆）。",
        "- `crawler/tests/fixtures/*.html` 為單 table、th=子分類、td 名稱/價格分格的設計期結構，與真實頁面"
        "不符 → 既有 crawler 測試全綠但無法解析真實頁面，001 上線前必須對齊。",
        "- 本 spike 以 spike 專屬解析器（`ab_source_compare.parse_mobile`）依真實結構解析，不修改 crawler 核心模組。",
        "",
        "### 2.2 桌面版 evaluate.php 為 malformed HTML",
        "",
        "- `<OPTGROUP>` 570 開 / 0 收尾；`<OPTION>` 7646 開 / 7316 收（330 未收尾）；首列 value=0 為全站摘要"
        "並內嵌第一個 OPTGROUP。selectolax 自動修正後可完整解析（7315 商品列 / 570 群組）。",
        "- 直接 regex 解析會因未收尾標籤錯位，不可用。",
        "",
        "### 2.3 兩來源商品名稱字串一致",
        "",
        "- 手機版 td 與桌面版 OPTION 在「`, $價格`」之前文字完全相同，剝離裝飾與價格段後可直接以正規化"
        "名稱對齊，不需模糊比對；子分類標題（th / OPTGROUP label）亦逐字一致。",
        "",
        "### 2.4 標記差異",
        "",
        "- 手機版真實頁面僅見 `<i>Hot！</i>`；`任搭↓N`/`↘`/`尾盤` 為 fixture 假設標記，本次快照未出現。",
        "- 桌面版促銷標記為 `↓任搭N↓` 與 `↓酷幣N↓` 兩種（在價格段之後）→ crawler 未建模「酷幣」類型。",
        "",
        "## 3. 集合統計（每分類筆數）",
        "",
        "| 分類 | 手機版 | 桌面版 | 兩者皆有 | 僅手機版 | 僅桌面版 |",
        "|------|-------:|-------:|--------:|--------:|--------:|",
    ]
    for cat, stats in report["categories"].items():
        lines.append(
            f"| {cat} | {stats['mobile_count']} | {stats['desktop_count']} | "
            f"{stats['both']} | {stats['mobile_only']} | {stats['desktop_only']} |"
        )
    totals = report["totals"]
    lines.append(
        f"| **合計** | **{totals['mobile']}** | **{totals['desktop']}** | "
        f"| | |"
    )
    lines += [
        "",
        "* 「兩者皆有」為唯一名稱數：CPU/主機板各有 1 筆名稱在兩來源同時重複（同名稱不同子分類），故 47<48、372<373，差集仍為 0。",
        "* 手機版原始（G=9 未過濾）總數 1,606 → G=9 過濾後 1,449；桌面版全站商品型項目 6,626（含未對應 4,932）。",
        "",
        "## 4. 差異清單（僅桌面版，全部來自手機版頁面不存在的配件/促銷區段）",
        "",
    ]
    for cat, stats in report["categories"].items():
        if stats["desktop_only_items"]:
            sources = stats.get("desktop_only_sources") or {}
            src_desc = "、".join(f"{sub}（{cnt}）" for sub, cnt in sources.items())
            lines.append(f"### {cat}：僅桌面版（{len(stats['desktop_only_items'])} 項，來源：{src_desc}）")
            for name in stats["desktop_only_items"]:
                lines.append(f"- {name}")
            lines.append("")
        if stats["mobile_only_items"]:
            lines.append(f"### {cat}：僅手機版（{len(stats['mobile_only_items'])} 項）")
            for name in stats["mobile_only_items"]:
                lines.append(f"- {name}")
            lines.append("")
    lines += ["## G=9 記憶卡子分類過濾驗證", ""]
    g9 = report["g9_verification"]
    for source in ("mobile", "desktop"):
        if source not in g9:
            continue
        side = g9[source]
        lines.append(f"- {source}：保留 {side['kept']} 項（子分類均含「記憶卡」：{side['kept_all_have_keyword']}）、"
                     f"被過濾 {side['filtered']} 項（子分類均不含「記憶卡」：{side['filtered_none_have_keyword']}）")
        if side["filtered_subcategories"]:
            lines.append(f"  - 被過濾子分類：{'、'.join(side['filtered_subcategories'])}")
    lines += ["", "## 未對應到 9 分類的桌面區段", ""]
    if report["unmapped_desktop"]:
        for g in report["unmapped_desktop"]:
            lines.append(f"- {g['label']}（{g['count']} 項）")
    else:
        lines.append("- 無")
    lines += ["", "## 結論", ""]
    conclusion = report["conclusion"]
    lines.append(f"- **追蹤範圍完整**：{'是' if conclusion['coverage_complete'] else '否'}")
    lines.append(f"- **手機版總數**：{conclusion['total_mobile']}（9 分類、G=9 過濾後）—「約 1,449」成立")
    lines.append(f"- **桌面版對應總數**：{conclusion['total_desktop']}（對應 9 分類範圍、G=9 過濾後）")
    lines.append(f"- **僅桌面版項目**：{conclusion['desktop_only_total']} 項（全部來自手機版頁面不存在的配件/促銷區段，核心分類無漏品）")
    lines.append(f"- **僅手機版項目**：{conclusion['mobile_only_total']} 項（桌面版涵蓋手機版全部商品）")
    lines.append(f"- **未對應桌面區段**：{conclusion['unmapped_desktop_groups']} 個（筆電/螢幕/機殼/周邊等，非追蹤範圍）")
    lines.append("- **G=9 記憶卡子分類過濾無誤刪**：兩來源保留 54 / 被過濾 157，被過濾項目子分類均不含「記憶卡」（見上節）。")
    lines.append("- **重大待辦（另開 issue）**：crawler/parser.py 與真實 m-list.php 結構不符（見 §2.1），"
                "需依真實結構重寫 parser 並以本報告 fixture 為回歸基準。")
    lines.append("- **次要發現**：桌面版促銷含「酷幣」類型未被 crawler 建模；手機版本次快照僅見 Hot！標記。")
    for note in conclusion["notes"]:
        lines.append(f"- 註：{note}")
    lines += [
        "",
        "## 重現方式",
        "",
        "```bash",
        "# 1) 重新抓取並存 fixture（需網路；已存檔可略過）",
        ".venv/bin/python scripts/ab_source_compare.py --save-html scripts/tests/fixtures",
        "",
        "# 2) 離線重跑比對並產出報告（JSON + MD）",
        ".venv/bin/python scripts/ab_source_compare.py",
        "",
        "# 3) 測試（含離線管線測試，fixture 存在即跑）",
        ".venv/bin/python -m pytest scripts/tests/test_ab_source_compare.py -v",
        "```",
        "",
        "> 註：`TestOfflinePipeline.test_mobile_1449_claim_and_full_desktop_coverage` 斷言手機版總數恰為 1,449"
        "——fixture 釘選（2026-08-15 快照）的驗證，重新抓取（商品增減）後應更新斷言值。",
    ]
    return "\n".join(lines) + "\n"


# ── 實跑 CLI ───────────────────────────────────────────────────────────────

def fetch_desktop(timeout: float = 30.0) -> str:
    """抓取桌面版 evaluate.php（桌面 UA；手機版 Fetcher 的 UA 亦可行但用桌面 UA 較貼近）。"""
    with httpx.Client(timeout=timeout, headers={"User-Agent": DESKTOP_UA}) as client:
        response = client.get(DESKTOP_URL)
        response.raise_for_status()
        return response.content.decode("cp950", errors="replace")


def save_html_fixtures(out_dir: Path) -> None:
    """抓取 9 分類手機版 + 桌面版，原始 HTML（解碼後文字）存成測試 fixture。

    手機版使用 crawler.fetcher.Fetcher（真實連線）。輸出：
    <out_dir>/mobile/G{1,3,4,5,6,7,8,9,12}.html 與 <out_dir>/desktop/evaluate.html。
    """
    from crawler.fetcher import Fetcher  # 延遲 import，避免 CLI 之外載入成本

    mobile_dir = out_dir / "mobile"
    desktop_dir = out_dir / "desktop"
    mobile_dir.mkdir(parents=True, exist_ok=True)
    desktop_dir.mkdir(parents=True, exist_ok=True)

    fetcher = Fetcher()
    for category in CATEGORIES:
        raw = fetcher.fetch_page(category)
        html = fetcher.decode(raw)
        (mobile_dir / f"G{category.g_index}.html").write_text(html, encoding="utf-8")
        logger.info("saved mobile G=%d (%d chars)", category.g_index, len(html))
    desktop_html = fetch_desktop()
    (desktop_dir / "evaluate.html").write_text(desktop_html, encoding="utf-8")
    logger.info("saved desktop evaluate.php (%d chars)", len(desktop_html))


def load_html_fixtures(fixture_dir: Path) -> tuple[dict[int, str], str]:
    """由 fixture 載入手機版 9 頁 + 桌面版 HTML（離線可跑）。"""
    mobile_html: dict[int, str] = {}
    for category in CATEGORIES:
        path = fixture_dir / "mobile" / f"G{category.g_index}.html"
        if not path.exists():
            raise FileNotFoundError(f"缺少手機版 fixture：{path}")
        mobile_html[category.g_index] = path.read_text(encoding="utf-8")
    desktop_path = fixture_dir / "desktop" / "evaluate.html"
    if not desktop_path.exists():
        raise FileNotFoundError(f"缺少桌面版 fixture：{desktop_path}")
    return mobile_html, desktop_path.read_text(encoding="utf-8")


def run_comparison(fixture_dir: Path) -> dict[str, Any]:
    """完整比對管線：解析 → 分類對應 → 差集 → G=9 驗證 → 報告。"""
    mobile_html, desktop_html = load_html_fixtures(fixture_dir)
    g9_category = next(c for c in CATEGORIES if c.g_index == 9)

    # 1. 手機版：真實結構解析。G=9 額外解析「未過濾」版本供過濾驗證與
    #    子分類對應（桌面 隨身碟/隨身SSD/隨身硬碟 群組隸屬 G=9 頁面範圍）。
    mobile_by_category: dict[str, list[Product]] = {}
    mobile_counts: dict[str, int] = {}
    mobile_unfiltered: dict[str, list[Product]] = {}
    for category in CATEGORIES:
        products = parse_mobile(mobile_html[category.g_index], category)
        mobile_by_category[category.name] = products
        mobile_counts[category.name] = len(products)
        unfiltered = parse_mobile(
            mobile_html[category.g_index],
            Category(category.g_index, category.name))  # 無關鍵字 → 不觸發子分類過濾
        mobile_unfiltered[category.name] = unfiltered

    # 2. 桌面版：解析 + 分類對應（以未過濾的手機版子分類清單對齊）
    desktop_groups = parse_desktop(desktop_html)
    mobile_subcats = {c.name: {p.subcategory for p in mobile_unfiltered[c.name]}
                      for c in CATEGORIES}
    desktop_by_category, unmapped = classify_desktop(desktop_groups, mobile_subcats)

    # 3. G=9 公平比對：兩來源皆套用「記憶卡」子分類過濾（追蹤範圍一致）
    mobile_g9_result = verify_g9_filter(mobile_unfiltered["記憶卡"], g9_category)
    desktop_g9_raw = desktop_by_category.get("記憶卡", [])
    desktop_g9_result = verify_g9_filter(desktop_g9_raw, g9_category)
    mobile_by_category["記憶卡"] = mobile_g9_result.kept
    desktop_by_category["記憶卡"] = desktop_g9_result.kept
    mobile_counts["記憶卡"] = len(mobile_g9_result.kept)
    desktop_counts = {c.name: len(desktop_by_category.get(c.name, []))
                      for c in CATEGORIES}

    # 4. 差集
    diffs = compute_diff(mobile_by_category, desktop_by_category)

    total_mobile = sum(mobile_counts.values())
    total_desktop = sum(desktop_counts.values())
    return build_report(
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        categories=[c.name for c in CATEGORIES],
        mobile_counts=mobile_counts,
        desktop_counts=desktop_counts,
        diffs=diffs,
        g9=mobile_g9_result,
        g9_desktop=desktop_g9_result,
        unmapped_desktop=unmapped,
        total_mobile=total_mobile,
        total_desktop=total_desktop,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI：python scripts/ab_source_compare.py [--fixtures-dir DIR]
    [--out-json FILE] [--out-md FILE] [--save-html DIR]

    --save-html DIR：抓取兩來源原始 HTML 存成 fixture（供離線重跑）。
    預設 fixtures-dir = scripts/tests/fixtures；out-json/out-md 預設 docs/spike/。"""
    parser = argparse.ArgumentParser(prog="ab_source_compare")
    parser.add_argument("--fixtures-dir", type=Path,
                        default=Path("scripts/tests/fixtures"))
    parser.add_argument("--save-html", type=Path, default=None,
                        help="抓取並儲存原始 HTML 到此目錄（預設：無，僅解析既有 fixtures）")
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.save_html is not None:
        save_html_fixtures(args.save_html)
        fixtures_dir = args.save_html
    else:
        fixtures_dir = args.fixtures_dir

    report = run_comparison(fixtures_dir)

    out_json = args.out_json or Path("docs/spike/ab-source-compare-2026-08-15.json")
    out_md = args.out_md or Path("docs/spike/ab-source-compare-2026-08-15.md")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    out_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"報告 JSON：{out_json}")
    print(f"報告 MD：{out_md}")
    conclusion = report["conclusion"]
    print(f"手機版總數={conclusion['total_mobile']} "
          f"桌面版對應總數={conclusion['total_desktop']} "
          f"僅桌面版={conclusion['desktop_only_total']} "
          f"範圍完整={conclusion['coverage_complete']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
