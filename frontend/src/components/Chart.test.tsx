import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Chart from './Chart'

// Deliberately NOT mocking echarts-for-react: this catches CJS/ESM import-interop bugs
// that only show up when the real library is loaded (the dashboard once rendered blank).
describe('Chart (real echarts-for-react)', () => {
  it('renders without throwing "Element type is invalid"', () => {
    const option = { xAxis: { type: 'category', data: ['a'] }, yAxis: { type: 'value' }, series: [{ type: 'bar', data: [1] }] }
    const { container } = render(<Chart option={option} height={200} />)
    expect(container.firstElementChild).not.toBeNull()
  })
})
