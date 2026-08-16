"""spec_parser.py 單元測試（BDD #11 規格解析依分類深度或輕量 Outline 9 例 + 容錯）。

覆蓋：
- 深度解析：CPU（Intel/AMD 兩例）、顯示卡、記憶體、SSD、HDD、主機板
- 輕量解析：記憶卡、套裝/準系統、劈發價組合區
- 容錯：無法解析的名稱回傳最少欄位 Spec（brand/model=None）不拋例外、
  未知分類回傳空 Spec、partial 解析不丟商品
- 範圍：Spec.extra 僅含該分類相關欄位（如 CPU 無 vram_gb / capacity_gb）
"""
from __future__ import annotations

import pytest

from crawler.spec_parser import Spec, parse_spec


# ── CPU 深度 ─────────────────────────────────────────────────────────────

class TestCpuDeepParse:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            # 例 1（規格 §4.3 / BDD Background 同款名稱）
            (
                "Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】",
                dict(
                    brand="Intel", model="i5-13600K",
                    cores=14, threads=20, base_ghz=3.5, turbo_ghz=5.1, tdp_w=125,
                ),
            ),
            # 例 2：AMD 例（時脈以「4.2G」無 Hz 表示）
            (
                "AMD R7 7800X3D【8核/16緒】4.2G(↑5.0G)/96M/120W",
                dict(
                    brand="AMD", model="R7 7800X3D",
                    cores=8, threads=16, base_ghz=4.2, turbo_ghz=5.0, tdp_w=120,
                ),
            ),
        ],
    )
    def test_deep_parse(self, name: str, expected: dict) -> None:
        spec = parse_spec("CPU", name)
        assert isinstance(spec, Spec)
        assert spec.brand == expected["brand"]
        assert spec.model == expected["model"]
        assert spec.extra["cores"] == expected["cores"]
        assert spec.extra["threads"] == expected["threads"]
        assert spec.extra["base_ghz"] == expected["base_ghz"]
        assert spec.extra["turbo_ghz"] == expected["turbo_ghz"]
        assert spec.extra["tdp_w"] == expected["tdp_w"]

    def test_socket_absent_in_name_is_none(self) -> None:
        # 名稱未含 LGA/AM5 等腳位字樣 → socket 欄位缺省（可為 None）
        spec = parse_spec("CPU", "AMD R7 7800X3D【8核/16緒】4.2G(↑5.0G)/96M/120W")
        assert spec.extra.get("socket") is None

    def test_partial_fields_not_dropped(self) -> None:
        # 名稱僅含品牌/型號時仍產出可解析欄位，不丟商品
        spec = parse_spec("CPU", "Intel i5-13600K")
        assert spec.brand == "Intel"
        assert spec.model == "i5-13600K"
        assert spec.extra == {}

    def test_apu_model_g_suffix_not_parsed_as_clock(self) -> None:
        # AMD 5600G/5500GT 等型號尾綴 G/GT 不得誤判為時脈（5600 ≠ 3.9GHz）
        spec = parse_spec("CPU", "AMD R5 5600G【6核/12緒】3.9G(↑4.4G)/65W")
        assert spec.brand == "AMD"
        assert spec.model == "R5 5600G"
        assert spec.extra["base_ghz"] == 3.9
        assert spec.extra["turbo_ghz"] == 4.4
        assert spec.extra["tdp_w"] == 65
        assert spec.extra["cores"] == 6
        assert spec.extra["threads"] == 12

    def test_apu_gt_suffix_not_parsed_as_clock(self) -> None:
        spec = parse_spec("CPU", "AMD R5 5500GT【6核/12緒】3.6G(↑4.2G)/65W")
        assert spec.extra["base_ghz"] == 3.6
        assert spec.extra["turbo_ghz"] == 4.2


# ── 顯示卡深度 ───────────────────────────────────────────────────────────

class TestGpuDeepParse:
    def test_msi_rtx4060(self) -> None:
        spec = parse_spec("顯示卡", "MSI RTX 4060 VENTUS 2X 8G OC")
        assert spec.brand == "MSI"
        assert spec.extra["chip"] == "RTX 4060"
        assert spec.extra["vram_gb"] == 8
        # 名稱未含介面/長度字樣 → None
        assert spec.extra.get("interface") is None
        assert spec.extra.get("length_mm") is None

    def test_no_vram_in_name(self) -> None:
        spec = parse_spec("顯示卡", "ASUS RX 6600 DUAL 顯示卡")
        assert spec.brand == "ASUS"
        assert spec.extra["chip"] == "RX 6600"
        assert spec.extra.get("vram_gb") is None

    def test_intel_arc_a770_chip(self) -> None:
        # 規格註記的 Arc A770 形式：ARC + A + 數字
        spec = parse_spec("顯示卡", "Intel Arc A770 16G")
        assert spec.brand == "Intel"
        assert spec.extra["chip"] == "Arc A770"
        assert spec.extra["vram_gb"] == 16


# ── 記憶體深度 ───────────────────────────────────────────────────────────

class TestRamDeepParse:
    def test_crucial_ddr5(self) -> None:
        spec = parse_spec("記憶體", "美光 Crucial DDR5-5600 16GB(8G*2) 桌上型記憶體")
        assert spec.brand == "美光"
        assert spec.extra["ram_gb"] == 16
        assert spec.extra["spec"] == "DDR5"
        assert spec.extra["clock_mhz"] == 5600

    def test_kingston_ddr4(self) -> None:
        spec = parse_spec("記憶體", "Kingston DDR4-3200 16GB 桌上型記憶體")
        assert spec.brand == "Kingston"
        assert spec.extra["ram_gb"] == 16
        assert spec.extra["spec"] == "DDR4"
        assert spec.extra["clock_mhz"] == 3200

    def test_gb_multiplier_form(self) -> None:
        # 8GB*2 雙通道套裝 → 總容量 16（與 16GB(8G*2) 形式一致）
        spec = parse_spec("記憶體", "Kingston 8GB*2 DDR4-3200 桌上型記憶體")
        assert spec.extra["ram_gb"] == 16

    def test_ram_writes_ram_gb_not_capacity_gb(self) -> None:
        # 根因修正：記憶體容量欄位為 ram_gb，與 SSD/HDD 的 capacity_gb（儲存）分離
        spec = parse_spec("記憶體", "美光 Crucial DDR5-5600 16GB(8G*2) 桌上型記憶體")
        assert spec.extra["ram_gb"] == 16
        assert "capacity_gb" not in spec.extra


# ── SSD 深度 ─────────────────────────────────────────────────────────────

class TestSsdDeepParse:
    def test_wd_nvme(self) -> None:
        spec = parse_spec("SSD", "WD 藍標 SN580 1TB M.2 PCIe 4.0 SSD")
        assert spec.brand == "WD"
        assert spec.extra["capacity_gb"] == 1024   # 1TB 統一轉整數 GB
        assert spec.extra["interface"] == "M.2"
        assert spec.extra["format"] == "NVMe"

    def test_samsung_sata(self) -> None:
        spec = parse_spec("SSD", 'Samsung 870 EVO 500GB 2.5" SATAIII SSD')
        assert spec.brand == "Samsung"
        assert spec.extra["capacity_gb"] == 500
        assert spec.extra["interface"] == "SATA"
        assert spec.extra["format"] == "SATA"


# ── HDD 深度 ─────────────────────────────────────────────────────────────

class TestHddDeepParse:
    def test_seagate_7200rpm(self) -> None:
        spec = parse_spec("HDD", "Seagate 新梭魚 2TB 256M/7200轉/3年保")
        assert spec.brand == "Seagate"
        assert spec.extra["capacity_gb"] == 2048   # 2TB → 2048
        assert spec.extra["rpm"] == 7200
        assert spec.extra.get("interface") is None  # 名稱未含介面字樣

    def test_wd_5400rpm(self) -> None:
        spec = parse_spec("HDD", "WD 藍標 1TB 5400轉 桌上型硬碟")
        assert spec.brand == "WD"
        assert spec.extra["capacity_gb"] == 1024
        assert spec.extra["rpm"] == 5400


# ── 主機板深度 ───────────────────────────────────────────────────────────

class TestMoboDeepParse:
    def test_gigabyte_b760m(self) -> None:
        spec = parse_spec("主機板", "技嘉 B760M GAMING X AX DDR4 主機板")
        assert spec.brand == "技嘉"
        assert spec.extra["chipset"] == "B760"        # 尾綴 M 不計入晶片組
        assert spec.extra["form_factor"] == "M-ATX"   # B760M 尾綴 M → 微板
        assert spec.extra.get("socket") is None

    def test_gigabyte_z790_atx(self) -> None:
        spec = parse_spec("主機板", "技嘉 Z790 AORUS ELITE AX ATX 主機板")
        assert spec.brand == "技嘉"
        assert spec.extra["chipset"] == "Z790"
        assert spec.extra["form_factor"] == "ATX"


# ── 記憶卡輕量 ───────────────────────────────────────────────────────────

class TestMemoryCardLightParse:
    def test_sandisk_microsdxc(self) -> None:
        spec = parse_spec("記憶卡", "SanDisk 128GB MicroSDXC U3 A2 記憶卡")
        assert spec.brand == "SanDisk"
        assert spec.extra["capacity"] == "128GB"      # 輕量保留原始字串 token
        assert spec.extra["spec"] == "MicroSDXC"

    def test_kingston_sdxc(self) -> None:
        spec = parse_spec("記憶卡", "Kingston 64GB SDXC 記憶卡")
        assert spec.brand == "Kingston"
        assert spec.extra["capacity"] == "64GB"
        assert spec.extra["spec"] == "SDXC"


# ── 套裝/準系統輕量 ──────────────────────────────────────────────────────

class TestPrebuiltLightParse:
    def test_asus_gaming(self) -> None:
        spec = parse_spec("套裝/準系統", "華碩 ROG G22CH 電競主機")
        assert spec.brand == "華碩"
        assert spec.model == "ROG G22CH"
        assert spec.extra["usage"] == "電競主機"

    def test_acer_business(self) -> None:
        spec = parse_spec("套裝/準系統", "Acer Aspire XC 商務桌上型電腦")
        assert spec.brand == "Acer"
        assert spec.model == "Aspire XC"
        assert spec.extra["usage"] == "商務主機"


# ── 劈發價組合區輕量 ─────────────────────────────────────────────────────

class TestBundleLightParse:
    def test_pifafa_bundle(self) -> None:
        spec = parse_spec("劈發價組合區", "【劈發價】i5-13600K + B760 主機板組合")
        assert spec.brand is None
        assert spec.model == "i5-13600K + B760 主機板組合"
        assert spec.extra["summary"] == "i5-13600K + B760 主機板組合"


# ── 容錯 ─────────────────────────────────────────────────────────────────

class TestFaultTolerance:
    @pytest.mark.parametrize(
        ("category", "name"),
        [
            ("CPU", "####???%%%"),          # 亂碼
            ("顯示卡", "@@@##@@"),          # 無品牌/晶片可辨識
            ("記憶體", "zzz 999"),          # 無品牌可辨識
            ("SSD", "QOO 123 SSD"),         # 未知品牌
            ("主機板", "ABC 123 主機板"),   # 未知品牌
        ],
    )
    def test_unparseable_returns_minimal_spec(self, category: str, name: str) -> None:
        # 解析失敗 → 最少欄位 Spec(brand=None, model=None)，不拋例外、不丟商品
        spec = parse_spec(category, name)
        assert spec.brand is None
        assert spec.model is None
        assert isinstance(spec.extra, dict)

    @pytest.mark.parametrize("name", ["Intel i5-13600K", "SanDisk 128GB", ""])
    def test_unknown_category_returns_empty_spec(self, name: str) -> None:
        spec = parse_spec("沒有這個分類", name)
        assert spec.brand is None
        assert spec.model is None
        assert spec.extra == {}


# ── extra 欄位範圍 ───────────────────────────────────────────────────────

class TestExtraScope:
    @pytest.mark.parametrize(
        ("category", "name", "allowed"),
        [
            ("CPU", "Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】",
             {"cores", "threads", "base_ghz", "turbo_ghz", "tdp_w", "socket"}),
            ("顯示卡", "MSI RTX 4060 VENTUS 2X 8G OC",
             {"chip", "vram_gb", "interface", "length_mm"}),
            ("記憶體", "美光 Crucial DDR5-5600 16GB(8G*2) 桌上型記憶體",
             {"ram_gb", "spec", "clock_mhz"}),
            ("SSD", "WD 藍標 SN580 1TB M.2 PCIe 4.0 SSD",
             {"capacity_gb", "interface", "format", "rpm"}),
            ("HDD", "Seagate 新梭魚 2TB 256M/7200轉/3年保",
             {"capacity_gb", "interface", "format", "rpm"}),
            ("主機板", "技嘉 B760M GAMING X AX DDR4 主機板",
             {"chipset", "socket", "form_factor"}),
            ("記憶卡", "SanDisk 128GB MicroSDXC U3 A2 記憶卡",
             {"capacity", "spec"}),
            ("套裝/準系統", "華碩 ROG G22CH 電競主機",
             {"usage"}),
            ("劈發價組合區", "【劈發價】i5-13600K + B760 主機板組合",
             {"summary"}),
        ],
    )
    def test_extra_only_contains_category_relevant_fields(
        self, category: str, name: str, allowed: set[str]
    ) -> None:
        spec = parse_spec(category, name)
        assert set(spec.extra) <= allowed
        # brand/model 為 Spec 通用欄位，不得重複出現於 extra
        assert "brand" not in spec.extra
        assert "model" not in spec.extra

    def test_cpu_extra_has_no_gpu_or_storage_fields(self) -> None:
        spec = parse_spec("CPU", "Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】")
        assert "vram_gb" not in spec.extra
        assert "capacity_gb" not in spec.extra
        assert "rpm" not in spec.extra
