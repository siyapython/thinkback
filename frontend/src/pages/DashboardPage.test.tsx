import { screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/endpoints'
import { renderWithProviders } from '../test/utils'
import DashboardPage from './DashboardPage'

// Only the mastery chart's Chart is made to blow up; analytics must still render.
vi.mock('../components/Chart', () => ({
  default: ({ height }: { height?: number }) => {
    if (height === undefined) throw new Error('mastery chart exploded')
    return <div data-testid="chart" />
  },
}))

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(api, 'listDocuments').mockResolvedValue([
      { id: 1, title: 'SQL', source_type: 'text', original_filename: null, page_count: null, status: 'ready', error_message: null, chunk_count: 1, created_at: '2026-03-01T00:00:00Z' },
    ])
    vi.spyOn(api, 'listConcepts').mockResolvedValue([])
    vi.spyOn(api, 'getIndependence').mockResolvedValue({ completed_attempts: 3, independent_attempts: 2, independence_rate: 0.667 })
    vi.spyOn(api, 'getMastery').mockResolvedValue([{ concept_id: 1, name: 'Joins', mastery: 0.9, attempt_count: 2, is_gap: false }])
    vi.spyOn(api, 'getAnalyticsUsers').mockResolvedValue([])
  })
  afterEach(() => vi.restoreAllMocks())

  it('keeps the rest of the page when one chart section crashes', async () => {
    renderWithProviders(<DashboardPage />)
    expect(await screen.findByText(/mastery chart section could not be displayed/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByText('Learning analytics')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})
