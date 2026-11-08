import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(cleanup)

// jsdom lacks these browser APIs, which antd uses.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
})
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver

// jsdom has no canvas. Give ECharts a no-op 2D context so real charts can render in tests.
const noopContext = new Proxy(
  { canvas: null as unknown },
  {
    get: (target, prop) => {
      if (prop === 'canvas') return target.canvas
      if (prop === 'measureText') return () => ({ width: 0 })
      if (prop === 'createLinearGradient' || prop === 'createRadialGradient') return () => ({ addColorStop() {} })
      if (prop === 'getImageData') return () => ({ data: new Uint8ClampedArray(4) })
      return () => {}
    },
    set: () => true,
  },
)
HTMLCanvasElement.prototype.getContext = function getContext(this: HTMLCanvasElement) {
  noopContext.canvas = this
  return noopContext
} as unknown as HTMLCanvasElement['getContext']
