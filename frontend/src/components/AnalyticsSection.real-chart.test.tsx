import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/endpoints'
import type { AnalyticsOverviewOut } from '../api/types'
import { renderWithProviders } from '../test/utils'
import AnalyticsSection from './AnalyticsSection'

// No mock of ./Chart or echarts-for-react: the real chart stack renders with the normal API shape.
const overview: AnalyticsOverviewOut = {
  user_id: 1, display_name: 'Demo Learner', is_synthetic: false, pipeline_ready: true,
  headline: {
    completed_attempts: 3, independent_attempts: 2, independence_rate: 0.667,
    avg_hint_level: 1.3, reveal_rate: 0.333, avg_effective_score: 0.5, gap_concepts: 1,
  },
  learner_daily: [
    { day: '2026-03-02', attempts_completed: 2, independence_rate: 0.5, avg_hint_level: 2, reveal_rate: 0, avg_effective_score: 0.4 },
  ],
  concept_summary: [
    { concept_id: 1, concept_name: 'Joins', document_id: 1, attempts: 2, avg_effective_score: 0.9, avg_max_hint_level: 0, reveal_count: 0, mastery: 0.9, is_gap: false, top_misconception: null },
  ],
  funnel: [{ document_id: 1, document_title: 'SQL', concepts_extracted: 1, question_served: 8, answer_submitted: 5, completed: 4, revealed: 1 }],
}

describe('AnalyticsSection with the real Chart', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'getAnalyticsUsers').mockResolvedValue([{ id: 1, display_name: 'Demo Learner', is_synthetic: false }])
    vi.spyOn(api, 'getAnalyticsOverview').mockResolvedValue(overview)
  })

  it('renders the stats and all three real charts without crashing', async () => {
    const { container } = renderWithProviders(<AnalyticsSection />)
    expect(await screen.findByText('Completed attempts')).toBeInTheDocument()
    expect(container.querySelectorAll('.echarts-for-react')).toHaveLength(3)
  })
})
