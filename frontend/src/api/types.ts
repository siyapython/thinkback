// Mirrors backend/app/schemas.py. Only student-facing models exist here: the API never
// returns the rubric, misconceptions or the grader's missed-point text, so neither do we.

export type DocumentStatus = 'uploaded' | 'processing' | 'ready' | 'failed'
export type QuestionType = 'explain' | 'apply' | 'predict'

export interface DocumentOut {
  id: number
  title: string
  source_type: string
  original_filename: string | null
  page_count: number | null
  status: DocumentStatus
  error_message: string | null
  chunk_count: number
  created_at: string
}

export interface TextDocumentIn {
  title: string
  text: string
}

export interface ConceptOut {
  id: number
  name: string
  definition: string
  source_chunk_ids: number[]
  origin: string
  is_active: boolean
  model: string | null
  prompt_version: string | null
  created_at: string
}

export interface ExtractionOut {
  document: DocumentOut
  created: number
  updated: number
  model: string
  prompt_version: string
  concepts: ConceptOut[]
}

export interface QuestionOut {
  id: number
  concept_id: number
  question_type: QuestionType | string
  prompt: string
}

export interface AttemptOut {
  id: number
  question_id: number
  status: 'in_progress' | 'completed' | string
  max_hint_level: number
  revealed: boolean
  effective_score: number | null
  started_at: string
  completed_at: string | null
}

export interface AnswerOut {
  answer_id: number
  rubric_score: number
  feedback: string
  points_covered_count: number
  points_total: number
  attempt: AttemptOut
}

export interface HintOut {
  level: number
  hint_text: string
  cited_chunk_ids: number[]
  hints_remaining: number
  attempt: AttemptOut
}

export interface RevealOut {
  explanation: string
  attempt: AttemptOut
}

export interface ConceptMasteryOut {
  concept_id: number
  name: string
  mastery: number
  attempt_count: number
  is_gap: boolean
}

export interface IndependenceOut {
  completed_attempts: number
  independent_attempts: number
  independence_rate: number | null
}

export const MAX_HINT_LEVEL = 4
