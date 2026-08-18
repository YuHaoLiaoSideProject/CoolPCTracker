@smoke @regression
Feature: Dashboard — 依規格分組比較商品
  作為一個裝機玩家
  我希望在 Dashboard 上依規格自動分組商品
  以便精確比較同規格商品的價格差異

  Background:
    Given 使用者已載入 Dashboard 頁面
    And   使用者已選取支援分組的分類（如「記憶體」）

  # ──────────────────────────────────────────────
  # Happy Path
  # ──────────────────────────────────────────────

  @happy-path
  Scenario: 系統自動依規格產生分組 Chips
    Given 該分類下有多種規格商品（DDR5 32GB、DDR4 16GB、DDR4 8GB）
    When  分組載入完成
    Then  顯示分組 Chips 包含「全部」「DDR5 32GB」「DDR4 16GB」「DDR4 8GB」
    And   預設選取「全部」分組 Chip

  @happy-path
  Scenario: 預設顯示最便宜商品標示 🥇
    Given 分組「DDR5 32GB」下有 3 件商品，價格分別為 1200、980、1500
    When  預設選取「DDR5 32GB」分組
    Then  商品列表按價格由低到高排序
    And   價格 980 的商品顯示 🥇 標示

  @happy-path
  Scenario: 使用者切換分組後正確篩選商品
    Given 使用者目前在「DDR5 32GB」分組
    When  使用者點擊「DDR4 16GB」分組 Chip
    Then  Chip 高亮切換至「DDR4 16GB」
    And   商品列表僅顯示 DDR4 16GB 商品
    And   列表按價格由低到高排序

  @happy-path
  Scenario: 分組切換為 client-side 篩選無 loading
    Given 使用者目前在「DDR5 32GB」分組
    When  使用者點擊「DDR4 16GB」分組 Chip
    Then  列表立即更新，無載入動畫或等待狀態

  # ──────────────────────────────────────────────
  # Business Rules
  # ──────────────────────────────────────────────

  @business-rules
  Scenario: 規格分組邏輯正確（DDR 代數 × 容量組合）
    Given 該分類商品包含以下規格組合：
      | spec_extra          | 預期分組     |
      | DDR5 / 32GB         | DDR5 32GB   |
      | DDR5 / 16GB         | DDR5 16GB   |
      | DDR4 / 16GB         | DDR4 16GB   |
      | DDR4 / 8GB          | DDR4 8GB    |
      | DDR3 / 8GB          | DDR3 8GB    |
    When  分組 Chips 載入完成
    Then  分組 Chips 依序顯示上述 5 個分組
    And   每個分組僅包含對應規格的商品

  @business-rules
  Scenario: 無規格商品歸入「其他」分組
    Given 該分類下有 2 件商品無 spec.extra 欄位
    And   有 3 件商品有完整規格
    When  分組 Chips 載入完成
    Then  分組 Chips 不包含「其他」分組（其他不出現在 Chips 中）
    And   「全部」分組包含 5 件商品（含 2 件無規格商品）

  @business-rules
  Scenario: 無規格商品在「全部」分組中按價格排序
    Given 該分類下有 3 件無規格商品，價格分別為 500、300、800
    And   有 2 件有規格商品（DDR5 32GB）
    When  使用者在「全部」分組
    Then  商品列表包含全部 5 件商品，按價格由低到高排序
    And   無規格商品（300、500、800）亦正確排序

  @business-rules
  Scenario: 每次切換分組最便宜者重新標示 🥇
    Given 「DDR5 16GB」分組最便宜商品為 A
    And   「DDR4 16GB」分組最便宜商品為 B
    When  使用者切換至「DDR4 16GB」分組
    Then  商品 B 顯示 🥇 標示
    And   商品 A 不顯示 🥇 標示

  @business-rules
  Scenario: 分組無商品時顯示空狀態
    Given 「DDR3 8GB」分組無任何商品（因篩選條件過濾後為空）
    When  使用者切換至「DDR3 8GB」分組
    Then  顯示空狀態訊息「暫無此規格商品」
    And   建議使用者切換其他分組

  # ──────────────────────────────────────────────
  # Edge Cases
  # ──────────────────────────────────────────────

  @edge-case
  Scenario: 分組 Chips 數量超過 8 個時折疊顯示
    Given 該分類有 12 種不同規格組合（加上「全部」共 13 個 Chip）
    When  分組 Chips 載入完成
    Then  僅顯示前 7 個分組 Chip + 「更多 (6) ▼」按鈕
    And   被折疊的分組不可見

  @edge-case
  Scenario: 使用者點擊「更多 ▼」展開所有分組 Chips
    Given 分組 Chips 有 13 個（含「全部」），目前僅顯示前 7 個 + 「更多 (6) ▼」
    When  使用者點擊「更多 ▼」按鈕
    Then  顯示全部 13 個分組 Chip
    And   「更多 (6) ▼」按鈕變為「收起 ▲」

  @edge-case
  Scenario: 使用者點擊「收起 ▲」重新折疊分組 Chips
    Given 分組 Chips 全部展開（共 13 個，含「全部」）
    When  使用者點擊「收起 ▲」按鈕
    Then  僅顯示前 7 個分組 Chip + 「更多 (6) ▼」按鈕
    And   按鈕恢復為「更多 (6) ▼」

  @edge-case
  Scenario: 所有分組 Chips 數量 ≤ 8 時不顯示折疊按鈕
    Given 該分類有 5 種不同規格組合（加上「全部」共 6 個 Chip）
    When  分組 Chips 載入完成
    Then  顯示全部 6 個分組 Chip
    And   不顯示「更多 ▼」按鈕

  @edge-case
  Scenario: 該分類僅有一種規格組合
    Given 該分類下所有商品均為相同規格
    When  分組 Chips 載入完成
    Then  顯示 2 個分組 Chip（「全部」+ 該規格）
    And   預設選取「全部」
    And   商品列表正確顯示該規格所有商品

  @edge-case
  Scenario: 該分類所有商品均無規格資料
    Given 該分類下所有商品均無 spec.extra 欄位
    When  分組 Chips 載入完成
    Then  不顯示任何分組 Chips（hasGroups = false）
    And   商品列表顯示全部商品

  @edge-case
  Scenario: 分組切換時間小於 300ms
    Given 使用者目前在「DDR5 32GB」分組
    When  使用者點擊「DDR4 16GB」分組 Chip
    Then  商品列表更新完成時間小於 300 毫秒
