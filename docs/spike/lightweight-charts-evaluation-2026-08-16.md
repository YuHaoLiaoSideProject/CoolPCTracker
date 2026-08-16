# Spike：004 詳情頁價格走勢圖 echarts → lightweight-charts 決策支援報告

- **日期**：2026-08-16
- **範圍**：唯讀評估，未改動任何 `web/src/`、`web/package.json`、未安裝依賴
- **動機**：004 詳情頁「只是顯示價格走勢」卻載入 echarts（樹搖後 chunk 594 kB raw / 203 kB gzip），使用者認為過重
- **結論摘要**：**Go（有條件）** — 兩項無法 1:1 取代（dataZoom slider、圖內 markLine 標籤）需產品接受替代方案；採一次性重寫，不做漸進並存
- **驗證方式**：`npm view lightweight-charts`（registry metadata）＋ `npm pack` 至 `/tmp/lwc-inspect` 檢查 dist 與 `typings.d.ts`（未進 repo）

---

## 1. 現況盤點

### 1.1 實際用到的 echarts 功能（`PriceTrendChart.vue` 全文逐條）

| # | 功能 | 實際用法 | 對應 echarts option |
|---|------|----------|---------------------|
| 1 | series 型別 | 單一條 `line`（`smooth:false` 直線），非 area | `series[0].type="line"` |
| 2 | X 軸 | `type:"time"`，非等間距如實呈現（不補點，E14）；label `MM-DD` | `xAxis.type="time"` + formatter |
| 3 | Y 軸 | `type:"value"`，`min/max` 由 props 傳入、`scale:true`、label `NT$n` | `yAxis` |
| 4 | tooltip | `trigger:"axis"` + `axisPointer.type:"cross"`，自訂 formatter：日期＋價格＋目標價 | `tooltip.formatter` |
| 5 | dataZoom | `inside`（非單筆恆開）＋ `slider`（**點數 ≥15 才顯示**，14px 高、琥珀色 filler） | `dataZoom[]` |
| 6 | markLine（目標價線） | dashed `#f59e0b`、`silent`、`symbol:"none"`、`lineWidth 1.5`、圖內 badge 標籤「目標價 NT$9,500」`insideEndTop` | `series[0].markLine` |
| 7 | legend | **註冊了 LegendComponent，但 `buildOption` 從未加入 `legend` 欄位 → 實際未使用** | 無（死註冊） |
| 8 | 動畫 | `animation: !reduceMotion()`（`prefers-reduced-motion` 時關閉） | `animation` |
| 9 | 資料點符號 | `showSymbol`：單筆或 ≤24 點顯示 circle（`symbolSize` 10/6） | `series.showSymbol/symbol/symbolSize` |
| 10 | 單筆標籤 | 單筆時 series label 顯示 `NT$n` | `series.label.formatter` |
| 11 | 單筆 X 軸 | 單筆以該日為中心 ±12h 視窗 | `xAxis.min/max`（手算 time） |
| 12 | 事件 | **無任何 click/hover/brush 事件** | — |
| 13 | resize | `ResizeObserver` → `chart.resize()`；容器 0 寬延後 init（E16）；`onUnmounted` dispose | 手動 |
| 14 | 明暗色 | 用硬編碼 design token 值（`#1f6feb` 品牌、`#f59e0b` 琥珀、`#f1f3f5` slider 底）——Canvas 不吃 CSS var，**無動態主題切換** | 硬編碼 |
| 15 | 無障礙 | 容器 `role="img"` + `aria-label="歷史價格趨勢圖"`（WCAG A5） | 外層 div |

**props / 資料形狀**（元件對外契約）：
- `history: PricePoint[]`（`{ d: "2026-08-15", p: 9990 }`，依 `d` 升冪，長度 ≥1）
- `targetPrice?: number | null`（null/undefined = 不畫目標價線）
- `yMin?: number`、`yMax?: number`（view 已含目標價以 ×0.98/×1.02 擴展後傳入）

### 1.2 資料流與目標價線來源

- `ProductDetailView.vue`：`history = item.history`（來自 `useItems` 正規化後的 `Item.history: PricePoint[]`）→ `usePriceHistory(history)` 算 stats → `targetPrice` 由 `parseTargetPrice()`（純 util）驗證後設為 ref → `yMin/yMax` 以 `histMin/histMax` 與 `targetPrice` 取 min/max 後 ×0.98/×1.02 → 全部以 props 傳入 `PriceTrendChart`。
- **關鍵**：目標價線的「值」由 `targetPrice.ts`（純邏輯）產生，與圖表渲染完全解耦；005 追蹤清單／006 Telegram 警示只 import `targetPrice`/`usePriceHistory` 的純函數，**不 import echarts**。因此換圖表庫對 005/006 零影響。
- `usePriceHistory.ts` 另輸出 `chartSeries`（`dates[]`/`prices[]`），但 `PriceTrendChart.vue` 目前**未使用**它（自己 map `[d,p]`），遷移時可順手消費或維持現狀。

### 1.3 測試耦合度

**`PriceTrendChart.test.ts`（7 個 test，約 120 LOC）— 高度耦合，需整檔重寫**
- `vi.mock("@/lib/echarts", () => ({ default: { init } }))`，`init` 回傳 `{ setOption, resize, dispose }` mock；`vi.stubGlobal("ResizeObserver", ROStub)`；stub `HTMLElement.prototype.clientWidth=480`。
- 所有斷言都在檢查 **echarts option 物件形狀**：`xAxis.type==="time"`、`series[0].data`、`dataZoom[1].show`、`markLine.lineStyle/label.formatter`、`symbolSize/label`、`yAxis.min/max`、`xAxis.min/max`（單筆中心）、`notMerge` 二次 setOption。
- 改 lightweight-charts 後，斷言需改為「檢查呼叫了 `createChart`/`addSeries(LineSeries)`/`setData`/`createPriceLine`/`applyOptions`/`timeScale().fitContent` 的參數」，或將「組態組裝」抽成純函數（`buildChartSpec()`）直接單測——後者測試成本更低、更不依賴 mock 內部。

**`ProductDetailView.test.ts`（約 230 LOC）— 解耦良好，預期 0 改動**
- `vi.mock("@/components/PriceTrendChart.vue")` 為 stub（props：`history/targetPrice/yMin/yMax`），斷言的是「view 傳了哪些 props」而非圖表內部。
- **只要元件保留相同 props 名稱與語意，此檔不需任何修改。**

### 1.4 registry / bundle 實測

| 項目 | 值 |
|------|-----|
| lightweight-charts 最新穩定版 | **5.2.1**（dist-tags：`latest=5.2.1`、`next=5.0.7-rc1`、`next-v5=5.0.0-rc3`） |
| license | Apache-2.0（TradingView, Inc.） |
| `dist.unpackedSize` | 3,095,012 B（3.09 MB，含 dev＋standalone＋map） |
| `dist/lightweight-charts.production.mjs` | **189,213 B raw / 60,617 B gzip** |
| `dist/lightweight-charts.standalone.production.js` | 197,922 B raw / 62,316 B gzip |
| 依賴 `fancy-canvas@2.1.0`（唯一 runtime dep） | 各 .mjs 極小，合計約 ~18 kB raw / ~6 kB gzip |
| **實際新增重量（估）** | **~207 kB raw / ~66 kB gzip**（production.mjs + fancy-canvas） |

> ⚠️ 任務背景寫「lightweight-charts min+gzip 約 40~50 kB」有誤：**min 約 189 kB，gzip 約 60 kB**（另加 fancy-canvas）。仍遠小於 echarts，但非「40~50 kB min」。

### 1.5 目前 build 產物（`web/dist/assets`，2026-08-16 build）

| 檔案 | raw | gzip |
|------|-----|------|
| `ProductDetailView-CK7reNKx.js`（含 echarts 的詳情頁 chunk） | **594,025 B（580 kB）** | **202,672 B（198 kB）** |
| `index-DWOeWjYV.js`（主 chunk，列表頁） | 122,379 B | 47,156 B |
| `index-VsKd_NJZ.css` / `ProductDetailView-D0tYcplX.css` | 14,737 / 6,854 B | 3,369 / 1,678 B |

- 確認 **主 chunk 不含 echarts**（`router/index.ts` 對 `/product/:id` 用 `() => import(...)` 懶載入；`ListingView.vue` 用 `requestIdleCallback` 背景 prefetch）。換庫後此機制不變，主 chunk 不受影響。

---

## 2. 功能對照（echarts → lightweight-charts v5.2.1）

| echarts 功能 | 支援？ | lightweight-charts 對應 | Caveat |
|-------------|:------:|--------------------------|--------|
| 折線 LineSeries | ✅ 1:1 | `chart.addSeries(LineSeries, { color:"#1f6feb", lineWidth:2, lineType:LineType.Simple })` + `series.setData(data)`；直線為預設（等同 `smooth:false`） | v5 用 series 定義物件（`addSeries(LineSeries)`）；v4 的 `addLineSeries()` 已移除，舊範例別照抄 |
| 面積線 AreaSeries | ✅ 1:1 | `addSeries(AreaSeries, {...})` | 目前未用 area，保留能力即可 |
| 時間軸（日期字串） | ✅ 1:1 | `Time = UTCTimestamp \| BusinessDay \| string`；**直接傳 `"2026-08-15"` 字串**（ISO business day），`setData` 即接受 | ① 資料須依時間**升冪**（契約已保證）；② **同一時間只能一個點**（歷史只在異動日 append，單日單點，安全）；③ 用字串可**完全避開時區/DST**——若改傳 `UTCTimestamp` 會踩「秒 vs 毫秒」陷阱（`UTCTimestamp` 單位是秒） |
| tooltip / 十字線 | ⚠️ 需自寫 | `chart.subscribeCrosshairMove(handler)` 回傳 `MouseEventParams{time, point, seriesData}`；自建 DOM tooltip 定位 | echarts 的 formatter 是內建，lwc **無內建 HTML tooltip**，需手寫（建 div、`point.x/y` 定位、邊界 clamp、hover 離開時隱藏、`unsubscribeCrosshairMove` 清理）——估 +40~60 LOC |
| 縮放／平移 | ⚠️ 部分 | 內建 time scale：滑鼠滾輪縮放、拖曳平移、`handleScroll/handleScale` 開關、雙擊重置；`timeScale().fitContent()` | **無 dataZoom「滑桿（slider）」元件**。可 1:1 取代 `inside`，但「點數 ≥15 顯示 slider」此 UX 只能刪除或以 `fitContent`/可見範圍控制替代 → 需產品接受 |
| 目標價水平線 | ⚠️ 部分 | `series.createPriceLine({ price, color:"#f59e0b", lineStyle:LineStyle.Dashed, lineWidth, title, axisLabelVisible })` | ✅ 虛線＋著色可對應；❌ **`lineWidth` 為枚舉 `1\|2\|3\|4`，無 1.5**（用 1 或 2）；❌ **`title` 標籤只顯示在右側價格軸刻度旁**（`axisLabelVisible`），**無法像 echarts markLine 在圖內畫 badge「目標價 NT$9,500」** → 替代：價格軸 title「目標價 9,500」，或自訂 DOM overlay 釘在價格座標 |
| legend / 多 series | ✅ 1:1（免做） | 詳情頁**只有一條線 + 一條目標價線**，echarts 根本沒用 legend（僅死註冊 LegendComponent）；lwc 多 series 天然支援（每 series 一條 price line），無 legend 需求 | — |
| resize 響應 | ✅ 1:1 | `chart.applyOptions({ width, height })`（保留現有 `ResizeObserver`）或 `autoSize:true`（v4.1+/v5 內建自動尺寸） | 建議保留現有手動 ResizeObserver 模式（與 E16 0 寬延後 init 一致）；`autoSize` 會自行建立 ResizeObserver，測試仍須 stub |
| 主題色（漲紅跌綠等） | ✅ 1:1 | 全部顯式選項：`layout.textColor`、`grid.*Color`、`crosshair.*Color`、series `color`、price line `color` | 現況 echarts 早已硬編碼 token 值（無動態明暗主題），lwc 同為 Canvas 顯式色，**零回歸**；紅/綠僅用於摘要卡 CSS（`--price-up/down`），與圖表庫無關 |
| 動畫 | ❌ 無 | lwc 無進場動畫（重繪為主） | echarts 只在非 reduced-motion 時開動畫；lwc 無此選項 → 少一進場動畫，非 BDD 需求，屬輕微視覺回歸 |
| 資料點符號（≤24 點/單筆） | ⚠️ 需自寫 | v5 `createSeriesMarkers(series, markers)`（plugin API）畫 circle marker＋文字；或舊 `setMarkers()` | LineSeries **預設不畫點**，`showSymbol` 無直接對應 → ≤24 點/單筆的符號與「單筆 NT$ 標籤」要用 markers 補 |
| 單筆降級（E5） | ⚠️ 需自寫 | 單筆 line series 畫不出線 → 用 marker 畫點＋文字；X 軸居中可用 `timeScale().setVisibleLogicalRange({from:-1.5,to:1.5})` | echarts 的「±12h 居中視窗」需改以 logical range 對應，邏輯要重寫但可達成 |
| 無障礙 | ✅ 1:1 | 保留外層 `role="img" aria-label`（lwc canvas 本身無語義） | 與現況相同，無增減 |
| 離線 / 打包 | ✅ | 純 npm ESM（`module` 指向 `production.mjs`），tree-shaking 良好；無 CDN 需求，可離線打包 | 唯一 runtime dep `fancy-canvas` 會一起進 chunk |

---

## 3. 遷移工作量與影響

### 3.1 檔案清單

| 檔案 | 動作 | 估 LOC |
|------|------|--------|
| `web/src/lib/echarts.ts` | **刪除** | -27 |
| `web/src/lib/lightweight-charts.ts`（新） | 新增：re-export `createChart`、`LineSeries`/`AreaSeries`、`LineStyle`/`LineType`/`ColorType` 型別，供元件與測試共用 | +15~30 |
| `web/src/components/PriceTrendChart.vue` | **重寫**：createChart → addSeries → setData → createPriceLine → subscribeCrosshairMove（自寫 tooltip）→ markers（單筆/≤24 點）→ ResizeObserver applyOptions → dispose | ~200~260（現況 250） |
| `web/package.json` | 移除 `echarts@^6.1.0`，加 `lightweight-charts@^5.2.1` | 2 行 |
| `web/src/components/__tests__/PriceTrendChart.test.ts` | **整檔重寫**：mock `@/lib/lightweight-charts`（`createChart` 回傳 `{addSeries, applyOptions, subscribeCrosshairMove, timeScale, remove}`），斷言改為檢查呼叫參數；或抽 `buildChartSpec()` 純函數直接單測（建議後者，降耦合） | ~120（重寫，非新增） |
| `web/src/views/__tests__/ProductDetailView.test.ts` | **0 改動**（stub props 不變） | 0 |
| 不需動 | `usePriceHistory.ts`、`targetPrice.ts`、`types/item.ts`、`ProductDetailView.vue`（props 契約不變）、`Sparkline.vue`（純 SVG）、`router/index.ts`、`ListingView.vue` prefetch | 0 |

### 3.2 bundle 影響（估）

| 指標 | 現況（echarts） | 換後（lwc） | 變化 |
|------|----------------|-------------|------|
| 詳情頁 chunk raw | 594 kB（含 echarts ~540 kB） | ~260 kB（非 echarts 54 kB + lwc 207 kB） | **-334 kB（-56%）** |
| 詳情頁 chunk gzip | 203 kB | **~100 kB**（非 echarts ~33 kB + lwc ~66 kB） | **-103 kB（-51%）** |
| 主 chunk | 122 kB raw / 47 kB gzip | 不變（已 lazy＋prefetch 不變） | 0 |

> 換算：**轉移後詳情頁 gzip 從 ~203 kB 降到 ~100 kB 以內**，符合使用者「只是價格走勢」的體感；主 chunk 零影響。

### 3.3 風險清單

1. **v4 vs v5 API 差異**：`addLineSeries()`（v4）已廢除，v5 改 `addSeries(LineSeries)`；`setMarkers` 在 v5 建議改用 `createSeriesMarkers` plugin；大量網路舊範例是 v4，直接照抄會編譯失敗。→ 以 `dist/typings.d.ts`（5.2.1）為準。
2. **日期型別陷阱**：`UTCTimestamp` 單位是**秒**（非 ms）；`BusinessDay` 需手拆 `{year,month,day}`；唯一零踩雷路徑是**直接用 `d` 的 `"yyyy-mm-dd"` 字串**。且 lwc 要求**升冪排序＋同時間單點**——現有契約已滿足，但遷移時切勿把 `new Date(d).getTime()`（ms）當 timestamp 塞進去。
3. **兩項非 1:1 功能回歸**：① dataZoom slider（點數 ≥15 才顯示）無對應 → 需刪除或改用可見範圍控制，屬 E14 UX 回歸；② markLine 圖內 badge「目標價 NT$9,500」→ lwc 只能放價格軸 `title` 或自訂 DOM overlay，樣式需重做。
4. **tooltip 自寫 DOM**：定位、邊界 clamp、清理、明暗色一致都要自己測，增加測試面與回歸風險（現 echarts 為內建 formatter）。
5. **測試環境（jsdom）**：lwc 同樣依賴 Canvas → 單元測試仍須 mock `@/lib/lightweight-charts` ＋ stub `ResizeObserver`（與現況同，無新增難度）；本專案為純 SPA（`createWebHashHistory`），無 SSR，故無 `window`/canvas 伺服器端問題。
6. **樣式回歸**：lwc 預設 grid/margin/字型/十字線外觀與 echarts 不同，需對 UIUX §4.4 重跑視覺驗收（尤其 tooltip、grid 間距、價格軸刻度）。

---

## 4. 結論與建議

### 4.1 Go / No-Go 判定

**Go（有條件）**。

理由：
- 收益明確：詳情頁 gzip 203 kB → ~100 kB（-51%），主 chunk 不受影響；且 echarts 在此頁只用了「一條線＋一條水平線」，lwc 完全覆蓋核心需求。
- 耦合面極小：echarts 僅被 `PriceTrendChart.vue` 一個元件消費（`Sparkline.vue` 是 SVG，005/006 只用純 `targetPrice`/`usePriceHistory` util），換庫是單一元件重寫，非跨功能手術。
- 前提（需產品接受兩項替代）：
  1. **放棄 dataZoom slider 滑桿**（保留內建滾輪縮放＋拖曳平移；可另加雙擊重置）。
  2. **目標價標籤從圖內 badge 移到右側價格軸**（`priceLine.title`＋`axisLabelVisible`），或接受自訂 DOM overlay 的額外成本。

### 4.2 分階段計畫（若 Go）

| 階段 | 內容 | 驗收 |
|------|------|------|
| 0. 產品確認 | 確認 slider 移除、目標價標籤位置兩項替代方案 | 書面同意 |
| 1. 資料型別轉換 | 新增 `buildChartSpec()`：`PricePoint[] → { time:"yyyy-mm-dd", value:p }[]`（純函數、可直接單測），確認升冪/單日單點 | 純函數單測 |
| 2. 圖表元件重寫 | 重寫 `PriceTrendChart.vue`（createChart/addSeries/setData/createPriceLine/subscribeCrosshairMove tooltip/markers/resize/dispose），保留 props 契約不變 | 手動視覺驗收＋單測 |
| 3. 移除 echarts | 刪 `lib/echarts.ts` → 新增 `lib/lightweight-charts.ts`；`package.json` 移除 echarts、加 lightweight-charts | `npm run build` 成功、chunk 體積符合預期 |
| 4. 測試改寫 | 重寫 `PriceTrendChart.test.ts`（斷言 lwc 呼叫參數，或直接測 `buildChartSpec`）；`ProductDetailView.test.ts` 不需改 | `npm test` 全綠 |
| 5. build / E2E | `npm run build` 檢查 chunk 大小；Playwright 詳情頁視覺/交互回歸 | E2E 綠、bundle 報告 |

### 4.3 一次性重寫 vs 漸進並存

**建議一次性重寫（非漸進並存）**：
- echarts 只被單一元件消費，無其他圖表需「並存期」共用；並存會讓 echarts 仍留在 bundle，**直接抵銷本次優化的唯一目的（減肥）**。
- 元件對外 props 契約不變，`ProductDetailView.vue` 與其測試零改動，切換風險被侷限在單一元件＋其單測，一次性重寫可控。

### 4.4 無法 1:1 取代的功能清單（明確）

| 功能 | 替代做法 |
|------|----------|
| **dataZoom slider 滑桿**（點數 ≥15 顯示） | 內建滾輪縮放＋拖曳平移（保留）；可加 `timeScale().fitContent()` 或「雙擊重置」提示；滑桿 UI 移除 |
| **markLine 圖內 badge 標籤**（「目標價 NT$9,500」） | 移至價格軸 `priceLine.title`＋`axisLabelVisible`；或自訂 DOM overlay 釘在價格座標（成本 +20~40 LOC） |
| **資料點符號**（`showSymbol`：單筆/≤24 點） | `createSeriesMarkers()` 畫 circle marker＋文字 |
| **單筆 X 軸居中 ±12h** | `timeScale().setVisibleLogicalRange({from:-1.5, to:1.5})` |
| **`lineWidth:1.5`（目標價線）** | 改用 `1` 或 `2`（枚舉限制） |
| **tooltip formatter（內建）** | 自寫 `subscribeCrosshairMove` DOM tooltip |
| **進場動畫**（非 reduced-motion 時） | 無，移除（非需求） |

---

*報告完*
