# language: zh-TW
@feature-021 @dashboard @watchlist
Feature: Dashboard — 快速加入追蹤清單
  作為一個追蹤用戶或裝機玩家
  我希望在商品卡片上一鍵加入追蹤清單
  以便持續監控該商品價格變動

  Background:
    Given 使用者已登入並位於 Dashboard 頁面
    And 商品列表已載入完成

  # ──────────────────────────────────────────────
  # Happy Path — §4 逐步互動說明
  # ──────────────────────────────────────────────

  @happy-path @p0
  Scenario: 未追蹤商品顯示「加入追蹤」按鈕
    # §4 步驟 1：檢視追蹤按鈕狀態 — 未追蹤
    Given 商品「MacBook Pro」尚未加入追蹤清單
    When 商品卡片渲染完成
    Then 商品「MacBook Pro」卡片顯示空心 Star icon
    And 商品「MacBook Pro」卡片顯示「加入追蹤」文字

  @happy-path @p0
  Scenario: 已追蹤商品顯示「已追蹤」按鈕
    # §4 步驟 1：檢視追蹤按鈕狀態 — 已追蹤
    Given 商品「iPhone 15」已加入追蹤清單
    When 商品卡片渲染完成
    Then 商品「iPhone 15」卡片顯示實心 Star icon
    And 商品「iPhone 15」卡片顯示「已追蹤」文字
    And 商品「iPhone 15」的追蹤按鈕為高亮狀態

  @happy-path @p0
  Scenario: 點擊「加入追蹤」成功加入追蹤清單
    # §4 步驟 2：加入追蹤清單
    Given 商品「PS5」尚未加入追蹤清單
    And 商品「PS5」有價格「15900」
    When 使用者點擊商品「PS5」的「加入追蹤」按鈕
    Then 商品「PS5」的追蹤按鈕變為實心 Star icon
    And 商品「PS5」的追蹤按鈕顯示「已追蹤」文字
    And 顯示 Toast「已加入追蹤」

  @happy-path @p0
  Scenario: 點擊「已追蹤」成功移除追蹤清單
    # §4 步驟 3：移除追蹤清單
    Given 商品「AirPods」已加入追蹤清單
    When 使用者點擊商品「AirPods」的「已追蹤」按鈕
    Then 商品「AirPods」的追蹤按鈕變為空心 Star icon
    And 商品「AirPods」的追蹤按鈕顯示「加入追蹤」文字
    And 顯示 Toast「已移除追蹤」

  @happy-path @p1
  Scenario: 加入追蹤時記錄價格快照
    # §6 邊界與限制 — 價格快照
    Given 商品「RTX 4090」尚未加入追蹤清單
    And 商品「RTX 4090」有價格「49900」
    When 使用者點擊商品「RTX 4090」的「加入追蹤」按鈕
    Then 商品「RTX 4090」的追蹤記錄包含 lastPriceSnapshot「49900」
    And 商品「RTX 4090」的追蹤記錄包含 priceSnapshotAt 時間戳

  # ──────────────────────────────────────────────
  # Error Handling — §5 異常處理
  # ──────────────────────────────────────────────

  @error-handling @p0
  Scenario: 商品無價格時點擊「加入追蹤」顯示錯誤
    # §5 異常處理表格第 4 行 — price === null
    Given 商品「Mystery Item」尚未加入追蹤清單
    And 商品「Mystery Item」無價格（price 為 null）
    When 使用者點擊商品「Mystery Item」的「加入追蹤」按鈕
    Then 顯示 Toast「該商品目前無價格，無法追蹤」
    And 商品「Mystery Item」的追蹤按鈕維持「加入追蹤」狀態

  @error-handling @p0
  Scenario: localStorage 不可用時加入追蹤顯示錯誤
    # §5 異常處理表格第 1 行
    Given 商品「Test Item」尚未加入追蹤清單
    And 商品「Test Item」有價格「1000」
    And 瀏覽器 localStorage 不可用
    When 使用者點擊商品「Test Item」的「加入追蹤」按鈕
    Then 顯示 Toast「瀏覽器未開放本機儲存，無法使用追蹤功能」
    And 商品「Test Item」的追蹤按鈕維持「加入追蹤」狀態

  @error-handling @p0
  Scenario: 儲存空間已滿時加入追蹤顯示錯誤
    # §5 異常處理表格第 2 行 — quota-exceeded
    Given 商品「Overflow Item」尚未加入追蹤清單
    And 商品「Overflow Item」有價格「2000」
    And localStorage 儲存空間已滿
    When 使用者點擊商品「Overflow Item」的「加入追蹤」按鈕
    Then 顯示 Toast「儲存空間已滿，無法新增追蹤項目」
    And 商品「Overflow Item」的追蹤按鈕維持「加入追蹤」狀態

  @error-handling @p1
  Scenario: 商品已在追蹤清單時重複加入顯示提示
    # §5 異常處理表格第 3 行
    Given 商品「Duplicate Item」已加入追蹤清單
    When 使用者點擊商品「Duplicate Item」的「已追蹤」按鈕後立即再次加入
    Then 顯示 Toast「該商品已在追蹤清單」
    And 商品「Duplicate Item」的追蹤按鈕維持「已追蹤」狀態

  # ──────────────────────────────────────────────
  # Edge Case — §6 邊界與限制
  # ──────────────────────────────────────────────

  @edge-case @p0
  Scenario: 已下架商品不顯示追蹤按鈕
    # §3 顯示條件 — status === 'gone' 不顯示追蹤按鈕
    Given 商品「Discontinued Widget」狀態為已下架
    When 商品卡片渲染完成
    Then 商品「Discontinued Widget」卡片不顯示追蹤按鈕

  @edge-case @p1
  Scenario: Toast 顯示 2 秒後自動消失
    # §6 邊界與限制 — Toast 持續時間 2 秒
    Given 商品「Toast Item」尚未加入追蹤清單
    And 商品「Toast Item」有價格「3000」
    When 使用者點擊商品「Toast Item」的「加入追蹤」按鈕
    Then 顯示 Toast「已加入追蹤」
    And Toast 在 2 秒後自動消失

  @edge-case @p1
  Scenario: DashboardCard 追蹤按鈕使用 button variant
    # §6 邊界與限制 — DashboardCard 用 button variant
    Given 商品「Dashboard Item」位於 Dashboard 頁面
    When 商品卡片渲染完成
    Then 商品「Dashboard Item」的追蹤按鈕以 button variant 顯示
    And 按鈕同時顯示 icon 與文字

  @edge-case @p1
  Scenario: 多個商品同時加入追蹤清單各自獨立
    # §6 邊界與限制 — localStorage 單例管理
    Given 商品「Item A」尚未加入追蹤清單
    And 商品「Item B」尚未加入追蹤清單
    When 使用者點擊商品「Item A」的「加入追蹤」按鈕
    And 使用者點擊商品「Item B」的「加入追蹤」按鈕
    Then 商品「Item A」顯示「已追蹤」狀態
    And 商品「Item B」顯示「已追蹤」狀態
    And 追蹤清單包含 2 項商品

  # ──────────────────────────────────────────────
  # Business Rules — §7 驗收檢查清單
  # ──────────────────────────────────────────────

  @business-rules @p0
  Scenario Outline: 追蹤按鈕狀態與追蹤清單同步
    # §7 驗收清單：未追蹤=空心 Star+「加入追蹤」、已追蹤=實心 Star+「已追蹤」
    Given 商品「<product>」的追蹤狀態為 <tracked_state>
    When 商品卡片渲染完成
    Then 追蹤按鈕顯示 <star_type> Star icon
    And 追蹤按鈕顯示「<button_text>」文字
    And 追蹤按鈕高亮狀態為 <highlight>

    Examples:
      | scenario   | product       | tracked_state | star_type | button_text | highlight |
      | 未追蹤     | MacBook Pro   | 未追蹤        | 空心      | 加入追蹤    | 非高亮    |
      | 已追蹤     | iPhone 15     | 已追蹤        | 實心      | 已追蹤      | 高亮      |

  @business-rules @p0
  Scenario Outline: 追蹤操作後按鈕狀態切換
    # §7 驗收清單：點擊[加入追蹤]→[已追蹤]、點擊[已追蹤]→[加入追蹤]
    Given 商品「<product>」目前狀態為 <initial_state>
    And 商品「<product>」有價格
    When 使用者點擊商品「<product>」的「<initial_button>」按鈕
    Then 商品「<product>」的追蹤按鈕變為 <final_star_type> Star icon
    And 商品「<product>」的追蹤按鈕顯示「<final_button_text>」文字
    And 顯示 Toast「<toast_message>」

    Examples:
      | scenario     | product       | initial_state | initial_button | final_star_type | final_button_text | toast_message |
      | 加入追蹤     | PS5           | 未追蹤        | 加入追蹤       | 實心            | 已追蹤            | 已加入追蹤    |
      | 移除追蹤     | AirPods       | 已追蹤        | 已追蹤         | 空心            | 加入追蹤          | 已移除追蹤    |

  @business-rules @p0
  Scenario Outline: 異常情況顯示對應錯誤 Toast
    # §7 驗收清單：各種異常顯示對應 toast
    Given 商品「<product>」尚未加入追蹤清單
    And <error_condition>
    When 使用者點擊商品「<product>」的「加入追蹤」按鈕
    Then 顯示 Toast「<toast_message>」

    Examples:
      | scenario                 | product        | error_condition                        | toast_message                                    |
      | 無價格無法追蹤            | Mystery Item   | 商品無價格（price 為 null）              | 該商品目前無價格，無法追蹤                          |
      | localStorage 不可用      | Storage Item   | 瀏覽器 localStorage 不可用              | 瀏覽器未開放本機儲存，無法使用追蹤功能               |
      | 儲存空間已滿              | Quota Item     | localStorage 儲存空間已滿               | 儲存空間已滿，無法新增追蹤項目                       |

  @business-rules @p0
  Scenario: 已下架商品不顯示追蹤按鈕
    # §7 驗收清單：已下架商品不顯示追蹤按鈕
    # §3 顯示條件：status === 'gone' 不顯示追蹤按鈕
    Given 商品「Gone Item」狀態為已下架
    When 商品卡片渲染完成
    Then 商品「Gone Item」卡片不顯示追蹤按鈕

  @business-rules @p1
  Scenario: 追蹤清單資料儲存於 localStorage
    # §6 邊界與限制 — localStorage 單例，key: coolpc.watchlist，version 1
    Given 商品「Store Item」尚未加入追蹤清單
    And 商品「Store Item」有價格「5000」
    When 使用者點擊商品「Store Item」的「加入追蹤」按鈕
    Then localStorage 中存在 key「coolpc.watchlist」
    And 資料格式 version 為 1
    And 追蹤記錄包含商品 id、name、price
