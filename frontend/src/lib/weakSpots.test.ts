import { describe, expect, it } from 'vitest'
import { pickWeakSpots, practiceUrl } from './weakSpots'

const m = (concept_id: number, mastery: number, is_gap = false) => ({
  concept_id, name: `c${concept_id}`, mastery, attempt_count: 1, is_gap,
})

describe('weak spots', () => {
  it('picks the lowest-mastery concepts first, gaps winning ties', () => {
    expect(pickWeakSpots([m(1, 0.9), m(2, 0.3), m(3, 0.3, true), m(4, 0.5), m(5, 0.1)], 3)).toEqual([5, 3, 2])
  })
  it('builds a practice url with a queue and document', () => {
    expect(practiceUrl([5, 3, 2], 9)).toBe('/practice/5?doc=9&queue=3%2C2')
    expect(practiceUrl([4])).toBe('/practice/4')
  })
})
