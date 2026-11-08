import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/endpoints'
import { renderWithProviders } from '../test/utils'
import LlmModeBanner from './LlmModeBanner'

describe('LlmModeBanner', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('shows the demo-mode banner when llm_mode is fake', async () => {
    vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok', llm_mode: 'fake' })
    renderWithProviders(<LlmModeBanner />)
    expect(await screen.findByText(/demo mode: ai responses are placeholders/i)).toBeInTheDocument()
    expect(screen.getByText(/LLM_MODE=real/)).toBeInTheDocument()
  })

  it('shows nothing when llm_mode is real', async () => {
    const spy = vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok', llm_mode: 'real' })
    renderWithProviders(<LlmModeBanner />)
    await vi.waitFor(() => expect(spy).toHaveBeenCalled())
    expect(screen.queryByText(/demo mode/i)).not.toBeInTheDocument()
  })
})
