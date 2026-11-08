import { BarChart, FunnelChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'
import ReactEChartsCoreModule from 'echarts-for-react/lib/core'
import { unwrapDefault } from '../lib/interop'

// echarts-for-react/lib/core is CommonJS; under Vite's dev server the default import is the
// module object ({ default: Component }) rather than the component, so unwrap it.
const ReactEChartsCore = unwrapDefault(ReactEChartsCoreModule)

echarts.use([BarChart, LineChart, FunnelChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

interface Props {
  option: EChartsCoreOption
  height?: number
}

/** Thin reusable wrapper: registers only the ECharts parts we use and sets a default size. */
export default function Chart({ option, height = 360 }: Props) {
  return <ReactEChartsCore echarts={echarts} option={option} style={{ height, width: '100%' }} notMerge />
}
