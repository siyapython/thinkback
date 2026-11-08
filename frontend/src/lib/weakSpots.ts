import type { ConceptMasteryOut } from '../api/types'

/** The n concepts most in need of work: lowest mastery first, gaps ahead of non-gaps on ties. */
export function pickWeakSpots(mastery: ConceptMasteryOut[], n = 3): number[] {
  return [...mastery]
    .sort((a, b) => a.mastery - b.mastery || Number(b.is_gap) - Number(a.is_gap) || a.concept_id - b.concept_id)
    .slice(0, n)
    .map((m) => m.concept_id)
}

/** Build the /practice URL for a list of concepts: the first now, the rest queued. */
export function practiceUrl(conceptIds: number[], documentId?: number): string {
  const [first, ...rest] = conceptIds
  const params = new URLSearchParams()
  if (documentId !== undefined) params.set('doc', String(documentId))
  if (rest.length) params.set('queue', rest.join(','))
  const qs = params.toString()
  return `/practice/${first}${qs ? `?${qs}` : ''}`
}

export const pct = (x: number) => Math.round(x * 100)
