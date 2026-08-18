# language: zh-TW
@dashboard @feature-017
Feature: Dashboard — 查看分類最便宜商品
  作為一個 CoolPC 比價追蹤網站的使用者
  我希望在 Dashboard 看到每個分類中最便宜的商品列表
  以便一目瞭然掌握市場行情

  Background:
    Given 使用者在任意頁面
    And API 資料已就緒（api/items/{g}.json）

  # ──────────────────────────────────────────────
  # 主要流程（Happy Path）
  # ──────────────────────────────────────────────

  @happy-path @smoke @p0
  Scenario: 透過導覽列進入 Dashboard
    When 使用者點擊導覽列「Dashboard」連結
    Then 系統顯示全頁骨架屏（skeleton loading）
    And 各分類區塊有佔位動畫

  @happy-path @smoke @p0
  Scenario: 透過直接訪問 URL 進入 Dashboard
    When 使用者直接訪問 URL "/#/dashboard"
    Then 系統顯示全頁骨架屏（skeleton loading）

  @happy-path @smoke @p0
  Scenario: 資料載入成功後顯示分類與商品
    Given 使用者已進入 Dashboard 頁面
    And 骨架屏正在顯示中
    When API 回應成功
    Then 骨架屏淡出
    And 系統顯示分類 Tab 列表
    And 預設選取第一個分類
    And 系統載入該分類的商品列表

  @happy-path @smoke @p0
  Scenario: 商品列表按價格低到高排序並顯示前 10 名
    Given 使用者已進入 Dashboard 頁面
    And 分類 Tab 已選取
    When 商品列表載入完成
    Then 商品按價格由低到高排序
    And 系統顯示前 10 名最便宜商品
    And 最便宜的商品標示 🥇 徽章

  @happy-path @p1
  Scenario: 商品卡片顯示完整資訊
    Given 商品列表已載入完成
    When 使用者瀏覽商品列表
    Then 每張卡片顯示商品名稱
    And 每張卡片顯示目前價格（千分位格式）
    And 每張卡片顯示歷史最低價
    And 每張卡片顯示規格摘要

  @happy-path @p0
  Scenario: 點擊商品卡片進入詳情頁
    Given 商品列表已載入完成
    When 使用者點擊任一商品卡片
    Then 系統導航至該商品的詳情頁面

  @happy-path @p1
  Scenario: 切換分類查看不同分類的商品
    Given 商品列表已載入完成
    And 目前選取分類為「CPU」
    When 使用者點擊分類 Tab「顯示卡」
    Then 系統載入「顯示卡」分類的商品列表
    And 商品按價格由低到高排序
    And 系統顯示前 10 名最便宜商品

  # ──────────────────────────────────────────────
  # 異常處理（Error Handling）
  # ──────────────────────────────────────────────

  @error-handling @p0
  Scenario: API 載入失敗顯示錯誤頁面
    Given 使用者已進入 Dashboard 頁面
    When API 載入失敗
    Then 系統顯示錯誤頁面
    And 錯誤訊息為「無法載入資料」
    And 系統顯示「重試」按鈕

  @error-handling @p0
  Scenario: 點擊重試按鈕重新載入資料
    Given API 載入失敗且錯誤頁面已顯示
    When 使用者點擊「重試」按鈕
    Then 系統重新嘗試載入各分類資料

  @error-handling @p1
  Scenario: 分類無商品時顯示空狀態
    Given 使用者已進入 Dashboard 頁面
    And 分類 Tab 已選取
    When 該分類無任何商品資料
    Then 系統顯示空狀態
    And 空狀態訊息為「暫無商品資料」
    And 空狀態顯示對應圖示

  # ──────────────────────────────────────────────
  # 邊界情況（Edge Cases）
  # ──────────────────────────────────────────────

  @edge-case @p1
  Scenario: 分類商品數少於 10 筆時顯示全部
    Given 使用者已進入 Dashboard 頁面
    When 該分類的商品總數少於 10 筆
    Then 系統顯示該分類的所有商品
    And 不足 10 筆時不顯示額外佔位

  @edge-case @p1
  Scenario: 價格格式化顯示千分位
    Given 商品列表已載入完成
    When 商品價格為 15800
    Then 價格顯示為「NT$ 15,800」

  @edge-case @p2
  Scenario: 歷史新低價商品顯示徽章
    Given 商品列表已載入完成
    When 某商品目前價格等於其歷史最低價
    Then 該商品顯示「歷史新低」徽章

  @edge-case @p2
  Scenario: 已下架商品顯示下架標籤
    Given 商品列表已載入完成
    When 某商品已被下架
    Then 該商品顯示「已下架」標籤
    And 該商品不顯示目前價格

  @edge-case @p2
  Scenario: 多個分類同時載入失敗
    Given 使用者已進入 Dashboard 頁面
    When 多個分類的 API 載入失敗
    Then 系統顯示錯誤頁面
    And 錯誤訊息為「無法載入資料」
    And 系統顯示「重試」按鈕

  # ──────────────────────────────────────────────
  # 商業規則（Business Rules）
  # ──────────────────────────────────────────────

  @business-rules @p0
  Scenario: Dashboard 無需登入即可訪問
    Given 使用者未登入
    When 使用者點擊導覽列「Dashboard」連結
    Then 系統允許訪問 Dashboard 頁面

  @business-rules @p0
  Scenario: 每個分類最多顯示前 10 名最便宜商品
    Given 商品列表已載入完成
    When 使用者瀏覽商品列表
    Then 系統僅顯示前 10 名最便宜商品
    And 超過 10 筆的商品不顯示

  @business-rules @p1
  Scenario: 商品按價格由低到高排序
    Given 商品列表已載入完成
    When 使用者瀏覽商品列表
    Then 第 1 件商品價格 <= 第 2 件商品價格
    And 第 2 件商品價格 <= 第 3 件商品價格
    And 依此類推

  @business-rules @p1
  Scenario: 預設選取第一個分類
    Given 商品列表已載入完成
    When 分類 Tab 列表顯示
    Then 第一個分類 Tab 為選取狀態
    And 系統自動載入該分類的商品

  @business-rules @p1
  Scenario: 最便宜商品標示金牌徽章
    Given 商品列表已載入完成
    When 商品按價格排序後
    Then 第 1 名商品顯示 🥇 徽章
