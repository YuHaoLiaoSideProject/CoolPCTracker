# A/B 來源驗證 spike 報告：手機版 9 分類 vs 桌面版 evaluate.php（issue #2）

- **方法**：手機版 m-list.php 9 分類頁 vs 桌面版 evaluate.php 單次快照比對；子分類以正規化名稱對齊，商品以正規化名稱差集比對；G=9 兩來源皆套用「記憶卡」子分類過濾後才比對
- **抓取時間**：2026-08-15T16:38:16+00:00
- **原始 HTML fixture**：`scripts/tests/fixtures/mobile/G{1,3,4,5,6,7,8,9,12}.html`、`scripts/tests/fixtures/desktop/evaluate.html`（離線可重跑）
- **完整結果 JSON**：`docs/spike/ab-source-compare-2026-08-15.json`

## 1. 方法

1. 抓取存檔：`crawler.fetcher.Fetcher` 依序抓手機版 9 頁；桌面版以 httpx（桌面 UA）抓 evaluate.php；原始 HTML（cp950 解碼後文字）存入測試 fixture。
2. 手機版解析：真實結構 `<span class=Q>` 內每子分類一個 table（thead/th 子分類標題、tbody/td 商品列，td 內 `名稱, $價格[↗|↘$異動價] <i>標記</i>`）；過濾 class=y/z 通知列、disabled、贈品列；G=9 依 `subcategory_keyword="記憶卡"` 過濾子分類。
3. 桌面版解析：selectolax 解析 `<OPTGROUP LABEL>`（每群組=一子分類）與 `<OPTION>` 商品列；過濾 disabled 與 ❤/↪ 通知列。
4. 分類對應：桌面 optgroup 以正規化名稱與手機版子分類精確對齊；未對齊者以關鍵字規則兜底；仍無法對應 → 「未對應桌面區段」。
5. 公平比對：G=9 兩來源皆套用「記憶卡」子分類過濾後，才以正規化商品名稱計算差集。
6. 名稱正規化重用 `crawler.categories.normalize_name`（NFKC→casefold→空白收縮）並剝離桌面裝飾（◆ ★ 熱賣 ↓任搭N↓ ↓酷幣N↓）與價格段；價格不參與比對（兩來源非同時快照）。

## 2. Spike 發現（重要）

### 2.1 手機版真實結構與 crawler/parser 假設不符（需另開 issue 對齊）

- 真實 m-list.php：`<span class=Q>` 內每子分類一個 `<table>`（thead/tr/th 子分類標題，無 `</th>`收尾），tbody/tr/td 商品列，**td 內名稱與價格同格**；class=y（↪ 限量/加贈通知）、class=z（❤ 專業性產品說明）非商品列。
- 現有 `crawler/parser.py` 以 `tree.css_first("table")` 只解析第一個 table（本頁為 logo 表頭），對真實頁面每分類僅產出 3 筆錯誤項目、0 個子分類（實測 G=4 應 48 筆）。
- `crawler/tests/fixtures/*.html` 為單 table、th=子分類、td 名稱/價格分格的設計期結構，與真實頁面不符 → 既有 crawler 測試全綠但無法解析真實頁面，001 上線前必須對齊。
- 本 spike 以 spike 專屬解析器（`ab_source_compare.parse_mobile`）依真實結構解析，不修改 crawler 核心模組。

### 2.2 桌面版 evaluate.php 為 malformed HTML

- `<OPTGROUP>` 570 開 / 0 收尾；`<OPTION>` 7646 開 / 7316 收（330 未收尾）；首列 value=0 為全站摘要並內嵌第一個 OPTGROUP。selectolax 自動修正後可完整解析（7315 商品列 / 570 群組）。
- 直接 regex 解析會因未收尾標籤錯位，不可用。

### 2.3 兩來源商品名稱字串一致

- 手機版 td 與桌面版 OPTION 在「`, $價格`」之前文字完全相同，剝離裝飾與價格段後可直接以正規化名稱對齊，不需模糊比對；子分類標題（th / OPTGROUP label）亦逐字一致。

### 2.4 標記差異

- 手機版真實頁面僅見 `<i>Hot！</i>`；`任搭↓N`/`↘`/`尾盤` 為 fixture 假設標記，本次快照未出現。
- 桌面版促銷標記為 `↓任搭N↓` 與 `↓酷幣N↓` 兩種（在價格段之後）→ crawler 未建模「酷幣」類型。

## 3. 集合統計（每分類筆數）

| 分類 | 手機版 | 桌面版 | 兩者皆有 | 僅手機版 | 僅桌面版 |
|------|-------:|-------:|--------:|--------:|--------:|
| 套裝/準系統 | 157 | 180 | 157 | 0 | 23 |
| 劈發價組合區 | 86 | 96 | 86 | 0 | 9 |
| CPU | 48 | 48 | 47 | 0 | 0 |
| 主機板 | 373 | 373 | 372 | 0 | 0 |
| 記憶體 | 216 | 230 | 216 | 0 | 14 |
| SSD | 171 | 189 | 171 | 0 | 18 |
| HDD | 89 | 89 | 89 | 0 | 0 |
| 記憶卡 | 54 | 54 | 54 | 0 | 0 |
| 顯示卡 | 255 | 278 | 255 | 0 | 23 |
| **合計** | **1449** | **1537** | | | |

* 「兩者皆有」為唯一名稱數：CPU/主機板各有 1 筆名稱在兩來源同時重複（同名稱不同子分類），故 47<48、372<373，差集仍為 0。
* 手機版原始（G=9 未過濾）總數 1,606 → G=9 過濾後 1,449；桌面版全站商品型項目 6,626（含未對應 4,932）。

## 4. 差異清單（僅桌面版，全部來自手機版頁面不存在的配件/促銷區段）

### 套裝/準系統：僅桌面版（23 項，來源：【主機搭購螢幕促銷專區】（23））
- Raymii HALO-MAX2-1M 白色 (單螢幕 / 氣壓式)承載27KG/15-57吋/USB3.0*2) $2799↘
- Raymii HALO-MAX2-1M 黑色 (單螢幕 / 氣壓式)承載27KG/15-57吋/USB3.0*2) $2799↘
- Raymii LS-140-M1 RGB 黑色 (單螢幕 /氣壓式) 承載12KG / 17-35吋 )$2399↘
- Raymii LS-140-M2 RGB 黑色 (雙螢幕 /氣壓式) 承載12KG / 17-35吋 )$3899↘
- Raymii LS-43-OP (單螢幕/穿夾兩用/氣壓式/銀色 )承載9KG /17-32吋 外箱擠壓 $2199↘
- Raymii LS-67-M1 (單螢幕 / 穿夾兩用 /機械彈簧) 承載11KG / 17-35吋/白色 $2299↘
- Raymii LS-67-M1 (單螢幕 / 穿夾兩用 /機械彈簧) 承載11KG / 17-35吋/黑色 $2299↘
- Raymii LS5U (單螢幕/穿夾兩用/高負重氣壓/17-43吋/承載18KG) $2,539↘
- 【主機搭購】Acer Nitro VG240Y P6〈1H1P/IPS/144Hz/含喇叭〉$2688↘
- 【主機搭購】AOC 25B40HM〈1A1H/VA/100Hz〉
- 【主機搭購】AOPEN 16PM1Q J〈15.6吋/1H2C/IPS/含喇叭〉
- 【主機搭購】BenQ GW2790〈2H1P/IPS/100Hz/含喇叭〉.光智慧2.0 $3988↘
- 【主機搭購】MSI G242L E14〈1H1P/IPS/144Hz〉$2690↘
- 【主機搭購】MSI MAG 272F〈1H1P/IPS/200Hz〉$3390↘
- 【主機搭購】MSI PRO MP242 E14C〈1H1C/IPS/144Hz/含喇叭/Type-C連接埠〉$2588↘
- 【主機搭購】MSI PRO MP272 E14C〈1H1C/IPS/144Hz/含喇叭/Type-C連接埠〉$2888↘
- 【主機搭購】三星 Odyssey G5 S27FG502EC〈1H1P/IPS/180Hz/HDR10〉可升降旋轉
- 【主機搭購】三星 S3 S27D300GAC〈1A1H/IPS/100Hz〉
- 【螢幕搭購】BenQ ERGO ARM BSH01 黑色 (單螢幕/穿夾兩用/底座加固板/承載20KG)
- 【螢幕搭購】BenQ ERGO ARM BSH02 白色 (單螢幕/穿夾兩用/底座加固板/承載20KG)
- 威世波 WST-MNT001 鋁合金螢幕支架 夾桌式/承載9.5KG/17-35吋【暗夜黑】$3280↘
- 威世波 WST-MNT002 鋁合金螢幕支架 夾桌式/承載9.5KG/17-35吋【冰川銀】$3280↘
- 威世波 WST-MNT003 鋁合金螢幕支架 夾桌式/承載9.5KG/17-35吋【冰雪白】$3280↘

### 劈發價組合區：僅桌面版（9 項，來源：【超級CP電競組合包】（9））
- Cougar 電競組合包(Cougar Ultimus EX 鍵盤+Minos T1 滑鼠鼠墊組)原價2490
- Razer CS2 組合包(Huntsman V3 Pro鍵盤+Viper V3 Pro滑鼠+Gigantus(大)鼠墊)原價16490
- Razer Minecraft 組合包(BlackWidow V4 X鍵盤+Cobra滑鼠+Gigantus(中)鼠墊+Kraken V4 X耳機)
- Razer 電競組合包(Ornata V3X 鍵盤+Essential 滑鼠+BlackShark V2 X 耳機)原價4929
- 亞碩(Power Master)超優質組合套餐(Km-11天蠍座 +G502 滑鼠鼠墊組)原價1980
- 微星 優質三件組組合包(GK20鍵盤+GM320滑鼠+GD21鼠墊)原價2219
- 微星 超值三件組組合包(GK20鍵盤+GM08滑鼠+GD21鼠墊)原價2219
- 華碩 ROG暑期電競組合(Scope II X青軸鍵盤+Harpe Mini Core滑鼠+Delta S Core耳麥)原價8370
- 華碩 TUF電競組合(K3 Gen II青軸鍵盤+M4 Wireless無線滑鼠+H1 Gen II耳麥)原價5670

### 記憶體：僅桌面版（14 項，來源：群暉 Synology【原廠擴充配件/儲存硬碟/記憶體】（14））
- Synology 2年延長保固(EW201) 須與NAS一同購買並期限註冊/支援型號 請點→
- Synology DX525【5Bay】擴充櫃(適用25系列：DS1825+, DS1525+, DS925+, DS725+)
- Synology E10G22-T1-Mini 10GbE 網路模組(適用DS923+/DS723+/DS1522+/DS1525+)
- Synology HAT3300 4TB PLUS系列(3.5吋/5400轉/三年保固)【限搭NAS主機】
- Synology HAT3300 6TB PLUS系列(3.5吋/5400轉/三年保固)【限搭NAS主機】
- Synology HAT3310 12TB PLUS系列(3.5吋/7200轉/三年保固)【限搭NAS主機】
- Synology HAT3310 16TB PLUS系列(3.5吋/7200轉/三年保固)【限搭NAS主機】
- Synology HAT3320 20TB PLUS系列(3.5吋/7200轉/三年保固)【限搭NAS主機】
- Synology HAT3320 8TB PLUS系列(3.5吋/7200轉/三年保固)【限搭NAS主機】
- Synology RAM D4ES02-4G (適用:DS923+/DS723+)支援型號→
- Synology RAM D4ES03-8G (適用:DS925+/DS725+/DS1525+/DS1825+)支援型號→
- Synology RAM D4ES04-4G (適用:DS925+/DS725+)支援型號→
- Synology RAM D4NS01-4G (適用:DS225+/DS425+)支援型號→
- Synology SNV3410 400G M.2 2280 NVMe PCIe 讀:3000/寫:750/五年保固

### SSD：僅桌面版（18 項，來源：M.2 SSD PCI-E 擴充卡（7）、M.2 SSD散熱片（11））
- 伽利略【PCI-E 1X】M.2 NVMe SSD 1埠 轉接卡【M2PE42】
- 伽利略【PCI-E 4X】M.2 NVMe SSD 1埠 轉接卡【M2PE41】
- 伽利略【PCI-E 5.0 X1】M.2 NVMe SSD 1埠 轉接卡【M2PE51】
- 伽利略【PCI-E 5.0 X4】M.2 NVMe SSD 1埠 轉接卡【M2PE54】
- 利民 HR-09 2280 SSD 固態硬碟散熱器/6 mm熱導管/電鍍鰭片/單雙面皆適用
- 利民 HR-10 2280 PRO DIGITAL(白) SSD散熱器/4導管/溫度,傳輸速度監控/3cm風扇/一年
- 利民 HR-10 2280 PRO DIGITAL(黑) SSD散熱器/4導管/溫度,傳輸速度監控/3cm風扇/一年
- 利民 HR-10 2280 PRO SSD 固態硬碟散熱器/4導管/3CM PWM風扇/單雙面皆適用/一年
- 利民 M.2 2280 PRO SSD 固態硬碟散熱片/鋁合金+8 mm純銅導管/單雙面皆適用
- 利民 M.2 2280 TYPE A B SSD 固態硬碟散熱片/鋁合金/單雙面皆適用
- 喬思伯 M.2-6(紅) 固態硬碟散熱器/2280/鋁合金/單雙面皆適用
- 喬思伯 M201(銀) 固態硬碟散熱器/2280/格柵式鋁合金散熱片/單雙面皆適用
- 喬思伯 M201(黑) 固態硬碟散熱器/2280/格柵式鋁合金散熱片/單雙面皆適用
- 喬思伯 M202(灰) 固態硬碟散熱器/2280/巧克力造型全鋁散熱塊/單雙面皆適用
- 喬思伯 M202(黑) 固態硬碟散熱器/2280/巧克力造型全鋁散熱塊/單雙面皆適用
- 華碩 HYPER M.2 X16 GEN 4 CARD (支援 4個 M.2 SSD/NVMe/限NVMe/PCIe 模式)
- 華碩 HYPER M.2 X16 GEN 5 CARD (支援 4個 M.2 SSD/NVMe/限NVMe/PCIe 模式)
- 銀欣 ECM21-E【PCI-E 4X】M.2 NVMe SSD 1埠 免螺絲 轉接卡

### 顯示卡：僅桌面版（23 項，來源：PCIe 延長排線、顯示卡轉接架（23））
- Antec 顯示卡直立套件(白) 基本款 含PCI-E 5.0延長線/200mm/1年保
- Antec 顯示卡直立套件(黑) 基本款 含PCI-E 5.0延長線/200mm/1年保
- Montech VGM 2 直立式顯卡套件(白) 通用型/含PCI-E 4.0延長線/200mm
- Phanteks PCI-E 4.0 X16 90度延長線/白色/220mm(PH-CBRS4.0_FL22_WT01)
- Phanteks PCI-E 4.0 X16 90度延長線/黑色/220mm(PH-CBRS4.0_FL22)
- Phanteks PCI-E 4.0 X16 90度延長線/黑色/600mm(PH-CBRS4.0_FL60_BK01)
- Phanteks Premium 顯卡直立套件 白(PCI-E 4.0)/30度可旋轉設計(PGPUKT4.0_DWT01)
- Phanteks Premium 顯卡直立套件 白(PCI-E 5.0)/30度可旋轉設計(PGPUKT5.0_DWT01)
- Phanteks Premium 顯卡直立套件 黑(PCI-E 5.0)/30度可旋轉設計(PGPUKT5.0_DBK01)
- Phanteks 通用型顯卡直立套件 白(PCI-E 4.0)/220mm(PH-VGPUKT4.0_03R_WT)
- Phanteks 通用型顯卡直立套件 黑(PCI-E 4.0)/220mm(PH-VGPUKT4.0_03R)
- 喬思伯 A50 灰 顯卡垂直支架 通用型/PCI-E 5.0/175mm/3mm鋁合金/1年保
- 喬思伯 A50 白 顯卡垂直支架 通用型/PCI-E 5.0/175mm/3mm鋁合金/1年保
- 酷碼 PCI-E 4.0 X16 延長線 V2(白色)/200mm/90度/抗干擾(MCA-U002R-WPCI40-200)
- 酷碼 PCI-E 4.0 X16 延長線 V2(白色)/300mm/90度/抗干擾(MCA-U002R-WPCI40-300)
- 酷碼 PCI-E 5.0 X16 延長線(白) 200mm/90度/抗電磁干擾(MCA-U000C-WPCI50-200)
- 酷碼 PCI-E 5.0 X16 延長線(白) 300mm/90度/抗電磁干擾(MCA-U000C-WPCI50-300)
- 酷碼 PCI-E 5.0 X16 延長線(黑) 200mm/90度/抗電磁干擾(MCA-U000C-KPCI50-200)
- 酷碼 PCI-E 5.0 X16 延長線(黑) 300mm/90度/抗電磁干擾(MCA-U000C-KPCI50-300)
- 酷碼 通用型垂直顯卡支架套件 ARGB版(PCIe 4.0) X,Z軸雙向(MCA-U004R-AVGBST-00)
- 酷碼 通用型垂直顯卡支架套件 V3(PCIe 4.0) 黑色/X,Z軸雙向調整(MCA-U000R-KFVK03)
- 酷碼 通用型垂直顯卡支架套件 V3(PCIe 5.0) 白色/X,Z軸雙向調整(MCA-U000C-WFVK03)
- 酷碼 通用型垂直顯卡支架套件 V3(PCIe 5.0) 黑色/X,Z軸雙向調整(MCA-U000C-KFVK03)

## G=9 記憶卡子分類過濾驗證

- mobile：保留 54 項（子分類均含「記憶卡」：True）、被過濾 157 項（子分類均不含「記憶卡」：True）
  - 被過濾子分類：2.5吋 - Seagate 隨身2.5吋硬碟 (保固內原廠資料救援)、2.5吋 - Toshiba 隨身2.5吋硬碟、2.5吋 - 創見 隨身2.5吋硬碟、2.5吋 - 威剛 隨身2.5吋硬碟、3.5吋 - Seagate 行動3.5吋硬碟 (保固內原廠資料救援)、Micron 隨身SSD碟 Type-C介面、Seagate 隨身SSD碟 Type-C介面、三星 Samsung 隨身SSD碟 Type-C介面、威剛 隨身SSD碟 Type-C介面、海盜船 隨身SSD碟 Type-C介面、致態 隨身SSD碟 Type-C介面、金士頓 隨身SSD碟 Type-C介面、隨身碟 Type-A、隨身碟 Type-C、隨身碟 Type-C+A 雙介面、高速隨身碟
- desktop：保留 54 項（子分類均含「記憶卡」：True）、被過濾 157 項（子分類均不含「記憶卡」：True）
  - 被過濾子分類：2.5吋 - Seagate 隨身2.5吋硬碟 (保固內原廠資料救援)、2.5吋 - Toshiba 隨身2.5吋硬碟、2.5吋 - 創見 隨身2.5吋硬碟、2.5吋 - 威剛 隨身2.5吋硬碟、3.5吋 - Seagate 行動3.5吋硬碟 (保固內原廠資料救援)、Micron 隨身SSD碟 Type-C介面、Seagate 隨身SSD碟 Type-C介面、三星 Samsung 隨身SSD碟 Type-C介面、威剛 隨身SSD碟 Type-C介面、海盜船 隨身SSD碟 Type-C介面、致態 隨身SSD碟 Type-C介面、金士頓 隨身SSD碟 Type-C介面、隨身碟 Type-A、隨身碟 Type-C、隨身碟 Type-C+A 雙介面、高速隨身碟

## 未對應到 9 分類的桌面區段

- PAD 智慧平板（5 項）
- 遊戲掌機（9 項）
- 筆電搭購電競周邊優惠專區（8 項）
- 筆電展示出清專區 (保固憑發票購買日起算，展示機無七日新品瑕疵換新)（18 項）
- 宏碁 Acer 筆電館-全館刷卡分期零利率(3)（2 項）
- 15吋 Acer宏碁 Aspire 7 系列（2 項）
- 14吋 Acer宏碁 Aspire Lite 系列（4 項）
- 15吋 Acer宏碁 Aspire Lite 系列（5 項）
- 16吋 Acer宏碁 Aspire Lite 系列（2 項）
- 17吋 Acer宏碁 Aspire Lite 系列（2 項）
- 15.6吋 Acer宏碁 Aspire Spin 系列（2 項）
- 16吋 Acer宏碁 Nitro 電競機（2 項）
- 14吋 Acer宏碁 Nitro V 電競機（1 項）
- 15吋 Acer宏碁 Nitro V 電競機（3 項）
- 16吋 Acer宏碁 Nitro V 電競機（4 項）
- 16吋 Acer宏碁 Nitro Lite 電競機（4 項）
- 14吋 Acer宏碁 Predator Helios Neo 14 電競機〈官網登錄送一年延保〉（2 項）
- 16吋 Acer宏碁 Predator Helios Neo 16 電競機〈官網登錄送一年延保〉（4 項）
- 16吋 Acer宏碁 Predator Helios Neo 16S AI 電競機〈官網登錄送一年延保〉（4 項）
- 14吋 Acer宏碁 Swift Lite 系列（5 項）
- 16吋 Acer宏碁 Swift Lite 系列（3 項）
- 14吋 Acer宏碁 Swift Go 系列（4 項）
- 16吋 Acer宏碁 Swift Go 系列（3 項）
- 14吋 Acer宏碁 Swift 14 系列（2 項）
- 14吋 Acer宏碁 Swift Air 系列（3 項）
- 16吋 Acer宏碁 Swift Air 系列（5 項）
- 14吋/16吋 Acer宏碁 Swift Edge 系列 〈頂級超輕量工作生活筆電〉（1 項）
- 15吋 Lenovo IdeaPad Slim 3 系列（2 項）
- 16吋 Lenovo IdeaPad Slim 3 系列（2 項）
- 13吋/14吋 Lenovo IdeaPad Slim 5 系列（1 項）
- 14吋 Lenovo IdeaPad Pro 5 系列（1 項）
- 14吋 Lenovo Yoga Slim 7 / Yoga Pro 7 系列（4 項）
- 15吋 Lenovo LOQ 系列（6 項）
- 15吋 Lenovo Legion 5 系列（1 項）
- 華碩 ASUS 筆電館-全館刷卡分期零利率(3)（7 項）
- 華碩 ROG 二十載淬鍊不凡 / ROG SAGA 特展 / 2026 限量特展（7 項）
- 13 吋 華碩 ProArt 系列〈打造全新 AI 體驗、提升工作效率〉（1 項）
- 14 吋 華碩 Zenbook 系列 / 高通Qualcomm系列（13 項）
- 16 吋 華碩 Zenbook 系列 / 高通Qualcomm系列（3 項）
- 14吋 華碩 Vivobook GO / Vivobook / Vivobook 14 Flip 系列（12 項）
- 15 吋 華碩 VivoBook GO / VivoBook 系列（11 項）
- 16 吋 華碩 Vivobook / V16 蒼藍戰魂 系列（9 項）
- 17 吋 華碩 Vivobook 系列（2 項）
- 18 吋 華碩 Vivobook 系列（1 項）
- 14 吋 華碩 TUF Gaming / ROG 電競系列（5 項）
- 15 吋 華碩 TUF Gaming 電競系列（2 項）
- 16 吋 華碩 TUF Gaming / ROG / Zephyrus 電競系列（21 項）
- 17 吋 華碩 TUF Gaming / ROG 電競系列（2 項）
- 18 吋 華碩 TUF Gaming / ROG 電競系列（9 項）
- 14吋 DELL戴爾 Inspiron 7000 Plus 系列 〈高性能創作筆電〉（1 項）
- 14吋 戴爾 DELL Base 系列（4 項）
- 14吋 戴爾 DELL Pro Base 系列（6 項）
- 15吋 戴爾 DELL Base 系列（2 項）
- 16吋 戴爾 DELL Pro Base 系列（4 項）
- 14吋 戴爾 DELL Pro Plus 系列（1 項）
- 14吋 戴爾 DELL Pro Essential 系列（2 項）
- 16吋 戴爾 DELL Alienware 系列（3 項）
- 15.6吋 捷元 ZEUS 系列（4 項）
- 16吋 捷元 AI Pro 系列（1 項）
- 18吋 捷元 ZEUS 18G 系列（1 項）
- 16吋 技嘉 GIGABYTE AERO X16 AI筆電（7 項）
- 16吋 技嘉 GIGABYTE EAGLE（2 項）
- 16吋 技嘉 GIGABYTE GAMING A16（8 項）
- 16 吋 技嘉 AORUS MASTER 16（4 項）
- 微星 MSI 筆電館-全館刷卡分期零利率(3)（4 項）
- 13 吋 微星 - 輕薄商務系列 Prestige（3 項）
- 14 吋 微星 - 輕薄商務系列 Modern S /Prestige / Commercial 效能商務AI系列 Venture（6 項）
- 15 吋 微星 - 輕薄美型系列 Modern / VenturePro（5 項）
- 16 吋 微星 - 輕薄商務系列 Prestige / Modern S（2 項）
- 15 吋 微星 - 炫彩戰鬥系列 Cyborg MAX/Katana（11 項）
- 16 吋 微星 - 極致龍魂系列 Pulse/Crosshair MAX/Stealth/Raider MAX（14 項）
- 17 吋 微星 - 巔峰效能系列 Cyborg/Katana/Crosshair（5 項）
- 18 吋 微星 - 極致炫彩系列 Vector/Crosshair/Stealth/Raider/Titan 電競霸主（4 項）
- 16吋 LG Gram -榮獲金氏世界紀錄最輕16吋筆電（2 項）
- 16 吋 LG Gram Pro 最新的處理器，領航著速度的先驅（5 項）
- 17 吋 LG Gram 高科技奈米碳鎂通過美國軍規測試（1 項）
- 14 吋 HP OmniBook 3（1 項）
- 16 吋 HP OmniBook 3（1 項）
- 17 吋 HP OmniBook 3（1 項）
- 14 吋 HP OmniBook 5 Flip 翻轉觸控筆電（4 項）
- 13 吋 HP OmniBook 7系列（2 項）
- 15吋 HP HyperX OMEN 潮競系列 /Victus 光影系列（2 項）
- 14 吋 HP惠普 ZBook Firefly 14 系列〈創意行動達人〉（1 項）
- 14吋 HP惠普 ZBook 8 G1i/G1a 14 系列（1 項）
- 16 吋 HP惠普 ZBook 8 G1i/G1a 14 系列（1 項）
- 筆電周邊（1 項）
- 快速充電器（20 項）
- 行動電源（14 項）
- ID-COOLING 散熱器【2年保固】（9 項）
- 利民 Thermalright(索摩樂) 散熱器（27 項）
- DEEPCOOL 九州風神【3年保固】（15 項）
- 銀欣 SILVERSTONE（8 項）
- CoolerMaster 酷碼散熱器（14 項）
- 鎌刀 Scythe 散熱器【3年保固】（11 項）
- Noctua 貓頭鷹 散熱器 【6年保固】（23 項）
- 威剛 XPG（3 項）
- 君主 Montech 散熱器（6 項）
- 快睿 CRYORIG 散熱器（6 項）
- 先馬 SAMA（6 項）
- 振華 Super Flower（1 項）
- 微星 MSI 散熱器（2 項）
- 全漢 FSP 散熱器（7 項）
- 大飛 darkFlash 散熱器（2 項）
- 創氪星系 TRYX 散熱器（2 項）
- 喬思伯 Jonsbo 散熱器（11 項）
- 高效能散熱膏（10 項）
- 矽膠導熱片（2 項）
- 筆記型專用散熱座（7 項）
- 特價 or 活動專區（4 項）
- 華碩 ASUS【0800到府 6年保固換新】保固內非人損漏液賠償！保固內非人損換新。（25 項）
- 微星 MSI (註冊享延保！保內到府收送，品質保證非人損漏液損害賠償！)（8 項）
- 君主 Montech（14 項）
- 美洲獅 COUGAR（11 項）
- 大飛 darkFlash（7 項）
- ID-COOLING 一體式水冷（6 項）
- 威剛 XPG（3 項）
- 保銳 ENERMAX（7 項）
- DEEPCOOL 九州風神（9 項）
- Noctua 貓頭鷹（4 項）
- 鈦鉭科技 TCOMAS (本體6年保固/液晶2年)（16 項）
- 酷碼 Cooler Master(漏液損害賠償)（11 項）
- 幾何未來 Geometric Future（6 項）
- 先馬 SAMA（6 項）
- 安鈦克 ANTEC（5 項）
- 快睿 CRYORIG（3 項）
- 追風者 Phanteks（6 項）
- 恩傑 NZXT（13 項）
- 美商艾湃電競(首利) Apexgaming（1 項）
- 銀欣 SILVERSTONE（6 項）
- 利民 Thermalright(索摩樂)（14 項）
- 聯力工業 LIAN LI【6年/漏液依年限折舊/曲面屏3年】（12 項）
- 技嘉 GIGABYTE（9 項）
- 華擎 ASRock（4 項）
- 全漢 FSP（4 項）
- 創氪星系 TRYX【水冷/無光扇(6年) 螢幕/ARGB扇(2年)保固】（12 項）
- 喬思伯 JONSBO【立光代理】故障換新、漏液損害賠償！（7 項）
- 水冷套件-水冷液【客訂商品】（1 項）
- 19吋(1280*1024)(5:4)〈亮暗點保固視廠商保固條款而定〉（1 項）
- 20吋(16:9)〈亮暗點保固視廠商保固條款而定〉（2 項）
- 22吋(1920*1080)(16:9)〈亮暗點保固視廠商保固條款而定〉（15 項）
- 24吋(1920*1080)(16:9)〈亮暗點保固視廠商保固條款而定〉（84 項）
- 24吋(1920*1200)(16:10)〈亮暗點保固視廠商保固條款而定〉（5 項）
- 24吋(2560*1440)(16:9)〈亮暗點保固視廠商保固條款而定〉（2 項）
- 24吋(2560*1600)(16:10)〈亮暗點保固視廠商保固條款而定〉（2 項）
- 25吋(1920*1080)(16:9)〈亮暗點保固視廠商保固條款而定〉（18 項）
- 27吋(1920*1080)(16:9)〈亮暗點保固視廠商保固條款而定〉（98 項）
- 27吋(2560*1440)(16:9)〈亮暗點保固視廠商保固條款而定〉（130 項）
- 27吋(3840*2160)(4K 16:9)〈亮暗點保固視廠商保固條款而定〉（66 項）
- 27吋(5120*2880)(5K 16:9)〈亮暗點保固視廠商保固條款而定〉（9 項）
- 28吋(3840*2160)(4K 16:9)〈亮暗點保固視廠商保固條款而定〉（1 項）
- 28吋(3840*2160)(3:2)〈亮暗點保固視廠商保固條款而定〉（1 項）
- 29吋(2560*1080)(21:9)〈亮暗點保固視廠商保固條款而定〉（2 項）
- 32吋(1920*1080)(16:9)〈亮暗點保固視廠商保固條款而定〉（17 項）
- 32吋(2560*1440)(16:9)〈亮暗點保固視廠商保固條款而定〉（18 項）
- 32吋(3840*2160)(4K 16:9)〈亮暗點保固視廠商保固條款而定〉（64 項）
- 32吋(6016*3384)(6K 16:9)〈亮暗點保固視廠商保固條款而定〉（3 項）
- 34吋(2560*1080)(21:9)〈亮暗點保固視廠商保固條款而定〉（1 項）
- 34吋(3440*1440)(21:9)〈亮暗點保固視廠商保固條款而定〉（34 項）
- 37吋(3840*2160)(16:9)〈亮暗點保固視廠商保固條款而定〉（3 項）
- 39吋(5120*2160)(21:9)〈亮暗點保固視廠商保固條款而定〉（1 項）
- 40吋(5120*2160)(21:9)〈亮暗點保固視廠商保固條款而定〉（2 項）
- 43吋(3840*2160)(16:9)〈亮暗點保固視廠商保固條款而定〉（3 項）
- 45吋(3440*1440)(21:9)〈亮暗點保固視廠商保固條款而定〉（1 項）
- 45吋(5120x2160)(21:9)〈亮暗點保固視廠商保固條款而定〉（1 項）
- 49吋(3840*1080)(32:9)〈亮暗點保固視廠商保固條款而定〉（1 項）
- 49吋(5120*1440)(32:9)〈亮暗點保固視廠商保固條款而定〉（7 項）
- 57吋(7680*2160)〈亮暗點保固視廠商保固條款而定〉（1 項）
- 觸控式螢幕、可攜式螢幕、遊戲TV（35 項）
- ASUS 華碩投影機（1 項）
- ACER 宏碁投影機（2 項）
- BenQ 投影機（10 項）
- 螢幕掛燈（5 項）
- 投影機支撐架（2 項）
- 桌上型筆電支架/增高架（6 項）
- 螢幕支撐架（65 項）
- 特價 or 活動專區（12 項）
- 工業機架式 / NAS 機殼（20 項）
- SFX 機殼專區（23 項）
- 華碩 ASUS 機殼（37 項）
- 君主 Montech 機殼（57 項）
- 視博通 Superchannel 機殼（27 項）
- 微星 MSI 機殼（19 項）
- 技嘉 GIGABYTE 機殼（12 項）
- 大飛 darkFlash 機殼（22 項）
- 美商艾湃電競(首利) Apexgaming【上市25年 "首利" 100%品牌】（8 項）
- 美洲獅 COUGAR 機殼（37 項）
- 亞碩國際 機殼（1 項）
- 先馬 SAMA 機殼（7 項）
- 旋剛 Sharkoon 機殼（14 項）
- 1st Player 首席玩家（2 項）
- 安鈦克 Antec 機殼（40 項）
- 火鳥 BitFenix 機殼（9 項）
- HYTE 美國電競潮牌（6 項）
- 追風者 Phanteks 機殼（31 項）
- Fractal Design 機殼（52 項）
- 酷碼 CoolerMaster 機殼（58 項）
- 幾何未來 Geometric Future 機殼（17 項）
- 威剛 XPG 機殼（6 項）
- 銀欣 SilverStone 機殼（23 項）
- 振華 Super Flower（3 項）
- 曜越 Thermaltake 機殼（33 項）
- DEEPCOOL 九州風神（13 項）
- 保銳 ENERMAX 機殼（3 項）
- 迎廣 InWin 機殼（19 項）
- 恩傑 NZXT 機殼（11 項）
- 全漢 FSP 機殼（14 項）
- 聯力工業 LIAN LI 機殼（32 項）
- 創氪星系 TRYX（5 項）
- 喬思伯 JONSBO 機殼（46 項）
- 特價 or 活動專區（14 項）
- 特規 SFX SFX-L 電源供應器（18 項）
- 華碩 ASUS【0800到府收送】（24 項）
- 海韻 Seasonic（30 項）
- 台達 DELTA 最穩定的電源【保固憑原價屋發票/保貼】（5 項）
- Apexgaming 美商艾湃電競【首利100%品牌，原價屋售出 3年快換】（15 項）
- 美洲獅 COUGAR 電源【偉訓30年品質保證】（10 項）
- 振華 Super Flower（23 項）
- 君主 Montech 【原廠兩年換新】（17 項）
- 銀欣 SilverStone【原價屋售出 2年快換】（16 項）
- 酷碼 Cooler Master（18 項）
- 威剛 XPG【保內原廠展服快換】（14 項）
- 保銳 ENERMAX【原價屋售出 2年快換】（19 項）
- 安鈦克 Antec 電源供應器 美國選購率第一【原價屋售出 2年快換!!】（16 項）
- 全漢 FSP 電源供應器【原價屋售出 2年快換 電供就是穩 !!】（31 項）
- 微星 MSI 【到府收件 兩年展服快換】（17 項）
- DEEPCOOL 九州風神（9 項）
- 火鳥 BitFenix（1 項）
- 大飛 darkFlash（4 項）
- 恩傑 NZXT【原價屋售出 2年快換】（7 項）
- 華擎 ASRock（5 項）
- 技嘉 GIGABYTE（11 項）
- 曜越 Thermaltake【原價屋售出 3年快換 !!】（4 項）
- 聯力工業 LIAN LI（4 項）
- 機殼風扇 超值推薦（13 項）
- 華碩 ASUS 風扇/配件（32 項）
- 君主 Montech 風扇（14 項）
- 美洲獅 COUGAR 風扇（8 項）
- 振華 Super Flower 風扇（11 項）
- 威剛 XPG 風扇（14 項）
- 追風者 Phanteks 機殼風扇/配件（22 項）
- 大飛 darkFlash 風扇（15 項）
- 喬思伯 JONSBO 風扇（28 項）
- 利民 Thermalright 機殼風扇(索摩樂)【未列示型號請詢問】（8 項）
- 鎌刀 Scythe 機殼風扇【全品項三年保固】（5 項）
- 旋剛 Sharkoon 機殼風扇（2 項）
- 聯力 LIAN LI 機殼風扇/配件（25 項）
- 酷碼 CoolerMaster 機殼風扇（10 項）
- 恩傑 NZXT 機殼風扇/配件【未列示型號請詢問】（10 項）
- 海盜船 CORSAIR 機殼風扇/配件【未列示型號請詢問】（2 項）
- 曜越 Thermaltake 機殼風扇/配件（6 項）
- 貓頭鷹 Noctua 機殼風扇【保固六年】【未列示型號請詢問】（21 項）
- 轉接支架、擴充周邊（9 項）
- 控制器、集線器、分接線（8 項）
- RGB燈條、發光套件（16 項）
- 火鳥 BitFenix 電源供應器線材（1 項）
- 銀欣 SilverStone 電源供應器線材【客訂】（7 項）
- 曜越 Thermaltake 電源供應器編織線 【客訂】（1 項）
- 【周邊活動熱賣專區】（14 項）
- 【超值入門款鍵盤滑鼠組】（10 項）
- Ducky One X 系列（4 項）
- Ducky OK-M 系列（4 項）
- Ducky Origin 系列 機械式鍵盤 【台灣製造】（14 項）
- 華碩 ROG/TUF 鍵盤（32 項）
- 微星 鍵盤（14 項）
- Cherry 原廠 機械式鍵盤（58 項）
- Razer 鍵盤（25 項）
- 君主 Montech 鍵盤（10 項）
- 大飛 darkFlash 鍵盤（3 項）
- Keychron 鍵盤（24 項）
- Varmilo 鍵盤（3 項）
- Lexking 雷斯特 機械式鍵盤（5 項）
- Glorious 鍵盤（3 項）
- 美洲獅 Cougar 鍵盤（4 項）
- 亞碩(Power Master) 鍵盤（5 項）
- Gigastone 鍵盤（4 項）
- RK(ROYAL KLUDGE)機械式鍵盤（7 項）
- 首席玩家 1st Player 機械式鍵盤（5 項）
- HyperX 鍵盤（3 項）
- B.Friend 鍵盤（7 項）
- 海盜船 Corsair 鍵盤（11 項）
- irocks 鍵盤（68 項）
- 羅技 鍵鼠組（22 項）
- 羅技 商務鍵盤（24 項）
- 羅技 電競鍵盤（40 項）
- 電競桌/升降桌 系列【客訂指送】（32 項）
- 華碩 ROG 電競椅【客訂指送】（7 項）
- 微星 龍魂電競椅【客訂指送】（3 項）
- Cougar 電競椅【客訂指送】外島 離島無配送 偏遠地區需額外收運費（46 項）
- 亞碩(Power Master) 電競椅 外島 離島無配送 偏遠地區需額外收運費（2 項）
- Fractal Design 電競椅（4 項）
- 威剛 XPG 電競椅 無電梯時物流司機商品無法搬運上樓服務 請見諒!!!（2 項）
- irocks 電競椅【客訂指送】電競椅 無電梯時物流司機商品無法搬運上樓服務 請見諒!!!（44 項）
- Razer 電競椅 [捷元代理-三年保固]（12 項）
- Marsrhino 火星犀牛 電競椅/沙發 貨運司機沒有商品搬運上樓服務，請見諒！（13 項）
- 海盜船 電競椅【客訂指送】捷元代理（5 項）
- ThunderX3 電競椅（11 項）
- 搖桿 遊戲周邊（34 項）
- 方向盤 方向盤支架 賽車座艙 賽車組套件組（20 項）
- 【周邊活動促銷專區】（10 項）
- 華碩 ROG 滑鼠（26 項）
- 華碩 TUF 滑鼠（2 項）
- MSI 微星 滑鼠（22 項）
- Razer 滑鼠（35 項）
- SteelSeries 滑鼠（3 項）
- EndGame Gear 滑鼠（7 項）
- darkFlash 滑鼠（8 項）
- 櫻桃 Cherry 滑鼠（3 項）
- Glorious 滑鼠（6 項）
- Turtle Beach 滑鼠（6 項）
- 美洲獅 Cougar 滑鼠（10 項）
- 亞碩(Power Master) 滑鼠（2 項）
- Gigastone 滑鼠（6 項）
- HyperX 滑鼠（9 項）
- Zowie 滑鼠（7 項）
- 海盜船 Corsair 滑鼠（7 項）
- LEXMA 滑鼠（7 項）
- irocks 滑鼠（21 項）
- 簡報器（7 項）
- 羅技 電競滑鼠（45 項）
- 羅技 商務滑鼠（48 項）
- 鼠墊 系列（44 項）
- XP-PEN 數位繪圖板(1年保固)（4 項）
- Wacom 數位繪圖板(1年保固)（2 項）
- 【網通促銷專區】（2 項）
- 智慧家庭 (Tapo T110 T100 須搭配 Tapo 智慧網關)（10 項）
- 電力線網路(HomePlug)（2 項）
- 內接式有線網路卡（7 項）
- 外接式有線網路卡（8 項）
- 10/100Mbps 集線器 / 交換器（5 項）
- 1Gb 集線器 / 交換器（37 項）
- 2.5Gb/10Gb 交換器（12 項）
- 整合式防火牆/網路VPN 路由器（1 項）
- WIFI無線延伸/分享(簡易型)網路設備（8 項）
- 4G＆5G LTE 無線路由器/SIM卡（15 項）
- 單頻.無線路由器/AP基地台（3 項）
- AC Wi-Fi 5 雙頻 系列無線路由器/AP基地台（7 項）
- Wi-Fi 6 雙頻 / 三頻 系列無線路由器/AP基地台（14 項）
- Wi-Fi 6E＆7 三頻 系列無線路由器/AP基地台（32 項）
- Mesh網狀路由器 無線新技術（39 項）
- Wi-Fi 4 單頻USB無線網卡（3 項）
- Wi-Fi 5 AC/ Wi-FI 6&7 USB無線網卡（32 項）
- 內接式無線網卡（6 項）
- USB 藍牙接收器（6 項）
- 室內 網路攝影機 (IP Camera) 都有支援雙向語音（15 項）
- 戶外 網路攝影機 (IP Camera) 都有支援雙向語音（11 項）
- 室內戶外兩用 網路攝影機 (IP Camera) 都有支援雙向語音（8 項）
- 華芸 Asustor（17 項）
- QNAP 威聯通（9 項）
- QNAP 威聯通【原廠擴充配件/交換器】（5 項）
- 群暉 Synology（13 項）
- 影像擷取卡/盒/器（7 項）
- 直播控制器（1 項）
- 【影音串流，歡樂無窮】（1 項）
- 外接音效卡（3 項）
- 內接音效卡（3 項）
- 【促銷強打活動】（9 項）
- 麥克風（28 項）
- 羅技 喇叭（15 項）
- Ktnet 喇叭（5 項）
- Razer 喇叭（4 項）
- Creative 創新未來 喇叭（12 項）
- 華碩 ROG ROG/TUF 耳麥 喇叭（18 項）
- MSI 微星 耳麥（6 項）
- Razer 耳麥（29 項）
- Vivo 耳機（2 項）
- Cherry 耳機（5 項）
- Gigastone 耳機（6 項）
- HyperX 耳麥（25 項）
- Fractal Design 耳麥（2 項）
- SteelSeries 賽睿 耳麥（14 項）
- 海盜船 耳麥（8 項）
- 羅技 耳麥（47 項）
- 終極DVD燒錄器 SATA介面（1 項）
- USB DVD外接燒錄器（5 項）
- USB 外接藍光COMBO燒錄器（1 項）
- USB 外接藍光燒錄器（2 項）
- 高速 M.2外接盒（27 項）
- 2.5吋 硬碟外接盒（11 項）
- 3.5吋 硬碟外接盒（8 項）
- 磁碟陣列外接盒（5 項）
- M.2 PCIe 外接硬碟座（6 項）
- 3.5吋 / 2.5吋 外接硬碟座（9 項）
- USB3.2 Gen1 HUB（30 項）
- Docking Station（3 項）
- 5.25" 內接式讀卡機（1 項）
- USB2.0 讀卡機（4 項）
- USB3.2 Gen1 讀卡機（4 項）
- 視訊鏡頭（24 項）
- 【機車用可攜式-行車記錄器】（2 項）
- CyberPower 碩天科技 不斷電系統UPS【監控軟體須至官網下載】原廠2年保固(含電池)（6 項）
- Eaton 伊頓飛瑞 不斷電系統UPS（9 項）
- 科風 不斷電系統UPS (一年保固)（6 項）
- Apc 施耐德電機 不斷電系統UPS【全美最大UPS】原廠2年保固(含電池)（4 項）
- 連供噴墨 / 點陣式印表機（6 項）
- Thunderbolt 擴充卡（2 項）
- USB40G 擴充卡（1 項）
- USB20G 擴充卡（1 項）
- USB10G 擴充卡（1 項）
- USB5G 擴充卡（3 項）
- SATA 擴充卡（2 項）
- RS-232 / Parallel (印表機埠) 擴充卡（2 項）
- RJ-45 網路線材（41 項）
- 硬碟排線（1 項）
- Type-C 轉接/線材（58 項）
- Thunderbolt 線材（1 項）
- HDMI 轉接/線材（62 項）
- Display port 轉接/線材（37 項）
- DVI 頭/線材（5 項）
- 其他 轉接/線材（16 項）
- 外接轉接線（8 項）
- USB延長線（5 項）
- 電源多孔排插（10 項）
- KVM SWITCH 切換器（11 項）
- 影音分配器（9 項）
- 影音切換器（5 項）
- Microsoft Windows 11 隨機版 (序號類商品一經售出不接受退貨)（5 項）
- Microsoft Windows 11 彩盒版(序號類商品一經售出不接受退貨)（6 項）
- Microsoft Office 實體彩盒版 (序號類商品一經售出不接受退貨)（4 項）
- Microsoft Office ESD 數位下載版(序號類商品一經售出不接受退貨)（2 項）
- 防毒軟體 卡巴斯基 kaspersky(序號類商品一經售出不接受退貨)（4 項）
- 禮物卡【數位下載版 - 捷元、聯強代理】(序號類商品一經售出不接受退貨)（2 項）
- 福利品【已非新品不符合快換原則】-請網路下單（16 項）

## 結論

- **追蹤範圍完整**：否
- **手機版總數**：1449（9 分類、G=9 過濾後）—「約 1,449」成立
- **桌面版對應總數**：1537（對應 9 分類範圍、G=9 過濾後）
- **僅桌面版項目**：87 項（全部來自手機版頁面不存在的配件/促銷區段，核心分類無漏品）
- **僅手機版項目**：0 項（桌面版涵蓋手機版全部商品）
- **未對應桌面區段**：422 個（筆電/螢幕/機殼/周邊等，非追蹤範圍）
- **G=9 記憶卡子分類過濾無誤刪**：兩來源保留 54 / 被過濾 157，被過濾項目子分類均不含「記憶卡」（見上節）。
- **重大待辦（另開 issue）**：crawler/parser.py 與真實 m-list.php 結構不符（見 §2.1），需依真實結構重寫 parser 並以本報告 fixture 為回歸基準。
- **次要發現**：桌面版促銷含「酷幣」類型未被 crawler 建模；手機版本次快照僅見 Hot！標記。
- 註：名稱以正規化後比對（NFKC/casefold/空白收縮 + 桌面裝飾剝離），價格不參與比對（兩來源非同時快照，價格差異不列入本 spike 結論）。
- 註：G=9 過濾驗證：被過濾項目子分類均不含「記憶卡」、保留項目均含「記憶卡」（兩來源一致）。
- 註：僅桌面版項目全部來自手機版頁面不存在的配件/促銷區段（如 PCIe 延長線、SSD 散熱片、NAS 配件、主機搭購螢幕、組合包），核心分類子分類無漏品。

## 重現方式

```bash
# 1) 重新抓取並存 fixture（需網路；已存檔可略過）
.venv/bin/python scripts/ab_source_compare.py --save-html scripts/tests/fixtures

# 2) 離線重跑比對並產出報告（JSON + MD）
.venv/bin/python scripts/ab_source_compare.py

# 3) 測試（含離線管線測試，fixture 存在即跑）
.venv/bin/python -m pytest scripts/tests/test_ab_source_compare.py -v
```

> 註：`TestOfflinePipeline.test_mobile_1449_claim_and_full_desktop_coverage` 斷言手機版總數恰為 1,449——fixture 釘選（2026-08-15 快照）的驗證，重新抓取（商品增減）後應更新斷言值。
