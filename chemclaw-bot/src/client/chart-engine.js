import { init, use } from 'echarts/core'
import { ScatterChart, RadarChart, HeatmapChart, FunnelChart, TreemapChart, SankeyChart, GaugeChart } from 'echarts/charts'
import { GridComponent, RadarComponent, TooltipComponent, LegendComponent, VisualMapComponent, AriaComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

use([ScatterChart, RadarChart, HeatmapChart, FunnelChart, TreemapChart, SankeyChart, GaugeChart,
  GridComponent, RadarComponent, TooltipComponent, LegendComponent, VisualMapComponent, AriaComponent, SVGRenderer])

export const create = element => init(element, null, { renderer: 'svg' })
