import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SectionBoundary from './SectionBoundary'

let shouldThrow = true
function Flaky() {
  if (shouldThrow) throw new Error('chart exploded')
  return <p>all good</p>
}

describe('SectionBoundary', () => {
  beforeEach(() => {
    shouldThrow = true
    vi.spyOn(console, 'error').mockImplementation(() => {}) // React logs caught render errors
  })
  afterEach(() => vi.restoreAllMocks())

  it('shows a friendly error instead of crashing, and recovers on retry', async () => {
    render(
      <>
        <p>sibling stays</p>
        <SectionBoundary name="test chart">
          <Flaky />
        </SectionBoundary>
      </>,
    )
    expect(screen.getByText(/test chart section could not be displayed/i)).toBeInTheDocument()
    expect(screen.getByText('sibling stays')).toBeInTheDocument()

    shouldThrow = false
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(screen.getByText('all good')).toBeInTheDocument()
  })
})
