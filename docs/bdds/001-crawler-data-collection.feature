@crawler @crawler-data-collection @p0 @regression
Feature: 爬蟲資料收集管道
  作為一個 系統（每日排程自動觸發）
  我希望 自動抓取原價屋手機版 9 個分類頁、解析商品、與既有資料比對並僅在異動時增量存檔
  以便 前端能展示最新商品價格與跨日歷史趨勢

  Background:
    Given 系統具備 9 個分類頁的清單：G=1 套裝/準系統、G=3 劈發價組合區、G=4 CPU、G=5 主機板、G=6 記憶體、G=7 SSD、G=8 HDD、G=9 記憶卡（子分類過濾）、G=12 顯示卡
    And 既有資料檔 data/items.json 已存在

  @smoke @happy-path @p0
  Scenario: 每日排程完整執行爬蟲管道
    Given 目前時間為每日 06:00 UTC（台北 14:00）
    And 原價屋手機版正常回應請求
    When 系統依序抓取 9 個分類頁並以 CP950 解碼
    And 系統解析出商品清單、產生商品 ID 並與既有 items.json 比對
    And 系統更新異動商品的歷史記錄
    Then 系統寫出更新後的 data/items.json 與 data/meta.json
    And meta.json 記錄 crawled_at、各分類商品計數與失敗分類

  @happy-path @p0
  Scenario: 新商品首次出現
    Given 今日分類頁包含一個既有 items.json 中不存在的商品「Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】」
    When 爬蟲執行完畢
    Then items.json 新增該商品
    And 該商品的 first_seen 與 last_seen 皆為今日
    And 該商品狀態為 in_stock
    And 該商品 history 含一筆今日價格記錄

  @happy-path
  Scenario Outline: 商品價格異動時追加歷史
    Given 商品「<商品名>」昨日價格為 <昨日價格> 元
    When 今日爬取到該商品價格為 <今日價格> 元
    Then 系統於 history 尾端 append 一筆 [今日, <今日價格>]
    And 該商品 last_seen 更新為今日
    Examples:
      | 商品名           | 昨日價格 | 今日價格 |
      | Intel i5-13600K  | 9990     | 9790     |
      | MSI RTX 4060 VENTUS 2X | 9990 | 10490    |

  @happy-path
  Scenario: 商品從分類頁消失時標記為 gone
    Given 商品「AMD R5 7600 主機板套餐」昨日存在於分類頁
    When 今日分類頁不再出現該商品
    Then 系統將該商品狀態改為 gone
    And 該商品 last_seen 保持為最後出現日（昨日）
    And 系統不新增今日價格歷史

  @business-rules @p1
  Scenario: 價格與狀態皆無異動時不追加歷史
    Given 商品「Intel i5-13600K」昨日價格為 9990 元
    And 今日價格仍為 9990 元且狀態維持 in_stock
    When 爬蟲執行完畢
    Then items.json 中該商品 history 維持原樣
    And 系統不新增今日歷史記錄

  @business-rules @p1
  Scenario Outline: 商品 ID 由主分類與正規化名稱的 hash 產生且跨日穩定
    Given 商品「<商品名稱>」屬於「<主分類>」
    When 系統以主分類與正規化名稱計算商品 ID
    Then 產生的 ID 為 hash(主分類 + 正規化名稱) 的值
    And 同一商品於不同日期重複計算時 ID 維持不變
    Examples:
      | 商品名稱                                                                   | 主分類 |
      | Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】      | CPU    |
      | 美光 Crucial DDR5-5600 16GB(8G*2) 桌上型記憶體                             | 記憶體 |
      | WD 藍標 SN580 1TB M.2 PCIe 4.0 SSD                                        | SSD    |

  @business-rules @p1
  Scenario: 爬蟲僅追蹤 9 個指定分類
    Given 原價屋手機版全站含 31 個主分類
    When 系統依分類清單發起抓取
    Then 僅抓取 G=1,3,4,5,6,7,8,9,12 共 9 個分類頁
    And 其餘分類頁不被抓取

  @business-rules @p1
  Scenario Outline: G=9 僅收錄子分類名稱含「記憶卡」的商品
    Given 系統抓取 G=9 外接硬碟/隨身碟/記憶卡混合頁
    When 系統套用子分類過濾規則處理「<子分類>」
    Then 子分類名稱含「記憶卡」者其商品被收錄，其餘被排除
    Examples:
      | 子分類                    | 收錄結果 |
      | Micro SD 記憶卡           | 收錄     |
      | SD 記憶卡                 | 收錄     |
      | CFexpress 記憶卡          | 收錄     |
      | MicroSDXC Express 記憶卡  | 收錄     |
      | 隨身碟                    | 排除     |
      | 外接硬碟                  | 排除     |

  @business-rules @p1
  Scenario: parser 過濾 disabled 加購列與贈品列
    Given 分類頁 table 同時包含一般商品列、disabled 加購列與贈品列
    When 系統解析該頁面
    Then 僅一般商品列被收錄進商品清單
    And disabled 加購列與贈品列被排除

  @business-rules @p1
  Scenario Outline: 商品標記解析
    Given 商品列文字為「<商品列文字>」
    When 系統解析該商品列的標記
    Then 系統標記該商品為<預期標記>
    Examples:
      | 商品列文字                                        | 預期標記 |
      | Hot！Intel i5-13600K【14核/20緒】...              | 「熱賣」 |
      | Intel i5-13600K【14核/20緒】... 任搭↓190          | 「促銷（任搭190）」 |
      | ↘Intel i5-13600K【14核/20緒】...                  | 「降價顯示」 |
      | Intel i5-13600K【14核/20緒】... 尾盤              | 「尾盤清倉」 |

  @business-rules @p1
  Scenario Outline: 規格解析依分類採取深度或輕量解析
    Given 商品屬於「<分類>」
    When 系統執行規格解析
    Then 系統以<解析深度>解析並輸出結構化規格欄位
    Examples:
      | 分類           | 解析深度 |
      | CPU            | 深度（品牌/型號/核心數/執行緒/時脈/TDP/腳位） |
      | 顯示卡         | 深度（品牌/晶片/VRAM/介面/長度） |
      | 記憶體         | 深度（品牌/容量/規格/時脈） |
      | SSD            | 深度（品牌/容量/介面/規格） |
      | HDD            | 深度（品牌/容量/轉速/介面） |
      | 主機板         | 深度（品牌/晶片組/腳位/尺寸） |
      | 記憶卡         | 輕量（品牌/容量/規格） |
      | 套裝/準系統    | 輕量（品牌/型號/用途） |
      | 劈發價組合區   | 輕量（組合名稱/內容摘要） |

  @error-handling @p0
  Scenario: 單一分類頁抓取失敗時沿用舊資料並繼續
    Given 爬蟲正在執行
    When G=5 主機板分類頁連線逾時且重試 3 次仍失敗
    Then 系統跳過該分類，其餘 8 個分類照常解析與更新
    And 該分類既有商品沿用舊資料
    And meta.json 標記該分類為失敗（failed_categories）

  @error-handling @p0
  Scenario Outline: 抓取失敗後重試成功恢復
    Given 原價屋手機版暫時無法回應請求
    When 系統抓取<G 值>分類頁首次失敗
    And 第<重試次數>次重試成功
    Then 系統以成功取得的頁面繼續後續解析
    And 本次 run 不視為失敗
    Examples:
      | G 值 | 重試次數 |
      | G=4  | 1 次     |
      | G=6  | 3 次     |

  @error-handling @p0
  Scenario: 商品數驟降超過 20% 時不覆寫資料並發警報
    Given 前次爬取解析出 1,449 個商品
    When 本次解析出商品數低於 1,159 個（降幅超過 20%）
    Then 系統不覆寫 data/items.json
    And 系統發送管理員 Telegram 警報
    And 既有資料保持原狀

  @error-handling @p0
  Scenario: HTML 結構改版導致解析出 0 商品
    Given 原價屋手機版頁面 HTML 結構改版
    When 系統解析 9 個分類頁皆無法解析出任何商品
    Then 系統不覆寫 data/items.json
    And meta.json 標記本次 run 失敗
    And 系統發送管理員 Telegram 警報

  @edge-case @boundary @p1
  Scenario: 分類頁為空表格
    Given 某分類頁 table 無任何商品列
    When 系統解析該頁面
    Then 該分類解析結果為 0 個商品且不拋出例外
    And 該分類沿用既有資料

  @edge-case @p1
  Scenario: CP950 解碼遇特殊字元
    Given 網頁內容含 Big5 無法完整解碼的特殊字元
    When 系統以 CP950 解碼（errors='replace'）
    Then 解碼過程不中斷
    And 無法解碼的字元以替代字元呈現

  @edge-case @p1
  Scenario: 同分類出現重複名稱商品
    Given 同一分類下兩筆商品名稱完全相同
    When 系統產生商品 ID
    Then 兩筆商品視為同一商品並以最後解析到的價格為準
    And 不產生第二筆商品記錄

  @edge-case @p1
  Scenario: 商品價格資訊缺失
    Given 商品列未標示價格
    When 系統解析該商品
    Then 商品仍依是否出現於當日清單判定狀態
    And 系統不記錄該日價格歷史

  @edge-case @p1
  Scenario: 排程延遲或跳過後手動補爬
    Given 昨日排程因 GitHub Actions 故障未執行
    When 管理者以 workflow_dispatch 手動觸發一次爬蟲
    Then 系統以當日資料正常執行完整管道
    And 商品歷史以實際爬取日記錄

  @edge-case @p1
  Scenario: 同日重複執行不重複追加歷史
    Given 今日 06:00 已執行過一次爬蟲並更新資料
    When 今日再次執行爬蟲且價格與狀態皆無異動
    Then 系統不重複 append 歷史
    And 同日同價格僅保留一筆歷史記錄
