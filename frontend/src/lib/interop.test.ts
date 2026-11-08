import { describe, expect, it } from 'vitest'
import { unwrapDefault } from './interop'

describe('unwrapDefault', () => {
  const Component = () => null
  it('returns a plain value unchanged', () => expect(unwrapDefault(Component)).toBe(Component))
  it('unwraps a CommonJS-style { default } module object (the Vite dev shape)', () => {
    expect(unwrapDefault({ default: Component })).toBe(Component)
  })
  it('unwraps a double-wrapped module', () => {
    expect(unwrapDefault({ default: { default: Component } })).toBe(Component)
  })
})
