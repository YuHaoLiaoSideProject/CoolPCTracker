"""商品名 → 結構化規格。深度：CPU/顯示卡/記憶體/SSD/HDD/主機板；輕量：記憶卡/套裝/劈發價。

純字串解析、無網路依賴（BDD #11「規格解析依分類深度或輕量」Outline 9 例）。

設計決策：
- brand/model 為 Spec 通用欄位；深度分類的結構化欄位一律置於 extra dict（依分類不同）。
- 深度解析以「品牌 token 比對」為錨點：品牌無法辨識 → 回傳最少欄位 Spec
  （brand=None, model=None）。不得因單一欄位缺失而丟棄商品（規格 §1.6）。
- 深度分類容量統一為整數 GB（capacity_gb，1TB = 1024）；輕量分類保留原始字串
  token（記憶卡 capacity = "128GB"）。
- 未知分類回傳空 Spec；任何解析例外由 parse_spec 捕捉 → 最少欄位 Spec，不中斷管道。
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Spec:
    """結構化規格（依分類僅填充相關欄位，其餘缺省）。"""

    brand: str | None = None
    model: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # 深度分類結構化欄位


# ── 共用小工具 ──────────────────────────────────────────────────────────


def _match_brand(name: str, brands: tuple[str, ...]) -> str | None:
    """比對名稱開頭的品牌 token。

    - 依 token 長度由長到短比對（避免 A 誤配 ASUS 等前綴）。
    - ASCII 品牌要求後接非字母數字（避免 "WD" 誤配 "WD_BLACK" 之類長 token；
      該情境應由長 token 先命中，此處為雙保險）。
    - 中文品牌精確前綴比對（「華碩ROG」無空白亦可命中）。
    """
    upper = name.upper()
    for b in sorted(brands, key=len, reverse=True):
        if upper.startswith(b.upper()):
            if b.isascii():
                tail = upper[len(b):]
                if tail and tail[0].isalnum():
                    continue
            return b
    return None


def _strip_brand(name: str, brands: tuple[str, ...]) -> tuple[str, str | None]:
    """回傳 (剝離品牌前綴後的剩餘名稱, 品牌)。品牌未命中 → (原名稱, None)。"""
    brand = _match_brand(name, brands)
    if brand is None:
        return name.strip(), None
    return name[len(brand):].strip(), brand


def _trim_suffix(text: str, suffixes: tuple[str, ...]) -> str:
    """反覆剝離尾端關鍵字（如「主機板」「桌上型記憶體」），直到無可剝離。"""
    t = text.strip()
    for s in sorted(suffixes, key=len, reverse=True):
        while t.endswith(s):
            t = t[: -len(s)].strip()
    return t


def _capacity_gb(name: str) -> int | None:
    """容量 → 整數 GB（1TB = 1024、2TB = 2048、500GB = 500）。取首個 TB/GB 出現處。"""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB)\b", name, re.IGNORECASE)
    if not m:
        return None
    num = float(m.group(1))
    return int(num * 1024) if m.group(2).upper() == "TB" else int(num)


# ── CPU 深度 ─────────────────────────────────────────────────────────────
# 例：Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】
#     AMD R7 7800X3D【8核/16緒】4.2G(↑5.0G)/96M/120W
_CPU_BRANDS: tuple[str, ...] = ("Intel", "AMD")

_RE_CORES_THREADS = re.compile(r"【\s*(\d+)\s*核\s*/\s*(\d+)\s*緒\s*】")  # 【14核/20緒】
# 基礎時脈：3.5GHz 或 4.2G；取第一個命中（基礎時脈先於增壓時脈出現）。
# 限定「小數 + G」或「整數 + GHz」兩形，避免型號尾綴誤配
# （如 AMD 5600G/5500GT 的 "5600G" 不得被讀成 5600GHz 時脈）。
_RE_BASE_GHZ = re.compile(
    r"(\d+(?:\.\d+)?)\s*GHz|(\d+\.\d+)\s*G",
    re.IGNORECASE,
)
_RE_TURBO_GHZ = re.compile(r"[↑⬆]\s*(\d+(?:\.\d+)?)\s*G(?:Hz)?", re.IGNORECASE)  # (↑5.1G)
_RE_TDP_W = re.compile(r"(\d+)\s*W(?!\w)", re.IGNORECASE)  # /125W（GHz 內無裸 W，不誤配）
_RE_SOCKET = re.compile(r"\b(LGA\s*\d+|AM\d+)\b", re.IGNORECASE)  # LGA1700 / AM5（CPU/主機板共用）


def _parse_cpu(name: str) -> Spec:
    rest, brand = _strip_brand(name, _CPU_BRANDS)
    if brand is None:  # 品牌無法辨識 → 最少欄位，不丟商品
        return Spec()
    extra: dict[str, Any] = {}
    m = _RE_CORES_THREADS.search(name)
    if m:
        extra["cores"] = int(m.group(1))
        extra["threads"] = int(m.group(2))
    m = _RE_BASE_GHZ.search(name)
    if m:
        # 兩個分支只會命中其一（整數+GHz 或 小數+G），取非 None 者
        value = m.group(1) if m.group(1) is not None else m.group(2)
        extra["base_ghz"] = float(value)
    m = _RE_TURBO_GHZ.search(name)
    if m:
        extra["turbo_ghz"] = float(m.group(1))
    m = _RE_TDP_W.search(name)
    if m:
        extra["tdp_w"] = int(m.group(1))
    m = _RE_SOCKET.search(name)
    if m:
        extra["socket"] = re.sub(r"\s+", "", m.group(1)).upper()
    model = rest.split("【", 1)[0].strip() or None  # 品牌後、【 前的 token 即型號
    return Spec(brand=brand, model=model, extra=extra)


# ── 顯示卡深度 ───────────────────────────────────────────────────────────
# 例：MSI RTX 4060 VENTUS 2X 8G OC
_GPU_BRANDS: tuple[str, ...] = (
    "MSI", "微星", "ASUS", "華碩", "Gigabyte", "技嘉", "ZOTAC", "索泰",
    "EVGA", "PNY", "Colorful", "七彩虹", "INNO3D", "映眾", "GALAX", "影馳",
    "PALIT", "耕宇", "Leadtek", "麗臺", "Sapphire", "藍寶", "PowerColor",
    "撼訊", "XFX", "ASRock", "華擎", "NVIDIA", "AMD", "Intel",
)
# 晶片：RTX 4060 / GTX 1650 / RX 6600 XT / RTX 4070 SUPER / Arc A770
_GPU_CHIP_RE = re.compile(
    r"\b(RTX\s*PRO|RADEON|RTX|GTX|RX|ARC)\s*(\d{3,4}\w*(?:\s*(?:Ti|Super|XT))?)\b"
    r"|\bARC\s*A\s*(\d{3})\b",
    re.IGNORECASE,
)
_GPU_VRAM_RE = re.compile(r"\b(\d{1,3})\s*G\s*B?\b", re.IGNORECASE)  # 8G / 12GB
_GPU_IFACE_RE = re.compile(r"PCIe\s*[\d.]+", re.IGNORECASE)  # PCIe 4.0
_GPU_LENGTH_RE = re.compile(r"\b(\d{3})\s*mm\b", re.IGNORECASE)  # 322mm


def _parse_gpu(name: str) -> Spec:
    rest, brand = _strip_brand(name, _GPU_BRANDS)
    if brand is None:
        return Spec()
    extra: dict[str, Any] = {}
    m = _GPU_CHIP_RE.search(rest)
    if m:
        if m.group(3):  # Intel Arc A770 形式（ARC 後接 A + 數字）
            extra["chip"] = f"Arc A{m.group(3)}"
        else:
            extra["chip"] = f"{m.group(1).upper()} {m.group(2)}".strip()
    m = _GPU_VRAM_RE.search(rest)
    if m:
        extra["vram_gb"] = int(m.group(1))
    m = _GPU_IFACE_RE.search(rest)
    if m:
        extra["interface"] = m.group(0)
    m = _GPU_LENGTH_RE.search(rest)
    if m:
        extra["length_mm"] = int(m.group(1))
    return Spec(brand=brand, model=rest, extra=extra)


# ── 記憶體深度 ───────────────────────────────────────────────────────────
# 例：美光 Crucial DDR5-5600 16GB(8G*2) 桌上型記憶體
_RAM_BRANDS: tuple[str, ...] = (
    "美光", "Crucial", "Micron", "金士頓", "Kingston", "威剛", "ADATA",
    "芝奇", "G.SKILL", "十銓", "TEAM", "海盜船", "CORSAIR", "Patriot",
    "博帝", "創見", "Transcend", "廣穎", "宇瞻", "Apacer", "KLEVV",
    "科賦", "PNY", "Samsung", "三星", "UMAX", "凌航", "T-FORCE",
)
_RE_RAM_SPEC = re.compile(r"\b(DDR[0-9])\b", re.IGNORECASE)  # DDR5 / DDR4
_RE_RAM_CLOCK = re.compile(r"\bDDR[0-9]\s*[-/]?\s*(\d+)\b", re.IGNORECASE)  # DDR5-5600 → 5600
_RE_RAM_GB_MULT = re.compile(r"(\d+)\s*GB\s*[*×x]\s*(\d+)\b", re.IGNORECASE)  # 8GB*2 → 16
_RE_RAM_GB = re.compile(r"(\d+)\s*GB\b", re.IGNORECASE)  # 16GB（優先）
_RE_RAM_G = re.compile(r"(\d+)\s*G(?:\s*\*\s*(\d+))?\b", re.IGNORECASE)  # 16G / 8G*2


def _ram_capacity_gb(name: str) -> int | None:
    """容量：優先取乘式（8GB*2 → 16）、次取 N GB（16GB(8G*2) → 16）、
    無則取 N G 含乘式（8G*2 → 16）。"""
    m = _RE_RAM_GB_MULT.search(name)
    if m:
        return int(m.group(1)) * int(m.group(2))
    m = _RE_RAM_GB.search(name)
    if m:
        return int(m.group(1))
    m = _RE_RAM_G.search(name)
    if m:
        base = int(m.group(1))
        return base * int(m.group(2)) if m.group(2) else base
    return None


def _parse_ram(name: str) -> Spec:
    rest, brand = _strip_brand(name, _RAM_BRANDS)
    if brand is None:
        return Spec()
    extra: dict[str, Any] = {}
    cap = _ram_capacity_gb(rest)
    if cap is not None:
        extra["capacity_gb"] = cap
    m = _RE_RAM_SPEC.search(rest)
    if m:
        extra["spec"] = m.group(1).upper()
    m = _RE_RAM_CLOCK.search(rest)
    if m:
        extra["clock_mhz"] = int(m.group(1))
    model = _trim_suffix(rest, ("桌上型記憶體", "筆記型記憶體", "記憶體", "桌上型", "筆記型"))
    return Spec(brand=brand, model=model or None, extra=extra)


# ── SSD 深度 ─────────────────────────────────────────────────────────────
# 例：WD 藍標 SN580 1TB M.2 PCIe 4.0 SSD
_SSD_BRANDS: tuple[str, ...] = (
    "WD", "Western Digital", "威騰", "Samsung", "三星", "Kingston", "金士頓",
    "Crucial", "美光", "ADATA", "威剛", "Intel", "KIOXIA", "鎧俠", "Toshiba",
    "東芝", "Seagate", "希捷", "Transcend", "創見", "Patriot", "博帝", "PNY",
    "TEAM", "十銓", "Gigabyte", "技嘉", "MSI", "微星", "SanDisk", "晟碟",
    "Silicon Power", "廣穎", "LiteOn", "Plextor", "Corsair", "海盜船",
)


def _ssd_interface(name: str) -> str | None:
    """介面：M.2 / U.2 / mSATA / SATA（mSATA 先於 SATA 比對，避免子字串誤判）。"""
    upper = name.upper()
    for token in ("M.2", "U.2", "mSATA", "SATA"):
        if token.upper() in upper:
            return token
    return None


def _ssd_format(name: str) -> str | None:
    """規格：NVMe（明示 NVMe 或由 PCIe 推論）；SATA；兩者皆無 → None。"""
    upper = name.upper()
    if "NVME" in upper or "PCIE" in upper:
        return "NVMe"
    if "SATA" in upper:
        return "SATA"
    return None


def _parse_ssd(name: str) -> Spec:
    rest, brand = _strip_brand(name, _SSD_BRANDS)
    if brand is None:
        return Spec()
    extra: dict[str, Any] = {}
    cap = _capacity_gb(rest)
    if cap is not None:
        extra["capacity_gb"] = cap
    iface = _ssd_interface(rest)
    if iface:
        extra["interface"] = iface
    fmt = _ssd_format(rest)
    if fmt:
        extra["format"] = fmt
    model = _trim_suffix(rest, ("M.2 PCIe 4.0 SSD", "M.2 SSD", "SSD", "固態硬碟"))
    return Spec(brand=brand, model=model or None, extra=extra)


# ── HDD 深度 ─────────────────────────────────────────────────────────────
# 例：Seagate 新梭魚 2TB 256M/7200轉/3年保
_HDD_BRANDS: tuple[str, ...] = (
    "Seagate", "希捷", "WD", "Western Digital", "威騰", "Toshiba", "東芝",
    "HGST", "日立", "Hitachi", "Samsung", "三星",
)
_RE_RPM = re.compile(r"(\d+)\s*(?:轉|RPM)\b", re.IGNORECASE)  # 7200轉 / 5400RPM


def _hdd_interface(name: str) -> str | None:
    """介面：SAS / SATA / USB；名稱未含 → None。"""
    upper = name.upper()
    if re.search(r"\bSAS\b", upper):
        return "SAS"
    if re.search(r"\bSATA\b", upper):
        return "SATA"
    if re.search(r"\bUSB\b", upper):
        return "USB"
    return None


def _parse_hdd(name: str) -> Spec:
    rest, brand = _strip_brand(name, _HDD_BRANDS)
    if brand is None:
        return Spec()
    extra: dict[str, Any] = {}
    cap = _capacity_gb(rest)
    if cap is not None:
        extra["capacity_gb"] = cap
    m = _RE_RPM.search(rest)
    if m:
        extra["rpm"] = int(m.group(1))
    iface = _hdd_interface(rest)
    if iface:
        extra["interface"] = iface
    model = _trim_suffix(rest, ("3年保", "2年保", "5年保", "企業級", "NAS", "桌上型", "內接"))
    return Spec(brand=brand, model=model or None, extra=extra)


# ── 主機板深度 ───────────────────────────────────────────────────────────
# 例：技嘉 B760M GAMING X AX DDR4 主機板
_MOBO_BRANDS: tuple[str, ...] = (
    "技嘉", "Gigabyte", "華碩", "ASUS", "微星", "MSI", "華擎", "ASRock",
    "映泰", "Biostar", "七彩虹", "Colorful", "銘瑄", "Maxsun", "精英", "ECS",
)
# 晶片組：B760 / Z790 / X670 / H610 / A620（型號尾綴 M/I 不計入）
_RE_CHIPSET = re.compile(r"\b([BZHXAI]\d{3})[A-Z]{0,2}\b")


def _mobo_form_factor(name: str, chipset: str | None) -> str | None:
    """尺寸：明確字樣優先（E-ATX / M-ATX / ATX / Mini-ITX）；
    晶片組代號尾綴 M（如 B760M）判為微板 M-ATX；皆無 → None。"""
    upper = name.upper()
    if re.search(r"\bE-ATX\b", upper):
        return "E-ATX"
    if re.search(r"\bM(?:ICRO|INI)?-?ATX\b", upper):  # M-ATX / MATX / Micro-ATX / Mini-ATX
        return "M-ATX"
    if re.search(r"\bATX\b", upper):
        return "ATX"
    if re.search(r"\bITX\b", upper):
        return "Mini-ITX"
    if chipset and re.search(r"\dM\b", upper):  # B760M / H610M → 微板
        return "M-ATX"
    return None


def _parse_mobo(name: str) -> Spec:
    rest, brand = _strip_brand(name, _MOBO_BRANDS)
    if brand is None:
        return Spec()
    extra: dict[str, Any] = {}
    m = _RE_CHIPSET.search(rest)
    if m:
        extra["chipset"] = m.group(1).upper()
    m = _RE_SOCKET.search(rest)
    if m:
        extra["socket"] = re.sub(r"\s+", "", m.group(1)).upper()
    ff = _mobo_form_factor(rest, extra.get("chipset"))
    if ff:
        extra["form_factor"] = ff
    model = _trim_suffix(rest, ("主機板",))
    return Spec(brand=brand, model=model or None, extra=extra)


# ── 記憶卡（輕量）────────────────────────────────────────────────────────
# 例：SanDisk 128GB MicroSDXC U3 A2 記憶卡
_CARD_BRANDS: tuple[str, ...] = (
    "SanDisk", "晟碟", "Kingston", "金士頓", "ADATA", "威剛", "Samsung",
    "三星", "Lexar", "雷克沙", "TEAM", "十銓", "Transcend", "創見",
    "Silicon Power", "廣穎", "PNY", "Patriot", "博帝", "Corsair", "海盜船",
)
_CARD_SPEC_CANON: tuple[tuple[str, str], ...] = (  # (比對關鍵字, 正規化輸出)；長者先比
    ("MICROSDXC", "MicroSDXC"), ("MICROSDHC", "MicroSDHC"), ("CFEXPRESS", "CFexpress"),
    ("SDXC", "SDXC"), ("SDHC", "SDHC"), ("MICROSD", "MicroSD"), ("SD", "SD"), ("CF", "CF"),
)
_RE_CARD_CAPACITY = re.compile(r"\b(\d+\s*(?:TB|GB|MB))\b", re.IGNORECASE)


def _card_spec(name: str) -> str | None:
    """卡規格（Micro SD / SD / CFexpress 等），回傳正規化名稱。"""
    upper = name.upper()
    for key, canon in _CARD_SPEC_CANON:  # 依序比對：MICROSDXC 先於 SD
        if re.search(rf"\b{key}\b", upper):
            return canon
    return None


def _parse_memory_card(name: str) -> Spec:
    rest, brand = _strip_brand(name, _CARD_BRANDS)
    if brand is None:
        return Spec()
    extra: dict[str, Any] = {}
    m = _RE_CARD_CAPACITY.search(rest)
    if m:
        # 輕量分類保留原始字串 token（與深度分類 capacity_gb 型別不同，屬刻意決策）
        extra["capacity"] = re.sub(r"\s+", "", m.group(1)).upper()
    spec = _card_spec(rest)
    if spec:
        extra["spec"] = spec
    model = _trim_suffix(rest, ("記憶卡", "記憶卡組", "高速卡"))
    return Spec(brand=brand, model=model or None, extra=extra)


# ── 套裝/準系統（輕量）───────────────────────────────────────────────────
# 例：華碩 ROG G22CH 電競主機
_PREBUILT_BRANDS: tuple[str, ...] = (
    "華碩", "ASUS", "微星", "MSI", "技嘉", "Gigabyte", "宏碁", "Acer",
    "聯想", "Lenovo", "戴爾", "Dell", "HP", "惠普", "華擎", "ASRock",
    "曜越", "Thermaltake", "君主", "Montech", "迎廣", "InWin", "Corsair",
    "海盜船", "Razer", "雷蛇", "Apple", "蘋果",
)
_PREBUILT_USAGE: dict[str, str] = {  # 名稱關鍵字 → 用途摘要
    "創作者": "創作者主機",
    "工作站": "工作站主機",
    "電競": "電競主機",
    "文書": "文書主機",
    "商務": "商務主機",
    "商用": "商用主機",
    "家用": "家用主機",
    "家庭": "家用主機",
    "影音": "影音主機",
}
# 長關鍵字先比對（「創作者」優於其子字串），模組載入時排序一次即可
_PREBUILT_USAGE_ORDERED: tuple[tuple[str, str], ...] = tuple(
    sorted(_PREBUILT_USAGE.items(), key=lambda kv: len(kv[0]), reverse=True)
)


def _parse_prebuilt(name: str) -> Spec:
    rest, brand = _strip_brand(name, _PREBUILT_BRANDS)
    if brand is None:
        return Spec()
    usage: str | None = None
    model = rest
    for kw, label in _PREBUILT_USAGE_ORDERED:
        if kw in rest:
            usage = label
            model = rest.split(kw, 1)[0].strip()  # 用途關鍵字前的文字即型號
            break
    if usage is None:
        model = _trim_suffix(rest, ("準系統", "桌上型", "電競主機", "主機", "電腦"))
    extra: dict[str, Any] = {"usage": usage} if usage else {}
    return Spec(brand=brand, model=model or None, extra=extra)


# ── 劈發價組合區（輕量）──────────────────────────────────────────────────
# 例：【劈發價】i5-13600K + B760 主機板組合
_BUNDLE_BRANDS: tuple[str, ...] = _PREBUILT_BRANDS + ("Intel", "AMD")
_RE_BUNDLE_TAG = re.compile(r"^【[^】]*】\s*")  # 開頭標籤：【劈發價】【任搭】…


def _parse_bundle(name: str) -> Spec:
    """組合名稱 = 剝離開頭標籤後的文字；brand 多數不存在（依名稱可選解析）。"""
    stripped = _RE_BUNDLE_TAG.sub("", name).strip()
    if not stripped:  # 只剩標籤的極端輸入 → 最少欄位
        return Spec()
    brand = _match_brand(stripped, _BUNDLE_BRANDS)
    model = stripped[len(brand):].strip() if brand else stripped
    return Spec(brand=brand, model=model, extra={"summary": stripped})


# ── 派發註冊表 ───────────────────────────────────────────────────────────

# 深度解析器：主分類名 → 解析函數（正規表示式/關鍵字比對商品名）
_DEEP_PARSERS: dict[str, Callable[[str], Spec]] = {
    "CPU": _parse_cpu,        # cores/threads/base_ghz/turbo_ghz/tdp_w/socket
    "顯示卡": _parse_gpu,     # chip/vram_gb/interface/length_mm
    "記憶體": _parse_ram,     # capacity_gb/spec/clock_mhz
    "SSD": _parse_ssd,        # capacity_gb/interface/format
    "HDD": _parse_hdd,        # capacity_gb/rpm/interface
    "主機板": _parse_mobo,    # chipset/socket/form_factor
}
# 輕量解析器：僅品牌/型號 + 內容摘要
_LIGHT_PARSERS: dict[str, Callable[[str], Spec]] = {
    "記憶卡": _parse_memory_card,   # brand/capacity/spec
    "套裝/準系統": _parse_prebuilt,  # brand/model/usage
    "劈發價組合區": _parse_bundle,   # model/summary
}
_PARSERS: dict[str, Callable[[str], Spec]] = {**_DEEP_PARSERS, **_LIGHT_PARSERS}


def parse_spec(category: str, name: str) -> Spec:
    """依主分類派發：深度分類走 _DEEP_PARSERS、輕量分類走 _LIGHT_PARSERS；
    未知分類回傳空 Spec；任何解析例外 → 回傳最少欄位 Spec，不中斷管道（BDD #11）。"""
    parser = _PARSERS.get(category)
    if parser is None:
        return Spec()
    try:
        return parser(name or "")
    except Exception:  # noqa: BLE001 — 單一商品解析失敗絕不中斷整個爬蟲管道
        return Spec()
