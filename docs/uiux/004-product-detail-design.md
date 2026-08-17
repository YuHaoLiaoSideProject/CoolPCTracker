# 004 商品詳情與歷史趨勢圖 — UI/UX 設計文件

> 功能：商品詳情頁（`/product/:id`）+ lightweight-charts 歷史趨勢圖 + 目標價線（session 級）
> 對應規格：`docs/development/004-product-detail-price-chart.md`（§2.1–2.6、§6、§7）
> 操作流程：`docs/interaction-flows/004-product-detail-price-chart.md`
> BDD：`docs/bdds/004-product-detail-price-chart.feature`
> 互動稿：`docs/uiux/004-product-detail-design.html`
> 輸出形式：完整規格（`-design.html`）；無既有 UI 可比對，不做 BEFORE/AFTER 比較稿

---

## 1. 現況審計

### 1.1 審計範圍與方法

| 項目 | 結果 |
|------|------|
| 審計對象 | `web/` 前端目錄（003/004/005 的實作綠地） |
| 審計方法 | 讀取 `web/src/` 全部原始碼（`main.ts`、`vite-env.d.ts`、`vite.config.ts`、`index.html`）＋資料契約（`data/items.json` 結構、`types/item.ts` 型別定義於 004 規格） |
| 實測 | 無既有 UI 元件可實測 DOM 尺寸；控制元件高度宣稱以本稿互動檔實測（playwright `getBoundingClientRect`）為準 |

### 1.2 審計表

| # | 現況事實 | 嚴重度 | 位置 |
|---|----------|--------|------|
| A1 | `web/` 為綠地：僅 Vite 骨架（`src/main.ts` 最小消費實作：渲染版本號＋fetch `data/meta.json` 顯示 crawled_at），**無任何既有 UI 元件、無 CSS、無路由** | —（事實） | `web/src/main.ts`、`web/src/vite-env.d.ts` |
| A2 | `docs/uiux/` 尚未存在，本功能為系列首份（與 003 平行） | —（事實） | `docs/uiux/` |
| A3 | 資料契約已定型：`items.json` 的 `history` 為 compact `[d,p]` 每日一點序列（含平價日、跨日連續）；`spec` 欄位可缺省 | —（上游契約） | 001 crawler `store.py`、004 規格 §2.2 |
| A4 | 上游已決定：圖表庫 lightweight-charts（原 ECharts 已演進）、目標價 session 級不持久化、time 軸非等間距如實呈現、空值規格欄位隱藏、降價綠/漲價紅/持平灰 | —（既有決策） | Tech Decision §3.1/§3.4、004 規格 §2.4–2.6 |

**結論**：本功能為全新設計，所有視覺與互動皆從零定義；沿用專案共用 Design Token 表（與 003 平行子任務一致，見 §3），確保兩功能上線後外觀一致。

---

## 2. 設計原則

1. **一致性（Consistency）** — 全站共用同一組 Design Token（`--brand`、`--price-up/down/flat`、`--h`、`--fs`…）；詳情頁與 003 列表共用 `useItems`／`useCrawledAt`／`types/item.ts`，錯誤與空狀態語義一致，不另起爐灶。
2. **漸進式揭露（Progressive Disclosure）** — 預設只展示「目前價＋漲跌＋歷史最低」三大決策資訊；目標價輸入、縮放／平移、完整歷史細節屬於進階操作，由使用者主動觸發（點擊、懸停、滾輪）。
3. **Contextual 不佔位（Contextual, Not Placeholder）** — 目標價是「期望線」語意，用琥珀色 dashed 目標價線（price line）與漲跌綠/紅明確區分；「資料不足」情境（history 空／僅一筆）以降級呈現而非空白畫面。
4. **語意化圖示（Semantic Icons）** — 圖示一律 inline SVG（`aria-hidden`）；漲跌方向用 SVG 箭頭，顏色僅為輔助，不以顏色單獨傳達（WCAG 1.4.1）。
5. **觸控與鍵盤優先（Touch & Keyboard First）** — desktop 控制元件 36px、mobile ≤767px 44px（WCAG 2.5.5）；目標價可 Enter 提交；所有互動有 focus ring（WCAG 2.4.7）。

---

## 3. Design Token 表（共用，與 003 一致，不可更動）

### 3.1 色彩與基礎

| Token | 值 | 用途 |
|-------|-----|------|
| `--brand` | `#1f6feb` | 品牌主色：主按鈕、focus ring、active 狀態 |
| `--brand-soft` | `#e8f0fe` | 品牌淺底：focus ring 光圈、標籤底 |
| `--price-up` | `#e02424` | 漲價（紅 ▲） |
| `--price-down` | `#18933f` | 降價（綠 ▼） |
| `--price-flat` | `#6b7280` | 持平（灰 —） |
| `--bg` | `#f7f8fa` | 頁面背景 |
| `--surface` | `#ffffff` | 卡片表面 |
| `--border` | `#e5e7eb` | 邊框 |
| `--text` | `#1f2937` | 主文字 |
| `--text-dim` | `#6b7280` | 次要文字 |
| `--warn-bg` | `#fff7e6` | 警告底（目標價超區間、過期提示） |
| `--warn-border` | `#f5c518` | 警告邊框 |
| `--warn-text` | `#8a6d00` | 警告文字 |
| `--radius` | `10px` | 卡片圓角 |
| `--shadow` | `0 1px 3px rgba(0,0,0,.08)` | 卡片陰影 |

### 3.2 尺寸、字級、動畫

| Token | 值 | 用途 |
|-------|-----|------|
| `--h` | `36px` | desktop 控制高度 |
| `--h-mobile` | `44px` | mobile（≤767px）控制高度 |
| `--fs` | `0.875rem`（14px） | 控制元件字級 |
| 強調 `--accent` | `#1a73e8` | 連結、focus、圖表互動元素 |
| 成功 `--success` | `#188038` | 成功／可執行 |
| 危險 `--danger` | `#c5221f` | 錯誤紅框、錯誤訊息 |
| 警告 `--warning` | `#e37400` | 圖表琥珀目標價線 `#f59e0b`、警告 |
| `--transition` | `0.2s ease` | hover/focus/狀態轉場 |
| 淡入 | `150ms` | 內容淡入（尊重 `prefers-reduced-motion`） |
| 字體 | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans TC", "PingFang TC", "Microsoft JhengHei"` | 正體中文 |
| mono | `ui-monospace, SFMono-Regular, Menlo, Consolas` | 數字、代碼 |

> 深色主題為各變數自訂對應值（兩主題皆可讀），詳見互動稿 `:root`／`[data-theme]`。

---

## 4. 狀態矩陣

### 4.1 詳情頁四態狀態機（`status: loading / error / not-found / ready`）

| 狀態 | 視覺 | 互動 | 對應規格 |
|------|------|------|----------|
| **載入中 loading** | 全頁 skeleton：標題列、價格摘要卡、規格列、圖表區灰階漸層佔位（shimmer 動畫） | 不可互動；載入完成自動切就緒 | §2.6、E1 |
| **載入失敗 error** | 全頁置中：警示圖示＋「資料載入失敗」＋次行「無法讀取商品資料 API（網路或伺服器錯誤）」＋「重新載入」主按鈕＋「返回列表」連結 | 點「重新載入」→ 回 loading → 成功就緒／失敗停留；可返回列表 | §2.3 `retry`、E1/E2 |
| **找不到商品 not-found** | 全頁置中：「找不到此商品」＋「返回列表」連結（deep link 失效／id 格式錯誤） | 點「返回列表」回到 003 列表（保留分類 context） | §2.6 `notFound`、E3/E15 |
| **就緒 ready** | 完整版面：麵包屑→標題（＋下架 badge）→價格摘要卡→規格表→趨勢圖＋目標價輸入→WatchActions（005 預留） | 全部互動可用：漲跌閱讀、trend 懸停/縮放、目標價套用/修改/清除 | §2.6、E4–E14 |

### 4.2 規格表（SpecTable）

| 狀態 | 視覺 | 互動 |
|------|------|------|
| 有值 | 兩欄 grid：欄位名（`--surface-2` 淺底）｜值；`--radius` 圓角、`overflow:hidden` | 純展示 |
| 空值 | `value == null \|\| value === ''` 欄位**整列不渲染**（demo：`turbo_ghz` 缺席）；欄位順序維持物件鍵序 | 純展示 |

### 4.3 目標價輸入（idle / focus / error）

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **idle** | 160px 輸入框（`--border` 邊框、`--radius-sm` 圓角）＋「設定目標價」按鈕 | 鍵盤輸入數字（含小數） |
| **focus** | 邊框 `--brand`、`0 0 0 3px --brand-soft` 光圈 | Enter 等同點「設定目標價」 |
| **error** | 紅框 `--danger`＋`rgba(220,38,38,.15)` 光圈＋紅字提示；**不套用目標價線** | 4 組訊息：空白「請輸入目標價」／`abc`「請輸入有效數字」／`0`、`-100`「請輸入大於 0 的有效數字」；修正後重新套用 |
| **有效套用** | 目標價線出現；輸入框回正常 | 目標價 session 級 `ref`，離開路由即銷毀（E12） |

### 4.4 目標價線（顯示 / 清除 / 超區間）

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **顯示** | 琥珀 `#f59e0b` dashed 橫線＋價格軸 title「目標價」 | tooltip 懸停一併顯示「目標價 NT$…」；修改輸入重新套用→線更新 |
| **清除** | 線與價格軸 title 消失 | 點「清除目標價」→ `targetPrice=null` |
| **超出區間** | 線仍顯示；`yMin/yMax` 擴展納入目標價（×0.98/×1.02）；提示「目標價超出歷史區間」（`--warn-*` 底） | 可調整或清除（E7） |

---

## 5. RWD 斷點行為表

| 區段 | ≥1024px（desktop） | 768–1023px（tablet） | ≤767px（mobile） |
|------|--------------------|----------------------|------------------|
| 控制高度 | `--h` 36px | 36px | `--h-mobile` 44px（WCAG 2.5.5） |
| 內容寬度 | `.detail-page` max-width 1080px 置中 | 100%（含 16px padding） | 100%（含 16px padding） |
| 價格摘要卡 | `grid auto-fit minmax(180px,1fr)` 多欄 | 多欄（自動折欄） | **單欄堆疊** |
| 規格表 | `grid-template-columns:140px 1fr` | 140px 1fr | **`120px 1fr`**（欄位名窄化） |
| 趨勢圖 | 高 360px 全寬 | 全寬 | 全寬；**觸控拖曳縮放／平移**（lwc 內建）；手勢取代滾輪 |
| 目標價輸入 | 輸入框＋按鈕同列 | 同列 | **按鈕全寬 44px**、輸入框拉伸 |
| 漲跌/歷史最低 | 摘要卡內並排 | 並排 | 同摘要卡堆疊 |
| 麵包屑／返回 | 文字連結 | 文字連結 | 文字連結（觸控區 ≥44px） |

---

## 6. 無障礙清單（WCAG）

| # | 準則 | 本設計對應 |
|---|------|-----------|
| A1 | 1.4.1 不以顏色單獨傳達 | 漲跌除顏色外附 ▼/▲ SVG 箭頭與「降價/漲價/持平」文字；持平顯示「—」 |
| A2 | 1.4.3 對比度 | 主文字 `#1f2937` on `#ffffff`（≥7:1）；`--text-dim` 僅用於次要說明；兩主題皆可讀 |
| A3 | 2.5.5 觸控目標 | mobile 控制元件一律 44px |
| A4 | 2.4.7 focus 可見 | 輸入框/按鈕 focus ring：`--brand` 邊框＋3px `--brand-soft` 光圈 |
| A5 | 4.1.2 語意狀態 | 載入中：圖表容器 `role="img"`＋`aria-label="歷史價格趨勢圖"`；錯誤訊息 `aria-live`（文字提示即時宣告）；下架 badge 為文字非僅色塊 |
| A6 | 2.1.1 鍵盤 | 目標價輸入 Enter 提交；圖表縮放提供鍵盤可達的 ＋/－/重置按鈕（非僅滾輪） |
| A7 | 2.3.3 動畫 | 所有動畫（shimmer、轉場、淡入 150ms）於 `prefers-reduced-motion` 下關閉/最小化 |
| A8 | 1.3.1 結構語意 | 標題用 `<h1>`、麵包屑用 nav 語意；規格表為 grid 但以 `<dl>`-like 結構渲染（欄位名:值） |
| A9 | 圖示語意 | 所有 inline SVG 設 `aria-hidden="true"`，資訊另以文字提供 |

---

## 7. 實作建議

1. **檔案依 004 規格 §2.1 建立**：`router`（hash history）、`types/item.ts`、`lib/lightweight-charts.ts`（re-export）、`composables/useItems+usePriceHistory+useCrawledAt`、`components/SpecTable+PriceTrendChart+WatchActions`、`views/ProductDetailView.vue`。
2. **共用契約優先**：`useItems` 以 003 契約為準（items/meta/loading/error/retry/isStale 單例共享），004 不重複 fetch；`types/item.ts` 若 003 已建則直接複用。
3. **漲跌計算抽 util**（`formatPrice/formatDiffAmount/formatDiffPercent/formatTrendLabel`）供 003 sparkline 與 005 複用；Vitest 覆蓋 BDD E8（三態）、E9（最早達成日）、E5（單筆）範例資料。
4. **圖表降級順序**：history 空 → 不渲染圖；1 筆 → 單點＋marker；多筆 → 完整互動。`init` 前檢查容器寬度（E16），ResizeObserver 驅動 `chart.applyOptions({width,height})`，`onUnmounted` `chart.remove()`。
5. **目標價**：view 內 `ref`（session 級）；驗證訊息文案以 BDD Examples 為唯一事實來源；`yMin/yMax` 統一由 view 計算傳入（含目標價 ×0.98/×1.02 擴展）。
6. **CSS 全部走共用 token**（§3），不得硬編碼色值；目標價線以 `series.createPriceLine()` 設定（dashed `#f59e0b`、價格軸 title「目標價」）。
7. **無障礙收尾**：`prefers-reduced-motion`、`aria-live` 錯誤提示、圖表 `role="img"`＋文字摘要（最高/最低/目前價）在互動稿驗證通過後再交付。
8. **驗收以 BDD 驅動**：先跑 §8 驗收清單，再依 004 規格 §8 DAG step 10 補 E2E（列表點入、目標價線、載入失敗重試）。

---

## 8. 驗收清單

- [ ] `web/` 綠地審計結果如實記錄於 §1（無既有 UI，不宣稱不存在的問題）
- [ ] Design Token 與共用表完全一致（§3，含深色主題對應值）
- [ ] 互動稿含詳情頁四態 Demo：loading skeleton／載入失敗重試／找不到商品／就緒
- [ ] 目標價輸入四組驗證訊息（空白／abc／0／-100）皆顯示紅框＋提示，且不套用目標價線
- [ ] 有效目標價套用後目標價線出現（價格軸 title「目標價」）；修改更新；清除消失
- [ ] 目標價超出歷史區間（9,000 vs 9,990–11,500）仍套用、Y 軸擴展、顯示「目標價超出歷史區間」
- [ ] 漲跌四態 Demo：降價綠▼／漲價紅▲／持平灰—／無昨日價「首日追蹤，尚無漲跌比較」
- [ ] 趨勢圖示意支援 tooltip 懸停（日期＋價格）、縮放／平移（滾輪／拖曳、雙擊重置）、歷史最低標示、單筆降級「資料不足」
- [ ] 規格表示範空值欄位（turbo_ghz）不渲染
- [ ] WatchActions（005 預留）佔位渲染、不報錯
- [ ] RWD：mobile 控制元件 44px（實測）、價格摘要單欄、規格表欄位名 120px
- [ ] Headless 驗證全過：console 無 error/pageerror、HTML 標籤平衡、宣稱數值實測成立、互動正常
- [ ] 互動稿內所有圖示為 inline SVG（aria-hidden），無 emoji-as-icon
- [ ] 兩主題（light/dark）下全部元件可讀
- [ ] 未修改 `web/` 原始碼、未 commit、未 push、未讀取 003 檔案
