import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ConceptMasteryOut, ConceptOut } from '../api/types'
import ConceptRow from './ConceptRow'

const concept: ConceptOut = {
  id: 7, name: 'Window functions', definition: 'Compute across related rows.', source_chunk_ids: [1, 2],
  origin: 'llm', is_active: true, model: null, prompt_version: null, created_at: '2026-01-01T00:00:00Z',
}
const mastery = (is_gap: boolean): ConceptMasteryOut => ({
  concept_id: 7, name: concept.name, mastery: 0.4, attempt_count: 3, is_gap,
})

describe('ConceptRow', () => {
  it('renders a Gap tag when is_gap is true', () => {
    render(<ConceptRow concept={concept} mastery={mastery(true)} onPractice={vi.fn()} />)
    expect(screen.getByText('Gap')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: /mastery of window functions/i })).toBeInTheDocument()
  })

  it('has no Gap tag otherwise', () => {
    render(<ConceptRow concept={concept} mastery={mastery(false)} onPractice={vi.fn()} />)
    expect(screen.queryByText('Gap')).not.toBeInTheDocument()
  })
})
