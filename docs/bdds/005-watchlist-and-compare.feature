@frontend @p1 @watchlist @compare @regression
Feature: 追蹤清單與比價
  作為一個訪客（無需註冊帳號）
  我希望把感興趣的商品加入追蹤清單，並將最多 6 件同類商品進行比價
  以便持續掌握價格變化，做出購買決策

  背景依據：docs/interaction-flows/005-watchlist-and-compare.md
  - 主流程 A（追蹤清單管理）→ @watchlist 場景
  - 主流程 B（比價）→ @compare 場景
  - 第 5 章異常處理 / 第 6 章邊界與限制 → @edge-case / @error-handling 場景
  - 第 7 章驗收檢查清單 → @business-rules 場景

  Background:
    Given 我是訪客，無需登入即可使用網站功能

  # ============ 追蹤清單管理（主流程 A） ============

  @watchlist @smoke @happy-path
  Scenario: 從商品列表加入追蹤
    Given 網站商品資料已載入完成，瀏覽器支援 localStorage
    And 我在商品列表頁看到商品「Intel i5-13600K」
    When 我點擊該商品的「加入追蹤」按鈕
    Then 商品「Intel i5-13600K」加入我的追蹤清單
    And 按鈕狀態變為「已追蹤」並顯示「已加入追蹤」提示
    And 重新整理頁面後，該商品仍在我的追蹤清單

  @watchlist @happy-path
  Scenario Outline: 從不同入口加入追蹤
    Given 網站商品資料已載入完成，瀏覽器支援 localStorage
    And 商品「<商品名>」尚未在我的追蹤清單
    When 我在<入口>點擊「加入追蹤」
    Then 商品「<商品名>」加入我的追蹤清單
    And 對應按鈕狀態變為「已追蹤」

    Examples:
      | 入口       | 商品名               |
      | 商品列表頁 | Intel i5-13600K      |
      | 商品詳情頁 | ASUS TUF RTX 4070    |

  @watchlist @business-rules
  Scenario: 已在追蹤清單的商品不重複加入
    Given 商品「Intel i5-13600K」已在我的追蹤清單
    When 我在商品詳情頁檢視該商品
    Then 按鈕顯示「已追蹤」狀態
    And 追蹤清單中該商品只有 1 筆，不會重複新增

  @watchlist @smoke @happy-path
  Scenario: 從追蹤清單頁移除商品
    Given 我的追蹤清單依序有商品「商品A」與「商品B」
    When 我在追蹤清單頁點擊「商品A」的「移除」按鈕
    Then 「商品A」從追蹤清單移除
    And 剩餘商品維持原有順序
    And 重新整理頁面後，「商品A」仍不在追蹤清單

  @watchlist @happy-path
  Scenario: 從列表頁移除已追蹤商品
    Given 商品「Intel i5-13600K」已在我的追蹤清單
    When 我在商品列表頁點擊該商品的「已追蹤」按鈕
    Then 商品「Intel i5-13600K」從追蹤清單移除
    And 按鈕狀態變回「加入追蹤」

  @watchlist @happy-path
  Scenario: 檢視追蹤清單的價格、價差與迷你趨勢
    Given 我的追蹤清單有商品「Intel i5-13600K」
    And 該商品上次查看價格為 9,990 元，目前價格為 9,490 元
    When 我進入「我的追蹤」頁面
    Then 畫面顯示商品名稱與目前價格 9,490 元
    And 顯示價差「-500 元」並以跌價樣式標示
    And 顯示該商品的迷你趨勢圖

  @watchlist @business-rules
  Scenario: 價差以「上次查看價格」為基準
    Given 商品「商品A」上次查看價格為 10,000 元，目前價格為 10,500 元
    When 我進入「我的追蹤」頁面
    Then 顯示價差為「+500 元」並以漲價樣式標示
    And 頁面以目前價格 10,500 元更新「上次查看快照」，作為下次價差基準

  @watchlist @business-rules
  Scenario: 迷你趨勢僅顯示最近 7 日歷史
    Given 商品「Intel i5-13600K」有 10 日歷史價格
    When 我檢視追蹤清單中該商品的迷你趨勢
    Then 迷你趨勢圖僅包含最近 7 日的價格

  @watchlist @happy-path
  Scenario: 拖曳排序追蹤清單
    Given 我的追蹤清單依序有商品「商品A」「商品B」「商品C」
    When 我將商品「商品C」拖曳到第一位
    Then 追蹤清單順序變為「商品C」「商品A」「商品B」
    And 重新整理頁面後順序維持「商品C」「商品A」「商品B」

  @watchlist @edge-case
  Scenario: 追蹤清單為空時顯示引導
    Given 我的追蹤清單為空
    When 我進入「我的追蹤」頁面
    Then 畫面顯示空狀態說明與「去逛逛」引導按鈕
    And 不顯示任何商品列

  @watchlist @error-handling
  Scenario: 瀏覽器不支援 localStorage 時加入追蹤失敗
    Given 瀏覽器不支援或封鎖 localStorage
    When 我點擊商品的「加入追蹤」按鈕
    Then 畫面提示「瀏覽器未開放本機儲存，無法使用追蹤功能」
    And 商品不會加入任何清單
    And 頁面不當機

  @watchlist @error-handling
  Scenario: localStorage 空間已滿時無法新增追蹤
    Given 瀏覽器 localStorage 可用空間不足
    When 我嘗試將商品加入追蹤清單
    Then 畫面提示「儲存空間已滿，無法新增追蹤項目」
    And 原有追蹤清單內容不受影響

  @watchlist @edge-case
  Scenario: 追蹤的商品已下架
    Given 我的追蹤清單有商品「商品X」
    And 商品「商品X」已不在當日商品資料中（下架）
    When 我進入「我的追蹤」頁面
    Then 該商品顯示「已下架」標示
    And 價格欄位顯示「—」

  @watchlist @edge-case
  Scenario: 迷你趨勢歷史資料不足
    Given 商品「商品A」僅有 1 日歷史價格
    When 我檢視追蹤清單中該商品的迷你趨勢
    Then 迷你趨勢顯示「資料不足」而非圖表

  @watchlist @error-handling
  Scenario: 商品資料載入失敗時追蹤頁顯示錯誤狀態
    Given 網站商品資料載入失敗
    When 我進入「我的追蹤」頁面
    Then 頁面顯示「資料載入失敗」錯誤訊息與「重新載入」按鈕
    And 既有 localStorage 追蹤資料不受影響

  # ============ 比價（主流程 B） ============

  @compare @smoke @happy-path
  Scenario: 從列表勾選同類商品產出比較表並標示最便宜
    Given 我在顯示卡分類的商品列表頁
    And 商品「顯卡A」目前價格 8,990 元，「顯卡B」目前價格 9,990 元
    When 我勾選「顯卡A」與「顯卡B」並點擊「開始比價」
    Then 進入比價結果頁
    And 比較表並排顯示兩商品的價格與規格欄位
    And 價格最低的商品「顯卡A」標示「最便宜」

  @compare @happy-path
  Scenario Outline: 從不同入口加入比價
    Given 網站商品資料已載入完成
    And 我在<入口>
    When 我將商品「<商品名>」加入比價
    Then 比價選取清單包含「<商品名>」
    And 畫面顯示已選計數 N/6

    Examples:
      | 入口       | 商品名               |
      | 商品列表頁 | ASUS TUF RTX 4070    |
      | 商品詳情頁 | Intel i5-13600K      |

  @compare @edge-case
  Scenario: 比價選取少於 2 件無法開始
    Given 我只勾選 1 件商品加入比價
    When 我點擊「開始比價」
    Then 「開始比價」按鈕維持停用狀態
    And 畫面提示「請至少選擇 2 件商品進行比價」

  @compare @edge-case
  Scenario: 比價選取超過 6 件上限
    Given 我已勾選 6 件商品加入比價
    When 我嘗試勾選第 7 件商品
    Then 第 7 件商品無法被勾選
    And 畫面提示「最多只能比較 6 件商品」
    And 已選的 6 件商品不受影響

  @compare @business-rules
  Scenario: 比價僅限同分類商品
    Given 我已勾選 1 件 CPU 商品加入比價
    When 我嘗試勾選 1 件顯示卡商品加入比價
    Then 系統拒絕加入並提示「比價僅限同類商品」
    And 原 CPU 商品的選取不受影響

  @compare @business-rules
  Scenario: 多件同價商品並列標示最便宜
    Given 我勾選「顯卡A」與「顯卡B」進行比價
    And 兩者目前價格皆為 9,990 元
    When 我檢視比價結果表
    Then 「顯卡A」與「顯卡B」皆標示「最便宜」

  @compare @business-rules
  Scenario: 比較表依分類顯示對應規格欄位
    Given 我勾選 2 件 CPU 商品進行比價
    When 我檢視比價結果表
    Then 比較表顯示價格欄位
    And 顯示 CPU 規格欄位（核心數、執行緒、基礎時脈、超頻時脈、TDP）
    And 各商品數值並排於對應欄位

  @compare @happy-path
  Scenario: 從比價結果表加入追蹤
    Given 我已完成「顯卡A」與「顯卡B」的比價
    When 我在比價表中點擊「顯卡A」的「加入追蹤」
    Then 商品「顯卡A」加入追蹤清單
    And 該商品按鈕變為「已追蹤」

  @compare @happy-path
  Scenario: 清除比價選取
    Given 我已勾選 3 件商品加入比價
    When 我點擊「清除比價」
    Then 比價選取清單清空
    And 各商品勾選框回到未勾選狀態

  @compare @edge-case
  Scenario: 比價清單中的商品已下架
    Given 我勾選「顯卡A」與「顯卡B」進行比價
    And 商品「顯卡B」已不在當日商品資料中（下架）
    When 我檢視比價結果表
    Then 商品「顯卡B」欄位標示「已下架」
    And 最便宜標示僅在仍有價格的商品「顯卡A」上計算
