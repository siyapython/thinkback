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

// ---- Analytics (GET /analytics/overview, POST /analytics/refresh) ----
export interface AnalyticsUserOut {
  id: number
  display_name: string
  is_synthetic: boolean
}

export interface LearnerDayOut {
  day: string // YYYY-MM-DD, a UTC day
  attempts_completed: number
  independence_rate: number // 0..1
  avg_hint_level: number // 0..4
  reveal_rate: number
  avg_effective_score: number | null
}

export interface ConceptSummaryOut {
  concept_id: number
  concept_name: string
  document_id: number
  attempts: number
  avg_effective_score: number | null // 0..1
  avg_max_hint_level: number | null
  reveal_count: number
  mastery: number | null
  is_gap: boolean
  top_misconception: string | null
}

export interface FunnelOut {
  document_id: number
  document_title: string | null
  concepts_extracted: number
  question_served: number
  answer_submitted: number
  completed: number
  revealed: number
}

export interface HeadlineOut {
  completed_attempts: number
  independent_attempts: number
  independence_rate: number | null
  avg_hint_level: number | null
  reveal_rate: number | null
  avg_effective_score: number | null
  gap_concepts: number
}

export interface AnalyticsOverviewOut {
  user_id: number
  display_name: string
  is_synthetic: boolean
  pipeline_ready: boolean
  headline: HeadlineOut
  learner_daily: LearnerDayOut[]
  concept_summary: ConceptSummaryOut[]
  funnel: FunnelOut[]
}

export interface RefreshOut {
  tables: Record<string, number>
}
