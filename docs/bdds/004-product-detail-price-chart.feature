@product-detail @004-product-detail-price-chart
Feature: 商品詳情與歷史趨勢圖（004-product-detail-price-chart）
  作為一個 一般訪客
  我希望 從商品列表進入詳情頁，查看完整規格、目前價格與漲跌、歷史最低價，並在歷史價格趨勢圖上設定目標價線
  以便 不須自行記錄比價，一眼判斷目前價格是否值得下手

  Background:
    Given 系統已載入同 origin 的資料 API 商品資料
    And 商品「Intel i5-13600K」存在於商品資料，id 為「3f9a1c2b8e4d5f6a」

  @happy-path @smoke @p0 @e2e
  Scenario: 從列表點入詳情頁並檢視完整資訊
    Given 我位於商品列表頁
    When 我點擊商品「Intel i5-13600K」
    Then 系統載入商品詳情頁並顯示「欄位名：值」形式的完整規格
    And 系統顯示目前價格 NT$9,990
    And 系統顯示與前一筆價格的漲跌（含金額與百分比）
    And 系統顯示歷史最低價與達成日期
    And 系統渲染歷史價格趨勢圖
    And 趨勢圖支援縮放與 tooltip 懸停查價

  @happy-path @smoke @p1 @e2e
  Scenario: 設定目標價格線
    Given 我已在商品「Intel i5-13600K」詳情頁
    And 歷史價格趨勢圖已渲染
    When 我輸入目標價「9,500」並按下「設定目標價」
    Then 趨勢圖上出現標示「目標價 NT$9,500」的目標價線

  @happy-path @p1
  Scenario: 修改與清除目標價線
    Given 我已於趨勢圖設定目標價線「9,500」
    When 我修改目標價為「9,800」並重新套用
    Then 目標價線更新為「目標價 NT$9,800」
    When 我點擊「清除目標價」
    Then 目標價線自趨勢圖上消失

  @error-handling @p0 @e2e
  Scenario: 資料 API 載入失敗時顯示錯誤並可重試
    Given 資料 API 無法載入（網路或伺服器錯誤）
    When 我點擊商品「Intel i5-13600K」
    Then 系統顯示「資料載入失敗」與「重新載入」按鈕
    When 我點擊「重新載入」且載入成功
    Then 系統顯示商品詳情頁

  @error-handling @p0
  Scenario: 以無效商品 id 直接進入詳情頁
    Given 我以 URL 直接進入不存在的商品 id「8a4b2c6d1e9f3a71」
    Then 系統顯示「找不到此商品」
    And 系統提供「返回列表」連結

  @error-handling @p1
  Scenario: 商品尚無歷史資料
    Given 商品「新品 X」存在於商品資料
    And 該商品 history 陣列為空
    When 我進入商品「新品 X」詳情頁
    Then 系統顯示規格與目前價格
    And 系統不顯示趨勢圖與漲跌比較
    And 系統顯示「尚無歷史資料」

  @edge-case @p1
  Scenario Outline: 目標價輸入驗證
    Given 我已在商品詳情頁
    When 我輸入目標價「<target>」並按下「設定目標價」
    Then 系統不套用目標價線
    And 輸入框顯示紅框並提示「<message>」
    Examples:
      | target  | message                |
      | 0       | 請輸入大於 0 的有效數字 |
      | -100    | 請輸入大於 0 的有效數字 |
      | abc     | 請輸入有效數字        |
      | (空白)  | 請輸入目標價          |

  @edge-case @p2
  Scenario: 目標價超出歷史價格區間
    Given 商品「Intel i5-13600K」歷史價格介於 NT$9,990 至 NT$11,500
    When 我輸入目標價「9,000」並按下「設定目標價」
    Then 系統仍套用目標價線
    And 圖表自動擴展 Y 軸以顯示該線
    And 系統提示「目標價超出歷史區間」

  @edge-case @business-rule @p1
  Scenario Outline: 漲跌計算與呈現
    Given 商品「<product>」目前價格為 <current>
    And 前一筆價格為 <previous>
    When 我進入該商品詳情頁
    Then 系統顯示漲跌「<label>」
    Examples:
      | product          | current | previous | label                  |
      | Intel i5-13600K  | 9990    | 10500    | 降價 NT$510（-4.9%）   |
      | 記憶體 X         | 1990    | 1890     | 漲價 NT$100（+5.3%）   |
      | SSD Y            | 2990    | 2990     | 持平                   |

  @edge-case @p1
  Scenario: 只有一筆歷史價格時的功能降級
    Given 商品「新品 X」的 history 僅有 1 筆資料「2026-08-15, NT$5,990」
    When 我進入商品「新品 X」詳情頁
    Then 系統顯示目前價格 NT$5,990
    And 系統顯示「首日追蹤，尚無漲跌比較」
    And 系統顯示歷史最低價 NT$5,990（2026-08-15）
    And 趨勢圖僅顯示單一資料點

  @edge-case @p2
  Scenario: 歷史最低價於多日相同時取最早日期
    Given 商品「Z」的 history 於 2026-08-10 至 2026-08-12 連續三日皆為最低價 NT$4,500
    When 我進入商品「Z」詳情頁
    Then 系統顯示歷史最低價 NT$4,500
    And 系統顯示達成日期為最早日 2026-08-10

  @business-rule @p1
  Scenario: 規格空值欄位不顯示
    Given 商品「Intel i5-13600K」的 spec 包含 brand、model、cores、threads、base_ghz、turbo_ghz、tdp_w、socket 欄位
    And spec 中 turbo_ghz 為空值
    When 我進入該商品詳情頁
    Then 系統顯示其餘規格欄位
    And 系統不顯示 turbo_ghz 空值欄位

  @business-rule @p2
  Scenario: 顯示資料最後更新時間
    Given 商品資料的 crawled_at 為「2026-08-15T06:00:00Z」
    When 我進入任一商品詳情頁
    Then 系統顯示最後更新時間為「2026-08-15 14:00（台北時間）」

  @business-rule @p2
  Scenario: 目標價僅本次瀏覽有效
    Given 我在商品詳情頁設定目標價「9,500」
    When 我離開詳情頁再重新進入同一商品
    Then 目標價線不會再次出現，需重新輸入

  @edge-case @business-rule @p2
  Scenario: 商品已下架仍可檢視歷史
    Given 商品「停產 Z」的 status 為「gone」
    When 我進入商品「停產 Z」詳情頁
    Then 系統顯示「此商品已下架」提示
    And 系統仍顯示既有歷史趨勢圖與價格資訊
