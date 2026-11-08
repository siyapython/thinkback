import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

// Reproduces what Vite's dev server hands us: the default import of the CommonJS
// echarts-for-react/lib/core is the module object { default: Component }, not the component.
vi.mock('echarts-for-react/lib/core', () => {
  const Component = () => <div data-testid="real-component" />
  return { default: { __esModule: true, default: Component } }
})

import Chart from './Chart'

describe('Chart with a CommonJS-wrapped echarts-for-react (Vite dev shape)', () => {
  it('still renders the component instead of throwing "Element type is invalid"', () => {
    const { getByTestId } = render(<Chart option={{}} />)
    expect(getByTestId('real-component')).toBeInTheDocument()
  })
})
