# language: zh-TW
@feature-020 @dashboard @sparkline
Feature: Dashboard — 查看價格走勢 sparkline
  作為一個追蹤用戶或比價消費者
  我希望在商品卡片上看到價格走勢 mini sparkline
  以便快速判斷價格趨勢（漲/跌/持平）

  Background:
    Given 使用者已登入並位於 Dashboard 頁面
    And 商品列表已載入完成

  # ──────────────────────────────────────────────
  # Happy Path — §4 逐步互動說明
  # ──────────────────────────────────────────────

  @happy-path @p0
  Scenario: 有充足歷史資料的商品顯示 sparkline
    # §4 步驟 1：商品卡片載入 — ≥2 筆歷史資料
    Given 商品「MacBook Pro」有 10 筆歷史價格資料
    When 商品卡片渲染完成
    Then 商品「MacBook Pro」卡片內顯示 sparkline 圖表
    And sparkline 線條走勢與實際價格變化一致

  @happy-path @p0
  Scenario: 價格下跌時 sparkline 顯示綠色線條
    # §4 步驟 2：檢視 sparkline — 下跌 = 綠色
    Given 商品「iPhone 15」有 5 筆歷史價格資料
    And 最近兩筆價格為「32900 → 29900」（下跌）
    When 商品卡片渲染完成
    Then 商品「iPhone 15」的 sparkline 線條顏色為綠色
    And sparkline 線條走勢向下

  @happy-path @p0
  Scenario: 價格上漲時 sparkline 顯示紅色線條
    # §4 步驟 2：檢視 sparkline — 上漲 = 紅色
    Given 商品「PS5」有 4 筆歷史價格資料
    And 最近兩筆價格為「15900 → 17500」（上漲）
    When 商品卡片渲染完成
    Then 商品「PS5」的 sparkline 線條顏色為紅色
    And sparkline 線條走勢向上

  @happy-path @p0
  Scenario: 價格持平时 sparkline 顯示灰色線條
    # §4 步驟 2：檢視 sparkline — 持平 = 灰色
    Given 商品「AirPods」有 6 筆歷史價格資料
    And 最近兩筆價格為「6500 → 6500」（持平）
    When 商品卡片渲染完成
    Then 商品「AirPods」的 sparkline 線條顏色為灰色
    And sparkline 線條走勢水平

  @happy-path @p1
  Scenario: Hover sparkline 顯示 tooltip 包含日期與價格
    # §4 步驟 3：hover 查看詳情
    Given 商品「MacBook Pro」的 sparkline 已顯示
    When 使用者 hover 在 sparkline 的某個數據點上
    Then 顯示 tooltip
    And tooltip 包含該數據點的日期
    And tooltip 包含該數據點的價格

  @happy-path @p1
  Scenario: 移開 cursor 後 tooltip 隱藏
    # §4 步驟 3 後續：移開 cursor 隱藏 tooltip
    Given 商品「MacBook Pro」的 sparkline tooltip 正在顯示
    When 使用者將 cursor 移離 sparkline 區域
    Then tooltip 隱藏

  # ──────────────────────────────────────────────
  # Error Handling — §5 異常處理
  # ──────────────────────────────────────────────

  @error-handling @p0
  Scenario: 商品無歷史資料（0 筆）顯示「資料不足」
    # §5 異常處理表格第 1 行
    Given 商品「New Gadget」無歷史價格資料
    When 商品卡片渲染完成
    Then 商品「New Gadget」卡片不顯示 sparkline
    And 商品「New Gadget」卡片顯示「資料不足」文字

  @error-handling @p0
  Scenario: 商品僅 1 點歷史資料顯示「資料不足」
    # §5 異常處理表格第 2 行
    Given 商品「Rare Item」僅有 1 筆歷史價格資料
    When 商品卡片渲染完成
    Then 商品「Rare Item」卡片不顯示 sparkline
    And 商品「Rare Item」卡片顯示「資料不足」文字

  @error-handling @p0
  Scenario: 已下架商品不顯示 sparkline
    # §5 異常處理表格第 3 行
    Given 商品「Discontinued Widget」狀態為已下架
    When 商品卡片渲染完成
    Then 商品「Discontinued Widget」卡片不顯示 sparkline
    And 商品「Discontinued Widget」卡片顯示「已下架」標籤

  @error-handling @p1
  Scenario: 歷史資料跨多月時僅顯示最近 30 天
    # §5 異常處理表格第 4 行 — §6 邊界與限制「資料範圍：最近 30 天」
    Given 商品「Old Laptop」有 60 筆歷史價格資料（跨 60 天）
    When 商品卡片渲染完成
    Then sparkline 僅繪製最近 30 天的資料點
    And 超過 30 天的資料點不顯示在 sparkline 上

  # ──────────────────────────────────────────────
  # Edge Case — §6 邊界與限制
  # ──────────────────────────────────────────────

  @edge-case @p1
  Scenario: 恰好 2 筆歷史資料時顯示 sparkline
    # §6 最小資料筆數：≥2 筆才顯示
    Given 商品「Borderline」恰好有 2 筆歷史價格資料
    And 最近兩筆價格為「1000 → 800」（下跌）
    When 商品卡片渲染完成
    Then 商品「Borderline」卡片內顯示 sparkline 圖表
    And sparkline 線條顏色為綠色

  @edge-case @p1
  Scenario: 歷史資料全部相同價格時 sparkline 為灰色水平線
    # §6 趨勢判定：diff=0 持平 = 灰色
    Given 商品「Stable Price」有 5 筆歷史價格資料
    And 所有歷史價格均為「5000」
    When 商品卡片渲染完成
    Then 商品「Stable Price」的 sparkline 線條顏色為灰色
    And sparkline 線條為水平走勢

  @edge-case @p2
  Scenario: 歷史資料恰好 31 天時第 1 天資料被截斷
    # §6 資料範圍：超過 30 天的資料點不繪製
    Given 商品「31 Day Item」有 31 筆歷史價格資料（跨 31 天）
    When 商品卡片渲染完成
    Then sparkline 僅繪製最近 30 天的資料點
    And 第 1 天的資料點不出現在 sparkline 上

  @edge-case @p2
  Scenario: 價格從高到低再回升的 sparkline 走勢正確
    # §6 Sparkline 線條走勢與實際價格變化一致
    Given 商品「Fluctuate」有 5 筆歷史價格資料
    And 歷史價格序列為「100 → 80 → 60 → 70 → 90」
    When 商品卡片渲染完成
    Then sparkline 線條走勢呈現「下降→回升」的 V 型變化

  # ──────────────────────────────────────────────
  # Business Rules — §7 驗收檢查清單
  # ──────────────────────────────────────────────

  @business-rules @p0
  Scenario Outline: 趨勢顏色與 trend 型別對應
    # §7 驗收清單：價格下跌=綠色、上漲=紅色、持平=灰色
    # §6 趨勢判定：diff<0 跌（綠）、diff>0 漲（紅）、diff=0 持平（灰）
    Given 商品有 ≥2 筆歷史價格資料
    And 最近兩筆價格為 <price_change>
    When 商品卡片渲染完成
    Then sparkline 線條顏色為 <color>

    Examples:
      | scenario | price_change       | color |
      | 下跌     | 「5000 → 4500」    | 綠色  |
      | 上漲     | 「5000 → 5500」    | 紅色  |
      | 持平     | 「5000 → 5000」    | 灰色  |

  @business-rules @p0
  Scenario Outline: 資料筆數決定 sparkline 顯示模式
    # §7 驗收清單：≥2 筆顯示 sparkline、<2 筆顯示「資料不足」
    # §6 最小資料筆數：≥2 筆
    Given 商品有 <count> 筆歷史價格資料
    When 商品卡片渲染完成
    Then <display>

    Examples:
      | scenario       | count | display                                      |
      | 0 筆           | 0     | 卡片顯示「資料不足」文字                       |
      | 1 筆           | 1     | 卡片顯示「資料不足」文字                       |
      | 2 筆           | 2     | 卡片內顯示 sparkline 圖表                     |
      | 10 筆          | 10    | 卡片內顯示 sparkline 圖表                     |

  @business-rules @p0
  Scenario: 已下架商品不顯示 sparkline 且顯示「已下架」標籤
    # §7 驗收清單：已下架商品不顯示 sparkline
    # §5 異常處理表格第 3 行
    Given 商品「Discontinued」狀態為已下架
    When 商品卡片渲染完成
    Then 商品「Discontinued」卡片不顯示 sparkline
    And 商品「Discontinued」卡片顯示「已下架」標籤

  @business-rules @p1
  Scenario: Sparkline 響應式縮放隨卡片寬度
    # §7 驗收清單：Sparkline 響應式縮放（隨卡片寬度）
    # §6 Sparkline 尺寸：viewBox 100×28，寬度 100%
    Given 商品「Responsive」有 ≥2 筆歷史價格資料
    And 商品卡片寬度為容器的 100%
    When 商品卡片渲染完成
    Then sparkline 的 viewBox 為「100×28」
    And sparkline 寬度隨卡片寬度縮放

  @business-rules @p1
  Scenario: 價格資料僅繪製最近 30 天
    # §7 驗收清單：歷史資料跨多月時僅顯示最近 30 天
    # §6 資料範圍：最近 30 天
    Given 商品「Month Item」有跨多月的歷史價格資料
    When 商品卡片渲染完成
    Then sparkline 僅繪製最近 30 天的資料點
    And 超過 30 天的資料點被截斷不顯示
