import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'
import ReactEChartsCore from 'echarts-for-react/lib/core'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

interface Props {
  option: EChartsCoreOption
  height?: number
}

/** Thin reusable wrapper: registers only the ECharts parts we use and sets a default size. */
export default function Chart({ option, height = 360 }: Props) {
  return <ReactEChartsCore echarts={echarts} option={option} style={{ height, width: '100%' }} notMerge />
}
