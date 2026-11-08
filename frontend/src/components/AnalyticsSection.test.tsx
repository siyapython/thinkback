import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/endpoints'
import type { AnalyticsOverviewOut } from '../api/types'
import { renderWithProviders } from '../test/utils'
import AnalyticsSection from './AnalyticsSection'

// Replace the real canvas chart with a stub that records the option it was given.
interface Datum { name?: string; value?: number; itemStyle?: { color: string } }
interface CapturedOption {
  xAxis: { data: string[] }
  series: { name?: string; data: (number | Datum)[] }[]
}
const charts: { option: CapturedOption }[] = []
vi.mock('./Chart', () => ({
  default: (props: { option: CapturedOption }) => {
    charts.push(props)
    return <div data-testid="chart" />
  },
}))

const headline = {
  completed_attempts: 3, independent_attempts: 2, independence_rate: 0.667,
  avg_hint_level: 1.3, reveal_rate: 0.333, avg_effective_score: 0.5, gap_concepts: 1,
}
const overview = (patch: Partial<AnalyticsOverviewOut> = {}): AnalyticsOverviewOut => ({
  user_id: 1, display_name: 'You', is_synthetic: false, pipeline_ready: true, headline,
  learner_daily: [
    { day: '2026-03-02', attempts_completed: 2, independence_rate: 0.5, avg_hint_level: 2, reveal_rate: 0, avg_effective_score: 0.4 },
    { day: '2026-03-03', attempts_completed: 1, independence_rate: 1, avg_hint_level: 0.5, reveal_rate: 0, avg_effective_score: 0.9 },
  ],
  concept_summary: [
    { concept_id: 1, concept_name: 'Joins', document_id: 1, attempts: 2, avg_effective_score: 0.9, avg_max_hint_level: 0, reveal_count: 0, mastery: 0.9, is_gap: false, top_misconception: null },
    { concept_id: 2, concept_name: 'Windows', document_id: 1, attempts: 2, avg_effective_score: 0.3, avg_max_hint_level: 3, reveal_count: 1, mastery: 0.3, is_gap: true, top_misconception: 'x' },
  ],
  funnel: [{ document_id: 1, document_title: 'SQL', concepts_extracted: 1, question_served: 8, answer_submitted: 5, completed: 4, revealed: 1 }],
  ...patch,
})

describe('AnalyticsSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    charts.length = 0
    vi.spyOn(api, 'getAnalyticsUsers').mockResolvedValue([
      { id: 1, display_name: 'You', is_synthetic: false },
      { id: 2, display_name: 'Demo Learner (synthetic)', is_synthetic: true },
    ])
  })

  it('shows the empty state when the pipeline has not run', async () => {
    vi.spyOn(api, 'getAnalyticsOverview').mockResolvedValue(
      overview({ pipeline_ready: false, learner_daily: [], concept_summary: [], funnel: [] }),
    )
    renderWithProviders(<AnalyticsSection />)
    expect(await screen.findByText(/analytics tables have not been built yet/i)).toBeInTheDocument()
    expect(screen.getByText('python -m pipeline.seed_demo')).toBeInTheDocument()
    expect(screen.queryByTestId('chart')).not.toBeInTheDocument()
  })

  it('passes the right series to the three charts', async () => {
    vi.spyOn(api, 'getAnalyticsOverview').mockResolvedValue(overview())
    renderWithProviders(<AnalyticsSection />)
    await waitFor(() => expect(screen.getAllByTestId('chart')).toHaveLength(3))
    const [progress, concepts, funnel] = charts.slice(-3).map((c) => c.option)

    expect(progress.xAxis.data).toEqual(['2026-03-02', '2026-03-03'])
    expect(progress.series.map((s) => [s.name, s.data])).toEqual([
      ['Independence rate', [50, 100]], // rates are shown as percentages
      ['Avg hint level', [2, 0.5]],
    ])
    expect(concepts.xAxis.data).toEqual(['Joins', 'Windows'])
    expect((concepts.series[0].data as Datum[]).map((d) => d.value)).toEqual([90, 30])
    const [ok, gap] = (concepts.series[0].data as Datum[]).map((d) => d.itemStyle?.color)
    expect(gap).not.toEqual(ok) // the gap concept is highlighted
    expect((funnel.series[0].data as Datum[]).map((d) => [d.name, d.value])).toEqual([
      ['Served', 8], ['Submitted', 5], ['Completed', 4], ['Revealed', 1],
    ])
  })

  it('labels synthetic data and switches learner from the selector', async () => {
    const spy = vi.spyOn(api, 'getAnalyticsOverview').mockResolvedValue(overview())
    renderWithProviders(<AnalyticsSection />)
    await waitFor(() => expect(spy).toHaveBeenCalledWith(1))
    spy.mockResolvedValue(overview({ user_id: 2, is_synthetic: true }))
    await userEvent.click(screen.getByRole('combobox', { name: /learner/i }))
    // synthetic users carry a visible tag in the list; the real account does not
    expect(await screen.findAllByText('synthetic data')).toHaveLength(1)
    await userEvent.click(await screen.findByText('Demo Learner (synthetic)'))
    await waitFor(() => expect(spy).toHaveBeenCalledWith(2))
    expect(await screen.findByText(/synthetic demo data/i)).toBeInTheDocument()
  })

  it('refreshes analytics with a loading state, then refetches', async () => {
    const overviewSpy = vi.spyOn(api, 'getAnalyticsOverview').mockResolvedValue(overview())
    let finish: (v: { tables: Record<string, number> }) => void = () => {}
    const refreshSpy = vi.spyOn(api, 'refreshAnalytics').mockReturnValue(new Promise((r) => (finish = r)))
    renderWithProviders(<AnalyticsSection />)
    const button = await screen.findByRole('button', { name: /refresh analytics/i })
    await userEvent.click(button)
    expect(refreshSpy).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(button).toHaveClass('ant-btn-loading'))
    const callsBefore = overviewSpy.mock.calls.length
    finish({ tables: { 'silver.attempt_facts': 3 } })
    await waitFor(() => expect(overviewSpy.mock.calls.length).toBeGreaterThan(callsBefore))
  })

  it('shows an error when the overview request fails', async () => {
    vi.spyOn(api, 'getAnalyticsOverview').mockRejectedValue(new Error('boom'))
    renderWithProviders(<AnalyticsSection />)
    expect(await screen.findByText('boom')).toBeInTheDocument()
  })
})
