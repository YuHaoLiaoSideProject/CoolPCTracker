# language: zh-TW
@crawler-health @monitoring @p2
Feature: 爬蟲健康監控（Crawler Health Monitoring）
  作為一個系統維護者
  我希望爬蟲在執行時自動偵測解析異常（商品數驟降、parser 例外），異常時保留既有資料並發送管理員 Telegram 警報
  以便網站商品資料不會被一次異常爬取覆寫，且我能掌握爬蟲健康狀態與資料新鮮度

  Background:
    Given 爬蟲已配置 9 個分類頁面（G=1, 3, 4, 5, 6, 7, 8, 9, 12）
    And 管理員 Telegram 機器人已設定
    And data/meta.json 已存在並記錄上次爬取時間與各分類商品數

  @smoke @happy-path @p0
  Scenario: 每日排程自動爬取且商品數正常，成功覆寫資料並更新健康指標
    Given 上次爬取商品總數為 1449 筆
    When 每日 06:00 UTC cron 自動觸發爬蟲
    And 9 個分類頁全部抓取並解析成功
    And 本次解析商品總數為 1452 筆（較上次增加 0.2%）
    Then data/items.json 被覆寫為本次最新資料
    And data/meta.json 記錄 crawled_at 為本次執行時間（ISO 8601）
    And data/meta.json 記錄 9 個分類各自的商品數
    And data/meta.json 記錄解析狀態為 ok
    And data/meta.json 記錄來源頁面資訊（每個分類頁的 URL 與抓取結果）
    And 系統不發送 Telegram 警報

  @happy-path @p0
  Scenario: 維護者手動觸發補爬且商品數正常，正常更新資料
    Given 維護者位於 GitHub Actions workflow 頁面
    When 維護者點擊「Run workflow」觸發 workflow_dispatch 手動補爬
    And 爬蟲執行完成且商品數正常
    Then data/items.json 被覆寫為本次最新資料
    And data/meta.json 解析狀態為 ok
    And 系統不發送 Telegram 警報

  @error-handling @p0
  Scenario: 商品數驟降超過 20% 時判定為解析異常，保留既有資料並發出警報
    Given 上次爬取商品總數為 1449 筆
    When 本次爬取完成且解析商品總數為 1100 筆（較上次減少 24%）
    Then data/items.json 不被覆寫，維持上次資料
    And data/meta.json 解析狀態記錄為 failed
    And data/meta.json 記錄異常原因「商品數驟降」及本次與上次計數
    And 系統發送 Telegram 警報給管理員，內容含異常分類與商品數對比

  @error-handling @p0
  Scenario: parser 解析過程拋出例外時保留舊資料並發出警報
    Given 原價屋改版導致 HTML 結構變更
    When parser 解析某分類頁時拋出例外
    Then data/items.json 不被覆寫，維持既有資料
    And data/meta.json 解析狀態記錄為 failed
    And data/meta.json 記錄失敗分類與例外訊息
    And 系統發送 Telegram 警報給管理員

  @error-handling
  Scenario: 全部分類頁抓取失敗時不覆寫資料並發出警報
    Given 原價屋網站暫時無法連線
    When 爬蟲抓取 9 個分類頁經重試後仍全部失敗
    Then data/items.json 不被覆寫，維持既有資料
    And data/meta.json 解析狀態記錄為 failed
    And 系統發送 Telegram 警報給管理員

  @edge-case @boundary
  Scenario Outline: 商品數驟降門檻（20%）的邊界判定
    Given 上次爬取商品總數為 <lastCount> 筆
    When 本次爬取完成且解析商品總數為 <currentCount> 筆（較上次減少 <dropPercent>）
    Then data/meta.json 解析狀態為 <expectedStatus>
    And 系統<alertBehavior> Telegram 警報
    And data/items.json <writeBehavior>

    Examples:
      | lastCount | currentCount | dropPercent | expectedStatus | alertBehavior | writeBehavior     |
      | 1000      | 900          | 10%         | ok             | 不發送          | 被覆寫             |
      | 1000      | 800          | 20%（邊界）  | ok             | 不發送          | 被覆寫             |
      | 1000      | 799          | 20.1%       | failed         | 發送            | 不被覆寫           |
      | 1000      | 500          | 50%         | failed         | 發送            | 不被覆寫           |

  @edge-case
  Scenario: 首次執行且無 meta.json 基準資料時，直接寫入不觸發驟降偵測
    Given data/meta.json 不存在（系統首次執行）
    When 爬蟲完成第一次爬取且解析商品總數為 1449 筆
    Then data/items.json 寫入首次資料
    And data/meta.json 解析狀態記錄為 ok
    And 系統不發送 Telegram 警報

  @edge-case
  Scenario: 部分分類頁抓取失敗時整體狀態為 partial，成功分類正常更新
    Given 9 個分類頁中僅「顯示卡」頁抓取失敗（經重試後仍失敗）
    When 爬蟲完成本次爬取
    Then 成功分類（其餘 8 頁）的商品資料正常更新
    And 失敗分類「顯示卡」維持既有資料
    And data/meta.json 解析狀態記錄為 partial
    And data/meta.json 記錄失敗分類清單
    And 系統發送 Telegram 警報給管理員，內容含失敗分類清單

  @business-rules @p1
  Scenario Outline: 前端依 crawled_at 顯示資料新鮮度
    Given data/meta.json 記錄 crawled_at 為 <daysAgo> 天前
    When 訪客開啟網站首頁
    Then 前端顯示「<displayText>」

    Examples:
      | daysAgo | displayText          |
      | 0       | 更新於今日           |
      | 1       | 更新於昨日           |
      | 2       | 更新於 2 天前        |
      | 7       | 更新於 7 天前        |

  @business-rules
  Scenario: 資料超過 7 天未更新時前端顯示過期提示
    Given data/meta.json 記錄 crawled_at 為 8 天前
    When 訪客開啟網站首頁
    Then 前端顯示「更新於 8 天前」
    And 前端顯示「資料可能過期」警告提示

  @business-rules
  Scenario: meta.json 記錄完整健康指標欄位
    When 任何一次爬蟲執行完成
    Then data/meta.json 記錄 crawled_at（ISO 8601 時間戳）
    And data/meta.json 記錄 9 個分類各自的商品數
    And data/meta.json 記錄解析狀態（僅為 ok、partial、failed 之一）
    And data/meta.json 記錄來源頁面資訊（每個分類頁的 URL 與抓取結果）

  @business-rules
  Scenario: 手動補爬同樣受商品數驟降偵測保護，無法繞過健康檢查
    Given 維護者手動觸發 workflow_dispatch 補爬
    When 本次解析商品數較上次低於 20%
    Then data/items.json 不被覆寫，維持既有資料
    And data/meta.json 解析狀態記錄為 failed
    And 系統發送 Telegram 警報給管理員
