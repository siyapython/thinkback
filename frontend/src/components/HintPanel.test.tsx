import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AttemptOut, HintOut } from '../api/types'
import HintPanel from './HintPanel'

const attempt: AttemptOut = {
  id: 1, question_id: 1, status: 'in_progress', max_hint_level: 1, revealed: false,
  effective_score: null, started_at: '2026-01-01T00:00:00Z', completed_at: null,
}
const hint = (level: number): HintOut => ({
  level, hint_text: `hint text ${level}`, cited_chunk_ids: [], hints_remaining: 4 - level, attempt,
})

describe('HintPanel', () => {
  it('requests a hint while levels remain', async () => {
    const onRequest = vi.fn()
    render(<HintPanel hints={[hint(1)]} level={1} onRequest={onRequest} />)
    expect(screen.getByText('Hint 1 of 4')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /i'm stuck/i }))
    expect(onRequest).toHaveBeenCalledOnce()
  })

  it('disables the button at level 4 and still shows every hint so far', () => {
    render(<HintPanel hints={[hint(1), hint(2), hint(3), hint(4)]} level={4} onRequest={vi.fn()} />)
    expect(screen.getByRole('button', { name: /i'm stuck/i })).toBeDisabled()
    expect(screen.getByText('Hint 4 of 4')).toBeInTheDocument()
    for (let i = 1; i <= 4; i++) expect(screen.getByText(`hint text ${i}`)).toBeInTheDocument()
  })
})
