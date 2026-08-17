# 002 每日排程與 GitHub Pages 部署 — Interaction Flow

> 功能編號：002
> 功能名稱：scheduler-and-pages-deploy
> 角色：維護者 / 系統自動
> 上游文件：docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md（§3.2、§3.3、§5）

---

## 1. 功能概述

一句話：讓 GitHub Actions 每日自動執行爬蟲、在資料有異動時更新資料檔、並把前端部署到 GitHub Pages，維護者可隨時手動補爬。

核心價值：**資料每天保持新鮮、頁面自動更新、部署全程零人工介入**，即使排程失誤也有手動補爬的保險。

---

## 2. 使用者與場景

| 項目 | 內容 |
|------|------|
| **角色** | 維護者（系統管理者）；主要執行者為「系統自動」（GitHub Actions 排程） |
| **觸發入口** | ① 每日 06:00 UTC（台北 14:00）cron 自動觸發 ② 維護者在 GitHub Actions 頁面對 crawl.yml 點「Run workflow」手動觸發（workflow_dispatch） |
| **前置條件** | ① .github/workflows/crawl.yml 已存在並推送至主分支 ② 爬蟲（功能 001）已可執行 ③ GitHub Pages 已設定為部署目標 ④ repo 具備 push 權限（GITHUB_TOKEN） |
| **使用情境** | 每天下午兩點網站自動更新價格資料；排程延遲、跳過或爬蟲出錯時，維護者手動觸發補爬 |

---

## 3. 操作流程圖

```mermaid
flowchart TD
    Cron([每日 06:00 UTC 排程自動觸發]) --> Checkout[1. checkout 取得最新程式碼]
    Manual([維護者手動觸發 workflow_dispatch]) --> Checkout
    Checkout --> Py[2. setup-python 3.12]
    Py --> Pip[3. pip install 安裝相依套件]
    Pip --> Crawl[4. 執行爬蟲（功能 001）]
    Crawl --> Diff{5. 資料有異動?}
    Diff --> TG[[6. Telegram 通知整合點（功能 006 預留，commit 前）]]
    TG -->|有異動| Commit[7a. commit data/ api/：items/{g}.json + daily/ + trends/ + index.json + meta.json + telegram.json]
    TG -->|無異動| Skip[7b. 跳過 commit，保留上次資料]
    Commit --> Build[8. 前端 Vite build]
    Skip --> Build
    Build --> Deploy[9. 部署 GitHub Pages]
    Deploy --> Done([10. Workflow 完成，頁面已更新])

    Crawl -.失敗.-> EC[爬蟲失敗：run 標記失敗，保留舊資料不覆寫]:::err
    Commit -.失敗.-> EK[commit 失敗：run 標記失敗，資料未提交]:::err
    Build -.失敗.-> EB[build 失敗：run 標記失敗，不部署]:::err
    Deploy -.失敗.-> ED[部署失敗：run 標記失敗，保留上次部署]:::err

    classDef err fill:#fff0f0,stroke:#e00
```

---

## 4. 逐步互動說明

### 步驟 1：觸發工作流（排程或手動）

| | 描述 |
|---|------|
| **觸發** | 系統每日 06:00 UTC（台北 14:00）由 GitHub Actions cron 自動觸發；或維護者在 Actions 頁面對 crawl.yml 點「Run workflow」手動觸發 |
| **操作前** | 工作流檔案已推送至主分支；crawler（001）已可執行 |
| **系統回應** | GitHub Actions 建立一個 run，進入待執行佇列 |
| **操作後** | run 開始執行，Actions 頁面顯示執行中狀態 |
| **下一步** | 步驟 2：checkout |

### 步驟 2：checkout 取得最新程式碼

| | 描述 |
|---|------|
| **觸發** | run 自動執行 checkout 步驟 |
| **操作前** | run 已啟動（步驟 1） |
| **系統回應** | 將主分支最新程式碼（含工作流、爬蟲、前端原始碼）複製到執行環境 |
| **操作後** | 執行環境具備最新程式碼，可開始後續步驟 |
| **下一步** | 步驟 3：setup-python 3.12 |

### 步驟 3：setup-python 3.12

| | 描述 |
|---|------|
| **觸發** | run 自動執行 setup-python 步驟 |
| **操作前** | 最新程式碼已就緒（步驟 2） |
| **系統回應** | 安裝並啟用 Python 3.12 執行環境 |
| **操作後** | 執行環境可執行 Python 爬蟲 |
| **下一步** | 步驟 4：pip install |

### 步驟 4：pip install 安裝相依套件

| | 描述 |
|---|------|
| **觸發** | run 自動執行 pip install |
| **操作前** | Python 3.12 已就緒（步驟 3） |
| **系統回應** | 依 pyproject.toml 安裝 httpx、selectolax 等爬蟲相依套件 |
| **操作後** | 爬蟲可被呼叫執行 |
| **下一步** | 步驟 5：執行爬蟲 |

### 步驟 5：執行爬蟲（功能 001 整合）

| | 描述 |
|---|------|
| **觸發** | run 自動執行爬蟲主程式 |
| **操作前** | 相依套件已安裝（步驟 4） |
| **系統回應** | 抓取 9 個分類頁 → 解析 1,449 商品 → 與既有資料 diff → 更新 data/items/{g}.json 各分類檔與 meta.json（含 crawled_at） |
| **操作後** | 爬取完成；若成功，資料檔反映本次爬取結果 |
| **下一步** | 步驟 6：資料異動判斷與 commit |

### 步驟 6：資料異動判斷與版本化

| | 描述 |
|---|------|
| **觸發** | version_data 比對本次爬取結果與上次各分類檔（讀 `api/items/{g}.json` 各分類檔與 `api/daily/` 差集判定異動；契約 v2：無 api/latest.json） |
| **操作前** | 爬蟲已完成（步驟 5） |
| **系統回應** | 輸出異動判定（changed）與新檔名（filename = {YYYYMMDD}.json，取自台北日期）；**此步不 commit**（0 衍生層檔不在此確認） |
| **操作後** | 工作目錄含本次資料與組裝後之 api/ 衍生層（items/{g}.json + daily/ + trends/ + index.json），待 telegram 階段與 commit |
| **下一步** | 步驟 7：Telegram 通知整合點（commit 前） |

### 步驟 7：Telegram 通知整合點（功能 006 預留）

| | 描述 |
|---|------|
| **觸發** | 爬蟲與版本化步驟成功結束後自動觸發（異動或無異動皆會經過） |
| **操作前** | 爬蟲已完成（步驟 5）；版本化已完成（步驟 6） |
| **系統回應** | 呼叫 Telegram 通知整合點；目前為預留佔位，尚未實作時不中斷 run（實際通知於功能 006 實作）；telegram.json（offset/追蹤清單）異動於步驟 7a 併入本次 commit |
| **操作後** | run 繼續往 commit 前進 |
| **下一步** | 步驟 7a/7b：資料 commit 或跳過 |

### 步驟 7a/7b：資料 commit（分支）

| | 描述 |
|---|------|
| **觸發** | telegram 階段完成後依異動判定分支 |
| **操作前** | 爬蟲與 telegram 已完成（步驟 5-7） |
| **系統回應** | **有異動（7a）**：commit data/ api/（items/{g}.json + daily/ + trends/ + index.json + meta.json + telegram.json）；**無異動（7b）**：跳過 commit，保留上次資料（不產生空 commit） | |
| **操作後** | 有異動 → 資料檔已推回主分支；無異動 → 工作目錄無變化 |
| **下一步** | 步驟 8：前端 Vite build |

### 步驟 8：前端 Vite build

| | 描述 |
|---|------|
| **觸發** | run 自動執行前端 build |
| **操作前** | 資料步驟已完成（步驟 6-7，含 commit 7a/7b） |
| **系統回應** | 對 web/ 執行 Vite build，產出靜態檔案 |
| **操作後** | build 產物就緒，等待部署 |
| **下一步** | 步驟 9：部署 GitHub Pages |

### 步驟 9：部署 GitHub Pages

| | 描述 |
|---|------|
| **觸發** | run 自動執行部署步驟 |
| **操作前** | build 產物已產生（步驟 8） |
| **系統回應** | 將 build 產物發布至 GitHub Pages |
| **操作後** | 線上網站更新為最新版本 |
| **下一步** | 步驟 10：完成與新鮮度驗證 |

### 步驟 10：完成與新鮮度驗證

| | 描述 |
|---|------|
| **觸發** | 部署完成後 run 收尾 |
| **操作前** | 部署成功（步驟 9） |
| **系統回應** | run 標記成功；使用者開啟網站可看到本次 crawled_at 的資料 |
| **操作後** | 網站可存取，資料新鮮度顯示為本次爬取時間 |
| **下一步** | 等待下一次排程（或維護者手動補爬） |

---

## 5. 異常處理

| 錯誤情境 | 使用者看到的回饋 | 恢復路徑 |
|----------|------------------|----------|
| 爬蟲執行失敗（原價屋改版、網路問題、parser 錯誤） | Actions run 標記紅色失敗；crawled_at 停留在上次成功時間；舊資料不被覆寫 | 檢查 run log → 修正 parser 或重試 → 手動 workflow_dispatch 補爬 |
| 資料無異動 | run 顯示「跳過 commit」（屬正常，非錯誤） | 不需處理；視為正常當日結果 |
| commit data/ 失敗（push 權限不足、並發衝突） | run 標記失敗，資料未提交 | 檢查 GITHUB_TOKEN 權限與並發設定 → 修正後手動重跑 |
| Vite build 失敗 | run 標記失敗，不執行部署 | 檢查前端相依套件與程式碼 → 修正後重跑 |
| GitHub Pages 部署失敗 | run 標記失敗，線上維持上次成功部署 | 檢查 Pages 部署設定與權限 → 修正後重跑部署 job |
| cron 排程延遲或跳過 | 當日沒有 run 或 run 延遲啟動 | 維護者手動 workflow_dispatch 補爬，資料新鮮度照常更新 |
| 排程與手動同時觸發（並發） | 若無 concurrency 控制，可能發生 commit 衝突或檔名重複 | concurrency group 確保同一時間僅一個 run 執行寫入 |

---

## 6. 邊界與限制

| 項目 | 限制說明 |
|------|----------|
| **更新頻率** | 每日一次（06:00 UTC = 台北 14:00）；手動觸發可隨時補爬，不受每日一次限制 |
| **cron 精準度** | GitHub Actions 排程不保證分秒不差，可能延遲數分鐘或偶發跳過（官方不提供 SLA） |
| **並發寫入** | 排程與手動同時觸發時，需以 concurrency 控制避免 commit 衝突；同一時間僅允許一個 run 進入寫入階段 |
| **資料檔命名** | 契約 v2（分類拆檔）：`api/items/{g}.json` 各分類鏡像（純 items 陣列、鏡像 data/items/{g}.json；**無 api/latest.json、無 latest_file**）；每日價格點鏡像 `api/daily/YYYYMMDD.json`；逐商品全歷史 `api/trends/{item_id}.json`；索引 `api/index.json`（categories[]（id/name/file/count）、daily_files[]、trends_prefix） |
| **資料新鮮度** | 資料檔含 crawled_at；爬蟲失敗當日不更新，網站顯示上次成功爬取時間 |
| **失敗保護** | 任一關鍵步驟失敗即停止後續步驟：爬蟲失敗不覆寫舊資料、build 失敗不部署、部署失敗保留上次版本 |
| **版本控制** | 資料檔納入 git 版控（每日一點累積歷史，含平價日）；每日成功爬取即新增 `data/daily/{date}.json` 並異動 items.json/api 衍生層 → 每日 commit 一次資料更新 |
| **頻寬額度** | GitHub Pages 免費額度 100GB/月，超出僅暫停服務，成本可控 |
| **Telegram 通知** | 本功能僅預留整合點；實際通知邏輯於功能 006 實作（爬蟲完成後觸發） |

---

## 7. 驗收檢查清單

- [ ] 每日 06:00 UTC（台北 14:00）cron 自動觸發 crawl.yml
- [ ] 維護者可透過 workflow_dispatch 手動觸發（Actions 頁面有「Run workflow」按鈕）
- [ ] 工作流依序執行：checkout → setup-python 3.12 → pip install → 爬蟲 → build → 部署
- [ ] 資料有異動時才 commit data/，無異動時跳過 commit（不產生空 commit）
- [ ] 資料有異動時組裝並 commit api/ 衍生層：`api/items/{g}.json`（各分類鏡像）+ `api/daily/YYYYMMDD.json` + `api/trends/` + `api/index.json`
- [ ] api/index.json 記錄 categories[]（id/name/file/count）、daily_files[] 完整日期檔清單與 trends_prefix；無 latest_file；meta.json 記錄最後爬取時間
- [ ] 資料含 crawled_at，前端可顯示資料新鮮度
- [ ] 爬蟲完成後觸發 Telegram 通知整合點（功能 006 預留，未實作不中斷 run）
- [ ] 爬蟲失敗 → run 標記失敗、舊資料不覆寫、不部署
- [ ] build 失敗 → run 標記失敗、不部署
- [ ] 部署失敗 → run 標記失敗、線上維持上次成功版本
- [ ] 並發 run 有 concurrency 控制，不產生 commit 衝突或檔名重複
- [ ] 首次執行（repo 尚無衍生層）建立 api/items/{g}.json（全部分類）、api/daily/{date}.json、api/trends/ 與 api/index.json（含 categories[]）
- [ ] 部署完成後 GitHub Pages 網站可存取，且資料為最新版本（crawled_at 為本次爬取時間）
