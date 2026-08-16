@cicd @scheduler @pages-deploy @p0
Feature: 每日排程與 GitHub Pages 部署
  作為一個系統維護者
  我希望 GitHub Actions 每日自動執行爬蟲、在資料有異動時更新資料檔並部署前端到 GitHub Pages，且必要時可手動觸發
  以便資料每天保持新鮮、頁面自動更新、部署流程零人工介入

  Background:
    Given 工作流 .github/workflows/crawl.yml 已存在並推送至 GitHub 主分支
    And 爬蟲（功能 001）已可執行並產出 items.json 與 meta.json
    And GitHub Pages 已設定為部署目標

  @happy-path @smoke @daily
  Scenario: 每日排程觸發且資料有異動時完成爬蟲與部署
    Given 目前時間為每日 06:00 UTC（台北 14:00）的排程時點
    When GitHub Actions 依 cron 排程自動觸發 crawl.yml
    And 爬蟲執行成功且本次資料有異動
    Then 工作流依序完成 checkout、setup-python 3.12、pip install 與爬蟲
    And commit data/ api/ 的異動並寫入日期制快照
    And 前端 build 成功並部署至 GitHub Pages
    And 工作流以成功狀態結束

  @happy-path @smoke @manual-trigger
  Scenario: 維護者手動觸發補爬成功
    Given 維護者開啟 GitHub Actions 頁面並選擇 crawl.yml
    When 維護者點擊「Run workflow」以 workflow_dispatch 手動觸發
    Then 工作流執行與每日排程相同的完整管線
    And 資料有異動時 commit data/ api/
    And 前端 build 成功並部署至 GitHub Pages
    And 工作流以成功狀態結束

  @business-rule @cache-busting @regression
  Scenario Outline: 資料異動時寫入日期制 cache-busting 資料檔
    Given 上次部署後 api/items/ 已有的同日檔案為 <同日既存>
    When 本次爬蟲產出與上次有異動的資料
    Then 工作流寫入 api/items/<filename>.json 並更新 api/index.json
    And 資料檔內含本次爬取時間 crawled_at
    Examples:
      | 同日既存                         | filename  |
      | 無                                | 20260816  |
      | 20260816.json                     | 20260816_1 |
      | 20260816.json, 20260816_1.json   | 20260816_2 |

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
    Given repo 內尚無 api/items/*.json 快照
    When 工作流首次執行爬蟲成功並產出資料
    Then 工作流建立 api/items/{date}.json 與 api/index.json
    And 資料檔含 crawled_at 與完整商品清單
