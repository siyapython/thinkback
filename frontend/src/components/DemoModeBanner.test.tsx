import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/endpoints'
import { renderWithProviders } from '../test/utils'
import DemoModeBanner from './DemoModeBanner'

const BANNER = /demo mode: ai responses are placeholders/i

describe('DemoModeBanner', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('is shown when the backend is in fake mode', async () => {
    vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok', llm_mode: 'fake' })
    renderWithProviders(<DemoModeBanner />)
    const banner = await screen.findByText(BANNER)
    expect(banner).toHaveTextContent('Set LLM_MODE=real in .env to use Claude.')
  })

  it('is hidden in real mode', async () => {
    const spy = vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok', llm_mode: 'real' })
    renderWithProviders(<DemoModeBanner />)
    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(screen.queryByText(BANNER)).not.toBeInTheDocument()
  })

  it('stays hidden if the backend cannot be reached', async () => {
    const spy = vi.spyOn(api, 'getHealth').mockRejectedValue(new Error('down'))
    renderWithProviders(<DemoModeBanner />)
    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(screen.queryByText(BANNER)).not.toBeInTheDocument()
  })
})
