/**
 * Unwrap a default import that may arrive as a CommonJS module object.
 *
 * Some packages (e.g. echarts-for-react/lib/core) are CommonJS with `exports.default = Component`.
 * Depending on the tool (Vite dev pre-bundling, Rollup/Rolldown build, Vitest, Node ESM) the
 * default import is either the component itself or the whole `{ default: Component }` object.
 * This returns the real value in both cases.
 */
export function unwrapDefault<T>(mod: T | { default: T }): T {
  let value: unknown = mod
  // Loop in case a tool double-wraps the module.
  while (value && typeof value === 'object' && 'default' in value) {
    value = (value as { default: unknown }).default
  }
  return value as T
}
