@telegram-price-alert @notification @p2
Feature: Telegram 降價通知
  作為一個 Telegram 使用者
  我希望透過 Bot 指令追蹤原價屋商品並在降價或商品消失時收到通知
  以便在商品到達目標價時可以即時購買

  Background:
    Given Bot 已從 GitHub Actions secret 取得有效 token
    And data/telegram.json 已存在且包含 bot offset 與使用者追蹤清單
    And 每日爬蟲已完成且 data/items/{g}.json 已更新當日分類商品清單

  @p0 @smoke @happy-path
  Scenario: 使用者首次使用發送 /start 取得使用說明
    Given 使用者為 Telegram 使用者且尚未與 Bot 互動過
    When 使用者發送 /start
    Then Bot 回覆使用說明
    And 說明內容包含 /watch、/unwatch、/list、/help 四個指令
    And 說明內容包含使用範例「/watch RTX 4060 9000」

  @p0 @happy-path
  Scenario: 使用者發送 /help 隨時取得使用說明
    Given 使用者已與 Bot 互動過
    When 使用者發送 /help
    Then Bot 回覆與 /start 相同的使用說明

  @p0 @happy-path
  Scenario: /watch 唯一符合商品時加入追蹤清單
    Given 當日商品清單包含「Intel i5-13600K」且目前價格為 9990 元
    And 使用者追蹤清單為空
    When 使用者發送「/watch i5-13600K 9000」
    Then Bot 回覆已加入追蹤的確認訊息
    And 確認訊息包含商品名稱「Intel i5-13600K」
    And 確認訊息包含目前價格 9990 元
    And 確認訊息包含目標價 9000 元
    And 使用者追蹤清單新增該商品且目標價為 9000 元

  @happy-path @data-driven
  Scenario Outline: 模糊比對不同關鍵字型態均能加入追蹤
    Given 當日商品清單包含「<商品名>」且目前價格為 <現價> 元
    When 使用者發送「/watch <關鍵字> <目標價>」
    Then Bot 回覆已加入追蹤的確認訊息
    And 確認訊息包含商品名稱「<商品名>」

    Examples:
      | 商品名           | 關鍵字           | 目標價 | 現價  |
      | Intel i5-13600K  | i5-13600K        | 9000   | 9990  |
      | 微星 RTX 4060 8G | rtx 4060         | 8000   | 8490  |
      | 金士頓 32G DDR5  | 金士頓 32G       | 2500   | 2688  |

  @error-handling @validation
  Scenario: /watch 缺少目標價時回覆格式錯誤
    Given 當日商品清單包含「Intel i5-13600K」
    When 使用者發送「/watch i5-13600K」
    Then Bot 回覆格式錯誤訊息
    And Bot 回覆正確格式範例「/watch 關鍵字 目標價」
    And 使用者追蹤清單不變

  @error-handling @validation
  Scenario: /watch 目標價非正整數時拒絕訂閱
    Given 當日商品清單包含「Intel i5-13600K」
    When 使用者發送「/watch i5-13600K abc」
    Then Bot 回覆目標價必須為正整數的錯誤訊息
    And 使用者追蹤清單不變

  @error-handling @validation @boundary
  Scenario: /watch 目標價為 0 元時拒絕訂閱
    Given 當日商品清單包含「Intel i5-13600K」
    When 使用者發送「/watch i5-13600K 0」
    Then Bot 回覆目標價必須為正整數的錯誤訊息
    And 使用者追蹤清單不變

  @error-handling
  Scenario: /watch 找不到符合商品時回覆提示
    Given 當日商品清單不包含關鍵字「3080Ti 水冷版」的商品
    When 使用者發送「/watch 3080Ti 水冷版 5000」
    Then Bot 回覆「找不到符合商品，請檢查關鍵字或改用較短關鍵字」
    And 使用者追蹤清單不變

  @error-handling
  Scenario: /watch 多個商品符合時回覆候選清單且不加入
    Given 當日商品清單有 3 個商品名稱包含「RTX 4060」
    When 使用者發送「/watch RTX 4060 8000」
    Then Bot 回覆候選商品清單
    And Bot 請使用者改用更精確的關鍵字重送
    And 使用者追蹤清單不變

  @business-rules
  Scenario: 重複 /watch 同一商品時更新目標價
    Given 使用者追蹤清單已包含「Intel i5-13600K」且目標價為 9500 元
    When 使用者發送「/watch i5-13600K 9000」
    Then Bot 回覆目標價已更新為 9000 元
    And 使用者追蹤清單維持一筆該商品記錄

  @business-rules @boundary
  Scenario: 訂閱時商品現價已低於目標價時提示已達標
    Given 當日商品清單包含「Intel i5-13600K」且目前價格為 8500 元
    When 使用者發送「/watch i5-13600K 9000」
    Then Bot 回覆已加入追蹤
    And Bot 提示目前價格 8500 元已低於目標價 9000 元
    And 該商品加入使用者追蹤清單

  @business-rules @boundary
  Scenario: 使用者追蹤數量達到上限時拒絕新增
    Given 使用者追蹤清單已有 20 個商品
    When 使用者發送「/watch i5-13600K 9000」
    Then Bot 回覆「追蹤數量已達上限 20 個，請先 /unwatch」
    And 使用者追蹤清單不變

  @p0 @happy-path
  Scenario: 使用者發送 /unwatch 移除追蹤商品
    Given 使用者追蹤清單包含「Intel i5-13600K」
    When 使用者發送「/unwatch i5-13600K」
    Then Bot 回覆已移除該商品
    And 使用者追蹤清單不再包含「Intel i5-13600K」

  @error-handling
  Scenario: /unwatch 商品不在追蹤清單時回覆提示
    Given 使用者追蹤清單不包含「Intel i5-13600K」
    When 使用者發送「/unwatch i5-13600K」
    Then Bot 回覆「該商品不在追蹤清單」
    And 使用者追蹤清單不變

  @p0 @happy-path
  Scenario: 使用者發送 /list 查看追蹤清單與現價
    Given 使用者追蹤清單包含「Intel i5-13600K」與「微星 RTX 4060 8G」兩個商品
    When 使用者發送 /list
    Then Bot 回覆追蹤清單
    And 每筆商品包含商品名稱、目前價格與目標價

  @edge-case
  Scenario: 追蹤清單為空時發送 /list
    Given 使用者追蹤清單為空
    When 使用者發送 /list
    Then Bot 回覆「目前沒有追蹤任何商品」
    And Bot 提示可使用 /watch 加入商品

  @error-handling
  Scenario: 發送未知指令時回覆不認識並提示 /help
    When 使用者發送「/price」
    Then Bot 回覆不認識該指令
    And Bot 提示輸入 /help 查看使用說明

  @p0 @system-trigger @happy-path
  Scenario: 每日執行時商品價格低於目標價推送降價通知
    Given 使用者追蹤清單包含「Intel i5-13600K」且目標價為 9000 元
    And 該商品目前價格為 8500 元且歷史最低價為 8200 元
    When 每日執行進入 telegram 通知階段
    Then Bot 向該使用者推送降價通知
    And 通知內容包含商品名稱「Intel i5-13600K」
    And 通知內容包含目前價格 8500 元
    And 通知內容包含目標價 9000 元
    And 通知內容包含歷史最低價 8200 元

  @system-trigger @boundary @data-driven
  Scenario Outline: 目前價格小於或等於目標價時均觸發降價通知
    Given 使用者追蹤清單包含「<商品名>」且目標價為 <目標價> 元
    And 該商品目前價格為 <目前價> 元
    When 每日執行進入 telegram 通知階段
    Then Bot 推送降價通知且通知包含目前價格 <目前價> 元

    Examples:
      | 商品名          | 目標價 | 目前價 |
      | Intel i5-13600K | 9000   | 9000   |
      | Intel i5-13600K | 9000   | 8500   |

  @p0 @system-trigger @happy-path
  Scenario: 追蹤商品從商品清單消失時推送消失通知
    Given 使用者追蹤清單包含「Intel i5-13600K」
    And 當日商品清單已無該商品
    When 每日執行進入 telegram 通知階段
    Then Bot 推送商品消失通知
    And 通知內容包含商品名稱「Intel i5-13600K」
    And 通知內容包含最後價格與消失日期

  @system-trigger @edge-case
  Scenario: 價格未達目標價且商品未消失時不發送通知
    Given 使用者追蹤清單包含「Intel i5-13600K」且目標價為 9000 元
    And 該商品目前價格為 9500 元且仍存在於當日商品清單
    When 每日執行進入 telegram 通知階段
    Then Bot 不發送任何訊息給該使用者

  @system-trigger @edge-case
  Scenario: 追蹤商品當日無價格資料時跳過且保留於追蹤清單
    Given 使用者追蹤清單包含「Intel i5-13600K」
    And 當日爬蟲未取得該商品價格資料
    When 每日執行進入 telegram 通知階段
    Then Bot 不發送降價通知
    And 該商品保留於使用者追蹤清單待下次執行比對

  @system-trigger @edge-case
  Scenario: 輪詢 getUpdates 後將新 offset 寫入 telegram.json
    Given 上次處理的 update offset 為 100
    And 伺服器有新訊息且最後一筆 update id 為 102
    When 每日執行處理完所有新訊息
    Then data/telegram.json 中 offset 更新為 102
    And 下次執行不會重複處理已讀訊息

  @system-trigger @error-handling
  Scenario: Bot token 無效時 telegram 步驟失敗且不影響資料更新
    Given Bot token 已失效
    When 每日執行進入 telegram 通知階段
    Then 系統記錄 token 錯誤日誌
    And 資料爬取與 commit 仍正常完成
    And data/telegram.json 中追蹤清單與 offset 不變

  @system-trigger @error-handling @edge-case
  Scenario: getUpdates 網路失敗時本次略過且不遺漏訊息
    Given 上次處理的 update offset 為 100
    When 每日執行輪詢 getUpdates 時發生網路錯誤
    Then 系統記錄錯誤日誌
    And offset 維持 100 不變
    And 下次執行重新輪詢時不遺漏 offset 100 之後的訊息
