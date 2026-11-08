import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import RevealButton from './RevealButton'

describe('RevealButton', () => {
  it('warns in a confirm modal before revealing, and only reveals on confirm', async () => {
    const onConfirm = vi.fn()
    render(<RevealButton onConfirm={onConfirm} />)
    await userEvent.click(screen.getByRole('button', { name: /show answer/i }))

    expect(await screen.findByText(/lowers your mastery/i)).toBeInTheDocument()
    expect(onConfirm).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: /yes, show it/i }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('does nothing when the student cancels', async () => {
    const onConfirm = vi.fn()
    render(<RevealButton onConfirm={onConfirm} />)
    await userEvent.click(screen.getByRole('button', { name: /show answer/i }))
    await userEvent.click(await screen.findByRole('button', { name: /keep trying/i }))
    expect(onConfirm).not.toHaveBeenCalled()
  })
})
