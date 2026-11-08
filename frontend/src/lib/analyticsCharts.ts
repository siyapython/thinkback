import type { EChartsCoreOption } from 'echarts/core'
import type { ConceptSummaryOut, FunnelOut, LearnerDayOut } from '../api/types'
import { pct } from './weakSpots'

// Pure functions: API data in, ECharts option out. Kept out of components so tests can check
// exactly which series a chart receives.
export const COLORS = { independence: '#2a78d6', hints: '#d9822b', ok: '#2a78d6', gap: '#d6452a', funnel: ['#2a78d6', '#4f94e0', '#79b0ea', '#d9822b'] }

/** Line chart: independence rate (% , left axis) and average max hint level (0-4, right axis). */
export function progressOption(days: LearnerDayOut[]): EChartsCoreOption {
  return {
    grid: { left: 48, right: 48, top: 40, bottom: 40 },
    legend: { top: 0 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: days.map((d) => d.day) },
    yAxis: [
      { type: 'value', name: 'Independence', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
      { type: 'value', name: 'Avg hint level', min: 0, max: 4, splitLine: { show: false } },
    ],
    series: [
      {
        type: 'line',
        name: 'Independence rate',
        yAxisIndex: 0,
        data: days.map((d) => pct(d.independence_rate)),
        itemStyle: { color: COLORS.independence },
        lineStyle: { color: COLORS.independence },
      },
      {
        type: 'line',
        name: 'Avg hint level',
        yAxisIndex: 1,
        data: days.map((d) => d.avg_hint_level),
        itemStyle: { color: COLORS.hints },
        lineStyle: { color: COLORS.hints, type: 'dashed' },
      },
    ],
  }
}

/** Bars: average effective score (%) per concept; gap concepts get the warning colour. */
export function conceptScoreOption(concepts: ConceptSummaryOut[]): EChartsCoreOption {
  return {
    grid: { left: 48, right: 16, top: 16, bottom: 90 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: unknown) => `${v}%` },
    xAxis: {
      type: 'category',
      data: concepts.map((c) => c.concept_name),
      axisLabel: { interval: 0, rotate: 30, width: 110, overflow: 'truncate' },
    },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
    series: [
      {
        type: 'bar',
        name: 'Avg effective score',
        barMaxWidth: 28,
        data: concepts.map((c) => ({
          value: pct(c.avg_effective_score ?? 0),
          itemStyle: { color: c.is_gap ? COLORS.gap : COLORS.ok, borderRadius: [4, 4, 0, 0] },
        })),
      },
    ],
  }
}

/** Funnel: question served -> answer submitted -> completed -> revealed (distinct attempts). */
export function funnelOption(f: FunnelOut): EChartsCoreOption {
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c}' },
    series: [
      {
        type: 'funnel',
        sort: 'none', // keep our stage order; "revealed" is not always the smallest
        minSize: '8%',
        left: '10%',
        width: '80%',
        label: { formatter: '{b}: {c}' },
        data: [
          { name: 'Served', value: f.question_served },
          { name: 'Submitted', value: f.answer_submitted },
          { name: 'Completed', value: f.completed },
          { name: 'Revealed', value: f.revealed },
        ].map((d, i) => ({ ...d, itemStyle: { color: COLORS.funnel[i] } })),
      },
    ],
  }
}
