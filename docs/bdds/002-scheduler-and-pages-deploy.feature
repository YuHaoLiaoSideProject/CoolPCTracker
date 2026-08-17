@cicd @scheduler @pages-deploy @p0
Feature: 每日排程與 GitHub Pages 部署
  作為一個系統維護者
  我希望 GitHub Actions 每日自動執行爬蟲、在資料有異動時更新資料檔並部署前端到 GitHub Pages，且必要時可手動觸發
  以便資料每天保持新鮮、頁面自動更新、部署流程零人工介入

  Background:
    Given 工作流 .github/workflows/crawl.yml 已存在並推送至 GitHub 主分支
    And 爬蟲（功能 001）已可執行並產出 data/items/{g}.json（每分類一檔、無 meta/category 欄位）、data/meta.json 與 data/daily/ 每日價格點檔
    And GitHub Pages 已設定為部署目標
    # 契約 v2（分類拆檔）：crawler 依分類 G 寫入 data/items/{g}.json（1=套裝/準系統、3=劈發價、4=CPU、5=主機板、6=記憶體、7=SSD、8=HDD、9=記憶卡、12=顯示卡）；
    # version_data 鏡像為 api/items/{g}.json；api/index.json 以 categories[] 收錄分類索引，**無 api/latest.json、無 latest_file**

  @happy-path @smoke @daily
  Scenario: 每日排程觸發且資料有異動時完成爬蟲與部署
    Given 目前時間為每日 06:00 UTC（台北 14:00）的排程時點
    When GitHub Actions 依 cron 排程自動觸發 crawl.yml
    And 爬蟲執行成功且本次資料有異動
    Then 工作流依序完成 checkout、setup-python 3.12、pip install 與爬蟲
    And commit data/ api/ 的異動並組裝 api/ 衍生層（latest / daily / trends / index）
    And 前端 build 成功並部署至 GitHub Pages
    And 工作流以成功狀態結束

  @happy-path @smoke @manual-trigger
  Scenario: 維護者手動觸發補爬成功
    Given 維護者開啟 GitHub Actions 頁面並選擇 crawl.yml
    When 維護者點擊「Run workflow」以 workflow_dispatch 手動觸發
    Then 工作流執行與每日排程相同的完整管線
    And 資料有異動時 commit data/ api/（含組裝後的 api/items/{g}.json、api/daily/、api/trends/ 與 api/index.json）
    And 前端 build 成功並部署至 GitHub Pages
    And 工作流以成功狀態結束

  @business-rule @cache-busting @regression
  Scenario Outline: 資料異動時重建 api/ 衍生層（latest/daily/trends/index）
    Given 上次部署後 api/daily/ 已有的同日價格點檔為 <同日既存>
    When 本次爬蟲產出與上次有異動的資料
    Then 工作流寫入/更新 api/daily/20260816.json（<行為>）、api/items/{g}.json（分類鏡像）與 api/index.json
    And 工作流重建 api/trends/{item_id}.json（逐商品完整歷史）並更新 api/index.json（categories[]（id/name/file/count）、daily_files[]、trends_prefix；**無 latest_file**）
    And 資料檔內含本次爬取時間 crawled_at
    Examples:
      | 同日既存      | 行為                       |
      | 無           | 新建                       |
      | 20260816.json | 覆寫（不再產生 20260816_1） |

  @business-rule @health-guard @regression
  Scenario Outline: 健康檢查擋下時不寫入 api/ 衍生層
    Given 爬蟲產出 meta.status 為 <status> 且商品總數 total 為 <total>
    When scripts/version_data.py 執行異動判定
    Then 判定 changed=false 且不寫入任何 api/ 衍生檔（api/items/{g}.json、api/daily/、api/trends/）
    And api/index.json 維持不變（保留上次成功快照）
    Examples:
      | status  | total |
      | failed  | 1449  |
      | ok      | 0     |

  @business-rule @regression
  Scenario: 資料無異動時跳過 commit 仍完成部署
    Given 本次爬蟲結果與上次資料完全一致
    When 工作流執行資料異動比對
    Then 工作流跳過 data/ 的 commit
    And 前端仍完成 Vite build 並部署至 GitHub Pages
    And 工作流以成功狀態結束

  @integration @placeholder @p2
  Scenario: 爬蟲完成後觸發 Telegram 通知整合點
    Given 爬蟲步驟以成功狀態結束
    When 工作流進入 Telegram 通知整合點（功能 006 預留）
    Then 整合點在爬蟲完成後被觸發
    And 整合點尚未實作時工作流不因此中斷

  @error-handling @regression @p0
  Scenario: 爬蟲執行失敗時保留舊資料且不部署
    Given 原價屋來源無法存取或 parser 解析失敗
    When 爬蟲步驟以失敗狀態結束
    Then 工作流停止後續步驟並標記為失敗
    And data/ 舊資料維持不變不被覆寫
    And GitHub Pages 不執行部署

  @error-handling
  Scenario: 資料 commit 失敗時工作流失敗
    Given 爬蟲執行成功且資料有異動
    When commit data/ 時發生 push 權限不足或衝突
    Then 工作流標記為失敗
    And 異動資料停留在工作目錄未提交

  @error-handling
  Scenario: 前端 build 失敗時不部署
    Given 爬蟲與資料步驟已完成
    When 前端 Vite build 以失敗狀態結束
    Then 工作流標記為失敗
    And 不執行 GitHub Pages 部署

  @error-handling
  Scenario: 部署失敗時保留上次部署版本
    Given 前端 build 執行成功
    When GitHub Pages 部署步驟失敗
    Then 工作流標記為失敗
    And 線上頁面維持上次成功部署的版本

  @edge-case @manual-trigger @regression
  Scenario: cron 排程延遲或跳過時可手動補爬
    Given GitHub Actions 排程延遲或跳過導致今日尚未執行
    When 維護者以 workflow_dispatch 手動觸發工作流
    Then 工作流執行完整管線
    And 資料新鮮度 crawled_at 更新為本次爬取時間

  @edge-case @robustness
  Scenario: 排程與手動並發觸發時不產生 commit 衝突
    Given 排程與手動觸發使兩次 run 同時進入寫入階段
    When 兩次 run 嘗試 commit data/
    Then 工作流以 concurrency 控制確保同一時間僅一個 run 執行寫入
    And 資料檔不發生 commit 衝突或檔名重複

  @edge-case @initial-setup
  Scenario: 首次執行建立初始資料檔
    Given repo 內尚無 api/items/{g}.json 與 api/daily/ 衍生檔
    When 工作流首次執行爬蟲成功並產出資料
    Then 工作流建立 api/items/{g}.json（每分類一檔，純 items 陣列）、api/daily/{date}.json、api/trends/ 與 api/index.json（categories[] 收錄全部分類）
    And api/index.json 含 crawled_at 與各分類計數
