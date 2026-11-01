import { init, use } from 'echarts/core'
import { CandlestickChart, BarChart, LineChart, ScatterChart, RadarChart, HeatmapChart, FunnelChart, TreemapChart, SankeyChart, GaugeChart } from 'echarts/charts'
import { DataZoomInsideComponent, DataZoomSliderComponent, AxisPointerComponent, GridComponent, RadarComponent, TooltipComponent, LegendComponent, VisualMapComponent, AriaComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

use([CandlestickChart, BarChart, LineChart, DataZoomInsideComponent, DataZoomSliderComponent, AxisPointerComponent, ScatterChart, RadarChart, HeatmapChart, FunnelChart, TreemapChart, SankeyChart, GaugeChart,
  GridComponent, RadarComponent, TooltipComponent, LegendComponent, VisualMapComponent, AriaComponent, SVGRenderer])

export const create = element => init(element, null, { renderer: 'svg' })
