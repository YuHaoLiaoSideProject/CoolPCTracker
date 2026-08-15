// web/src/lib/echarts.ts — ECharts on-demand 註冊（開發規格 004 §2.5）
// 全站共用單一註冊點：只打包 LineChart 與所需元件/渲染器（tree-shaking，
// 避免整包 echarts 進入 bundle）。003–005 共用此模組，不重複註冊。
import * as echarts from "echarts/core"
import { LineChart } from "echarts/charts"
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  MarkLineComponent,
  LegendComponent,
} from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  MarkLineComponent,
  LegendComponent,
  CanvasRenderer,
])

export default echarts
export type { ECharts } from "echarts/core"
export type { EChartsOption } from "echarts"
