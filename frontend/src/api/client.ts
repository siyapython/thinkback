import axios, { AxiosError } from 'axios'

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const http = axios.create({ baseURL: API_URL })

/** Turn any failure into a short, student-friendly sentence. */
export function errorMessage(err: unknown, opts: { conflict?: string } = {}): string {
  if (err instanceof AxiosError) {
    const status = err.response?.status
    const detail = err.response?.data?.detail
    if (!err.response) return 'Cannot reach the server. Is the backend running?'
    if (status === 409) return opts.conflict ?? (typeof detail === 'string' ? detail : 'That conflicts with the current state.')
    if (status === 413) return typeof detail === 'string' ? detail : 'That file is too large.'
    if (status === 422) {
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0] as { loc?: unknown[]; msg?: string }
        const field = first.loc?.at(-1)
        return `${field ? `${String(field)}: ` : ''}${first.msg ?? 'invalid input'}`
      }
      return 'The server could not accept that input.'
    }
    if (status === 502) return typeof detail === 'string' ? detail : 'The AI service failed. Try again.'
    if (status === 503) return typeof detail === 'string' ? detail : 'The AI service is unavailable.'
    if (typeof detail === 'string') return detail
    return `Request failed (${status}).`
  }
  return err instanceof Error ? err.message : 'Something went wrong.'
}

/** Status code of a failed request, if there was a response. */
export function errorStatus(err: unknown): number | undefined {
  return err instanceof AxiosError ? err.response?.status : undefined
}
