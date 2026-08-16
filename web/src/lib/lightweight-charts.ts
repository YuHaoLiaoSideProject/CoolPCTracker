// web/src/lib/lightweight-charts.ts — lightweight-charts v5 單一註冊點（004 價格走勢圖）
// 全站只在此 re-export 元件與測試所需的 API/型別；其它模組一律 import 此檔。
// v5 重點：以 addSeries(LineSeries, {...}) 取代 v4 的 addLineSeries()；createSeriesMarkers 為 plugin API。
export {
  createChart,
  createSeriesMarkers,
  ColorType,
  CrosshairMode,
  LineStyle,
  LineType,
  LineSeries,
  AreaSeries,
} from "lightweight-charts"

export type {
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  IPriceLine,
  ITimeScaleApi,
  LineData,
  SeriesMarker,
  MouseEventParams,
  DeepPartial,
  TimeChartOptions,
  CreatePriceLineOptions,
  Time,
} from "lightweight-charts"
