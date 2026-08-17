@frontend @listing-search @p1 @smoke
Feature: 前端列表與搜尋篩選（frontend-listing-search）
  作為一個一般訪客
  我希望瀏覽 9 大分類、全文搜尋並套用結構化規格篩選來瀏覽商品列表
  以便快速找到目標商品並掌握目前價格與昨日漲跌

  Background:
    Given 網站已部署於 GitHub Pages，且同 origin 的資料 API 包含約 1,449 筆追蹤商品
    And 我以一般訪客身分開啟網站首頁（無需登入）
    And 首頁已完成資料載入

  @happy-path @smoke @p0
  Scenario: 進入首頁並瀏覽全部商品
    When 我查看首頁內容
    Then 左側側欄顯示 9 大分類：CPU、主機板、記憶體、顯示卡、SSD、HDD、套裝/準系統、劈發價組合區、記憶卡
    And 商品列表顯示全部 1,449 筆商品

  @happy-path @p0
  Scenario: 點擊分類瀏覽該分類商品
    When 我點擊分類側欄的「顯示卡」
    Then 商品列表僅顯示顯示卡分類的商品
    And 分類側欄高亮「顯示卡」
    And 頁面網址反映目前分類（如 ?category=GPU）

  @happy-path @smoke @p0
  Scenario Outline: 全文搜尋命中目標商品（名稱與規格欄位）
    Given 商品列表中存在名稱或規格欄位含 <關鍵字> 的商品
    When 我在搜尋框輸入「<關鍵字>」
    Then 商品列表僅顯示名稱或規格命中該關鍵字的商品
    And 列表標題顯示命中筆數
    Examples:
      | 關鍵字    |
      | RTX 4070  |
      | i5-13600K |
      | LGA1700   |

  @happy-path @p0
  Scenario Outline: 套用單一結構化規格篩選
    Given 商品列表顯示全部商品
    When 我套用規格篩選「<篩選條件>」
    Then 商品列表僅顯示規格欄位滿足 <篩選條件> 的商品
    Examples:
      | 篩選條件  |
      | VRAM≥12G  |
      | 瓦數≥750W |
      | CPU核數≥8 |

  @happy-path @p1
  Scenario: 同時套用多個篩選條件（AND 交集）
    Given 商品列表顯示全部商品
    When 我套用規格篩選「VRAM≥12G」
    And 我再套用規格篩選「瓦數≥750W」
    Then 商品列表僅顯示同時滿足 VRAM≥12G 且瓦數≥750W 的商品

  @happy-path @p1
  Scenario: 搜尋與篩選同時作用
    Given 商品列表顯示全部商品
    When 我搜尋「RTX 4070」
    And 我套用規格篩選「VRAM≥12G」
    Then 商品列表僅顯示名稱含「RTX 4070」且 VRAM≥12G 的商品

  @happy-path @p0
  Scenario: 瀏覽商品卡片資訊
    Given 商品列表至少顯示一筆商品
    When 我檢視任一商品卡片
    Then 卡片顯示商品名稱、規格 chips、目前價格、昨日漲跌與 sparkline 迷你趨勢

  @happy-path @p1
  Scenario: 清除全部搜尋與篩選條件
    Given 我已套用搜尋「RTX 4070」與篩選「VRAM≥12G」
    When 我點擊「清除全部條件」
    Then 搜尋框清空且篩選條件移除
    And 商品列表顯示目前分類下的完整商品集合

  @happy-path @p1
  Scenario: 直接以分類頁網址進入
    When 我直接開啟含分類參數的網址（如 ?category=GPU）
    Then 頁面載入後直接顯示該分類的商品列表
    And 分類側欄高亮對應分類

  @error-handling @smoke @p0
  Scenario: 資料 API 載入失敗
    Given 網路連線中斷或資料 API 回應 404
    When 我開啟網站首頁
    Then 列表區域顯示「資料載入失敗」與「重試」按鈕
    And 頁面其餘 UI（側欄、搜尋框）仍正常顯示，不產生白畫面

  @error-handling @p1
  Scenario: 資料格式錯誤
    Given 資料 API 內容被截斷而無法解析
    When 我開啟網站首頁
    Then 列表區域顯示「資料格式錯誤」提示
    And 頁面不產生白畫面

  @error-handling @p0
  Scenario: 搜尋無結果
    Given 商品列表中沒有任何商品的名稱或規格包含「量子電腦」
    When 我在搜尋框輸入「量子電腦」
    Then 列表顯示空狀態「沒有符合『量子電腦』的商品」
    And 顯示「清除搜尋」按鈕

  @error-handling @p1
  Scenario: 篩選組合無結果
    Given 商品列表中沒有任何商品同時滿足 VRAM≥24G 且瓦數≥1200W
    When 我套用規格篩選「VRAM≥24G」
    And 我再套用規格篩選「瓦數≥1200W」
    Then 列表顯示空狀態「沒有符合條件的商品」
    And 空狀態列出已套用的篩選條件並顯示「清除篩選」按鈕

  @error-handling @p2
  Scenario: 資料過期提示
    Given 商品資料的 crawled_at 距今已超過 7 天（>7 天，與 007 新鮮度規則共用）
    When 我開啟網站首頁
    Then 頁面頂部顯示「資料可能已過期（最後更新：X）」提示橫幅
    And 商品資料仍正常顯示

  @edge-case @p2
  Scenario: 搜尋框僅輸入空白字元
    When 我在搜尋框輸入「   」（僅空白字元）
    Then 搜尋視同未執行
    And 商品列表維持目前的完整集合

  @edge-case @p2
  Scenario: 搜尋含特殊字元的關鍵字
    When 我在搜尋框輸入「RTX+4070 & 12G≥」
    Then 頁面正常回應且不發生錯誤
    And 搜尋以字面字元比對，列表顯示名稱或規格同時包含上述字元的商品（若無則顯示空狀態）

  @edge-case @p1
  Scenario: 無規格欄位的商品仍可由名稱搜尋命中
    Given 商品「XC-5500 隨機贈品主機」存在且無結構化規格欄位
    When 我在搜尋框輸入「XC-5500」
    Then 該商品仍顯示於搜尋結果

  @edge-case @p1
  Scenario: 商品缺少昨日價格時漲跌顯示「—」
    Given 某商品的歷史價格僅有一筆（無昨日價）
    When 我檢視該商品卡片
    Then 該卡片漲跌欄位顯示「—」
    And 其餘欄位（名稱、價格、sparkline）正常顯示

  @edge-case @p2
  Scenario: 分類下無任何商品
    Given 某分類當日資料為 0 筆商品
    When 我點擊該分類
    Then 列表顯示空狀態且不顯示錯誤

  @edge-case @business-rules @p1
  Scenario Outline: 篩選門檻為「大於等於」，邊界值納入結果
    Given 商品「<商品名稱>」的 <規格欄位> 為 <實際數值>
    When 我套用規格篩選「<篩選條件>」
    Then 該商品被納入篩選結果
    Examples:
      | 商品名稱         | 規格欄位 | 實際數值 | 篩選條件   |
      | 某 12G 顯示卡    | VRAM     | 12G      | VRAM≥12G   |
      | 某 8 核 CPU      | CPU 核數 | 8 核     | CPU核數≥8  |
      | 某 750W 套裝主機 | 電源瓦數 | 750W     | 瓦數≥750W  |

  @business-rules @p1
  Scenario Outline: 昨日漲跌依今日與昨日價格計算
    Given 商品「<商品名稱>」昨日價格為 <昨日價>
    And 今日價格為 <今日價>
    When 我檢視該商品卡片
    Then 漲跌欄位顯示 <顯示結果>
    Examples:
      | 商品名稱         | 昨日價 | 今日價 | 顯示結果      |
      | 某 12G 顯示卡    | 10000  | 10500  | 漲 500（紅）  |
      | 某 8 核 CPU      | 8000   | 7500   | 跌 500（綠）  |
      | 某 750W 套裝主機 | 20000  | 20000  | 持平（灰）    |

  @business-rules @p2
  Scenario: 分類側欄僅顯示追蹤範圍內的 9 大分類
    Given 網站載入完成
    When 我檢視分類側欄
    Then 側欄不顯示追蹤範圍外的分類（如電源、機殼、螢幕）

  @business-rules @p1
  Scenario: 搜尋範圍僅涵蓋名稱與規格欄位
    Given 某商品的歷史價格包含 9999 且商品名稱與規格欄位皆不含 9999
    When 我在搜尋框輸入「9999」
    Then 商品列表不顯示任何商品

  @business-rules @p1
  Scenario: 結構化篩選僅對有對應規格欄位的商品生效
    Given 商品「XC-5500 隨機贈品主機」存在且無結構化規格欄位
    When 我套用規格篩選「VRAM≥12G」
    Then 該商品不會出現在篩選結果
    And 頁面不顯示錯誤
