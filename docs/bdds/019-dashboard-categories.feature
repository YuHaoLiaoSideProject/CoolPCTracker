# language: zh-TW
@dashboard @feature-019
Feature: Dashboard — 切換分類瀏覽
  作為一個 CoolPC 比價追蹤網站的使用者
  我希望在 Dashboard 上快速切換不同分類（CPU / 記憶體 / 顯示卡...）
  以便一次比較多個分類的最便宜商品

  Background:
    Given 使用者已載入 Dashboard 頁面
    And   API 資料已就緒

  # ──────────────────────────────────────────────
  # Happy Path
  # ──────────────────────────────────────────────

  @happy-path @smoke @p0
  Scenario: Dashboard 載入後顯示分類 Tab 列表
    Given 骨架屏已淡出
    When  分類 Tab 列表載入完成
    Then  系統顯示所有分類 Tab（CPU、記憶體、顯示卡、SSD、主機板...）
    And   第一個分類 Tab 為選取狀態（反白高亮）

  @happy-path @smoke @p0
  Scenario: 預設選取第一個分類並載入商品
    Given 分類 Tab 列表已顯示
    When  系統預設選取第一個分類
    Then  該分類 Tab 反白高亮
    And   系統載入該分類的商品列表
    And   分組 Chips 更新為對應分類的規格

  @happy-path @smoke @p0
  Scenario: 切換分類 Tab 載入新分類商品
    Given 目前選取分類為「CPU」
    And   CPU 分類商品已顯示
    When  使用者點擊分類 Tab「記憶體」
    Then  「記憶體」Tab 反白高亮
    And   「CPU」Tab 恢復為未選取狀態
    And   系統顯示載入 spinner
    And   載入完成後顯示記憶體分類商品列表
    And   分組 Chips 更新為記憶體規格（DDR3/4/5 × 容量）

  @happy-path @p1
  Scenario: 切換分類後商品列表正確更新
    Given 目前選取分類為「CPU」
    And   CPU 分類顯示 10 筆商品
    When  使用者點擊分類 Tab「顯示卡」
    Then  商品列表更新為顯示卡分類商品
    And   商品按價格由低到高排序
    And   系統顯示前 10 名最便宜商品

  @happy-path @p1
  Scenario: 切換分類後分組 Chips 正確更新
    Given 目前選取分類為「CPU」
    And   CPU 分類無分組 Chips
    When  使用者點擊分類 Tab「記憶體」
    Then  分組 Chips 更新為記憶體規格分組
    And   預設選取第一個分組 Chip

  @happy-path @p1
  Scenario: 快速連續切換分類顯示最新分類商品
    Given 目前選取分類為「CPU」
    When  使用者快速點擊分類 Tab「記憶體」
    And   使用者隨即點擊分類 Tab「顯示卡」
    Then  顯示卡分類 Tab 反白高亮
    And   顯示卡分類商品列表正確顯示
    And   記憶體分類載入被取消

  @happy-path @p2
  Scenario: 切換分類後顯示載入 spinner
    Given 目前選取分類為「CPU」
    When  使用者點擊分類 Tab「記憶體」
    Then  系統顯示載入 spinner
    And   記憶體分類商品載入完成後 spinner 淡出

  # ──────────────────────────────────────────────
  # Error Handling
  # ──────────────────────────────────────────────

  @error-handling @p1
  Scenario: 切換分類時取消上一個分類的載入請求
    Given 目前選取分類為「CPU」
    And   CPU 分類資料仍在載入中
    When  使用者點擊分類 Tab「記憶體」
    Then  系統取消 CPU 分類的載入請求
    And   系統僅顯示記憶體分類商品
    And   無殘留的 CPU 分類載入狀態

  @error-handling @p1
  Scenario: 新分類無商品時顯示空狀態
    Given 目前選取分類為「CPU」
    When  使用者點擊分類 Tab「主機板」
    And   「主機板」分類無任何商品資料
    Then  系統顯示空狀態
    And   空狀態訊息為「暫無商品資料」

  @error-handling @p1
  Scenario: 切換分類失敗時保留目前顯示的商品
    Given 目前選取分類為「CPU」且商品已顯示
    When  使用者點擊分類 Tab「記憶體」
    And   記憶體分類 API 載入失敗
    Then  系統顯示錯誤提示
    And   保留目前 CPU 分類的商品顯示

  @error-handling @p2
  Scenario: 切換分類失敗後重試
    Given 記憶體分類 API 載入失敗
    When  使用者重新點擊分類 Tab「記憶體」
    Then  系統重新嘗試載入記憶體分類資料

  # ──────────────────────────────────────────────
  # Edge Cases
  # ──────────────────────────────────────────────

  @edge-case @p1
  Scenario: 分類 Tab 超過 5 個時折疊顯示
    Given 系統有 7 個分類
    When  分類 Tab 列表載入完成
    Then  顯示前 5 個分類 Tab
    And   顯示「更多 ▼」折疊按鈕

  @edge-case @p1
  Scenario: 點擊「更多 ▼」展開所有分類 Tab
    Given 分類 Tab 有 7 個，目前僅顯示前 5 個
    And   第 6～7 個分類被折疊在「更多 ▼」按鈕後
    When  使用者點擊「更多 ▼」按鈕
    Then  顯示全部 7 個分類 Tab
    And   「更多 ▼」按鈕變為「收起 ▲」

  @edge-case @p1
  Scenario: 點擊「收起 ▲」重新折疊分類 Tab
    Given 分類 Tab 全部展開（共 7 個）
    When  使用者點擊「收起 ▲」按鈕
    Then  僅顯示前 5 個分類 Tab
    And   按鈕恢復為「更多 ▼」

  @edge-case @p1
  Scenario: 分類 Tab 數量 ≤ 5 時不顯示折疊按鈕
    Given 系統有 4 個分類
    When  分類 Tab 列表載入完成
    Then  顯示全部 4 個分類 Tab
    And   不顯示「更多 ▼」折疊按鈕

  @edge-case @p2
  Scenario: 僅有一個分類時正常顯示
    Given 系統僅有 1 個分類
    When  分類 Tab 列表載入完成
    Then  顯示該分類 Tab
    And   預設選取該分類
    And   商品列表正確顯示

  @edge-case @p2
  Scenario: 切換分類時間小於 1 秒
    Given 目前選取分類為「CPU」
    When  使用者點擊分類 Tab「記憶體」
    Then  記憶體分類商品載入完成時間小於 1 秒

  # ──────────────────────────────────────────────
  # Business Rules
  # ──────────────────────────────────────────────

  @business-rules @p0
  Scenario: 分類 Tab 列表正確顯示所有分類
    Given API 回傳分類資料
    When  分類 Tab 列表載入完成
    Then  Tab 數量與 API 回傳的分類數量一致
    And   每個 Tab 顯示對應分類名稱

  @business-rules @p0
  Scenario: 預設選取第一個分類
    Given 分類 Tab 列表已顯示
    When  Dashboard 首次載入完成
    Then  第一個分類 Tab 為選取狀態
    And   系統自動載入該分類的商品

  @business-rules @p0
  Scenario: 切換分類後 Tab 反白高亮
    Given 目前選取分類為「CPU」
    When  使用者點擊分類 Tab「記憶體」
    Then  「記憶體」Tab 反白高亮
    And   「CPU」Tab 恢復為未選取樣式

  @business-rules @p1
  Scenario: 切換分類後商品列表正確更新
    Given 目前選取分類為「CPU」
    When  使用者點擊分類 Tab「顯示卡」
    Then  商品列表僅顯示顯示卡分類商品
    And   不殘留 CPU 分類商品

  @business-rules @p1
  Scenario: 切換分類後分組 Chips 正確更新
    Given 目前選取分類為「CPU」且無分組 Chips
    When  使用者點擊分類 Tab「記憶體」
    Then  分組 Chips 更新為記憶體規格分組
    And   分組 Chips 不殘留 CPU 分類的 Chips

  @business-rules @p1
  Scenario: 切換分類時顯示載入 spinner
    Given 目前選取分類為「CPU」
    When  使用者點擊分類 Tab「記憶體」
    Then  系統顯示載入 spinner
    And   記憶體分類資料載入完成後 spinner 淡出

  @business-rules @p2
  Scenario: 切換分類時間 < 1 秒
    Given 目前選取分類為「CPU」
    When  使用者點擊分類 Tab「記憶體」
    Then  記憶體分類商品載入完成時間小於 1 秒
